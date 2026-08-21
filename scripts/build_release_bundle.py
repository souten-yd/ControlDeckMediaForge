from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copy_file(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(mode)


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
                "--add-data", f"{ROOT / 'frontend'}:frontend",
                "--add-data", f"{ROOT / 'schemas'}:schemas",
                "--add-data", f"{ROOT / 'worker_packs'}:worker_packs",
                "--add-data", f"{ROOT / 'runtimes' / 'rocm-torch' / 'requirements.txt'}:runtimes/rocm-torch",
                str(ROOT / "scripts" / "bundle_entrypoint.py"),
            ],
            cwd=ROOT,
            check=True,
        )
        bundle = work / name
        copy_file(dist / "mediaforge-core", bundle / "bin" / "mediaforge-core", 0o755)
        copy_file(ROOT / "scripts" / "bundle-launcher.sh", bundle / "bin" / "mediaforge", 0o755)
        addon = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
        addon["version"] = args.version
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
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        checksum = artifact.with_name(artifact.name + ".sha256")
        checksum.write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
        print(json.dumps({"artifact": str(artifact), "sha256": digest, "bytes": artifact.stat().st_size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
