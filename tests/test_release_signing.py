"""公開する manifest は、署名したバイト列そのものでなければならない。

実測（v0.9.0）: 末尾に改行 1 つを足して配っていた。署名は改行の無い方に
付いているので、検証側が受け取るバイト列とは別物になる。ControlDeck 側が
改行を落としてくれている間は通っていたが、その処理が無くなった途端に、
正しい署名が「信頼できる鍵に一致しない」として拒まれた。

検証側に落としてもらう前提にしない。配るものと署名したものを同じにする。

署名の依存（cryptography）は build runtime にしかない。出荷物に鍵を扱う
コードを持ち込まないためで、その判断は変えない。だから署名も検証も向こうの
python で実行し、こちらは結果とファイルの中身だけを見る。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SIGN = ROOT / "scripts" / "sign_release.py"
BUILD_PYTHON = ROOT / "runtimes/bundle-build/.venv/bin/python"

VERIFY = """
import base64, json, subprocess, sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

root = Path(sys.argv[1])
key = Ed25519PrivateKey.generate()
key_path = root / "key.pem"
key_path.write_bytes(key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
))
artifact = root / "control-deck-media-forge-1.2.3-linux-x86_64.tar.gz"
artifact.write_bytes(b"bundle")
subprocess.run([sys.executable, sys.argv[2], "sign", "--artifact", str(artifact),
                "--feature-id", "media-forge", "--version", "1.2.3",
                "--private-key", str(key_path)], check=True, capture_output=True)
message = artifact.with_name(artifact.name + ".manifest.json").read_bytes()
signature = base64.b64decode(
    artifact.with_name(artifact.name + ".manifest.json.sig").read_text().strip())
public = key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
# 受け取ったままのバイト列で検証する。落としたり整形したりしない。
Ed25519PublicKey.from_public_bytes(public).verify(signature, message)
print("VERIFIED")
"""


def run_signing(tmp_path: Path) -> Path:
    if not BUILD_PYTHON.is_file():
        pytest.skip("署名には build runtime が要る")
    result = subprocess.run(
        [str(BUILD_PYTHON), "-c", VERIFY, str(tmp_path), str(SIGN)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert "VERIFIED" in result.stdout
    return tmp_path / "control-deck-media-forge-1.2.3-linux-x86_64.tar.gz.manifest.json"


def test_the_published_manifest_verifies_as_received(tmp_path: Path):
    """検証側が改行を落としてくれることに頼らない。"""
    assert run_signing(tmp_path).is_file()


def test_the_manifest_is_canonical_json(tmp_path: Path):
    """整形が違えば、同じ内容でもバイト列は別になる。"""
    message = run_signing(tmp_path).read_bytes()

    assert message == json.dumps(
        json.loads(message), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def test_the_signature_covers_more_than_the_digest(tmp_path: Path):
    """digest だけの署名は再生できる。古い release を新しいものの代わりに
    配れてしまう。"""
    manifest = json.loads(run_signing(tmp_path).read_bytes())

    assert {"feature_id", "version", "platform", "architecture", "size_bytes"} <= set(manifest)
