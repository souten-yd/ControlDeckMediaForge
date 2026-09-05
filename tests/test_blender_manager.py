from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from mediaforge.app import create_app
from mediaforge.blender_manager import BlenderRuntimeManager, RUNTIME_ID
from mediaforge.blender_operation import (
    BlenderRuntimeOperationAction,
    BlenderRuntimeOperationState,
)
from mediaforge.blender_runtime import BlenderRuntimeResolver
from mediaforge.config import Settings
from mediaforge.store import Store


ROOT = Path(__file__).resolve().parents[1]


def archive_content(version: str, *, reported_version: str | None = None) -> bytes:
    reported = reported_version or version
    executable = (
        "#!/bin/sh\nprintf 'MEDIA_FORGE_BLENDER_PREFLIGHT="
        f"{{\"version\":\"{reported}\",\"background\":true}}\\n'\\n"
    ).encode()
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:xz") as archive:
        directory = tarfile.TarInfo(f"blender-{version}-linux-x64")
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o700
        archive.addfile(directory)
        binary = tarfile.TarInfo(f"blender-{version}-linux-x64/blender")
        binary.size = len(executable)
        binary.mode = 0o755
        archive.addfile(binary, io.BytesIO(executable))
    return payload.getvalue()


def spec_value(version: str, content: bytes) -> dict[str, object]:
    return {
        "schema_version": 1,
        "version": version,
        "archive_name": f"blender-{version}-linux-x64.tar.xz",
        "archive_url": f"https://download.blender.org/release/Blender4.5/blender-{version}-linux-x64.tar.xz",
        "archive_size_bytes": len(content),
        "archive_sha256": hashlib.sha256(content).hexdigest(),
        "top_level_directory": f"blender-{version}-linux-x64",
        "executable": "blender",
        "license": "GPL-3.0-or-later",
        "source_url": "https://projects.blender.org/blender/blender",
    }


def archive_fixture(tmp_path: Path) -> tuple[bytes, Path]:
    content = archive_content("4.5.9")
    manifest = tmp_path / "blender-runtime.json"
    manifest.write_text(json.dumps(spec_value("4.5.9", content)), encoding="utf-8")
    return content, manifest


def catalog_fixture(
    tmp_path: Path, base_content: bytes, recommended_content: bytes
) -> Path:
    catalog = tmp_path / "blender-runtime-catalog.json"
    catalog.write_text(json.dumps({
        "schema_version": 1,
        "base_runtime_id": "blender-4.5.9-linux-x64",
        "recommended_studio_runtime_id": "blender-4.5.13-linux-x64",
        "runtimes": [
            {"runtime_id": "blender-4.5.9-linux-x64", "spec": spec_value("4.5.9", base_content)},
            {"runtime_id": "blender-4.5.13-linux-x64", "spec": spec_value("4.5.13", recommended_content)},
        ],
    }), encoding="utf-8")
    return catalog


def runtime_manager(
    tmp_path: Path,
    store: Store,
    manifest: Path,
    transport: httpx.AsyncBaseTransport,
    *,
    catalog: Path | None = None,
) -> tuple[BlenderRuntimeManager, BlenderRuntimeResolver]:
    resolver = BlenderRuntimeResolver(
        registry_path=tmp_path / "data/runtime-state/blender-runtimes.json",
        managed_root=tmp_path / "managed",
        legacy_root=tmp_path / "missing-legacy",
        manifest_path=manifest,
        trusted_worker=ROOT / "worker_packs/blender/compile_asset.py",
        catalog_path=catalog,
    )
    manager = BlenderRuntimeManager(
        store,
        resolver,
        manifest_path=manifest,
        preflight_script=ROOT / "worker_packs/blender/preflight.py",
        download_root=tmp_path / "downloads",
        catalog_path=catalog,
        transport=transport,
    )
    return manager, resolver


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
    raise AssertionError("Blender runtime operation did not finish")


def response_transport(content: bytes) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.headers.get("range", "bytes=0-").removeprefix("bytes=").removesuffix("-"))
        headers = {"ETag": '"fixture-v1"', "Content-Length": str(len(content) - start)}
        if start:
            headers["Content-Range"] = f"bytes {start}-{len(content) - 1}/{len(content)}"
        return httpx.Response(206 if start else 200, content=content[start:], headers=headers, request=request)
    return httpx.MockTransport(handler)


def catalog_transport(contents: dict[str, bytes]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        version = next((item for item in contents if f"blender-{item}-" in request.url.path), None)
        assert version is not None
        content = contents[version]
        start = int(request.headers.get("range", "bytes=0-").removeprefix("bytes=").removesuffix("-"))
        headers = {"ETag": f'"fixture-{version}"', "Content-Length": str(len(content) - start)}
        if start:
            headers["Content-Range"] = f"bytes {start}-{len(content) - 1}/{len(content)}"
        return httpx.Response(206 if start else 200, content=content[start:], headers=headers, request=request)
    return httpx.MockTransport(handler)


def test_install_is_durable_atomic_and_registers_only_opaque_identity(tmp_path: Path) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))
        await manager.start()
        created = manager.install()
        finished = await wait_terminal(store, created.id)
        assert finished.state == BlenderRuntimeOperationState.READY
        assert [created.state, finished.state] == [
            BlenderRuntimeOperationState.QUEUED, BlenderRuntimeOperationState.READY,
        ]
        selected = resolver.resolve_g8()
        assert selected is not None and selected.runtime_id == RUNTIME_ID
        assert selected.ownership == "managed"
        assert not (resolver.managed_root / ".staging" / created.id).exists()
        serialized = resolver.registry_path.read_text(encoding="utf-8")
        assert str(tmp_path) not in serialized and "/home" not in serialized
        assert finished.result is not None and finished.result["preflight"]["background"] is True
        await manager.stop()
    asyncio.run(scenario())


class PausedStream(httpx.AsyncByteStream):
    def __init__(self, first: bytes, rest: bytes, release: asyncio.Event):
        self.first = first
        self.rest = rest
        self.release = release

    async def __aiter__(self):
        yield self.first
        await self.release.wait()
        yield self.rest


def test_cancel_keeps_resumable_partial_but_removes_staging(tmp_path: Path) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        release = asyncio.Event()
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                stream=PausedStream(content[:16], content[16:], release),
                headers={"ETag": '"fixture-v1"', "Content-Length": str(len(content))},
                request=request,
            )
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(
            tmp_path, store, manifest, httpx.MockTransport(handler)
        )
        await manager.start()
        created = manager.install()
        partial = tmp_path / "downloads/blender-4.5.9-linux-x64.tar.xz.partial"
        for _ in range(200):
            if partial.exists() and partial.stat().st_size:
                break
            await asyncio.sleep(0.01)
        manager.cancel(created.id)
        release.set()
        finished = await wait_terminal(store, created.id)
        assert finished.state == BlenderRuntimeOperationState.CANCELED
        assert partial.is_file() and partial.stat().st_size > 0
        assert not (resolver.managed_root / ".staging" / created.id).exists()
        assert resolver.resolve_g8() is None
        await manager.stop()
    asyncio.run(scenario())


def test_restart_requeues_and_resumes_only_with_matching_etag(tmp_path: Path) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        release = asyncio.Event()
        def slow(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                stream=PausedStream(content[:32], content[32:], release),
                headers={"ETag": '"fixture-v1"', "Content-Length": str(len(content))},
                request=request,
            )
        store = Store(tmp_path / "data")
        store.initialize()
        first, _resolver = runtime_manager(tmp_path, store, manifest, httpx.MockTransport(slow))
        await first.start()
        created = first.install()
        partial = tmp_path / "downloads/blender-4.5.9-linux-x64.tar.xz.partial"
        for _ in range(200):
            if partial.exists() and partial.stat().st_size == 32:
                break
            await asyncio.sleep(0.01)
        assert partial.stat().st_size == 32
        await first.stop()

        restarted_store = Store(tmp_path / "data")
        restarted_store.initialize()
        assert restarted_store.get_blender_runtime_operation(created.id).state == (
            BlenderRuntimeOperationState.QUEUED
        )
        ranges: list[str] = []
        def resumed(request: httpx.Request) -> httpx.Response:
            range_value = request.headers.get("range", "")
            ranges.append(range_value)
            start = int(range_value.removeprefix("bytes=").removesuffix("-"))
            return httpx.Response(
                206,
                content=content[start:],
                headers={
                    "ETag": '"fixture-v1"',
                    "Content-Length": str(len(content) - start),
                    "Content-Range": f"bytes {start}-{len(content) - 1}/{len(content)}",
                },
                request=request,
            )
        second, resolver = runtime_manager(
            tmp_path, restarted_store, manifest, httpx.MockTransport(resumed)
        )
        await second.start()
        assert second.install().id == created.id
        finished = await wait_terminal(restarted_store, created.id)
        assert finished.state == BlenderRuntimeOperationState.READY
        assert ranges == ["bytes=32-"]
        assert resolver.resolve_g8() is not None
        await second.stop()
    asyncio.run(scenario())


def test_restart_discards_partial_when_server_rejects_its_identity(tmp_path: Path) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        partial = tmp_path / "downloads/blender-4.5.9-linux-x64.tar.xz.partial"
        partial.parent.mkdir(parents=True)
        partial.write_bytes(content[:32])
        partial.with_suffix(partial.suffix.removesuffix(".partial") + ".partial.json").write_text(
            json.dumps({"etag": '"old-identity"'}), encoding="utf-8"
        )
        queued = store.create_blender_runtime_operation(
            RUNTIME_ID,
            "4.5.9",
            BlenderRuntimeOperationAction.INSTALL,
            bytes_total=len(content),
        )
        def changed(request: httpx.Request) -> httpx.Response:
            assert request.headers["range"] == "bytes=32-"
            return httpx.Response(
                200,
                content=content,
                headers={"ETag": '"new-identity"', "Content-Length": str(len(content))},
                request=request,
            )
        manager, resolver = runtime_manager(
            tmp_path, store, manifest, httpx.MockTransport(changed)
        )
        await manager.start()
        finished = await wait_terminal(store, queued.id)
        assert finished.state == BlenderRuntimeOperationState.FAILED
        assert finished.error_code == "blender_runtime_resume_rejected"
        assert not partial.exists()
        assert resolver.resolve_g8() is None
        await manager.stop()
    asyncio.run(scenario())


def test_hash_mismatch_never_registers_or_leaves_destination(tmp_path: Path) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        altered = content[:-1] + bytes([content[-1] ^ 1])
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(altered))
        await manager.start()
        created = manager.install()
        finished = await wait_terminal(store, created.id)
        assert finished.state == BlenderRuntimeOperationState.FAILED
        assert finished.error_code == "blender_runtime_install_failed"
        assert resolver.resolve_g8() is None
        assert not (resolver.managed_root / RUNTIME_ID).exists()
        assert not (tmp_path / "downloads/blender-4.5.9-linux-x64.tar.xz").exists()
        await manager.stop()
    asyncio.run(scenario())


def test_verified_archive_still_requires_extraction_headroom(tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        free_values = iter((10_000_000_000, 0))
        monkeypatch.setattr(
            "mediaforge.blender_manager.shutil.disk_usage",
            lambda _path: SimpleNamespace(free=next(free_values)),
        )
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))
        await manager.start()
        created = manager.install()
        finished = await wait_terminal(store, created.id)
        assert finished.state == BlenderRuntimeOperationState.FAILED
        assert finished.error_code == "insufficient_disk"
        assert resolver.resolve_g8() is None
        assert not (resolver.managed_root / RUNTIME_ID).exists()
        await manager.stop()
    asyncio.run(scenario())


def test_restart_recovers_destination_committed_before_registry_update(tmp_path: Path) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        first, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))
        await first.start()
        installed = first.install()
        assert (await wait_terminal(store, installed.id)).state == BlenderRuntimeOperationState.READY
        await first.stop()

        resolver.registry_path.unlink()
        queued = store.create_blender_runtime_operation(
            RUNTIME_ID,
            "4.5.9",
            BlenderRuntimeOperationAction.INSTALL,
            bytes_total=len(content),
        )
        restarted_store = Store(tmp_path / "data")
        restarted_store.initialize()
        second, recovered_resolver = runtime_manager(
            tmp_path, restarted_store, manifest, response_transport(content)
        )
        await second.start()
        recovered = await wait_terminal(restarted_store, queued.id)
        assert recovered.state == BlenderRuntimeOperationState.READY
        assert recovered.result is not None and recovered.result["recovered"] is True
        assert recovered_resolver.resolve_g8() is not None
        await second.stop()
    asyncio.run(scenario())


def test_private_workspace_install_uses_only_the_trusted_catalog(tmp_path: Path) -> None:
    content, manifest = archive_fixture(tmp_path)
    settings = Settings(
        data_dir=tmp_path / "data",
        blender_legacy_runtime_root=tmp_path / "missing-legacy",
        blender_managed_runtime_root=tmp_path / "managed",
        blender_runtime_registry=tmp_path / "data/runtime-state/blender-runtimes.json",
        blender_download_root=tmp_path / "downloads",
    )
    app = create_app(
        settings,
        blender_download_transport=response_transport(content),
        blender_manifest_path=manifest,
    )
    with TestClient(app) as client:
        initial = client.get("/workspace-api/blender/runtime").json()
        assert initial["state"] == "missing"
        assert initial["management_available"] is True
        assert initial["catalog"]["license"] == "GPL-3.0-or-later"
        rejected = client.post(
            "/workspace-api/blender/runtime/operations",
            json={"action": "install", "url": "https://attacker.invalid/runtime.tar.xz"},
        )
        assert rejected.status_code == 422
        created = client.post(
            "/workspace-api/blender/runtime/operations", json={"action": "install"}
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
        assert status["state"] == "ready"
        serialized = json.dumps(status)
        assert str(tmp_path) not in serialized and "path" not in serialized


def test_update_installs_side_by_side_then_switches_without_changing_g8(tmp_path: Path) -> None:
    async def scenario() -> None:
        base, manifest = archive_fixture(tmp_path)
        recommended = archive_content("4.5.13")
        catalog = catalog_fixture(tmp_path, base, recommended)
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(
            tmp_path, store, manifest,
            catalog_transport({"4.5.9": base, "4.5.13": recommended}),
            catalog=catalog,
        )
        await manager.start()
        installed = await wait_terminal(store, manager.install().id)
        assert installed.state == BlenderRuntimeOperationState.READY
        updated = await wait_terminal(store, manager.update().id)
        assert updated.state == BlenderRuntimeOperationState.READY
        assert resolver.resolve_active().runtime_id == "blender-4.5.13-linux-x64"
        assert resolver.resolve_g8().runtime_id == "blender-4.5.9-linux-x64"
        assert (resolver.managed_root / "blender-4.5.9-linux-x64/install/blender").is_file()
        assert (resolver.managed_root / "blender-4.5.13-linux-x64/install/blender").is_file()
        switched = await wait_terminal(
            store, manager.switch("blender-4.5.9-linux-x64").id
        )
        assert switched.state == BlenderRuntimeOperationState.READY
        assert resolver.resolve_active().runtime_id == "blender-4.5.9-linux-x64"
        await manager.stop()
    asyncio.run(scenario())


def test_failed_update_probe_preserves_previous_active_runtime(tmp_path: Path) -> None:
    async def scenario() -> None:
        base, manifest = archive_fixture(tmp_path)
        bad_recommended = archive_content("4.5.13", reported_version="4.5.12")
        catalog = catalog_fixture(tmp_path, base, bad_recommended)
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(
            tmp_path, store, manifest,
            catalog_transport({"4.5.9": base, "4.5.13": bad_recommended}),
            catalog=catalog,
        )
        await manager.start()
        assert (await wait_terminal(store, manager.install().id)).state == BlenderRuntimeOperationState.READY
        failed = await wait_terminal(store, manager.update().id)
        assert failed.state == BlenderRuntimeOperationState.FAILED
        assert resolver.resolve_active().runtime_id == "blender-4.5.9-linux-x64"
        assert resolver.resolve_g8().runtime_id == "blender-4.5.9-linux-x64"
        assert not (resolver.managed_root / "blender-4.5.13-linux-x64").exists()
        await manager.stop()
    asyncio.run(scenario())


def test_repair_replaces_damaged_managed_runtime_and_keeps_active_id(tmp_path: Path) -> None:
    async def scenario() -> None:
        base, manifest = archive_fixture(tmp_path)
        recommended = archive_content("4.5.13")
        catalog = catalog_fixture(tmp_path, base, recommended)
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(
            tmp_path, store, manifest,
            catalog_transport({"4.5.9": base, "4.5.13": recommended}),
            catalog=catalog,
        )
        await manager.start()
        assert (await wait_terminal(store, manager.install().id)).state == BlenderRuntimeOperationState.READY
        assert (await wait_terminal(store, manager.update().id)).state == BlenderRuntimeOperationState.READY
        executable = resolver.managed_root / "blender-4.5.13-linux-x64/install/blender"
        executable.unlink()
        assert next(row for row in resolver.status()["runtimes"] if row["runtime_id"].endswith("4.5.13-linux-x64"))["state"] == "damaged"
        repaired = await wait_terminal(
            store, manager.repair("blender-4.5.13-linux-x64").id
        )
        assert repaired.state == BlenderRuntimeOperationState.READY
        assert executable.is_file()
        assert resolver.resolve_active().runtime_id == "blender-4.5.13-linux-x64"
        assert not any((resolver.managed_root / ".staging").glob("previous-*"))
        await manager.stop()
    asyncio.run(scenario())


def test_repair_registry_failure_rolls_back_the_original_directory(
    tmp_path: Path, monkeypatch
) -> None:
    async def scenario() -> None:
        base, manifest = archive_fixture(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(
            tmp_path, store, manifest, response_transport(base)
        )
        await manager.start()
        assert (await wait_terminal(store, manager.install().id)).state == BlenderRuntimeOperationState.READY
        destination = resolver.managed_root / RUNTIME_ID
        marker = destination / "preserve-on-rollback.txt"
        marker.write_text("old directory", encoding="utf-8")
        (destination / "install/blender").unlink()

        def reject_registration(**_kwargs):
            raise RuntimeError("injected registry failure")

        monkeypatch.setattr(resolver, "register_managed", reject_registration)
        failed = await wait_terminal(store, manager.repair(RUNTIME_ID).id)
        assert failed.state == BlenderRuntimeOperationState.FAILED
        assert marker.read_text(encoding="utf-8") == "old directory"
        assert not any((resolver.managed_root / ".staging").glob("previous-*"))
        await manager.stop()
    asyncio.run(scenario())


def test_update_repair_and_switch_reject_untrusted_runtime_identity(tmp_path: Path) -> None:
    content, manifest = archive_fixture(tmp_path)
    settings = Settings(
        data_dir=tmp_path / "data",
        blender_legacy_runtime_root=tmp_path / "missing-legacy",
        blender_managed_runtime_root=tmp_path / "managed",
        blender_runtime_registry=tmp_path / "data/runtime-state/blender-runtimes.json",
        blender_download_root=tmp_path / "downloads",
    )
    app = create_app(
        settings,
        blender_download_transport=response_transport(content),
        blender_manifest_path=manifest,
    )
    with TestClient(app) as client:
        for action in ("repair", "switch"):
            response = client.post(
                "/workspace-api/blender/runtime/operations",
                json={"action": action, "runtime_id": "attacker-runtime"},
            )
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "blender_runtime_not_found"
        response = client.post(
            "/workspace-api/blender/runtime/operations",
            json={"action": "update", "url": "https://attacker.invalid/blender.tar.xz"},
        )
        assert response.status_code == 422


def test_invalid_catalog_disables_management_without_hiding_runtime_status(tmp_path: Path) -> None:
    content, manifest = archive_fixture(tmp_path)
    target = tmp_path / "catalog-target.json"
    target.write_text("{}", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.symlink_to(target)
    settings = Settings(
        data_dir=tmp_path / "data",
        blender_legacy_runtime_root=tmp_path / "missing-legacy",
        blender_managed_runtime_root=tmp_path / "managed",
        blender_runtime_registry=tmp_path / "data/runtime-state/blender-runtimes.json",
        blender_download_root=tmp_path / "downloads",
    )
    app = create_app(
        settings,
        blender_download_transport=response_transport(content),
        blender_manifest_path=manifest,
        blender_catalog_path=catalog,
    )
    with TestClient(app) as client:
        response = client.get("/workspace-api/blender/runtime")
        assert response.status_code == 200
        assert response.json()["management_available"] is False
        assert response.json()["management_reason"] == "blender_runtime_catalog_invalid"
