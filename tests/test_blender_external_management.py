from __future__ import annotations

import asyncio
import shutil
import threading

import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationError
from mediaforge.blender_runtime import G8_RUNTIME_ID, G8_MANAGED_RUNTIME_ID


PATH = "/workspace-api/blender/runtime/operations"


def add_alternative(client) -> object:
    manager = client.app.state.blender_runtime_operations
    resolver = manager.resolver
    shutil.copytree(resolver.legacy_root, resolver.managed_root / G8_MANAGED_RUNTIME_ID)
    resolver.register_managed(runtime_id=G8_MANAGED_RUNTIME_ID, version="4.5.9",
        location=G8_MANAGED_RUNTIME_ID, archive_sha256=manager.spec.archive_sha256)
    resolver.activate(G8_MANAGED_RUNTIME_ID)
    return manager


def test_http_external_active_guard_and_unregister_reregister(client) -> None:
    preview = client.post(PATH, json={"action": "unregister_preview", "runtime_id": G8_RUNTIME_ID}).json()
    assert not preview["can_remove"] and preview["blocked_reasons"] == ["active_runtime"]
    assert client.post(PATH, json={"action": "unregister", "runtime_id": G8_RUNTIME_ID,
        "confirmation_fingerprint": preview["confirmation_fingerprint"]}).status_code == 422
    manager = add_alternative(client)
    before = (manager.resolver.legacy_root / "install/blender").read_bytes()
    preview = client.post(PATH, json={"action": "unregister_preview", "runtime_id": G8_RUNTIME_ID}).json()
    assert preview["operation"] == "unregister" and preview["can_remove"]
    response = client.post(PATH, json={"action": "unregister", "runtime_id": G8_RUNTIME_ID,
        "confirmation_fingerprint": preview["confirmation_fingerprint"]})
    assert response.status_code == 200 and response.json()["removed_bytes"] == 0
    assert client.get("/workspace-api/blender/runtime").json()["legacy_registration_disabled"]
    assert client.post(PATH, json={"action": "register_legacy"}).json()["registered"]
    assert not client.get("/workspace-api/blender/runtime").json()["legacy_registration_disabled"]
    assert (manager.resolver.legacy_root / "install/blender").read_bytes() == before


def test_external_confirmation_rechecks_new_project_references(client, monkeypatch) -> None:
    manager = add_alternative(client)
    preview = client.post(PATH, json={"action": "unregister_preview", "runtime_id": G8_RUNTIME_ID}).json()
    monkeypatch.setattr(manager.store, "scene_runtime_reference_count", lambda runtime_id: 1)
    response = client.post(PATH, json={"action": "unregister", "runtime_id": G8_RUNTIME_ID,
        "confirmation_fingerprint": preview["confirmation_fingerprint"]})
    assert response.json()["detail"]["code"] == "blender_runtime_remove_changed"
    blocked = client.post(PATH, json={"action": "unregister_preview", "runtime_id": G8_RUNTIME_ID}).json()
    assert not blocked["can_remove"] and "project_reference" in blocked["blocked_reasons"]
    response = client.post(PATH, json={"action": "unregister", "runtime_id": G8_RUNTIME_ID,
        "confirmation_fingerprint": blocked["confirmation_fingerprint"]})
    assert response.json()["detail"]["code"] == "blender_runtime_in_use"
    assert manager.resolver.resolve_registered(G8_RUNTIME_ID) is not None


@pytest.mark.parametrize("payload", [
    {"action": "register_legacy", "path": "/tmp/arbitrary"},
    {"action": "unregister_preview", "runtime_id": G8_MANAGED_RUNTIME_ID},
    {"action": "unregister", "runtime_id": G8_RUNTIME_ID},
])
def test_external_rejects_arbitrary_path_managed_identity_and_missing_confirmation(client, payload: dict) -> None:
    assert client.post(PATH, json=payload).status_code == 422


def test_external_registry_work_runs_off_loop_and_finishes_after_request_cancel(client, monkeypatch) -> None:
    manager = add_alternative(client)
    entered, release = threading.Event(), threading.Event()
    original = manager.resolver.register_legacy
    worker_threads: list[int] = []

    def delayed(*, explicit: bool = False) -> bool:
        worker_threads.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return original(explicit=explicit)

    monkeypatch.setattr(manager.resolver, "register_legacy", delayed)

    async def scenario() -> None:
        loop_thread = threading.get_ident()
        task = asyncio.create_task(manager.external_registration(register=True))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert worker_threads == [worker_threads[0]] and worker_threads[0] != loop_thread
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not manager._guard.locked()

    asyncio.run(scenario())


def test_external_change_rejects_busy_orchestrator(client) -> None:
    manager = add_alternative(client)

    async def scenario() -> None:
        async with manager._guard:
            with pytest.raises(BlenderRuntimeOperationError) as error:
                await manager.external_registration(register=True)
            assert error.value.code == "blender_runtime_operation_active"

    asyncio.run(scenario())
