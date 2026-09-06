"""Real isolated-package image generation with Host-issued diagnostic credentials.

The caller supplies a short-lived service credential for the existing dedicated
acceptance user. No Host modules, fake workers, or broker replacements are used.
This verifies Blender independence, not the installed browser login/proxy path.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import time
from typing import Any

import httpx
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    authorization = os.environ.pop("MF_ACCEPTANCE_AUTHORIZATION")
    assert authorization.startswith("Bearer ")
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict[str, Any] = {"mode": "isolated_package_real_host_broker", "events": [],
                                "authentication_setup": "host_issued_diagnostic_service_credential"}
    started = time.monotonic()

    def record(stage: str, **values: Any) -> None:
        row = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        evidence["events"].append(row)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(row), flush=True)

    with httpx.Client(base_url="http://127.0.0.1:9161", timeout=20) as client:
        def get(path: str) -> Any:
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        runtime = get("/workspace-api/blender/runtime")
        assert runtime["state"] == "missing" and runtime["runtimes"] == []
        assert runtime["active_runtime_id"] is None and runtime["operations"] == []
        assert get("/api/v1/jobs")["items"] == []
        request = {"operation": "image.generate", "intent": "A blue ceramic cube on a white studio background",
                   "model_policy": "auto", "constraints": {"width": 256, "height": 256, "steps": 4, "seed": 73},
                   "output": {"format": "png", "count": 1}, "local_only": True}
        response = client.post("/addon/v1/workflow/execute", json={"input": request}, headers={
            "Authorization": authorization, "X-Control-Deck-Addon-ID": "media-forge"})
        # Never serialize credentials or request headers into evidence.
        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]
        record("submitted", job_id=job_id, request=request, blender=runtime)
        deadline = time.monotonic() + 480
        previous = None
        while time.monotonic() < deadline:
            job = get(f"/api/v1/jobs/{job_id}")
            state = (job["status"], job.get("phase"))
            if state != previous:
                record("job_state", job=job)
                previous = state
            if job["status"] in {"succeeded", "failed", "canceled"}:
                break
            time.sleep(1)
        else:
            record("observation_timeout", job_id=job_id, terminal=False)
            raise AssertionError("Observe the SAME job; timeout does not mean execution stopped")
        assert job["status"] == "succeeded", job.get("error")
        assert len(job["asset_ids"]) == 1
        asset_id = job["asset_ids"][0]
        asset = get(f"/api/v1/assets/{asset_id}")
        provenance = get(f"/api/v1/assets/{asset_id}/provenance")
        response = client.get(f"/api/v1/assets/{asset_id}/content")
        response.raise_for_status()
        content = response.content
        digest = hashlib.sha256(content).hexdigest()
        assert digest == asset["sha256"] == provenance["output_sha256"]
        assert len(content) == asset["size_bytes"]
        assert provenance["runtime_adapter"] == "diffusers.flux2-klein"
        assert provenance["weights_hash"].startswith("sha256:")
        assert provenance["tool_versions"]["media-forge"] == "0.28.33"
        with Image.open(io.BytesIO(content)) as picture:
            assert picture.format == "PNG" and picture.size == (256, 256)
            picture.verify()
        assert get("/workspace-api/blender/runtime") == runtime
        assert [item["id"] for item in get("/api/v1/assets")["items"]] == [asset_id]
        (args.evidence_dir / "generated.png").write_bytes(content)
        record("passed", asset=asset, provenance=provenance, blender_unchanged=True)


if __name__ == "__main__":
    main()
