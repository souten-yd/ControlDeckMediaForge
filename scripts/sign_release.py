"""Sign a release bundle so ControlDeck can trust it without being edited.

The problem this removes: ControlDeck pinned each bundle's SHA-256 in its own
`trusted-catalog.json`, so shipping Media Forge meant changing ControlDeck too.
Trust was attached to one specific file rather than to whoever publishes it.

What replaces it is an Ed25519 signature over a small manifest. ControlDeck
holds the public key once; every later release verifies against it.

The manifest — not the tarball digest alone — is what gets signed, and that
distinction matters. A signature over the digest by itself is replayable: an
old release, correctly signed, can be served in place of a new one. Binding
feature id, version, platform, architecture and size into the signed bytes
means a substituted artifact fails verification rather than passing as
something it is not. ControlDeck refuses a downgrade on top of that.

Signing is a build-time job and its dependency lives in the build runtime, not
in the shipped core. Run this with runtimes/bundle-build/.venv/bin/python.

    # once, on the publisher's machine
    python scripts/sign_release.py keygen --private-key ~/.keys/media-forge.pem

    # per release, after build_release_bundle.py
    python scripts/sign_release.py sign \\
        --artifact dist/control-deck-media-forge-0.6.3-linux-x86_64.tar.gz \\
        --feature-id media-forge --version 0.6.3 \\
        --private-key ~/.keys/media-forge.pem

The private key never belongs in this repository. `keygen` writes it 0600 and
refuses to overwrite an existing file.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


MANIFEST_SCHEMA_VERSION = 1
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([.+-][0-9A-Za-z.+-]+)?$")
FEATURE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
# 名前から platform/arch を読む。build_release_bundle.py が付ける形と同じ。
ARTIFACT_RE = re.compile(
    r"^(?P<stem>[a-z0-9-]+)-(?P<version>[0-9][0-9A-Za-z.+-]*)"
    r"-(?P<platform>[a-z0-9]+)-(?P<arch>[a-z0-9_]+)\.tar\.gz$"
)


def canonical_bytes(manifest: dict[str, object]) -> bytes:
    """Serialise exactly one way, so both sides sign and verify the same bytes.

    Key order and spacing are part of the signed message. Re-serialising with
    different settings on the verifying side would fail every signature, so the
    encoding is fixed here and mirrored in ControlDeck.
    """
    return json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def build_manifest(artifact: Path, *, feature_id: str, version: str) -> dict[str, object]:
    match = ARTIFACT_RE.fullmatch(artifact.name)
    if match is None:
        raise SystemExit(f"artifact name is not in the expected form: {artifact.name}")
    if match.group("version") != version:
        raise SystemExit(
            f"--version {version} does not match the artifact name {match.group('version')}"
        )
    digest, size = sha256_file(artifact)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "feature_id": feature_id,
        "version": version,
        "platform": match.group("platform"),
        "architecture": match.group("arch"),
        "artifact_name": artifact.name,
        "sha256": digest,
        "size_bytes": size,
    }


def keygen(args: argparse.Namespace) -> int:
    private_path = Path(args.private_key).expanduser()
    if private_path.exists():
        raise SystemExit(
            f"{private_path} already exists. 鍵を作り直すと、既存のリリースが"
            "検証できなくなります。入れ替えるなら明示的に消してください。"
        )
    private_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    private_path.chmod(0o600)
    public = base64.b64encode(key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )).decode("ascii")
    print(json.dumps({
        "private_key": str(private_path),
        "public_key_base64": public,
        "note": "public_key_base64 を ControlDeck の trusted-catalog.json へ登録してください。",
    }, ensure_ascii=False, indent=2))
    return 0


def sign(args: argparse.Namespace) -> int:
    artifact = Path(args.artifact).expanduser().resolve(strict=True)
    if FEATURE_ID_RE.fullmatch(args.feature_id) is None:
        raise SystemExit("feature id is invalid")
    if VERSION_RE.fullmatch(args.version) is None:
        raise SystemExit("version is invalid")

    private_path = Path(args.private_key).expanduser()
    try:
        key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"signing key could not be read: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("signing key must be Ed25519")

    manifest = build_manifest(artifact, feature_id=args.feature_id, version=args.version)
    message = canonical_bytes(manifest)
    signature = key.sign(message)

    manifest_path = artifact.with_name(f"{artifact.name}.manifest.json")
    signature_path = artifact.with_name(f"{artifact.name}.manifest.json.sig")
    # 署名した通りのバイト列を書く。整形し直すと検証側と食い違う。
    manifest_path.write_bytes(message + b"\n")
    manifest_path.chmod(0o644)
    signature_path.write_text(base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
    signature_path.chmod(0o644)

    public = base64.b64encode(key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )).decode("ascii")
    # 署名した鍵で自分の署名を確かめる。書き出しの取り違えをここで捕まえる。
    Ed25519PublicKey.from_public_bytes(
        base64.b64decode(public)
    ).verify(base64.b64decode(signature_path.read_text(encoding="ascii").strip()),
             manifest_path.read_bytes().rstrip(b"\n"))

    print(json.dumps({
        "manifest": str(manifest_path),
        "signature": str(signature_path),
        "public_key_base64": public,
        **manifest,
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("keygen", help="発行者の Ed25519 鍵を作る（1 度だけ）")
    generate.add_argument("--private-key", required=True)
    generate.set_defaults(handler=keygen)

    signer = sub.add_parser("sign", help="リリース成果物に署名する")
    signer.add_argument("--artifact", required=True)
    signer.add_argument("--feature-id", required=True)
    signer.add_argument("--version", required=True)
    signer.add_argument("--private-key", required=True)
    signer.set_defaults(handler=sign)

    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
