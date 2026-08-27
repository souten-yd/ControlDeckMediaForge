from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from mediaforge.app import create_app
from mediaforge.config import Settings
from mediaforge.host.client import ControlDeckHostClient
from mediaforge.model_manager import ModelOperationManager
from mediaforge.models import (
    ModelOperation,
    ModelOperationAction,
    ModelOperationError,
    ModelOperationState,
    ModelOwnership,
    ModelRegistry,
)
from mediaforge.store import Store
from test_host_execution import control_deck_stub


REVISION = "d" * 40
WEIGHT = b"test-model-weight"
WEIGHT_DIGEST = hashlib.sha256(WEIGHT).hexdigest()
CONFIG = b'{"model_type":"test"}'


def manifests(
    tmp_path: Path,
    *,
    digest: str = WEIGHT_DIGEST,
    gated: bool = False,
    approx_download_bytes: int | None = None,
) -> tuple[Path, Path]:
    runtime = tmp_path / "models.json"
    runtime.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [{
            "model_id": "owner/model", "family": "test", "version": "1", "revision": REVISION,
            "weights_hash": "sha256:" + "e" * 64, "license": "Apache-2.0", "runtime_adapter": "test",
            "capabilities": ["image.text_to_image"], "hardware_backends": ["rocm"],
            "state": "available", "policy_rank": {"auto": 1},
            "measurements": {
                "resident_vram_bytes": 1, "execution_peak_vram_bytes": 2,
                "cold_load_peak_vram_bytes": 3, "headroom_vram_bytes": 1,
                "measured_runtime_sec": 1,
            },
            "required_files": ["config.json"],
            "weights": [{
                "path": "model.safetensors", "size_bytes": len(WEIGHT), "sha256": digest,
            }],
        }],
    }), encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [{
            "model_id": "owner/model", "display_name": "Example Model", "domains": ["general"],
            "media_types": ["image"],
            "description": "Test fixture", "approx_download_bytes": (
                approx_download_bytes if approx_download_bytes is not None else len(CONFIG) + len(WEIGHT)
            ),
            "source": {"kind": "huggingface", "repo_id": "owner/model", "revision": REVISION},
            "ownership": "managed", "supports_lora": False, "max_references": 0,
            "recommended_profiles": [], "gated": gated, "license_notice": "Apache-2.0",
        }],
    }), encoding="utf-8")
    return runtime, catalog


def transport(*, weight: bytes = WEIGHT) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        content = CONFIG if request.url.path.endswith("/config.json") else weight
        start = int(request.headers.get("range", "bytes=0-").removeprefix("bytes=").removesuffix("-"))
        status = 206 if "range" in request.headers else 200
        return httpx.Response(status, content=content[start:], request=request)

    return httpx.MockTransport(handler)


def manager(
    tmp_path: Path,
    store: Store,
    runtime: Path,
    catalog: Path,
    *,
    mock: httpx.AsyncBaseTransport | None = None,
    model_in_use=None,
) -> ModelOperationManager:
    return ModelOperationManager(
        store,
        model_manifest=runtime,
        catalog_manifest=catalog,
        model_store_root=tmp_path / "managed",
        hf_home=tmp_path / "external",
        model_in_use=model_in_use,
        download_origin="https://models.invalid",
        transport=mock or transport(),
    )


async def wait_terminal(store: Store, operation_id: str) -> object:
    for _ in range(500):
        operation = store.get_model_operation(operation_id)
        if operation.state in {
            ModelOperationState.READY,
            ModelOperationState.FAILED,
            ModelOperationState.CANCELED,
        }:
            return operation
        await asyncio.sleep(0.01)
    raise AssertionError("model operation did not finish")


def test_successful_install_is_atomic_and_registry_visible(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        service = manager(tmp_path, store, runtime, catalog)
        await service.start()
        operation = service.install("owner/model")
        finished = await wait_terminal(store, operation.id)
        assert finished.state == ModelOperationState.READY
        assert not (tmp_path / "managed/.downloads" / operation.id).exists()
        detected = ModelRegistry.load(
            runtime, catalog_manifest=catalog, hf_home=tmp_path / "external",
            model_store_root=tmp_path / "managed",
        ).all()[0]
        assert (detected.installed, detected.healthy, detected.ownership, detected.removable) == (
            True, True, ModelOwnership.MANAGED, True,
        )
        await service.stop()

    asyncio.run(scenario())


def test_composite_bundle_downloads_weight_from_its_pinned_auxiliary_source(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        value = json.loads(runtime.read_text(encoding="utf-8"))
        value["models"][0]["weights"][0]["source"] = {
            "kind": "huggingface",
            "repo_id": "auxiliary/weights",
            "revision": "a" * 40,
        }
        runtime.write_text(json.dumps(value), encoding="utf-8")
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(request.url.path)
            content = CONFIG if request.url.path.endswith("/config.json") else WEIGHT
            return httpx.Response(200, content=content, request=request)

        store = Store(tmp_path / "data")
        store.initialize()
        service = manager(tmp_path, store, runtime, catalog, mock=httpx.MockTransport(handler))
        await service.start()
        operation = service.install("owner/model")
        finished = await wait_terminal(store, operation.id)
        assert finished.state == ModelOperationState.READY
        assert any(
            path == f"/auxiliary/weights/resolve/{'a' * 40}/model.safetensors"
            for path in requested
        )
        await service.stop()

    asyncio.run(scenario())


def test_gated_install_requires_acceptance_bound_to_exact_catalog_entry(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path, gated=True)
        store = Store(tmp_path / "data")
        store.initialize()
        service = manager(tmp_path, store, runtime, catalog)
        await service.start()
        item = service.catalog()["items"][0]
        acceptance = item["license_acceptance_id"]
        assert isinstance(acceptance, str) and acceptance.startswith("sha256:")
        with pytest.raises(ModelOperationError, match="exact catalog license") as missing:
            service.install("owner/model")
        assert missing.value.code == "model_gated"
        with pytest.raises(ModelOperationError) as stale:
            service.install("owner/model", license_acceptance="sha256:" + "0" * 64)
        assert stale.value.code == "model_gated"
        operation = service.install("owner/model", license_acceptance=acceptance)
        finished = await wait_terminal(store, operation.id)
        assert finished.state == ModelOperationState.READY
        await service.stop()

    asyncio.run(scenario())


def test_managed_catalog_preserves_lora_identity_for_the_create_picker(tmp_path: Path):
    runtime, catalog = manifests(tmp_path)
    value = json.loads(runtime.read_text(encoding="utf-8"))
    model = value["models"][0]
    model["runtime_adapter"] = "lora.diffusers"
    model["capabilities"] = ["image.lora"]
    model["runtime_options"] = {
        "base_model": "SDXL 1.0", "trigger_words": ["detail style"],
    }
    runtime.write_text(json.dumps(value), encoding="utf-8")
    store = Store(tmp_path / "data")
    store.initialize()

    item = manager(tmp_path, store, runtime, catalog).catalog()["items"][0]

    assert item["kind"] == "lora"
    assert item["base_model"] == "SDXL 1.0"
    assert item["trigger_words"] == ["detail style"]


def test_managed_download_at_or_above_32gb_fails_before_operation(tmp_path: Path):
    runtime, catalog = manifests(tmp_path, approx_download_bytes=32_000_000_000)
    store = Store(tmp_path / "data")
    store.initialize()
    service = manager(tmp_path, store, runtime, catalog)

    with pytest.raises(ModelOperationError) as rejected:
        service.install("owner/model")
    assert rejected.value.code == "model_too_large"
    assert store.list_model_operations() == []


def test_bad_hash_never_becomes_installed_and_cleans_partial_files(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        service = manager(tmp_path, store, runtime, catalog, mock=transport(weight=b"wrong-model-data"))
        await service.start()
        operation = service.install("owner/model")
        finished = await wait_terminal(store, operation.id)
        assert (finished.state, finished.error_code) == (
            ModelOperationState.FAILED, "model_verify_failed",
        )
        assert not (tmp_path / "managed/hub/models--owner--model").exists()
        assert not (tmp_path / "managed/.downloads" / operation.id).exists()
        await service.stop()

    asyncio.run(scenario())


class PausedStream(httpx.AsyncByteStream):
    def __init__(self, first: bytes, rest: bytes, released: asyncio.Event):
        self.first = first
        self.rest = rest
        self.released = released

    async def __aiter__(self):
        yield self.first
        await self.released.wait()
        if self.rest:
            yield self.rest


class TimedStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self):
        split = max(1, len(self.content) // 2)
        yield self.content[:split]
        await asyncio.sleep(0.05)
        yield self.content[split:]


class FailingStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self):
        yield self.content[:2]
        raise httpx.RemoteProtocolError("connection interrupted")


def test_cancel_cleans_contained_partial_download(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        released = asyncio.Event()

        def handler(request: httpx.Request) -> httpx.Response:
            content = CONFIG if request.url.path.endswith("/config.json") else WEIGHT
            return httpx.Response(
                200, stream=PausedStream(content[:2], content[2:], released), request=request
            )

        service = manager(tmp_path, store, runtime, catalog, mock=httpx.MockTransport(handler))
        await service.start()
        operation = service.install("owner/model")
        partial_root = tmp_path / "managed/.downloads" / operation.id
        for _ in range(200):
            if any(partial_root.rglob("*")) if partial_root.exists() else False:
                break
            await asyncio.sleep(0.01)
        service.cancel(operation.id)
        released.set()
        finished = await wait_terminal(store, operation.id)
        assert finished.state == ModelOperationState.CANCELED
        assert not partial_root.exists()
        assert not (tmp_path / "managed/hub/models--owner--model").exists()
        await service.stop()

    asyncio.run(scenario())


def test_restart_preserves_operation_and_resumes_range_download(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        released = asyncio.Event()

        def slow_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/config.json"):
                return httpx.Response(200, content=CONFIG, request=request)
            return httpx.Response(
                200, stream=PausedStream(WEIGHT[:2], WEIGHT[2:], released), request=request
            )

        first = manager(tmp_path, store, runtime, catalog, mock=httpx.MockTransport(slow_handler))
        await first.start()
        operation = first.install("owner/model")
        partial = tmp_path / "managed/.downloads" / operation.id / "files/model.safetensors"
        for _ in range(200):
            if partial.exists() and partial.stat().st_size == 2:
                break
            await asyncio.sleep(0.01)
        assert partial.stat().st_size == 2
        await first.stop()

        restarted_store = Store(tmp_path / "data")
        restarted_store.initialize()
        assert restarted_store.get_model_operation(operation.id).state == ModelOperationState.QUEUED
        seen_ranges: list[str] = []

        def resumed_handler(request: httpx.Request) -> httpx.Response:
            content = CONFIG if request.url.path.endswith("/config.json") else WEIGHT
            range_value = request.headers.get("range", "")
            if range_value:
                seen_ranges.append(range_value)
            start = int(range_value.removeprefix("bytes=").removesuffix("-")) if range_value else 0
            if start == len(content):
                return httpx.Response(
                    416, headers={"Content-Range": f"bytes */{len(content)}"}, request=request
                )
            return httpx.Response(206 if range_value else 200, content=content[start:], request=request)

        second = manager(
            tmp_path, restarted_store, runtime, catalog, mock=httpx.MockTransport(resumed_handler)
        )
        await second.start()
        assert second.install("owner/model").id == operation.id
        finished = await wait_terminal(restarted_store, operation.id)
        assert finished.state == ModelOperationState.READY
        assert f"bytes={len(CONFIG)}-" in seen_ranges
        assert "bytes=2-" in seen_ranges
        await second.stop()

    asyncio.run(scenario())


def test_external_remove_and_in_use_managed_remove_are_rejected(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        external = tmp_path / "external/hub/models--owner--model"
        blob = external / "blobs" / WEIGHT_DIGEST
        blob.parent.mkdir(parents=True)
        blob.write_bytes(WEIGHT)
        config_blob = external / "blobs" / hashlib.sha256(CONFIG).hexdigest()
        config_blob.write_bytes(CONFIG)
        snapshot = external / "snapshots" / REVISION
        snapshot.mkdir(parents=True)
        (snapshot / "config.json").symlink_to(config_blob)
        (snapshot / "model.safetensors").symlink_to(blob)
        store = Store(tmp_path / "data")
        store.initialize()
        external_service = manager(tmp_path, store, runtime, catalog)
        await external_service.start()
        with pytest.raises(ModelOperationError, match="external model") as external_error:
            external_service.remove("owner/model")
        assert external_error.value.code == "external_model_owned"
        await external_service.stop()

        # Remove the external fixture, install a managed copy, then hold it in use.
        for link in snapshot.iterdir():
            link.unlink()
        snapshot.rmdir()
        (external / "snapshots").rmdir()
        config_blob.unlink()
        blob.unlink()
        (external / "blobs").rmdir()
        external.rmdir()
        (tmp_path / "external/hub").rmdir()
        (tmp_path / "external").rmdir()
        install_service = manager(tmp_path, store, runtime, catalog)
        await install_service.start()
        installed = install_service.install("owner/model")
        assert (await wait_terminal(store, installed.id)).state == ModelOperationState.READY
        await install_service.stop()
        held = manager(tmp_path, store, runtime, catalog, model_in_use=lambda _model_id: True)
        await held.start()
        with pytest.raises(ModelOperationError, match="running job") as in_use_error:
            held.remove("owner/model")
        assert in_use_error.value.code == "model_in_use"
        await held.stop()

    asyncio.run(scenario())


def test_uninstalled_external_candidate_cannot_start_managed_download(tmp_path: Path):
    runtime, catalog = manifests(tmp_path)
    value = json.loads(catalog.read_text(encoding="utf-8"))
    value["models"][0]["ownership"] = "external"
    catalog.write_text(json.dumps(value), encoding="utf-8")
    store = Store(tmp_path / "data")
    store.initialize()
    service = manager(tmp_path, store, runtime, catalog)

    with pytest.raises(ModelOperationError, match="runtime owner") as error:
        service.install("owner/model")

    assert error.value.code == "external_model_owned"
    assert store.list_model_operations() == []


def test_managed_hub_symlink_escape_fails_without_writing_outside(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        managed = tmp_path / "managed"
        outside = tmp_path / "outside"
        managed.mkdir()
        outside.mkdir()
        (managed / "hub").symlink_to(outside, target_is_directory=True)
        store = Store(tmp_path / "data")
        store.initialize()
        service = manager(tmp_path, store, runtime, catalog)
        await service.start()
        operation = service.install("owner/model")
        finished = await wait_terminal(store, operation.id)
        assert (finished.state, finished.error_code) == (
            ModelOperationState.FAILED, "model_verify_failed",
        )
        assert list(outside.iterdir()) == []
        await service.stop()

    asyncio.run(scenario())


def test_workspace_catalog_install_watch_remove_and_capability_rescan(tmp_path: Path):
    runtime, catalog = manifests(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        content = CONFIG if request.url.path.endswith("/config.json") else WEIGHT
        return httpx.Response(200, stream=TimedStream(content), request=request)

    host_app, _state = control_deck_stub()
    bridge = ControlDeckHostClient(
        "https://control-deck.test", transport=httpx.ASGITransport(app=host_app)
    )
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            control_deck_url="https://control-deck.test",
            model_manifest=runtime,
            model_catalog_manifest=catalog,
            model_store_root=tmp_path / "managed",
            hf_home=tmp_path / "external",
        ),
        host_client=bridge,
        model_download_origin="https://models.invalid",
        model_download_transport=httpx.MockTransport(handler),
    )
    headers = {
        "Authorization": "Bearer valid-user",
        "X-Control-Deck-Addon-ID": "media-forge",
    }

    def call(socket, request_id: str, method: str, params: dict | None = None) -> dict:
        socket.send_json({"id": request_id, "method": method, "params": params or {}})
        while True:
            answer = socket.receive_json()
            if answer.get("id") == request_id:
                return answer

    with TestClient(app) as client, client.websocket_connect("/ws", headers=headers) as socket:
        catalog_result = call(socket, "catalog", "models.catalog")["result"]
        item = catalog_result["items"][0]
        assert (item["installed"], item["ownership"], item["removable"]) == (False, "managed", False)
        assert item["media_types"] == ["image"]
        assert (item["reclaimable_bytes"], item["profile_reference_count"]) == (0, 0)
        assert catalog_result["management_available"] is True
        assert "local_path" not in item and str(tmp_path) not in json.dumps(catalog_result)
        rejected = call(
            socket, "unknown", "models.install", {"model_id": "owner/not-in-catalog"}
        )
        assert (rejected["ok"], rejected["error"]["code"]) == (False, "model_not_found")
        assert call(socket, "empty-operations", "models.operations.list")["result"]["items"] == []

        created = call(
            socket, "install", "models.install", {"model_id": "owner/model"}
        )["result"]
        operation_id = created["id"]
        watched = call(
            socket, "watch", "models.operations.watch", {"operation_ids": [operation_id]}
        )
        assert watched["result"]["watching"] == [operation_id]
        while True:
            event = socket.receive_json()
            if event.get("event") == "model.operation.changed" and event["data"]["state"] == "ready":
                break
        listed = call(socket, "operations", "models.operations.list")["result"]["items"]
        assert listed[0]["state"] == "ready"
        capability = call(socket, "capabilities", "capabilities.get")["result"]
        assert capability["capabilities"]["image.text_to_image"]["state"] == "available"

        removed = call(
            socket, "remove", "models.remove", {"model_id": "owner/model"}
        )["result"]
        remove_id = removed["id"]
        for _ in range(200):
            operations = call(socket, "remove-list", "models.operations.list")["result"]["items"]
            terminal = next(item for item in operations if item["id"] == remove_id)
            if terminal["state"] == "ready":
                break
        assert terminal["state"] == "ready"
        after = call(socket, "after", "models.catalog")["result"]["items"][0]
        assert (after["installed"], after["removable"]) == (False, False)


def test_workspace_model_evaluation_passes_host_identity_and_rejects_extra_inputs(tmp_path: Path):
    runtime, catalog = manifests(tmp_path)
    host_app, _state = control_deck_stub()
    bridge = ControlDeckHostClient(
        "https://control-deck.test", transport=httpx.ASGITransport(app=host_app)
    )

    class FakeEvaluator:
        def __init__(self) -> None:
            self.identities = []

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        def available_model_ids(self) -> list[str]:
            return ["owner/model"]

        def evaluate(self, model_id: str, identity) -> ModelOperation:
            assert model_id == "owner/model"
            self.identities.append(identity)
            return ModelOperation(
                id="modelop_evaluation",
                model_id=model_id,
                action=ModelOperationAction.EVALUATE,
                state=ModelOperationState.QUEUED,
                bytes_total=0,
                bytes_done=0,
                created_at="2026-08-23T00:00:00+00:00",
                updated_at="2026-08-23T00:00:00+00:00",
            )

    evaluator = FakeEvaluator()
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            control_deck_url="https://control-deck.test",
            model_manifest=runtime,
            model_catalog_manifest=catalog,
            model_store_root=tmp_path / "managed",
            hf_home=tmp_path / "external",
        ),
        host_client=bridge,
        native_model_evaluator=evaluator,  # type: ignore[arg-type]
    )
    headers = {
        "Authorization": "Bearer valid-user",
        "X-Control-Deck-Addon-ID": "media-forge",
    }

    def call(socket, request_id: str, method: str, params: dict | None = None) -> dict:
        socket.send_json({"id": request_id, "method": method, "params": params or {}})
        while True:
            answer = socket.receive_json()
            if answer.get("id") == request_id:
                return answer

    with TestClient(app) as client, client.websocket_connect("/ws", headers=headers) as socket:
        result = call(socket, "catalog", "models.catalog")["result"]
        assert result["evaluation"]["available_model_ids"] == ["owner/model"]
        rejected = call(
            socket,
            "reject-extra",
            "models.evaluate",
            {"model_id": "owner/model", "prompt": "untrusted"},
        )
        assert rejected["error"]["code"] == "workspace_request_rejected"
        started = call(socket, "evaluate", "models.evaluate", {"model_id": "owner/model"})

    assert started["result"]["action"] == "evaluate"
    assert len(evaluator.identities) == 1
    assert evaluator.identities[0].subject == "7"
    assert "resources.acquire" in evaluator.identities[0].granted_capabilities


def test_transient_network_failure_retries_from_partial_offset(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        failed_once = False
        ranges: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal failed_once
            if request.url.path.endswith("/config.json"):
                return httpx.Response(200, content=CONFIG, request=request)
            range_value = request.headers.get("range", "")
            if range_value:
                ranges.append(range_value)
            if not failed_once:
                failed_once = True
                return httpx.Response(200, stream=FailingStream(WEIGHT), request=request)
            start = int(range_value.removeprefix("bytes=").removesuffix("-")) if range_value else 0
            return httpx.Response(206 if range_value else 200, content=WEIGHT[start:], request=request)

        service = manager(tmp_path, store, runtime, catalog, mock=httpx.MockTransport(handler))
        await service.start()
        operation = service.install("owner/model")
        finished = await wait_terminal(store, operation.id)
        assert finished.state == ModelOperationState.READY
        assert "bytes=2-" in ranges
        await service.stop()

    asyncio.run(scenario())


def test_installer_download_parallelism_is_one(tmp_path: Path):
    async def scenario() -> None:
        runtime, catalog = manifests(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        active = 0
        maximum = 0

        class TrackingStream(httpx.AsyncByteStream):
            def __init__(self, content: bytes):
                self.content = content

            async def __aiter__(self):
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                try:
                    await asyncio.sleep(0.02)
                    yield self.content
                finally:
                    active -= 1

        def handler(request: httpx.Request) -> httpx.Response:
            content = CONFIG if request.url.path.endswith("/config.json") else WEIGHT
            return httpx.Response(200, stream=TrackingStream(content), request=request)

        service = manager(tmp_path, store, runtime, catalog, mock=httpx.MockTransport(handler))
        await service.start()
        operation = service.install("owner/model")
        assert (await wait_terminal(store, operation.id)).state == ModelOperationState.READY
        assert maximum == 1
        await service.stop()

    asyncio.run(scenario())
