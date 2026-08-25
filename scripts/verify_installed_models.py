"""Check every installed image model by actually generating with it.

The catalog lists 55 pipeline classes the runtime can construct. That is a
statement about what can be *loaded*, not a promise that each one works here —
proving the latter would mean downloading 55 repositories. What can be proven
is everything actually present on this machine, and that is what this does.

For each installed diffusers model:

* not measured yet  -> run it once, record what it cost, promote it
* already measured  -> run it once anyway and confirm it still produces a
  picture, because a model that was measured months ago can be broken by a
  runtime upgrade and nothing else would notice

Run it after downloading a batch. Models on other adapters (the GGUF video
runtimes) are listed and skipped rather than silently omitted, so the report
accounts for everything installed.

    python scripts/verify_installed_models.py
    python scripts/verify_installed_models.py --only stabilityai/stable-diffusion-xl-base-1.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from mediaforge.custom_models import CustomModelCatalog  # noqa: E402
from mediaforge.image_evaluation import (  # noqa: E402
    ImageEvaluationError,
    measure_image_model,
)
from mediaforge.models.registry import ModelRegistry  # noqa: E402

FEATURE_DATA = Path("/data1tb/ControlDeck/data/feature-data/media-forge")
SHARED_CACHE = Path("/data1tb/ControlDeck/data/cache")


def load_models(catalog: CustomModelCatalog):
    extra_models, extra_catalog = catalog.manifests()
    return list(ModelRegistry.load(
        REPO / "worker_packs/image/models.json",
        catalog_manifest=REPO / "worker_packs/image/catalog.json",
        hf_home=SHARED_CACHE / "huggingface",
        model_store_root=FEATURE_DATA / "data" / "models",
        extra_models=extra_models,
        extra_catalog=extra_catalog,
    ).all())


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None, help="この model_id だけを見る")
    parser.add_argument("--work-dir", type=Path, default=Path("/tmp/mediaforge-verify"))
    parser.add_argument(
        "--skip-measured", action="store_true",
        help="実測済みは走らせない（速いが、壊れていても気づかない）",
    )
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)

    catalog = CustomModelCatalog(FEATURE_DATA / "data" / "custom-models.json")
    models = load_models(catalog)
    installed = [item for item in models if item.installed and item.local_path is not None]
    if args.only:
        installed = [item for item in installed if item.model_id == args.only]
        if not installed:
            print(f"{args.only} は導入されていません", file=sys.stderr)
            return 1

    runtime = FEATURE_DATA / "runtimes/rocm-torch/.venv/bin/python"
    rows: list[dict[str, object]] = []
    for model in installed:
        if not model.runtime_adapter.startswith("diffusers."):
            # 黙って省くと、報告が「全部通った」に見えてしまう。
            rows.append({
                "model": model.model_id,
                "outcome": "skipped",
                "detail": f"{model.runtime_adapter} は画像ワーカーの経路ではない",
            })
            continue
        measured = model.measurement_confidence == "measured"
        if measured and args.skip_measured:
            rows.append({"model": model.model_id, "outcome": "skipped", "detail": "実測済み"})
            continue

        print(f"→ {model.model_id} を実行中…", file=sys.stderr)
        started = time.perf_counter()
        try:
            measurement = await measure_image_model(
                model,
                runtime_python=runtime,
                work_root=args.work_dir,
                repository_root=REPO,
                timeout_sec=1800,
            )
        except ImageEvaluationError as exc:
            rows.append({
                "model": model.model_id, "outcome": "failed",
                "detail": f"{exc.code}: {exc}"[:160],
            })
            continue
        promoted = False
        if not measured:
            try:
                catalog.record_measurement(model.model_id, measurement.catalog_measurements())
                promoted = True
            except Exception as exc:  # noqa: BLE001 - shipped entry は書き換えない
                rows.append({
                    "model": model.model_id, "outcome": "generated",
                    "detail": f"生成はできたが記録は据置: {str(exc)[:80]}",
                    "vram_bytes": measurement.execution_peak_vram_bytes,
                    "seconds": round(time.perf_counter() - started, 2),
                })
                continue
        rows.append({
            "model": model.model_id,
            "outcome": "promoted" if promoted else "verified",
            "vram_bytes": measurement.execution_peak_vram_bytes,
            "seconds": round(measurement.measured_runtime_sec, 2),
            "output": f"{measurement.width}x{measurement.height}",
            "output_bytes": measurement.output_bytes,
        })

    print(json.dumps({"models": rows}, ensure_ascii=False, indent=2))
    failed = [row for row in rows if row["outcome"] == "failed"]
    print(
        f"\n通った {sum(1 for r in rows if r['outcome'] in ('promoted', 'verified'))} / "
        f"失敗 {len(failed)} / 対象外 {sum(1 for r in rows if r['outcome'] == 'skipped')}",
        file=sys.stderr,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
