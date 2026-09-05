from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from mediaforge.app import create_app
from mediaforge.blender_manager import BlenderRuntimeManager
from mediaforge.blender_operation import BlenderRuntimeOperationState
from mediaforge.blender_runtime import BlenderRuntimeResolver
from mediaforge.blender_web import (
    BlenderWebPack,
    BlenderWebPackError,
    load_web_pack_spec,
    validate_web_pack_archive,
)
from mediaforge.config import Settings
from mediaforge.store import Store


ROOT = Path(__file__).resolve().parents[1]


def tar_bytes(root: str, files: dict[str, tuple[bytes, int]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        directory = tarfile.TarInfo(root)
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        archive.addfile(directory)
        for relative, (content, mode) in files.items():
            parts = relative.split("/")[:-1]
            for index in range(1, len(parts) + 1):
                name = f"{root}/{'/'.join(parts[:index])}"
                if name in archive.getnames():
                    continue
                member = tarfile.TarInfo(name)
                member.type = tarfile.DIRTYPE
                member.mode = 0o755
                archive.addfile(member)
            member = tarfile.TarInfo(f"{root}/{relative}")
            member.size = len(content)
            member.mode = mode
            archive.addfile(member, io.BytesIO(content))
    return output.getvalue()


def fixture_archives() -> tuple[bytes, bytes, dict[str, tuple[bytes, int]], dict[str, tuple[bytes, int]]]:
    tiger = {
        "usr/bin/Xvnc": (b"#!/bin/sh\necho 'Xvnc TigerVNC 1.16.2'\n", 0o755),
        "usr/bin/vncpasswd": (b"#!/bin/sh\necho 'Usage: vncpasswd'\n", 0o755),
        "usr/share/doc/tigervnc/LICENCE.TXT": (b"GPL-2.0-or-later\n", 0o644),
    }
    novnc = {
        "core/rfb.js": (b"export default class RFB {}\n", 0o644),
        "core/websock.js": (b"export default class Websock {}\n", 0o644),
        "package.json": (json.dumps({
            "name": "@novnc/novnc", "version": "1.7.0", "license": "MPL-2.0",
        }).encode(), 0o644),
        "LICENSE.txt": (b"MPL-2.0\n", 0o644),
    }
    return (
        tar_bytes("tigervnc-fixture", tiger),
        tar_bytes("noVNC-fixture", novnc),
        tiger,
        novnc,
    )


def manifest_value(
    tiger_archive: bytes,
    novnc_archive: bytes,
    tiger: dict[str, tuple[bytes, int]],
    novnc: dict[str, tuple[bytes, int]],
) -> dict[str, object]:
    components = []
    for component_id, version, name, top, content, license_value in (
        ("tigervnc", "1.16.2", "tigervnc-fixture.tar.gz", "tigervnc-fixture", tiger_archive, "GPL-2.0-or-later"),
        ("novnc", "1.7.0", "novnc-fixture.tar.gz", "noVNC-fixture", novnc_archive, "MPL-2.0"),
    ):
        components.append({
            "id": component_id,
            "version": version,
            "archive_name": name,
            "archive_url": f"https://example.invalid/{name}",
            "archive_size_bytes": len(content),
            "archive_sha256": hashlib.sha256(content).hexdigest(),
            "top_level_directory": top,
            "license": license_value,
            "source_url": f"https://example.invalid/source/{component_id}",
        })
    required = []
    for component_id, files in (("tigervnc", tiger), ("novnc", novnc)):
        for relative, (content, mode) in files.items():
            required.append({
                "path": f"{component_id}/{relative}",
                "sha256": hashlib.sha256(content).hexdigest(),
                "executable": bool(mode & 0o111),
            })
    return {
        "schema_version": 1,
        "pack_id": "blender-web-fixture-linux-x64",
        "version": "1.0.0",
        "platform": "linux-x86_64",
        "components": components,
        "required_files": required,
    }


def fixture_manifest(tmp_path: Path) -> tuple[Path, dict[str, bytes]]:
    tiger_archive, novnc_archive, tiger, novnc = fixture_archives()
    value = manifest_value(tiger_archive, novnc_archive, tiger, novnc)
    path = tmp_path / "blender-web-runtime.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, {
        "/tigervnc-fixture.tar.gz": tiger_archive,
        "/novnc-fixture.tar.gz": novnc_archive,
    }


def response_transport(contents: dict[str, bytes]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        content = contents[request.url.path]
        start = int(request.headers.get("range", "bytes=0-").removeprefix("bytes=").removesuffix("-"))
        headers = {"ETag": '"fixture-v1"', "Content-Length": str(len(content) - start)}
        if start:
            headers["Content-Range"] = f"bytes {start}-{len(content) - 1}/{len(content)}"
        return httpx.Response(206 if start else 200, content=content[start:], headers=headers, request=request)
    return httpx.MockTransport(handler)


def manager_fixture(
    tmp_path: Path, store: Store, manifest: Path, transport: httpx.AsyncBaseTransport
) -> tuple[BlenderRuntimeManager, BlenderWebPack]:
    resolver = BlenderRuntimeResolver(
        registry_path=tmp_path / "data/runtime-state/blender-runtimes.json",
        managed_root=tmp_path / "blender",
        legacy_root=tmp_path / "missing-legacy",
        manifest_path=ROOT / "config/blender-runtime.json",
        trusted_worker=ROOT / "worker_packs/blender/compile_asset.py",
        catalog_path=ROOT / "config/blender-runtime-catalog.json",
    )
    web_pack = BlenderWebPack(manifest, tmp_path / "web")
    manager = BlenderRuntimeManager(
        store,
        resolver,
        manifest_path=ROOT / "config/blender-runtime.json",
        preflight_script=ROOT / "worker_packs/blender/preflight.py",
        download_root=tmp_path / "downloads",
        catalog_path=ROOT / "config/blender-runtime-catalog.json",
        web_pack=web_pack,
        web_download_root=tmp_path / "web-downloads",
        transport=transport,
    )
    return manager, web_pack


async def wait_terminal(store: Store, operation_id: str):
    for _ in range(500):
        operation = store.get_blender_runtime_operation(operation_id)
        if operation.state in {
            BlenderRuntimeOperationState.READY,
            BlenderRuntimeOperationState.FAILED,
            BlenderRuntimeOperationState.CANCELED,
        }:
            return operation
        await asyncio.sleep(0.01)
    raise AssertionError("web pack operation did not finish")


def test_pinned_production_manifest_matches_downloaded_archives() -> None:
    spec = load_web_pack_spec(ROOT / "config/blender-web-runtime.json")
    assert spec.pack_id == "blender-web-1.0.0-linux-x64"
    assert [(item.id, item.version, item.license) for item in spec.components] == [
        ("tigervnc", "1.16.2", "GPL-2.0-or-later"),
        ("novnc", "1.7.0", "MPL-2.0"),
    ]
    assert spec.archive_size_bytes == 15_769_716


def test_install_is_atomic_probed_and_detects_required_file_tamper(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest, contents = fixture_manifest(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        manager, web_pack = manager_fixture(tmp_path, store, manifest, response_transport(contents))
        await manager.start()
        assert manager.web_status()["state"] == "missing"
        created = manager.install_web()
        finished = await wait_terminal(store, created.id)
        assert finished.state == BlenderRuntimeOperationState.READY
        assert finished.bytes_done == finished.bytes_total == sum(map(len, contents.values()))
        assert finished.result is not None
        assert finished.result["probe"] == {
            "tigervnc": "1.16.2", "novnc": "1.7.0", "software_display": True,
        }
        status = manager.web_status()
        assert status["state"] == "ready" and status["install_available"] is False
        assert str(tmp_path) not in json.dumps(status)
        destination = web_pack.destination()
        assert not (tmp_path / "web/.staging" / created.id).exists()
        (destination / "install/novnc/core/rfb.js").write_text("tampered", encoding="utf-8")
        assert manager.web_status()["state"] == "damaged"
        await manager.stop()
    asyncio.run(scenario())


def test_client_file_serves_only_pinned_javascript_and_rechecks_hash(tmp_path: Path) -> None:
    manifest, contents = fixture_manifest(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, web_pack = manager_fixture(
        tmp_path, store, manifest, response_transport(contents)
    )

    async def install() -> None:
        await manager.start()
        operation = manager.install_web()
        assert (await wait_terminal(store, operation.id)).state == BlenderRuntimeOperationState.READY
        await manager.stop()

    asyncio.run(install())
    resolved = web_pack.client_file("core/rfb.js")
    assert resolved.read_text(encoding="utf-8") == "export default class RFB {}\n"
    with pytest.raises(BlenderWebPackError) as traversal:
        web_pack.client_file("../package.json")
    assert traversal.value.code == "blender_web_client_unavailable"
    with pytest.raises(BlenderWebPackError):
        web_pack.client_file("package.json")
    resolved.write_text("tampered", encoding="utf-8")
    with pytest.raises(BlenderWebPackError) as tampered:
        web_pack.client_file("core/rfb.js")
    assert tampered.value.code == "blender_web_client_unavailable"


def test_private_client_route_is_cors_readable_immutable_and_not_public(tmp_path: Path) -> None:
    manifest, contents = fixture_manifest(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _web_pack = manager_fixture(
        tmp_path, store, manifest, response_transport(contents)
    )

    async def install() -> None:
        await manager.start()
        operation = manager.install_web()
        assert (await wait_terminal(store, operation.id)).state == BlenderRuntimeOperationState.READY
        await manager.stop()

    asyncio.run(install())
    settings = Settings(
        data_dir=tmp_path / "data",
        blender_legacy_runtime_root=tmp_path / "missing-blender",
        blender_managed_runtime_root=tmp_path / "managed-blender",
        blender_runtime_registry=tmp_path / "data/runtime-state/blender-runtimes.json",
        blender_download_root=tmp_path / "downloads",
        blender_web_runtime_root=tmp_path / "web",
        blender_web_download_root=tmp_path / "web-downloads",
    )
    app = create_app(settings, blender_web_manifest_path=manifest)
    with TestClient(app) as client:
        response = client.get("/blender-web-client/core/rfb.js")
        assert response.status_code == 200
        assert response.content == b"export default class RFB {}\n"
        assert response.headers["access-control-allow-origin"] == "*"
        assert response.headers["cross-origin-resource-policy"] == "cross-origin"
        assert response.headers["cache-control"].endswith("immutable")
        loader = client.get("/blender-rfb-loader.js")
        assert loader.status_code == 200
        assert b'import RFB from "./blender-web-client/core/rfb.js"' in loader.content
        assert loader.headers["access-control-allow-origin"] == "*"
        assert loader.headers["cross-origin-resource-policy"] == "cross-origin"
        assert client.get("/blender-web-client/package.json").status_code == 404
        assert "/blender-web-client" not in client.get("/openapi.json").text
        assert "/blender-rfb-loader.js" not in client.get("/openapi.json").text


def test_private_workspace_installs_only_the_pinned_web_pack(tmp_path: Path) -> None:
    manifest, contents = fixture_manifest(tmp_path)
    settings = Settings(
        data_dir=tmp_path / "data",
        blender_legacy_runtime_root=tmp_path / "missing-legacy",
        blender_managed_runtime_root=tmp_path / "blender",
        blender_runtime_registry=tmp_path / "data/runtime-state/blender-runtimes.json",
        blender_download_root=tmp_path / "downloads",
        blender_web_runtime_root=tmp_path / "web",
        blender_web_download_root=tmp_path / "web-downloads",
    )
    app = create_app(
        settings,
        blender_download_transport=response_transport(contents),
        blender_web_manifest_path=manifest,
    )
    with TestClient(app) as client:
        initial = client.get("/workspace-api/blender/runtime")
        assert initial.status_code == 200
        assert initial.json()["web_pack"]["state"] == "missing"
        rejected = client.post(
            "/workspace-api/blender/runtime/operations",
            json={"action": "web_install", "url": "https://attacker.invalid/pack.tar.gz"},
        )
        assert rejected.status_code == 422
        created = client.post(
            "/workspace-api/blender/runtime/operations", json={"action": "web_install"}
        )
        assert created.status_code == 200
        operation_id = created.json()["id"]
        for _ in range(200):
            status = client.get("/workspace-api/blender/runtime").json()
            operation = next(item for item in status["operations"] if item["id"] == operation_id)
            if operation["state"] in {"ready", "failed", "canceled"}:
                break
            time.sleep(0.01)
        assert operation["state"] == "ready"
        assert status["web_pack"]["state"] == "ready"
        assert str(tmp_path) not in json.dumps(status)


def test_invalid_web_pack_catalog_fails_closed_at_the_private_boundary(tmp_path: Path) -> None:
    manifest = tmp_path / "invalid-web-runtime.json"
    manifest.write_text("{}", encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        blender_legacy_runtime_root=tmp_path / "missing-legacy",
        blender_managed_runtime_root=tmp_path / "blender",
        blender_runtime_registry=tmp_path / "data/runtime-state/blender-runtimes.json",
        blender_download_root=tmp_path / "downloads",
        blender_web_runtime_root=tmp_path / "web",
        blender_web_download_root=tmp_path / "web-downloads",
    )
    app = create_app(settings, blender_web_manifest_path=manifest)
    with TestClient(app) as client:
        status = client.get("/workspace-api/blender/runtime").json()["web_pack"]
        assert status["state"] == "invalid"
        assert status["install_available"] is False
        response = client.post(
            "/workspace-api/blender/runtime/operations", json={"action": "web_install"}
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "blender_web_catalog_invalid"


class PausedStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes, release: asyncio.Event):
        self.content = content
        self.release = release

    async def __aiter__(self):
        yield self.content[:16]
        await self.release.wait()
        yield self.content[16:]


def test_cancel_retains_bounded_partial_and_restart_resumes(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest, contents = fixture_manifest(tmp_path)
        release = asyncio.Event()

        def paused(request: httpx.Request) -> httpx.Response:
            content = contents[request.url.path]
            return httpx.Response(
                200, stream=PausedStream(content, release),
                headers={"ETag": '"fixture-v1"', "Content-Length": str(len(content))},
                request=request,
            )

        store = Store(tmp_path / "data")
        store.initialize()
        manager, _web_pack = manager_fixture(tmp_path, store, manifest, httpx.MockTransport(paused))
        await manager.start()
        created = manager.install_web()
        partial = tmp_path / "web-downloads/tigervnc-fixture.tar.gz.partial"
        for _ in range(200):
            if partial.is_file() and partial.stat().st_size == 16:
                break
            await asyncio.sleep(0.01)
        assert partial.stat().st_size == 16
        manager.cancel(created.id)
        release.set()
        canceled = await wait_terminal(store, created.id)
        assert canceled.state == BlenderRuntimeOperationState.CANCELED
        assert partial.stat().st_size == 16
        assert not (tmp_path / "web/.staging" / created.id).exists()
        await manager.stop()

        restarted_store = Store(tmp_path / "data")
        restarted_store.initialize()
        resumed, _ = manager_fixture(
            tmp_path, restarted_store, manifest, response_transport(contents)
        )
        retried = resumed.install_web()
        await resumed.start()
        finished = await wait_terminal(restarted_store, retried.id)
        assert finished.state == BlenderRuntimeOperationState.READY
        assert resumed.web_status()["state"] == "ready"
        await resumed.stop()
    asyncio.run(scenario())


def test_archive_rejects_traversal_link_duplicate_and_hash_change(tmp_path: Path) -> None:
    manifest, contents = fixture_manifest(tmp_path)
    spec = load_web_pack_spec(manifest)
    component = spec.components[0]
    valid = tmp_path / component.archive_name
    valid.write_bytes(contents[f"/{component.archive_name}"])
    assert validate_web_pack_archive(valid, component)["members"] > 0
    changed = bytearray(valid.read_bytes())
    changed[-8] ^= 1
    valid.write_bytes(changed)
    try:
        validate_web_pack_archive(valid, component)
    except BlenderWebPackError as exc:
        assert exc.code == "blender_web_verify_failed"
    else:
        raise AssertionError("changed archive was accepted")

    for kind in ("traversal", "alias", "link", "duplicate"):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            root = tarfile.TarInfo(component.top_level_directory)
            root.type = tarfile.DIRTYPE
            archive.addfile(root)
            name = (
                f"{component.top_level_directory}/../escape"
                if kind == "traversal"
                else (
                    f"{component.top_level_directory}//file"
                    if kind == "alias" else f"{component.top_level_directory}/file"
                )
            )
            member = tarfile.TarInfo(name)
            if kind == "link":
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
                archive.addfile(member)
            else:
                member.size = 1
                archive.addfile(member, io.BytesIO(b"x"))
                if kind == "duplicate":
                    duplicate = tarfile.TarInfo(name)
                    duplicate.size = 1
                    archive.addfile(duplicate, io.BytesIO(b"y"))
        content = output.getvalue()
        unsafe = tmp_path / f"{kind}.tar.gz"
        unsafe.write_bytes(content)
        altered = component.__class__(
            **{**component.__dict__, "archive_name": unsafe.name,
               "archive_size_bytes": len(content), "archive_sha256": hashlib.sha256(content).hexdigest()}
        )
        try:
            validate_web_pack_archive(unsafe, altered)
        except BlenderWebPackError as exc:
            assert exc.code == "blender_web_verify_failed"
        else:
            raise AssertionError(f"{kind} archive was accepted")
