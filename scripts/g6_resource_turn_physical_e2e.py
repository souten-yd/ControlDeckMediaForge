#!/usr/bin/env python3
"""Physical acceptance for the G6 resource turn, with no credential handling.

Why this exists next to ``g6_resource_turn_e2e.py``: that script drives the
installed stack through a browser and therefore needs a ControlDeck login. This
one proves the same physical claim without touching anybody's credentials, by
splitting the evidence at the HTTP auth boundary:

* the Host half — that ControlDeck really hands its VRAM back, and refuses while
  somebody is mid-inference — is measured directly against the running
  ControlDeck (see docs/implementation-status.md, G6 S3)
* the Media Forge half — the one this script runs — is the ordering: that the AI
  turn is declared finished *before* the generation lease is requested, and that
  a real image then lands on the real GPU

Everything physical here is real: the resident LLM, the VRAM it holds, the
release that frees it, the FLUX worker, and the produced PNG. Only ControlDeck's
token/lease HTTP surface is stubbed, and its ``ai/release`` handler performs the
genuine unload through ControlDeck's own code, so nothing is simulated away.

    scripts/g6_resource_turn_physical_e2e.py --evidence-dir <dir>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

CONTROL_DECK_PYTHON = Path("/data1tb/ControlDeck/app/.venv/bin/python")
CONTROL_DECK_BACKEND = Path("/data1tb/ControlDeck/app/backend")
FEATURE_DATA = Path("/data1tb/ControlDeck/data/feature-data/media-forge")
SHARED_CACHE = Path("/data1tb/ControlDeck/data/cache")

TERMINAL = {"succeeded", "failed", "canceled"}


def check(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def vram_used_bytes() -> int:
    """Read the device itself, never a model's own accounting."""
    try:
        out = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"], capture_output=True, text=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return -1
    for line in out.splitlines():
        if "GPU[0]" in line and "Total Used Memory" in line:
            try:
                return int(line.split(":")[-1].strip())
            except ValueError:
                return -1
    return -1


class VramSampler:
    """Sample the device continuously, keeping the time of each sample.

    Two earlier designs were useless and both looked green:

    * sampling only at phase boundaries read the idle baseline, because the
      generating phase is entered before the worker allocates anything
    * taking a single peak over the whole job could never fail, because the
      resident LLM (31.5 GB) dominates whatever the image worker later uses

    The question is what the GPU held *after* the LLM was handed back, so
    samples are timestamped and split at the release.
    """

    def __init__(self, interval_sec: float = 0.25):
        self.interval_sec = interval_sec
        self.samples: list[tuple[float, int]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            value = vram_used_bytes()
            if value >= 0:
                self.samples.append((time.monotonic(), value))
            self._stop.wait(self.interval_sec)

    def __enter__(self) -> "VramSampler":
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def summary(self, released_at: float | None) -> dict[str, Any]:
        if not self.samples:
            return {"samples": 0}
        values = [value for _at, value in self.samples]
        after = [value for at, value in self.samples if released_at and at >= released_at]
        return {
            "samples": len(values),
            "interval_sec": self.interval_sec,
            "peak_bytes": max(values),
            "min_bytes": min(values),
            "samples_after_release": len(after),
            # これが画像 worker の実占有。LLM に支配されない区間で見る。
            "peak_after_release_bytes": max(after) if after else None,
        }


def control_deck(snippet: str, timeout: float = 900.0) -> dict[str, Any]:
    """Run one bounded snippet inside the real ControlDeck venv.

    This is how the harness performs a genuine LLM load or release: through
    ControlDeck's own code, as the machine operator, with no token involved.
    """
    result = subprocess.run(
        [str(CONTROL_DECK_PYTHON), "-c", snippet],
        cwd=str(CONTROL_DECK_BACKEND),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ControlDeck snippet failed: {result.stderr[-2000:]}")
    for line in reversed(result.stdout.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"ControlDeck snippet produced no result: {result.stdout[-2000:]}")


LOAD_SNIPPET = """
import asyncio, json, time
from app.models_mgmt import llama

async def main():
    instance = next(i for i in llama.list_instances() if i.get("role", "llm") == "llm")
    alias = str(instance["alias"])
    started = time.perf_counter()
    ok = await llama.ensure_ready(alias, timeout_seconds=600)
    print(json.dumps({"ok": ok, "alias": alias, "elapsed_sec": round(time.perf_counter() - started, 3)}))

asyncio.run(main())
"""

RELEASE_SNIPPET = """
import asyncio, json, time
from app.models_mgmt.resource_provider import provider

async def main():
    started = time.perf_counter()
    released, reason, freed = await provider().release_on_request()
    print(json.dumps({
        "released": released, "reason": reason, "model_bytes": freed,
        "elapsed_sec": round(time.perf_counter() - started, 3),
    }))

asyncio.run(main())
"""

LOADED_SNIPPET = """
import json
from app.models_mgmt import llama
print(json.dumps({"loaded": [str(i["alias"]) for i in llama.list_instances() if i.get("loaded")]}))
"""


def loaded_aliases() -> list[str]:
    return control_deck(LOADED_SNIPPET, timeout=120)["loaded"]


# 「同じ入口で、モデルを替えても同じ出口になる」ことを見るために、model だけ
# 差し替えられるようにする。それ以外は 1 文字も変えない。変えると、通った理由が
# モデルなのか手順なのか分からなくなる。
REQUESTED_MODEL: dict[str, Any] = {"model_policy": "auto"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument(
        "--model-id", default=None,
        help="このモデルを名指しで使う（既定は routing に任せる）",
    )
    parser.add_argument(
        "--keep-data", action="store_true", help="生成物を残す（既定は一時ディレクトリごと削除）"
    )
    args = parser.parse_args()
    if args.model_id:
        global REQUESTED_MODEL
        REQUESTED_MODEL = {"model_policy": "manual", "model_id": args.model_id}
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    # worker が何をしたのかを見えるようにする。緑だけでは証拠にならない。
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(levelname)s %(name)s %(message)s")

    # worker の timing / placement は log にしか出ない。証跡に取り込むため
    # ここで拾う。worker 自身の申告なので、rocm-smi の実測と揃えて判断する。
    worker_lines: list[str] = []

    class _WorkerCapture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            message = record.getMessage()
            if message.startswith(("image worker timing", "image worker placement")):
                worker_lines.append(message)

    logging.getLogger("uvicorn.error").addHandler(_WorkerCapture())

    observations: dict[str, Any] = {"vram_baseline": vram_used_bytes()}
    check(
        not loaded_aliases(),
        "a model is already resident; refusing to disturb work in progress",
    )

    # ── 1. 実 LLM を常駐させ、本当に VRAM を握らせる ──────────────────
    load = control_deck(LOAD_SNIPPET)
    check(load["ok"], f"the Host LLM did not become ready: {load}")
    time.sleep(3)
    resident = vram_used_bytes()
    observations["llm"] = {**load, "vram_resident": resident}
    check(
        resident > observations["vram_baseline"] + 1_000_000_000,
        f"the Host LLM is not holding VRAM: {observations['llm']}",
    )

    released_at: dict[str, Any] = {}

    # ── 2. Media Forge を実 model store と実 worker で起動する ────────
    from fastapi import FastAPI

    from conftest import fake_settings  # noqa: E402 - test harness lives under tests/
    from test_host_execution import control_deck_stub  # noqa: E402

    import httpx
    from fastapi.testclient import TestClient

    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.host.client import ControlDeckHostClient

    host_app, state = control_deck_stub()

    # stub の ai/release は「本物の解放」を行う。ここを模擬したら、この試験が
    # 確かめたい物理現象そのものが消える。
    for route in list(host_app.router.routes):
        if getattr(route, "path", "") == "/api/v1/addon-runtime/media-forge/ai/release":
            host_app.router.routes.remove(route)

    @host_app.post("/api/v1/addon-runtime/media-forge/ai/release")
    async def ai_release() -> dict[str, Any]:
        outcome = await asyncio.to_thread(control_deck, RELEASE_SNIPPET)
        await asyncio.sleep(2)
        outcome["vram_after_release"] = vram_used_bytes()
        outcome["monotonic_at"] = time.monotonic()
        released_at.update(outcome)
        return {
            "released": outcome["released"],
            "reason": outcome["reason"],
            "freed_bytes": outcome["model_bytes"],
        }

    work = Path(subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip())
    settings = Settings(
        data_dir=work / "data",
        worker_timeout_sec=900.0,
        control_deck_url="http://127.0.0.1:8765",
        model_manifest=REPO / "worker_packs/image/models.json",
        model_catalog_manifest=REPO / "worker_packs/image/catalog.json",
        model_store_root=FEATURE_DATA / "data" / "models",
        hf_home=SHARED_CACHE / "huggingface",
        image_runtime_python=FEATURE_DATA / "runtimes/rocm-torch/.venv/bin/python",
    )
    app = create_app(
        settings,
        host_client=ControlDeckHostClient(
            "https://control-deck.test", transport=httpx.ASGITransport(app=host_app)
        ),
    )
    headers = {"Authorization": "Bearer valid-user", "X-Control-Deck-Addon-ID": "media-forge"}

    phases: list[str] = []
    vram_by_phase: dict[str, int] = {}
    try:
        with TestClient(app) as client:
            models = client.get("/api/v1/models").json()["items"]
            routable = [m for m in models if m["installed"] and m["healthy"] and m["state"] == "available"]
            observations["routable_models"] = [
                {"id": m["id"], "measured_vram_bytes": m.get("measured_vram_bytes")} for m in routable
            ]
            check(routable, f"no routable image model is installed: {models}")

            with client.websocket_connect("/ws", headers=headers) as socket:
                def call(method: str, params: dict[str, Any], tag: str) -> dict[str, Any]:
                    socket.send_json({"id": tag, "method": method, "params": params})
                    while True:
                        message = socket.receive_json()
                        if message.get("id") == tag:
                            return message

                started = time.perf_counter()
                sampler = VramSampler()
                sampler.__enter__()
                created = call("jobs.create", {
                    "operation": "image.generate",
                    "intent": "an orange field robot folds its solar panels at dusk",
                    "inputs": [],
                    **REQUESTED_MODEL,
                    "constraints": {"width": 256, "height": 256, "seed": 60601},
                    "output": {"format": "png", "count": 1},
                    "qa": {"semantic": False, "max_regeneration_attempts": 0},
                    "local_only": True,
                }, "create")
                check(created["ok"], f"the job was not accepted: {created}")
                job_id = created["result"]["id"]

                last: dict[str, Any] = created["result"]
                deadline = time.monotonic() + 1800
                while time.monotonic() < deadline:
                    answer = call("jobs.get", {"job_id": job_id}, f"get-{len(phases)}-{time.time()}")
                    if not answer["ok"]:
                        break
                    last = answer["result"]
                    phase = last.get("phase")
                    if phase and (not phases or phases[-1] != phase):
                        phases.append(phase)
                        vram_by_phase[phase] = vram_used_bytes()
                    if last.get("status") in TERMINAL:
                        break
                    time.sleep(0.2)
                sampler.__exit__()
                observations["vram_during_job"] = sampler.summary(
                    released_at.get("monotonic_at")
                )
                observations["generation"] = {
                    "status": last.get("status"),
                    "error": last.get("error"),
                    "asset_ids": last.get("asset_ids", []),
                    "phases": phases,
                    "vram_by_phase": vram_by_phase,
                    "elapsed_sec": round(time.perf_counter() - started, 3),
                }
                # 緑になったこと自体は証拠にならない。何が走ったのかを
                # provenance で確かめる。fake worker との取り違えを許さない。
                for asset_id in last.get("asset_ids", []):
                    provenance = client.get(
                        f"/api/v1/assets/{asset_id}/provenance"
                    ).json()
                    asset = client.get(f"/api/v1/assets/{asset_id}").json()
                    observations.setdefault("produced", []).append({
                        "asset_id": asset_id,
                        "model_id": provenance.get("model_id"),
                        "runtime_adapter": provenance.get("runtime_adapter"),
                        "weights_hash": provenance.get("weights_hash"),
                        "output_sha256": provenance.get("output_sha256"),
                        "model_route": provenance.get("parameters", {}).get("model_route"),
                        "width": asset.get("width"),
                        "height": asset.get("height"),
                        "size_bytes": asset.get("size_bytes"),
                        "mime_type": asset.get("mime_type"),
                    })
    finally:
        observations["worker_log"] = list(worker_lines)
        placement: dict[str, Any] = {}
        for line in worker_lines:
            if line.startswith("image worker timing"):
                placement.update({
                    key: value for key, value in (
                        part.split("=", 1) for part in line.split() if "=" in part
                    ) if key in {"load_sec", "generation_sec"}
                })
            if line.startswith("image worker placement"):
                for part in line.split():
                    if part.startswith("device_mode="):
                        placement["device_mode"] = part.split("=", 1)[1]
                placement["component_devices"] = line.split("component_devices=", 1)[-1]
        observations["worker_placement"] = placement
        observations["ai_release"] = released_at
        observations["vram_final_before_cleanup"] = vram_used_bytes()
        # 後片付け。測定前の状態へ戻す。
        control_deck(RELEASE_SNIPPET, timeout=300)
        if not args.keep_data and work.exists():
            shutil.rmtree(work, ignore_errors=True)
        time.sleep(2)
        observations["vram_final"] = vram_used_bytes()
        observations["loaded_after"] = loaded_aliases()

    generation = observations["generation"]
    check("release_ai" in phases, f"the AI turn was never declared finished: {phases}")
    for later in ("waiting_resource", "starting", "generating"):
        if later in phases:
            check(
                phases.index("release_ai") < phases.index(later),
                f"the AI turn ended after {later}: {phases}",
            )
    check(released_at.get("released") is True, f"the release was refused: {released_at}")
    check(
        released_at["vram_after_release"] < observations["llm"]["vram_resident"] - 1_000_000_000,
        f"VRAM was not actually returned: {released_at}",
    )
    check(
        generation["status"] == "succeeded" and len(generation["asset_ids"]) == 1,
        f"the real image job did not produce an asset: {generation}",
    )
    produced = observations.get("produced") or []
    check(len(produced) == 1, f"provenance was not recorded: {produced}")
    made = produced[0]
    routable_ids = {item["id"] for item in observations["routable_models"]}
    check(
        made["model_id"] in routable_ids,
        f"the asset did not come from the installed measured model: {made}",
    )
    check(
        "fake" not in str(made["runtime_adapter"]).lower(),
        f"the fake worker produced this asset, not the GPU: {made}",
    )
    check(
        (made["width"], made["height"]) == (256, 256) and made["mime_type"] == "image/png",
        f"the produced asset does not match the request: {made}",
    )
    # LLM を返したあとに GPU が実際に使われたこと。全区間のピークで見ると
    # 常駐 LLM に支配され、画像 worker が GPU を使わなくても通ってしまう。
    during = observations.get("vram_during_job", {})
    peak_after = during.get("peak_after_release_bytes") or 0
    check(
        peak_after > observations["vram_baseline"] + 2_000_000_000,
        f"the GPU was never occupied after the AI turn ended: {during}",
    )
    # worker が本当に GPU へ載せたこと。placement は worker 自身の申告なので
    # 上の実測と揃って初めて証拠になる。
    placement = observations.get("worker_placement") or {}
    check(
        placement.get("device_mode") and "cpu" not in json.dumps(placement).lower(),
        f"the image worker did not run on the GPU: {placement}",
    )

    (args.evidence_dir / "g6-resource-turn-physical.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    print("PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
