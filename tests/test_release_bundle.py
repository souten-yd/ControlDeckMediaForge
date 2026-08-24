from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_release_launcher_uses_managed_persistent_roots_without_source_build():
    launcher = (ROOT / "scripts" / "bundle-launcher.sh").read_text(encoding="utf-8")
    assert "CONTROL_DECK_FEATURE_DATA_DIR" in launcher
    assert "CONTROL_DECK_SHARED_CACHE_DIR" in launcher
    assert "MEDIA_FORGE_IMAGE_RUNTIME_PYTHON" in launcher
    assert "MEDIA_FORGE_ENV_STATUS_FILE" in launcher
    assert "git clone" not in launcher
    assert "pip install" not in launcher
    assert "npm install" not in launcher
    assert 'exec "$BUNDLE_ROOT/bin/mediaforge-core" "$1"' in launcher


def test_bundle_builder_excludes_heavy_runtime_and_binds_package_identity():
    builder = (ROOT / "scripts" / "build_release_bundle.py").read_text(encoding="utf-8")
    assert '"feature_id": "media-forge"' in builder
    assert '"entrypoint": "bin/mediaforge"' in builder
    assert '"addon_manifest": "control-deck-addon.json"' in builder
    assert '"provision_args": ["provision"]' in builder
    assert '"health_url": "http://127.0.0.1:9130/health"' in builder
    assert "runtimes/rocm-torch/.venv" not in builder
    assert 'f"{ROOT / \'creative\'}:creative"' in builder


def test_bundle_provision_writes_health_only_after_runtime_gpu_and_model(monkeypatch, tmp_path):
    from scripts import bundle_entrypoint

    feature_data = tmp_path / "feature-data"
    cache = tmp_path / "cache"
    monkeypatch.setenv("CONTROL_DECK_FEATURE_DATA_DIR", str(feature_data))
    monkeypatch.setenv("CONTROL_DECK_SHARED_CACHE_DIR", str(cache))
    monkeypatch.setattr(bundle_entrypoint, "_resource_root", lambda: ROOT)
    monkeypatch.setattr(bundle_entrypoint.shutil, "disk_usage", lambda _path: SimpleNamespace(free=100_000_000_000))
    monkeypatch.setattr(bundle_entrypoint, "_model_installed", lambda _cache: True)
    runtime_python = feature_data / "runtimes" / "rocm-torch" / ".venv" / "bin" / "python"
    monkeypatch.setattr(bundle_entrypoint, "_ensure_runtime", lambda *_args: (runtime_python, True))
    monkeypatch.setattr(bundle_entrypoint, "_verify_gpu", lambda _python: {"gcn_arch": "gfx1201"})
    monkeypatch.setattr(bundle_entrypoint, "_ensure_model", lambda *_args: True)
    result = bundle_entrypoint.provision()
    assert result["runtime_reused"] is True and result["model_reused"] is True
    status = (feature_data / "environment-status.json").read_text(encoding="utf-8")
    assert '"status": "healthy"' in status
    assert "gfx1201" in status


def test_bundle_provision_failure_does_not_publish_healthy_status(monkeypatch, tmp_path):
    from scripts import bundle_entrypoint

    feature_data = tmp_path / "feature-data"
    monkeypatch.setenv("CONTROL_DECK_FEATURE_DATA_DIR", str(feature_data))
    monkeypatch.setenv("CONTROL_DECK_SHARED_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(bundle_entrypoint, "_resource_root", lambda: ROOT)
    monkeypatch.setattr(bundle_entrypoint.shutil, "disk_usage", lambda _path: SimpleNamespace(free=100_000_000_000))
    monkeypatch.setattr(bundle_entrypoint, "_model_installed", lambda _cache: True)
    monkeypatch.setattr(bundle_entrypoint, "_ensure_runtime", lambda *_args: (tmp_path / "python", False))
    monkeypatch.setattr(bundle_entrypoint, "_verify_gpu", lambda _python: (_ for _ in ()).throw(RuntimeError("gpu failed")))
    with pytest.raises(RuntimeError, match="gpu failed"):
        bundle_entrypoint.provision()
    assert not (feature_data / "environment-status.json").exists()


def test_bundle_build_environment_contains_no_ml_runtime_dependencies():
    requirements = (ROOT / "runtimes" / "bundle-build" / "requirements.txt").read_text(encoding="utf-8")
    assert "pyinstaller==6.22.0" in requirements
    assert "torch" not in requirements
    assert "diffusers" not in requirements
    assert "transformers" not in requirements


def test_bundle_ships_what_the_worker_imports():
    """Worker-owned repository packages must be explicit bundle data."""
    import ast
    import re
    from pathlib import Path

    root = Path(__file__).parents[1]
    build = (root / "scripts" / "build_release_bundle.py").read_text(encoding="utf-8")
    shipped = set(re.findall(r'--add-data", f"\{[^}]+\}:([a-zA-Z_/]+)"', build))

    top_level: set[str] = set()
    for path in (root / "worker_packs").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                top_level.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top_level.add(alias.name.split(".")[0])

    # 同梱が要るのは、この repository のパッケージだけ（外部依存は worker venv 側）
    local = {name for name in top_level if (root / "backend" / name).is_dir() or (root / name).is_dir()}
    missing = local - shipped
    assert not missing, f"worker が import するのに bundle へ入っていない: {sorted(missing)}"
    assert "mediaforge" not in shipped, "core source must not be shipped for the worker"


def test_the_bundle_refuses_to_ship_two_different_versions():
    """--version が addon.json を黙って上書きしていた。束ねた manifest と、
    同じ束の中の mediaforge.__version__ が別の版を名乗り、ControlDeck の
    一覧に出ている版と実際に動いている版が食い違う原因になる。"""
    import re

    root = Path(__file__).parents[1]
    script = (root / "scripts" / "build_release_bundle.py").read_text(encoding="utf-8")
    assert "version mismatch" in script, "版の食い違いを素通りさせている"
    assert 'addon["version"] = args.version' not in script

    packaged = re.search(
        r'__version__ = "([^"]+)"',
        (root / "backend" / "mediaforge" / "__init__.py").read_text(encoding="utf-8"),
    ).group(1)
    addon = json.loads((root / "addon.json").read_text(encoding="utf-8"))
    assert addon["version"] == packaged
