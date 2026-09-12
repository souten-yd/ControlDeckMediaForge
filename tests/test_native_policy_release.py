from __future__ import annotations

import ast
import builtins
import hashlib
import json
from pathlib import Path
import subprocess

import jsonschema
import pytest

from worker_packs.native_setup import policy_release

ROOT = Path(__file__).resolve().parents[1]


def test_native_verifier_with_real_os_crypto() -> None:
    result = subprocess.run(
        ["/usr/bin/python3", "-I", str(ROOT / "tests/native_policy_os_check.py")],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, close_fds=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Ran 9 tests" in result.stderr and "OK" in result.stderr


def test_native_manifest_schema_is_explicit_and_additive() -> None:
    schema = json.loads((ROOT / "schemas/native-policy-release.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    manifest = {
        "schema_version": policy_release.SCHEMA, "feature_id": "media-forge",
        "purpose": policy_release.PURPOSE, "version": "0.28.80", "source_commit": "a" * 40,
        "platform": "linux", "architecture": "x86_64",
        "artifact_name": "control-deck-media-forge-os-policy-0.28.80-linux-x86_64.deb",
        "sha256": hashlib.sha256(b"fixture").hexdigest(), "size_bytes": 7,
    }
    jsonschema.validate(manifest, schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(manifest)


def test_core_does_not_import_native_verification_or_crypto() -> None:
    for path in (ROOT / "backend/mediaforge").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                     else [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            assert not any(name.startswith(("cryptography", "worker_packs.native_setup"))
                           for name in names), path


def test_missing_os_crypto_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = builtins.__import__

    def without_crypto(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("cryptography"):
            raise ImportError("private dependency detail")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_crypto)
    manifest = {
        "schema_version": policy_release.SCHEMA, "feature_id": "media-forge",
        "purpose": policy_release.PURPOSE, "version": "0.28.80", "source_commit": "a" * 40,
        "platform": "linux", "architecture": "x86_64",
        "artifact_name": "control-deck-media-forge-os-policy-0.28.80-linux-x86_64.deb",
        "sha256": hashlib.sha256(b"fixture").hexdigest(), "size_bytes": 7,
    }
    with pytest.raises(policy_release.PolicyReleaseError, match="^native_policy_crypto_unavailable$"):
        policy_release.verify_policy_release(policy_release.canonical_bytes(manifest), b"x" * 64,
            b"fixture", expected_version="0.28.80", expected_source_commit="a" * 40)
