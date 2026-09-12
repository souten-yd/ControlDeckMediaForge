"""Purpose-bound native policy verification; no filesystem or OS mutations.

Run in the OS/native process, never import into core. cryptography belongs to
that process's OS dependencies. The caller must obtain expected identity from
trusted release metadata, not browser input. A future privileged consumer must
call this verifier itself and stage returned bytes without reopening a path.
This module does not establish trust in its own executable or install anything.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

SCHEMA = "media-forge.native-policy-release@1"
PURPOSE = "blender-gui-confinement"
# Existing MediaForge publisher; no alternate caller-supplied key/fallback.
PUBLISHER_KEY = base64.b64decode("80bNiqW1CzAzQ3LSqYqtwecm6TYQywDLxGACF9AVsac=")
MAX_MANIFEST_BYTES = 4096
MAX_PACKAGE_BYTES = 8 * 1024 * 1024
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?")
COMMIT = re.compile(r"[0-9a-f]{40}")


class PolicyReleaseError(ValueError):
    """Fixed, non-sensitive validation error code."""


@dataclass(frozen=True)
class VerifiedPolicyRelease:
    version: str
    source_commit: str
    artifact_name: str
    sha256: str
    package_bytes: bytes


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PolicyReleaseError("native_policy_invalid_manifest")
        value[key] = item
    return value


def verify_policy_release(
    manifest_bytes: bytes, signature: bytes, package_bytes: bytes, *,
    expected_version: str, expected_source_commit: str,
) -> VerifiedPolicyRelease:
    """Verify a fixed release without reading paths or changing external state.

    signature is the decoded raw Ed25519 signature (64 bytes). Canonical JSON is
    verified exactly as received, without whitespace trimming/re-serialization.
    Exact expected version/commit prevents replay, including signed downgrades.
    Package structure/scripts and OS compatibility still require separate gates.
    """
    if (type(expected_version) is not str or len(expected_version) > 64
            or not VERSION.fullmatch(expected_version)
            or type(expected_source_commit) is not str
            or not COMMIT.fullmatch(expected_source_commit)):
        raise PolicyReleaseError("native_policy_invalid_expectation")
    if (type(manifest_bytes) is not bytes or not 0 < len(manifest_bytes) <= MAX_MANIFEST_BYTES
            or type(signature) is not bytes or len(signature) != 64
            or type(package_bytes) is not bytes or not 0 < len(package_bytes) <= MAX_PACKAGE_BYTES):
        raise PolicyReleaseError("native_policy_invalid_input")
    try:
        manifest = json.loads(manifest_bytes, object_pairs_hook=_unique_object)
        if type(manifest) is not dict or canonical_bytes(manifest) != manifest_bytes:
            raise PolicyReleaseError("native_policy_invalid_manifest")
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise PolicyReleaseError("native_policy_invalid_manifest") from None
    name = f"control-deck-media-forge-os-policy-{expected_version}-linux-x86_64.deb"
    identity = {
        "schema_version": SCHEMA, "feature_id": "media-forge", "purpose": PURPOSE,
        "version": expected_version, "source_commit": expected_source_commit,
        "platform": "linux", "architecture": "x86_64", "artifact_name": name,
    }
    if (set(manifest) != set(identity) | {"sha256", "size_bytes"}
            or any(manifest.get(key) != value for key, value in identity.items())
            or type(manifest["size_bytes"]) is not int
            or manifest["size_bytes"] != len(package_bytes)
            or type(manifest["sha256"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", manifest["sha256"])):
        raise PolicyReleaseError("native_policy_identity_mismatch")
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        raise PolicyReleaseError("native_policy_crypto_unavailable") from None
    try:
        Ed25519PublicKey.from_public_bytes(PUBLISHER_KEY).verify(signature, manifest_bytes)
    except UnsupportedAlgorithm:
        raise PolicyReleaseError("native_policy_crypto_unavailable") from None
    except (InvalidSignature, ValueError):
        raise PolicyReleaseError("native_policy_signature_invalid") from None
    digest = hashlib.sha256(package_bytes).hexdigest()
    if digest != manifest["sha256"]:
        raise PolicyReleaseError("native_policy_digest_mismatch")
    return VerifiedPolicyRelease(expected_version, expected_source_commit, name,
                                 digest, package_bytes)
