"""Host-venv diagnostic: generate arguments through the normal broker gateway.

No MCP executor, project creation, asset writes or global configuration changes.
This cannot establish OpenCode/Blender acceptance. Only a private runtime config
is created through the existing provider and removed in finally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Iterable
import uuid


ROOT = Path(__file__).resolve().parents[1]


def prompt_for(mode: str) -> str:
    brief = (
        "This is an argument generation probe with no executor and no asset creation. "
        "Design a closed chest armor with a front ridge, width 0.4m, height 0.5m, thickness 0.08m, "
        "at most 10 vertices. Choose coordinates and faces yourself. Use exactly one mesh.create "
        "with object_id armor, name Armor, require_closed=true and one teal metallic material.set. "
        "Every edge must have two opposite face uses; only triangle/quad faces. "
    )
    if mode == "plan":
        return brief + (
            "First output one compact JSON code block containing the complete name/recipe request "
            "as a data artifact, with no reasoning or prose. Then call record_probe exactly once "
            "by copying that identical request without recomputing the geometry. No alternative candidates."
        )
    return brief + "Call record_probe exactly once with complete valid name/recipe JSON. No explanations."


def stream_events(lines: Iterable[str]) -> Iterable[dict[str, Any]]:
    data: list[str] = []
    for line in lines:
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
        elif not line and data:
            raw = "\n".join(data)
            data.clear()
            if raw == "[DONE]":
                return
            yield json.loads(raw)
    if data and "\n".join(data) != "[DONE]":
        yield json.loads("\n".join(data))


def collect_event(event: dict[str, Any], calls: dict[int, dict[str, str]],
                  finishes: list[str], errors: list[str]) -> None:
    if "error" in event:
        # Never include generated content or headers in the summary.
        error = event["error"]
        errors.append(str(error.get("code", "provider_error")) if isinstance(error, dict) else "provider_error")
    for choice in event.get("choices", []):
        if choice.get("finish_reason"):
            finishes.append(choice["finish_reason"])
        for call in choice.get("delta", {}).get("tool_calls", []):
            current = calls.setdefault(call["index"], {"name": "", "arguments": ""})
            function = call.get("function", {})
            current["name"] += function.get("name", "")
            current["arguments"] += function.get("arguments", "")


def plan_matches(content: str, calls: dict[int, dict[str, str]]) -> bool:
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", content, re.DOTALL)
    if len(blocks) != 1 or len(calls) != 1:
        return False
    try:
        return json.loads(blocks[0]) == json.loads(next(iter(calls.values()))["arguments"])
    except ValueError:
        return False


def main() -> None:
    import httpx
    from app.addons.execution import model_facing_schema
    from app.integrations.opencode import provider

    sys.path.insert(0, str(ROOT / "backend"))
    from mediaforge.scene_recipes import MeshCreate, SceneCreateRequest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("direct", "plan"), required=True)
    parser.add_argument("--temperature", type=float, default=0.1)
    args = parser.parse_args()
    if not 0 <= args.temperature <= 2:
        parser.error("temperature must be between 0 and 2")
    settings = provider.get_settings()
    assert provider.is_gateway_url(settings["base_url"])
    with httpx.Client(timeout=10) as client:
        response = client.get("http://127.0.0.1:9130/schemas/scene-create-request.json")
        response.raise_for_status()
        schema = model_facing_schema(response.json())
    schema.pop("description", None)
    config = provider._runtime_config("tool-probe-" + uuid.uuid4().hex[:8], settings["base_url"], settings["model"])
    try:
        options = json.loads(config.read_text())["provider"]["controldeck"]["options"]
        headers = {"Authorization": "Bearer " + options["apiKey"], **options.get("headers", {})}
        body = {
            "model": settings["model"], "stream": True, "max_tokens": 4096, "seed": 7,
            "temperature": args.temperature, "messages": [{"role": "user", "content": prompt_for(args.mode)}],
            "tools": [{"type": "function", "function": {"name": "record_probe",
                "description": "Diagnostic data receiver. No execution will occur.", "parameters": schema}}],
        }
        calls: dict[int, dict[str, str]] = {}
        finishes: list[str] = []
        errors: list[str] = []
        content = ""
        models: set[str] = set()
        started = time.monotonic()
        with httpx.Client(timeout=180) as client:
            with client.stream("POST", options["baseURL"].rstrip("/") + "/chat/completions",
                               headers=headers, json=body) as response:
                response.raise_for_status()
                for event in stream_events(response.iter_lines()):
                    if isinstance(event.get("model"), str):
                        models.add(event["model"])
                    for choice in event.get("choices", []):
                        fragment = choice.get("delta", {}).get("content")
                        if isinstance(fragment, str):
                            content += fragment
                    collect_event(event, calls, finishes, errors)
        checks: list[dict[str, Any]] = []
        for value in calls.values():
            check: dict[str, Any] = {"json_valid": False, "closed_contract_valid": False,
                "argument_bytes": len(value["arguments"].encode()),
                "argument_sha256": hashlib.sha256(value["arguments"].encode()).hexdigest()}
            try:
                request = json.loads(value["arguments"])
                check["json_valid"] = True
                parsed = SceneCreateRequest.model_validate(request)
                mesh = parsed.recipe.operations[0]
                check["closed_contract_valid"] = (
                    value["name"] == "record_probe" and isinstance(mesh, MeshCreate)
                    and mesh.require_closed and len(mesh.vertices) <= 10
                    and len(parsed.recipe.operations) == 2
                    and parsed.recipe.operations[1].type == "material.set"
                )
            except (ValueError, IndexError) as exc:
                check["failure_type"] = type(exc).__name__
            checks.append(check)
        success = not errors and finishes == ["tool_calls"] and len(checks) == 1 and checks[0]["closed_contract_valid"]
        matched = plan_matches(content, calls)
        if args.mode == "plan":
            success = success and matched
        print(json.dumps({"diagnostic_only": True, "mode": args.mode, "temperature": args.temperature,
            "models": sorted(models), "plan_matches_call": matched,
            "schema_sha256": hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest(),
            "elapsed_sec": round(time.monotonic() - started, 3), "calls": checks,
            "finish": finishes, "errors": errors, "success": success}), flush=True)
        if not success:
            raise SystemExit(1)
    finally:
        config.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
