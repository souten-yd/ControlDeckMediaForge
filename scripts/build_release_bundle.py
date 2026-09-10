from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def stage_bundle_data(source: Path, destination: Path) -> None:
    """Copy resource trees without interpreter caches left by local tests.

    Workers run with their own Python versions; cached build-interpreter
    bytecode is neither a release resource nor a replacement for their source.
    Never clean the checkout itself to obtain a clean release.
    """
    for name in ("frontend", "schemas", "worker_packs", "creative", "profiles"):
        shutil.copytree(
            source / name, destination / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )


def copy_file(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(mode)


# 出来上がりが小さすぎたら、途中で終わっている。
#
# SonicForge で実際に起きた: PyInstaller が OOM killer に落とされ、それでも
# exit code は 0 で返り、2.4MB の tar.gz ができた（正常なら 30MB）。署名は
# マニフェストと実物が一致するかしか見ないので、そのまま署名すれば**壊れた状態が
# 正しいと証明される**。気づかなければ公開して、適用時に壊れる。
#
# 数字は「明らかにおかしい」を弾くためのもので、正常値に張り付けない。
MIN_EXECUTABLE_BYTES = 10 * 1024 * 1024
MIN_ARTIFACT_BYTES = 10 * 1024 * 1024


def check_executable(entrypoint: Path, core: Path) -> None:
    """出来上がった実行ファイルが、大きさを持ち、実際に起動することを確かめる。

    大きさだけでは足りない。ビルド環境を取り違えると、大きさはあっても依存が
    欠けたものができる（実際に起きた: 別の venv で建てて `No module named
    'pydantic'` になった）。起動させるのが最も確かで、doctor は依存を全部踏む。
    """
    size = core.stat().st_size
    if size < MIN_EXECUTABLE_BYTES:
        raise SystemExit(
            f"built executable is only {size} bytes; the build did not finish"
        )
    # launcher は ControlDeck が導入時に渡す場所を要求する。ここでは実際の
    # 持ち物へ触らせたくないので、捨てる場所を渡す。doctor は読むだけで、
    # 足りないものを数え上げて返す。
    with tempfile.TemporaryDirectory(prefix="mediaforge-smoke-") as scratch:
        environment = dict(os.environ)
        environment["CONTROL_DECK_FEATURE_DATA_DIR"] = str(Path(scratch) / "feature")
        environment["CONTROL_DECK_SHARED_CACHE_DIR"] = str(Path(scratch) / "cache")
        finished = subprocess.run(
            [str(entrypoint), "doctor"],
            capture_output=True,
            timeout=600,
            env=environment,
        )
    if finished.returncode != 0:
        tail = finished.stderr.decode("utf-8", "replace")[-2000:]
        raise SystemExit(f"built executable failed its smoke run:\n{tail}")


def check_artifact(path: Path, name: str) -> None:
    size = path.stat().st_size
    if size < MIN_ARTIFACT_BYTES:
        raise SystemExit(f"archive is only {size} bytes; the build did not finish")
    with tarfile.open(path, "r:gz") as archive:
        members = set(archive.getnames())
    required = {
        f"{name}/bin/mediaforge",
        f"{name}/bin/mediaforge-core",
        f"{name}/control-deck-addon.json",
        f"{name}/control-deck-feature.json",
    }
    missing = sorted(required - members)
    if missing:
        raise SystemExit(f"archive is missing: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pyinstaller", type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise SystemExit("only linux-x86_64 release bundles are currently supported")
    if not args.version or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._+-" for character in args.version):
        raise SystemExit("invalid bundle version")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    name = f"control-deck-media-forge-{args.version}-linux-x86_64"
    with tempfile.TemporaryDirectory(prefix="mediaforge-bundle-") as temporary:
        work = Path(temporary)
        dist = work / "dist"
        resources = work / "resources"
        stage_bundle_data(ROOT, resources)
        pyinstaller_python = args.pyinstaller.parent / "python"
        pyinstaller_argv = (
            [str(pyinstaller_python), "-m", "PyInstaller"]
            if pyinstaller_python.is_file()
            else [str(args.pyinstaller)]
        )
        subprocess.run(
            [
                *pyinstaller_argv,
                "--noconfirm",
                "--clean",
                "--onefile",
                "--name", "mediaforge-core",
                "--paths", str(ROOT / "backend"),
                "--distpath", str(dist),
                "--workpath", str(work / "build"),
                "--specpath", str(work),
                "--add-data", f"{resources / 'frontend'}:frontend",
                "--add-data", f"{resources / 'schemas'}:schemas",
                "--add-data", f"{resources / 'worker_packs'}:worker_packs",
                "--add-data", f"{resources / 'creative'}:creative",
                "--add-data", f"{resources / 'profiles'}:profiles",
                "--add-data", f"{ROOT / 'config' / 'blender-runtime.json'}:config",
                "--add-data", f"{ROOT / 'config' / 'blender-runtime-catalog.json'}:config",
                "--add-data", f"{ROOT / 'config' / 'blender-web-runtime.json'}:config",
                "--add-data", f"{ROOT / 'runtimes' / 'rocm-torch' / 'requirements.txt'}:runtimes/rocm-torch",
                str(ROOT / "scripts" / "bundle_entrypoint.py"),
            ],
            cwd=ROOT,
            check=True,
        )
        bundle = work / name
        copy_file(dist / "mediaforge-core", bundle / "bin" / "mediaforge-core", 0o755)
        copy_file(ROOT / "scripts" / "bundle-launcher.sh", bundle / "bin" / "mediaforge", 0o755)
        check_executable(bundle / "bin" / "mediaforge", bundle / "bin" / "mediaforge-core")
        addon = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
        # --version で addon.json を黙って上書きしていた。結果、束ねた
        # control-deck-addon.json と、同じ束の中の mediaforge.__version__ が
        # 別の版を名乗ることになる。ControlDeck 側は前者を出すので、
        # 一覧に出ている版と実際に動いている版が食い違う。名乗る版は 1 つにする。
        packaged = re.search(
            r'__version__ = "([^"]+)"',
            (ROOT / "backend" / "mediaforge" / "__init__.py").read_text(encoding="utf-8"),
        ).group(1)
        if args.version != addon["version"] or args.version != packaged:
            raise SystemExit(
                f"version mismatch: --version={args.version} "
                f"addon.json={addon['version']} mediaforge.__version__={packaged}. "
                "リリース前に 3 つを揃えてください。"
            )
        (bundle / "control-deck-addon.json").write_text(
            json.dumps(addon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (bundle / "control-deck-addon.json").chmod(0o644)
        package = {
            "schema_version": 1,
            "feature_id": "media-forge",
            "version": args.version,
            "platform": "linux",
            "architecture": "x86_64",
            "entrypoint": "bin/mediaforge",
            "addon_manifest": "control-deck-addon.json",
            "provision_args": ["provision"],
            "smoke_args": ["doctor"],
            "service_args": ["serve"],
            "health_url": "http://127.0.0.1:9130/health",
        }
        (bundle / "control-deck-feature.json").write_text(
            json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (bundle / "control-deck-feature.json").chmod(0o644)
        artifact = args.output_dir / f"{name}.tar.gz"
        with tarfile.open(artifact, "w:gz", compresslevel=9) as archive:
            archive.add(bundle, arcname=name, recursive=True)
        check_artifact(artifact, name)
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        checksum = artifact.with_name(artifact.name + ".sha256")
        checksum.write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
        print(json.dumps({"artifact": str(artifact), "sha256": digest, "bytes": artifact.stat().st_size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
