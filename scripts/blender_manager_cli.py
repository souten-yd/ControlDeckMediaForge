#!/usr/bin/env python3
"""Operate the Media Forge-owned Blender manager through its loopback service."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


TERMINAL_STATES = {"ready", "failed", "canceled"}
MAX_RESPONSE_BYTES = 1024 * 1024


class BlenderManagerCLIError(RuntimeError):
    pass


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise BlenderManagerCLIError("Media Forge URL must be a plain loopback HTTP origin")
    return value.rstrip("/")


def request_json(
    base_url: str, path: str, *, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        base_url + path,
        data=body,
        method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - loopback validated above
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        content = exc.read(MAX_RESPONSE_BYTES + 1)
        try:
            detail = json.loads(content).get("detail", {})
            code = detail.get("code", f"http_{exc.code}")
            message = detail.get("message", code)
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            code = f"http_{exc.code}"
            message = code
        raise BlenderManagerCLIError(f"{code}: {message}") from exc
    except (OSError, URLError) as exc:
        raise BlenderManagerCLIError("Media Forge service is unavailable") from exc
    if len(content) > MAX_RESPONSE_BYTES:
        raise BlenderManagerCLIError("Media Forge response exceeded the CLI bound")
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlenderManagerCLIError("Media Forge returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise BlenderManagerCLIError("Media Forge returned an invalid response")
    return value


def wait_operation(base_url: str, operation_id: str) -> dict[str, Any]:
    last = ""
    for _attempt in range(14_400):
        status = request_json(base_url, "/workspace-api/blender/runtime")
        operation = next(
            (
                item for item in status.get("operations", [])
                if isinstance(item, dict) and item.get("id") == operation_id
            ),
            None,
        )
        if operation is None:
            raise BlenderManagerCLIError("Blender runtime operation disappeared")
        state = str(operation.get("state", ""))
        if state != last:
            print(json.dumps(operation, ensure_ascii=False, sort_keys=True), flush=True)
            last = state
        if state in TERMINAL_STATES:
            if state != "ready":
                raise BlenderManagerCLIError(
                    f"{operation.get('error_code') or state}: "
                    f"{operation.get('error_message') or state}"
                )
            return operation
        time.sleep(0.25)
    raise BlenderManagerCLIError("Blender runtime operation timed out")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:9130")
    parser.add_argument(
        "action",
        choices=("status", "install", "update", "switch", "repair", "remove-preview", "remove"),
    )
    parser.add_argument("runtime_id", nargs="?")
    parser.add_argument("--yes", action="store_true", help="confirm a removal after printing preview")
    args = parser.parse_args(argv)
    try:
        base_url = validate_base_url(args.base_url)
        if args.action == "status":
            if args.runtime_id:
                raise BlenderManagerCLIError("status accepts no runtime ID")
            print(json.dumps(
                request_json(base_url, "/workspace-api/blender/runtime"),
                ensure_ascii=False, sort_keys=True,
            ))
            return 0
        if args.action in {"install", "update"}:
            if args.runtime_id:
                raise BlenderManagerCLIError(f"{args.action} accepts no runtime ID")
            payload = {"action": args.action}
        elif args.action in {"switch", "repair"}:
            if not args.runtime_id:
                raise BlenderManagerCLIError(f"{args.action} requires one opaque runtime ID")
            payload = {"action": args.action, "runtime_id": args.runtime_id}
        else:
            if not args.runtime_id:
                raise BlenderManagerCLIError("remove requires one opaque runtime ID")
            preview = request_json(
                base_url,
                "/workspace-api/blender/runtime/operations",
                payload={"action": "remove_preview", "runtime_id": args.runtime_id},
            )
            print(json.dumps(preview, ensure_ascii=False, sort_keys=True), flush=True)
            if args.action == "remove-preview":
                return 0
            if not preview.get("can_remove"):
                raise BlenderManagerCLIError("blender_runtime_in_use: runtime cannot be removed")
            confirmed = args.yes
            if not confirmed:
                try:
                    confirmed = input("Remove only this managed Blender runtime? [y/N] ").strip().lower() == "y"
                except EOFError:
                    confirmed = False
            if not confirmed:
                raise BlenderManagerCLIError("removal canceled")
            payload = {
                "action": "remove",
                "runtime_id": args.runtime_id,
                "confirmation_fingerprint": preview["confirmation_fingerprint"],
            }
        operation = request_json(
            base_url, "/workspace-api/blender/runtime/operations", payload=payload
        )
        return 0 if wait_operation(base_url, str(operation["id"])) else 1
    except (BlenderManagerCLIError, KeyError) as exc:
        print(f"blender manager: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
