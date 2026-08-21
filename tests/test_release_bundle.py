from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_launcher_uses_managed_persistent_roots_without_source_build():
    launcher = (ROOT / "scripts" / "bundle-launcher.sh").read_text(encoding="utf-8")
    assert "CONTROL_DECK_FEATURE_DATA_DIR" in launcher
    assert "CONTROL_DECK_SHARED_CACHE_DIR" in launcher
    assert "MEDIA_FORGE_IMAGE_RUNTIME_PYTHON" in launcher
    assert "git clone" not in launcher
    assert "pip install" not in launcher
    assert "npm install" not in launcher
    assert 'exec "$BUNDLE_ROOT/bin/mediaforge-core" "$1"' in launcher


def test_bundle_builder_excludes_heavy_runtime_and_binds_package_identity():
    builder = (ROOT / "scripts" / "build_release_bundle.py").read_text(encoding="utf-8")
    assert '"feature_id": "media-forge"' in builder
    assert '"entrypoint": "bin/mediaforge"' in builder
    assert '"addon_manifest": "control-deck-addon.json"' in builder
    assert '"health_url": "http://127.0.0.1:9130/health"' in builder
    assert "runtimes/rocm-torch/.venv" not in builder


def test_bundle_build_environment_contains_no_ml_runtime_dependencies():
    requirements = (ROOT / "runtimes" / "bundle-build" / "requirements.txt").read_text(encoding="utf-8")
    assert "pyinstaller==6.22.0" in requirements
    assert "torch" not in requirements
    assert "diffusers" not in requirements
    assert "transformers" not in requirements
