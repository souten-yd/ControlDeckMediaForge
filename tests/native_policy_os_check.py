"""Real OS Ed25519 checks. Only ephemeral in-memory test keys are used."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker_packs.native_setup import policy_release as policy
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class PolicyChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.payload = b"read-only native verification fixture"
        self.manifest = {
            "schema_version": policy.SCHEMA, "feature_id": "media-forge",
            "purpose": policy.PURPOSE, "version": "0.28.80", "source_commit": "a" * 40,
            "platform": "linux", "architecture": "x86_64",
            "artifact_name": "control-deck-media-forge-os-policy-0.28.80-linux-x86_64.deb",
            "sha256": hashlib.sha256(self.payload).hexdigest(), "size_bytes": len(self.payload),
        }

    def verify(self, *, message: bytes | None = None, payload: bytes | None = None,
               signature: bytes | None = None) -> policy.VerifiedPolicyRelease:
        message = message if message is not None else policy.canonical_bytes(self.manifest)
        with patch.object(policy, "PUBLISHER_KEY", self.public):
            return policy.verify_policy_release(
                message, self.key.sign(message) if signature is None else signature,
                self.payload if payload is None else payload,
                expected_version="0.28.80", expected_source_commit="a" * 40)

    def test_actual_publisher_rejects_test_key(self) -> None:
        message = policy.canonical_bytes(self.manifest)
        with self.assertRaisesRegex(policy.PolicyReleaseError, "signature_invalid"):
            policy.verify_policy_release(message, self.key.sign(message), self.payload,
                expected_version="0.28.80", expected_source_commit="a" * 40)

    def test_success_retains_identical_immutable_bytes(self) -> None:
        result = self.verify()
        self.assertIs(result.package_bytes, self.payload)
        self.manifest["sha256"] = "b" * 64
        self.assertEqual(result.sha256, hashlib.sha256(self.payload).hexdigest())
        with self.assertRaises(FrozenInstanceError):
            result.package_bytes = b"replacement"

    def test_wrong_signature(self) -> None:
        with self.assertRaisesRegex(policy.PolicyReleaseError, "signature_invalid"):
            self.verify(signature=Ed25519PrivateKey.generate().sign(b"different"))

    def test_payload_tamper_same_size(self) -> None:
        with self.assertRaisesRegex(policy.PolicyReleaseError, "digest_mismatch"):
            self.verify(payload=b"X" * len(self.payload))

    def test_signed_wrong_identities(self) -> None:
        for field, value in [
            ("schema_version", "media-forge.release@1"), ("feature_id", "other"),
            ("purpose", "general-root-code"), ("version", "0.28.79"),
            ("source_commit", "b" * 40), ("platform", "windows"),
            ("architecture", "aarch64"), ("artifact_name", "../../evil.deb"),
            ("sha256", "A" * 64), ("size_bytes", True), ("extra", "forbidden"),
        ]:
            with self.subTest(field=field), patch.dict(self.manifest, {field: value}):
                with self.assertRaisesRegex(policy.PolicyReleaseError, "identity_mismatch"):
                    self.verify()

    def test_missing_fields(self) -> None:
        for field in list(self.manifest):
            manifest = dict(self.manifest)
            del manifest[field]
            with self.subTest(field=field), self.assertRaises(policy.PolicyReleaseError):
                self.verify(message=policy.canonical_bytes(manifest))

    def test_noncanonical_and_duplicate_json(self) -> None:
        valid = policy.canonical_bytes(self.manifest)
        for message in [valid + b"\n", b" " + valid, json.dumps(self.manifest).encode(),
                        b'{"purpose":"x","purpose":"y"}', b"[]", b"null", b"NaN",
                        b'{"x":NaN}', b'"\\ud800"', b"\xff", b"[" * 2000]:
            with self.subTest(message=message[:20]), self.assertRaises(policy.PolicyReleaseError):
                self.verify(message=message)

    def test_limits_and_mutable_input(self) -> None:
        valid = policy.canonical_bytes(self.manifest)
        signature = self.key.sign(valid)
        for message, sig, data in [
            (b"", signature, self.payload), (b"x" * 4097, signature, self.payload),
            (bytearray(valid), signature, self.payload), (valid, b"x" * 63, self.payload),
            (valid, bytearray(signature), self.payload), (valid, signature, b""),
            (valid, signature, bytearray(self.payload)),
            (valid, signature, b"x" * (policy.MAX_PACKAGE_BYTES + 1)),
        ]:
            with self.assertRaisesRegex(policy.PolicyReleaseError, "invalid_input"):
                policy.verify_policy_release(message, sig, data,
                    expected_version="0.28.80", expected_source_commit="a" * 40)

    def test_expected_identity_must_be_fixed(self) -> None:
        for version, commit in [("latest", "a" * 40), ("0.28.80", "main"),
                                (True, "a" * 40), ("0.28.80", "A" * 40),
                                ("0.28.80\n", "a" * 40)]:
            with self.assertRaisesRegex(policy.PolicyReleaseError, "invalid_expectation"):
                policy.verify_policy_release(b"", b"", b"",
                    expected_version=version, expected_source_commit=commit)


if __name__ == "__main__":
    unittest.main()
