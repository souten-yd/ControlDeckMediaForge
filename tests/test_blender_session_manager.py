from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import tarfile

import pytest
from fastapi.testclient import TestClient

from mediaforge.app import create_app
from mediaforge.blender_session_manager import BlenderSessionError, BlenderSessionManager
from mediaforge.blender_session_record import BlenderSessionState
from mediaforge.blender_web import BlenderWebPack, load_web_pack_spec
from mediaforge.config import Settings
from mediaforge.scenes import SceneRevisionInput
from test_blender_web import fixture_manifest
from test_scene_workspace import fake_scene_workspace, upload_scene


OWNER = "user:1"


def ready_web_pack(tmp_path: Path) -> BlenderWebPack:
    manifest, contents = fixture_manifest(tmp_path)
    web = BlenderWebPack(manifest, tmp_path / "web-pack")
    spec = load_web_pack_spec(manifest)
    destination = web.destination(spec)
    install = destination / "install"
    install.mkdir(parents=True)
    for component in spec.components:
        with tarfile.open(fileobj=io.BytesIO(contents[f"/{component.archive_name}"]), mode="r:gz") as archive:
            archive.extractall(tmp_path / component.id, filter="data")
        os.replace(
            tmp_path / component.id / component.top_level_directory,
            install / component.id,
        )
    web.write_stamp(destination, spec)
    assert web.status()["state"] == "ready"
    return web


class FakeController:
    def __init__(self, *, fail_start: bool = False, fail_save: bool = False) -> None:
        self.fail_start = fail_start
        self.fail_save = fail_save
        self.units: dict[str, tuple[socket.socket, Path, dict]] = {}
        self.starts = 0
        self.stops = 0

    async def start(
        self, unit_id: str, _runner: Path, spec_path: Path, writable: tuple[Path, Path, Path]
    ) -> None:
        self.starts += 1
        assert spec_path.parent == writable[0]
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        assert Path(spec["scene_path"]).parent == writable[1]
        assert Path(spec["rfb_socket"]).parent == writable[2]
        if self.fail_start:
            raise BlenderSessionError("blender_session_runner_failed", "fixture start failed")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(spec["rfb_socket"])
        Path(spec["rfb_socket"]).chmod(0o600)
        (spec_path.parent / "ready.json").write_text(json.dumps({
            "schema_version": 1,
            "session_id": spec["session_id"],
            "blender_version": spec["runtime_version"],
            "background": False,
            "autoexec_disabled": True,
            "gpu_backend": "VULKAN",
            "gpu_renderer": "llvmpipe fixture",
        }), encoding="utf-8")
        self.units[unit_id] = (listener, spec_path.parent, spec)

    async def stop(self, unit_id: str) -> None:
        self.stops += 1
        value = self.units.pop(unit_id, None)
        if value is not None:
            value[0].close()
            Path(value[2]["rfb_socket"]).unlink(missing_ok=True)

    async def active(self, unit_id: str) -> bool:
        value = self.units.get(unit_id)
        if value is None:
            return False
        _listener, root, spec = value
        command = root / "command.json"
        if command.is_file():
            payload = json.loads(command.read_text(encoding="utf-8"))
            command.unlink()
            scene = Path(spec["scene_path"])
            scene.write_bytes(scene.read_bytes() + b"-saved-by-gui")
            response = {
                "schema_version": 1,
                "request_id": payload["request_id"],
                "ok": not self.fail_save,
                "result": None if self.fail_save else {
                    "size_bytes": scene.stat().st_size,
                    "sha256": hashlib.sha256(scene.read_bytes()).hexdigest(),
                },
                "error": {"code": "fixture_save_failed"} if self.fail_save else None,
            }
            (root / f"response-{payload['request_id']}.json").write_text(
                json.dumps(response), encoding="utf-8"
            )
        return True


async def wait_state(manager: BlenderSessionManager, session_id: str, state: str) -> dict:
    for _ in range(500):
        value = manager.get(OWNER, session_id)
        if value["state"] == state:
            return value
        if value["state"] in {"failed", "interrupted"} and state not in {"failed", "interrupted"}:
            raise AssertionError(value)
        await asyncio.sleep(0.01)
    raise AssertionError(f"session did not reach {state}")


def session_fixture(
    tmp_path: Path,
    *,
    fail_start: bool = False,
    fail_save: bool = False,
    **manager_options,
):
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER" + b"gui-scene" * 100)
    web = ready_web_pack(tmp_path)
    runner = tmp_path / "trusted-runner.py"
    runner.write_text("# fixture", encoding="utf-8")
    bootstrap = tmp_path / "trusted-bootstrap.py"
    bootstrap.write_text("# fixture", encoding="utf-8")
    preferences_bootstrap = tmp_path / "trusted-preferences.py"
    preferences_bootstrap.write_text("# fixture", encoding="utf-8")
    controller = FakeController(fail_start=fail_start, fail_save=fail_save)
    software_vulkan_icd = tmp_path / "lvp_icd.json"
    software_vulkan_icd.write_text(json.dumps({
        "file_format_version": "1.0.1",
        "ICD": {"api_version": "1.4.0", "library_path": "libvulkan_lvp.so"},
    }), encoding="utf-8")
    manager = BlenderSessionManager(
        store,
        workspace,
        resolver,  # type: ignore[arg-type]
        web,
        runner=runner,
        bootstrap=bootstrap,
        preferences_bootstrap=preferences_bootstrap,
        controller=controller,  # type: ignore[arg-type]
        start_timeout_sec=1,
        command_timeout_sec=1,
        socket_root=tmp_path / "s",
        software_vulkan_icd=software_vulkan_icd,
        **manager_options,
    )
    return store, workspace, imported["scene"]["id"], controller, manager


def test_session_save_commits_revision_and_exposes_no_runner_paths(tmp_path: Path) -> None:
    store, workspace, scene_id, controller, manager = session_fixture(tmp_path)

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        ready = await wait_state(manager, created["id"], "ready")
        assert ready["display"] == {"mode": "software", "width": 1280, "height": 720, "depth": 24}
        serialized = json.dumps(ready)
        assert str(tmp_path) not in serialized and "unit_id" not in serialized and "working_id" not in serialized
        with pytest.raises(BlenderSessionError) as busy:
            manager.create(OWNER, scene_id)
        assert busy.value.code == "scene_working_locked" or busy.value.code == "blender_session_busy"
        saving = manager.save_and_stop(OWNER, created["id"])
        assert saving["state"] == "saving"
        stopped = await wait_state(manager, created["id"], "stopped")
        assert stopped["result"]["saved"] is True
        assert stopped["result"]["scene"]["revision"]["sequence"] == 2
        assert controller.units == {}
        assert not (manager.root / created["id"]).exists()
        document, _ = workspace.catalog.get(OWNER, scene_id)
        assert document.revision_count == 2
        assert store.list_active_blender_web_sessions() == []
        await manager.stop()

    asyncio.run(scenario())


def test_discard_releases_working_copy_and_allows_next_session(tmp_path: Path) -> None:
    _store, workspace, scene_id, controller, manager = session_fixture(tmp_path)

    async def scenario() -> None:
        await manager.start()
        first = manager.create(OWNER, scene_id)
        await wait_state(manager, first["id"], "ready")
        manager.discard_and_stop(OWNER, first["id"])
        stopped = await wait_state(manager, first["id"], "stopped")
        assert stopped["result"] == {"saved": False}
        second = manager.create(OWNER, scene_id)
        await wait_state(manager, second["id"], "ready")
        manager.discard_and_stop(OWNER, second["id"])
        await wait_state(manager, second["id"], "stopped")
        document, _ = workspace.catalog.get(OWNER, scene_id)
        assert document.revision_count == 1
        assert controller.starts == 2 and controller.stops == 2
        await manager.stop()

    asyncio.run(scenario())


def test_queued_session_can_be_stopped_before_a_working_copy_exists(tmp_path: Path) -> None:
    store, _workspace, scene_id, controller, manager = session_fixture(tmp_path)

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        stopping = manager.discard_and_stop(OWNER, created["id"])
        assert stopping["state"] == "stopping"
        assert stopping["can_stop"] is False
        stopped = await wait_state(manager, created["id"], "stopped")
        assert stopped["result"] == {"saved": False}
        assert store.list_scene_working_copies(OWNER) == []
        assert controller.units == {}
        await manager.stop()

    asyncio.run(scenario())


def test_start_failure_retains_recovery_and_is_terminal(tmp_path: Path) -> None:
    store, _workspace, scene_id, controller, manager = session_fixture(tmp_path, fail_start=True)

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        failed = await wait_state(manager, created["id"], "failed")
        assert failed["error_code"] == "blender_session_runner_failed"
        records = store.list_scene_working_copies(OWNER)
        assert len(records) == 1 and records[0].state == "recovery"
        assert controller.units == {}
        await manager.stop()

    asyncio.run(scenario())


def test_missing_software_renderer_fails_closed_without_creating_a_session(tmp_path: Path) -> None:
    store, _workspace, scene_id, _controller, manager = session_fixture(tmp_path)
    manager.software_vulkan_icd = tmp_path / "missing-lvp.json"

    with pytest.raises(BlenderSessionError) as unavailable:
        manager.create(OWNER, scene_id)

    assert unavailable.value.code == "blender_software_renderer_unavailable"
    assert store.list_blender_web_sessions(OWNER) == []


def test_service_restart_reattaches_active_unit_then_stops_it(tmp_path: Path) -> None:
    store, workspace, scene_id, controller, first = session_fixture(tmp_path)

    async def scenario() -> None:
        await first.start()
        created = first.create(OWNER, scene_id)
        await wait_state(first, created["id"], "ready")
        await first.stop()
        second = BlenderSessionManager(
            store,
            workspace,
            first.resolver,
            first.web_pack,
            runner=first.runner,
            bootstrap=first.bootstrap,
            preferences_bootstrap=first.preferences_bootstrap,
            controller=controller,  # type: ignore[arg-type]
            start_timeout_sec=1,
            command_timeout_sec=1,
            socket_root=tmp_path / "s",
            software_vulkan_icd=first.software_vulkan_icd,
        )
        await second.start()
        assert second.get(OWNER, created["id"])["state"] == BlenderSessionState.READY
        second.discard_and_stop(OWNER, created["id"])
        await wait_state(second, created["id"], "stopped")
        assert controller.starts == 1 and controller.stops == 1
        await second.stop()

    asyncio.run(scenario())


def test_gateway_is_owner_scoped_single_controller_and_releasable(tmp_path: Path) -> None:
    _store, _workspace, scene_id, _controller, manager = session_fixture(tmp_path)

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        ready = await wait_state(manager, created["id"], "ready")
        assert ready["connection_state"] == "disconnected"
        assert ready["can_connect"] is True
        socket_path = await manager.acquire_gateway(OWNER, created["id"])
        assert socket_path.is_socket()
        connected = manager.get(OWNER, created["id"])
        assert connected["connection_state"] == "connected"
        assert connected["can_connect"] is False
        with pytest.raises(BlenderSessionError) as duplicate:
            await manager.acquire_gateway(OWNER, created["id"])
        assert duplicate.value.code == "blender_session_already_connected"
        with pytest.raises(BlenderSessionError):
            await manager.acquire_gateway("user:2", created["id"])
        await manager.release_gateway(OWNER, created["id"])
        assert manager.get(OWNER, created["id"])["can_connect"] is True
        manager.discard_and_stop(OWNER, created["id"])
        await wait_state(manager, created["id"], "stopped")
        await manager.stop()

    asyncio.run(scenario())


def test_disconnected_timeout_stops_unit_and_retains_recovery(tmp_path: Path) -> None:
    store, _workspace, scene_id, controller, manager = session_fixture(
        tmp_path, monitor_interval_sec=0.01, disconnect_grace_sec=0.03
    )

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        interrupted = await wait_state(manager, created["id"], "interrupted")
        assert interrupted["error_code"] == "blender_session_disconnected_timeout"
        assert interrupted["result"]["recovery"]["state"] == "candidate"
        recovery_id = interrupted["result"]["recovery"]["working_id"]
        assert store.get_scene_working_copy(OWNER, recovery_id).state == "recovery"
        assert controller.units == {}
        await manager.stop()

    asyncio.run(scenario())


def test_connected_activity_delays_idle_timeout_then_session_is_retained(tmp_path: Path) -> None:
    _store, _workspace, scene_id, controller, manager = session_fixture(
        tmp_path,
        monitor_interval_sec=0.01,
        disconnect_grace_sec=1,
        idle_timeout_sec=0.04,
    )

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        await wait_state(manager, created["id"], "ready")
        await manager.acquire_gateway(OWNER, created["id"])
        for _ in range(4):
            await asyncio.sleep(0.02)
            manager.note_gateway_activity(OWNER, created["id"])
            assert manager.get(OWNER, created["id"])["state"] == "ready"
        interrupted = await wait_state(manager, created["id"], "interrupted")
        assert interrupted["error_code"] == "blender_session_idle_timeout"
        assert interrupted["result"]["recovery"]["state"] == "candidate"
        assert controller.units == {}
        await manager.stop()

    asyncio.run(scenario())


def test_host_disable_interrupts_and_recovery_can_become_a_revision(tmp_path: Path) -> None:
    store, workspace, scene_id, controller, manager = session_fixture(tmp_path)

    async def scenario() -> None:
        await manager.start()
        first = manager.create(OWNER, scene_id)
        await wait_state(manager, first["id"], "ready")
        stopping = manager.interrupt(
            OWNER, first["id"], code="blender_session_host_disabled"
        )
        assert stopping["state"] == "stopping"
        interrupted = await wait_state(manager, first["id"], "interrupted")
        recovery_id = interrupted["result"]["recovery"]["working_id"]
        assert store.get_scene_working_copy(OWNER, recovery_id).state == "recovery"

        recovered = manager.create(
            OWNER, scene_id, recovery_working_id=recovery_id
        )
        await wait_state(manager, recovered["id"], "ready")
        manager.save_and_stop(OWNER, recovered["id"])
        saved = await wait_state(manager, recovered["id"], "stopped")
        assert saved["result"]["scene"]["revision"]["sequence"] == 2
        assert store.get_scene_working_copy(OWNER, recovery_id).state == "released"
        assert not (workspace.working_root / recovery_id).exists()
        assert controller.units == {}
        await manager.stop()

    asyncio.run(scenario())


def test_host_revocation_uses_the_same_fail_closed_recovery_path(tmp_path: Path) -> None:
    _store, _workspace, scene_id, controller, manager = session_fixture(tmp_path)

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        await wait_state(manager, created["id"], "ready")
        manager.interrupt(OWNER, created["id"], code="blender_session_host_revoked")
        repeated = manager.interrupt(
            OWNER, created["id"], code="blender_session_host_revoked"
        )
        assert repeated["state"] == "stopping"
        interrupted = await wait_state(manager, created["id"], "interrupted")
        assert interrupted["error_code"] == "blender_session_host_revoked"
        assert interrupted["result"]["recovery"]["state"] == "candidate"
        assert controller.units == {}
        assert controller.stops == 1
        await manager.stop()

    asyncio.run(scenario())


def test_crash_and_save_failure_both_retain_unvalidated_bytes(tmp_path: Path) -> None:
    store, _workspace, scene_id, controller, manager = session_fixture(
        tmp_path, fail_save=True, monitor_interval_sec=0.01
    )

    async def scenario() -> None:
        await manager.start()
        first = manager.create(OWNER, scene_id)
        await wait_state(manager, first["id"], "ready")
        unit = next(iter(controller.units))
        await controller.stop(unit)
        crashed = await wait_state(manager, first["id"], "interrupted")
        assert crashed["error_code"] == "blender_session_runner_lost"
        assert crashed["result"]["recovery"]["state"] == "candidate"
        assert not (manager.root / first["id"]).exists()

        second = manager.create(OWNER, scene_id)
        await wait_state(manager, second["id"], "ready")
        manager.save_and_stop(OWNER, second["id"])
        failed = await wait_state(manager, second["id"], "failed")
        assert failed["error_code"] == "blender_session_save_failed"
        assert failed["result"]["recovery"]["state"] == "candidate"
        assert not (manager.root / second["id"]).exists()
        assert len([item for item in store.list_scene_working_copies(OWNER) if item.state == "recovery"]) == 2
        await manager.stop()

    asyncio.run(scenario())


def test_revision_conflict_save_projects_the_existing_recovery_candidate(tmp_path: Path) -> None:
    store, workspace, scene_id, controller, manager = session_fixture(tmp_path)

    async def scenario() -> None:
        await manager.start()
        created = manager.create(OWNER, scene_id)
        await wait_state(manager, created["id"], "ready")
        document, revisions = workspace.catalog.get(OWNER, scene_id)
        current = next(item for item in revisions if item.id == document.current_revision_id)
        workspace.catalog.commit(
            OWNER,
            scene_id,
            current.id,
            SceneRevisionInput(
                source_asset_id=current.source_asset_id,
                preview_asset_id=current.preview_asset_id,
                dependencies=current.dependencies,
                runtime_id=current.runtime_id,
                runtime_version=current.runtime_version,
                validation=current.validation,
            ),
        )

        manager.save_and_stop(OWNER, created["id"])
        failed = await wait_state(manager, created["id"], "failed")
        assert failed["error_code"] == "scene_revision_conflict"
        assert failed["result"]["recovery"]["state"] == "candidate"
        candidate_id = failed["result"]["recovery"]["working_id"]
        assert store.get_scene_working_copy(OWNER, candidate_id).state == "recovery"
        assert controller.units == {}
        await manager.stop()

    asyncio.run(scenario())


def test_private_standalone_session_transport_is_bounded_and_not_public(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        blender_legacy_runtime_root=tmp_path / "missing-blender",
        blender_managed_runtime_root=tmp_path / "managed-blender",
        blender_runtime_registry=tmp_path / "data/runtime-state/blender-runtimes.json",
        blender_download_root=tmp_path / "downloads",
        blender_web_runtime_root=tmp_path / "missing-web-pack",
        blender_web_download_root=tmp_path / "web-downloads",
    )
    app = create_app(settings, blender_session_controller=FakeController())
    with TestClient(app) as client:
        scenes = client.get("/workspace-api/scenes")
        assert scenes.status_code == 200
        assert scenes.json() == {"items": [], "working_copies": []}
        listed = client.get("/workspace-api/blender/sessions")
        assert listed.status_code == 200 and listed.json() == {"items": []}
        rejected = client.post(
            "/workspace-api/blender/sessions",
            json={"action": "start", "scene_id": "scene_" + "0" * 32, "path": "/etc/passwd"},
        )
        assert rejected.status_code == 422
        unavailable = client.post(
            "/workspace-api/blender/sessions",
            json={"action": "start", "scene_id": "scene_" + "0" * 32},
        )
        assert unavailable.status_code == 422
        assert unavailable.json()["detail"]["code"] == "blender_web_runtime_unavailable"
        assert "/workspace-api/blender/sessions" not in client.get("/openapi.json").text


def test_gui_runner_uses_only_trusted_python_files() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "worker_packs/blender/web_session_runner.py"
    ).read_text(encoding="utf-8")
    assert "--python-expr" not in source
    assert '"--python", spec["preferences_path"]' in source
