from __future__ import annotations

import asyncio
import base64
import hashlib
from io import BytesIO
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, ValidationError

from . import __version__
from .config import Settings
from .domain import JobRequest
from .environment import setup_snapshot
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.files import GrantContentTooLarge, read_grant, require_grant_id
from .host.jobs import HostExecution
from .jobs import JobManager
from .models import ModelRegistry, ModelRegistryError
from .host.security import reject_host_paths, require_host_service, require_host_service_headers
from .store import Store


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPOSITORY_ROOT / "schemas"
FRONTEND_DIR = REPOSITORY_ROOT / "frontend"
HealthState = Literal["healthy", "degraded", "unavailable", "setup_required"]
MAX_CONTEXT_IMAGE_BYTES = 64 * 1024 * 1024
MAX_CONTEXT_IMAGE_PIXELS = 100_000_000


def workspace_test_response_delay_sec() -> float:
    if os.environ.get("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS") != "1":
        return 0.0
    try:
        requested = float(os.environ.get("MEDIA_FORGE_TEST_WORKSPACE_DELAY_SEC", "0"))
    except ValueError:
        return 0.0
    return min(max(requested, 0.0), 2.0)


class HealthUpdate(BaseModel):
    status: HealthState


class HostFileRoundtrip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_grant_id: str
    export_grant_id: str
    filename: str


def _unavailable(reason: str, message: str) -> dict[str, Any]:
    return {
        "state": "unavailable",
        "reason_code": reason,
        "message": message,
        "action": {"kind": "open_route", "route": "/x/media-forge/workspace/settings"},
    }


def create_app(
    settings: Settings | None = None,
    *,
    host_client: ControlDeckHostClient | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    store = Store(resolved.data_dir)
    host = host_client or ControlDeckHostClient(
        resolved.control_deck_url,
        timeout_sec=resolved.host_request_timeout_sec,
    )
    manager = JobManager(
        store,
        worker_timeout_sec=resolved.worker_timeout_sec,
        host_client=host,
        lease_renew_sec=resolved.host_lease_renew_sec,
        model_manifest=resolved.model_manifest,
        hf_home=resolved.hf_home,
        image_runtime_python=resolved.image_runtime_python,
    )
    workspace_test_delay_pending = True

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.initialize()
        await manager.start()
        yield
        await manager.stop()
        await host.close()

    app = FastAPI(title="ControlDeck Media Forge", version=__version__, lifespan=lifespan)
    app.state.health_override = None
    app.state.store = store
    app.state.jobs = manager
    app.state.host = host
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    async def authorize_host(request: Request) -> HostIdentity:
        return await require_host_service(request, host)

    def model_catalog() -> dict[str, Any]:
        try:
            models = ModelRegistry.load(resolved.model_manifest, hf_home=resolved.hf_home).all()
        except ModelRegistryError as exc:
            raise HTTPException(status_code=503, detail={"code": "model_registry_invalid"}) from exc
        return {
            "items": [
                {
                    "id": item.model_id,
                    "family": item.family,
                    "version": item.version,
                    "revision": item.revision,
                    "license": item.license,
                    "runtime_adapter": item.runtime_adapter,
                    "capabilities": list(item.capabilities),
                    "state": item.state,
                    "installed": item.installed,
                    "healthy": item.healthy,
                    "measured_vram_bytes": item.measured_vram_bytes,
                    "measured_runtime_sec": item.measured_runtime_sec,
                }
                for item in models
            ]
        }

    async def submit_hosted(
        value: JobRequest,
        identity: HostIdentity,
        *,
        workload_class: str,
    ) -> dict[str, Any]:
        missing = {"jobs.write", "resources.acquire"} - identity.granted_capabilities
        if missing:
            raise HTTPException(status_code=403, detail={"code": "host_capability_not_granted"})
        try:
            attached = await host.create_or_attach_job(identity, title="Media Forge image generation")
        except HostApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
        host_job = attached.get("job")
        if not isinstance(host_job, dict) or not isinstance(host_job.get("id"), str):
            raise HTTPException(status_code=502, detail={"code": "invalid_host_response"})
        execution = HostExecution(
            identity=identity,
            host_job_id=host_job["id"],
            workload_class=workload_class,
            owns_terminal=attached.get("created") is True,
        )
        return manager.submit_hosted(value, execution).model_dump(mode="json")

    async def wait_for_terminal(job_id: str, timeout: float = 25.0) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            job = store.get_job(job_id)
            if job.status.value in {"succeeded", "failed", "canceled"}:
                return job.model_dump(mode="json")
            await asyncio.sleep(0.02)
        raise HTTPException(status_code=504, detail={"code": "job_wait_timeout", "job_id": job_id})

    def submitted_reference(value: dict[str, Any]) -> dict[str, Any]:
        return {"job_id": value["id"], "status": value["status"], "asset_ids": value["asset_ids"]}

    def host_job_input(payload: object) -> JobRequest:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "invalid_execution_envelope"})
        reject_host_paths(payload)
        try:
            return JobRequest.model_validate(payload.get("input", {}))
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_job_request"}) from exc

    @app.get("/health")
    async def health() -> dict[str, Any]:
        environment = setup_snapshot()
        token_state: str | dict[str, Any] = "available"
        status: HealthState = app.state.health_override or (
            environment.get("status", "setup_required") if environment else "setup_required"
        )
        payload: dict[str, Any] = {
            "status": status,
            "contract_version": "2.0",
            "contributions": {
                "navigation:workspace": "available",
                "embedded_view:workspace": "available",
                "command:create-media": token_state,
                "quick_action:create-media": token_state,
                "settings:settings": "available",
                "workflow_executor:media.generate": token_state,
                "agent_tool:media.capabilities": token_state,
                "agent_tool:media.generate": token_state,
                "agent_tool:media.inspect": token_state,
                "context_action:edit-image": token_state,
            },
            "setup": (
                environment["setup"]
                if environment
                else [
                    {
                        "id": "environment",
                        "label": "Media Forge environment",
                        "state": "missing",
                        "message": "Start the service with ./mf.sh serve",
                        "action": {
                            "kind": "open_route",
                            "route": "/x/media-forge/workspace/settings",
                        },
                    }
                ]
            ),
        }
        return payload

    @app.get("/api/v1/host-integration")
    async def host_integration() -> dict[str, Any]:
        return {
            "service_token_verifier": "control_deck_introspection",
            "resource_lease_bridge": "configured",
            "remote_jobs_bridge": "configured",
            "scoped_files_bridge": "configured",
            "control_deck_origin": resolved.control_deck_url,
            "known_host_limitations": [],
            "fallback": "none",
        }

    @app.post("/test/health")
    async def set_health(update: HealthUpdate) -> dict[str, Any]:
        if os.environ.get("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS") != "1":
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        app.state.health_override = update.status
        return await health()

    @app.post("/test/host-files/roundtrip")
    async def host_file_roundtrip(update: HostFileRoundtrip, request: Request) -> dict[str, Any]:
        if os.environ.get("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS") != "1":
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        identity = await authorize_host(request)
        if Path(update.filename).name != update.filename or update.filename in {"", ".", ".."}:
            raise HTTPException(status_code=422, detail={"code": "invalid_filename"})
        try:
            read_id = require_grant_id(update.read_grant_id)
            export_id = require_grant_id(update.export_grant_id)
            metadata, content = await read_grant(host, identity, read_id)
            attached = await host.create_or_attach_job(identity, title="Media Forge scoped file bridge test")
            host_job_id = attached["job"]["id"]
            created = await host.create_output(identity, {
                "job_id": host_job_id,
                "grant_id": export_id,
                "filename": update.filename,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "content_type": "application/octet-stream",
            })
            await host.upload_output(identity, created["output_id"], content)
            committed = await host.commit_output(identity, created["output_id"])
            if attached.get("created") is True:
                await host.update_job(identity, host_job_id, {
                    "phase": "package",
                    "progress": {"completed": 1, "total": 1},
                    "status": "succeeded",
                    "result": {"asset_id": committed["asset_id"]},
                })
        except (HostApiError, KeyError, ValueError) as exc:
            code = exc.code if isinstance(exc, HostApiError) else "invalid_host_response"
            raise HTTPException(status_code=502, detail={"code": code}) from exc
        return {
            "source": {"grant_id": read_id, "name": metadata["name"], "size": len(content)},
            "output": committed,
        }

    @app.get("/api/v1/capabilities")
    async def capabilities() -> dict[str, Any]:
        return {
            "contract_version": "1.0",
            "capabilities": {
                "image.text_to_image": {
                    "state": "available",
                    "implementation": "fake",
                    "confidence": "low",
                    "local_only": True,
                },
                "image.single_reference_edit": {"state": "unavailable", "reason": "planned_for_g2"},
                "image.multi_reference_edit": {"state": "unavailable", "reason": "planned_for_g2"},
                "image.strict_edit": {"state": "unavailable", "reason": "planned_for_g2"},
                "video.image_to_video": {"state": "unavailable", "reason": "planned_for_g7"},
                "3d.image_to_3d": {"state": "unavailable", "reason": "planned_for_g9"},
            },
        }

    @app.get("/api/v1/models")
    async def models() -> dict[str, Any]:
        return model_catalog()

    @app.post("/api/v1/jobs", status_code=202)
    async def create_job(job_request: JobRequest, response: Response) -> dict[str, Any]:
        job = manager.submit(job_request)
        response.headers["Location"] = f"/api/v1/jobs/{job.id}"
        return job.model_dump(mode="json")

    @app.get("/api/v1/jobs")
    async def list_jobs(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in store.list_jobs(limit)]}

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        try:
            return store.get_job(job_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"}) from exc

    @app.delete("/api/v1/jobs/{job_id}")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        try:
            await manager.cancel(job_id)
            return store.get_job(job_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"}) from exc

    @app.get("/api/v1/assets")
    async def list_assets(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in store.list_assets(limit)]}

    @app.get("/api/v1/assets/{asset_id}")
    async def get_asset(asset_id: str) -> dict[str, Any]:
        try:
            return store.get_asset(asset_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc

    @app.get("/api/v1/assets/{asset_id}/content")
    async def asset_content(asset_id: str) -> FileResponse:
        try:
            asset = store.get_asset(asset_id)
            return FileResponse(
                store.asset_path(asset_id),
                media_type=asset.mime_type,
                filename=asset.suggested_filename,
                content_disposition_type="inline",
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc

    @app.get("/api/v1/assets/{asset_id}/provenance")
    async def asset_provenance(asset_id: str) -> dict[str, Any]:
        try:
            return store.get_provenance(asset_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc

    @app.get("/schemas/{schema_name}")
    async def schema(schema_name: str) -> FileResponse:
        allowed = {item.name for item in SCHEMAS_DIR.glob("*.json")}
        if schema_name not in allowed:
            raise HTTPException(status_code=404, detail={"code": "schema_not_found"})
        return FileResponse(SCHEMAS_DIR / schema_name, media_type="application/schema+json")

    @app.post("/addon/v1/commands/create")
    async def create_command(request: Request) -> dict[str, Any]:
        await authorize_host(request)
        return {"route": "/x/media-forge/workspace/create"}

    @app.post("/addon/v1/workflow/execute")
    async def workflow_execute(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        value = host_job_input(payload)
        return submitted_reference(await submit_hosted(value, identity, workload_class="workflow"))

    @app.post("/addon/v1/workflow/media.generate/execute")
    async def workflow_execute_compat(request: Request) -> dict[str, Any]:
        return await workflow_execute(request)

    @app.post("/addon/v1/workflow/media.generate/cancel")
    async def workflow_cancel(request: Request) -> dict[str, Any]:
        await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        job_id = payload.get("job_id")
        if not isinstance(job_id, str):
            raise HTTPException(status_code=422, detail={"code": "invalid_job_id"})
        try:
            job = await manager.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"}) from exc
        return submitted_reference(job.model_dump(mode="json"))

    @app.post("/addon/v1/agent/capabilities")
    async def agent_capabilities(request: Request) -> dict[str, Any]:
        await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        return await capabilities()

    @app.post("/addon/v1/agent/generate")
    async def agent_generate(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        value = host_job_input(payload)
        job = await submit_hosted(value, identity, workload_class="agent-interactive")
        terminal = await wait_for_terminal(job["id"])
        await manager.wait_cleanup(job["id"])
        if terminal["status"] != "succeeded":
            error = terminal.get("error") or {"code": "media_job_failed"}
            raise HTTPException(status_code=502, detail={"code": error.get("code", "media_job_failed")})
        result = submitted_reference(terminal)
        result["asset_id"] = terminal["asset_ids"][0] if terminal["asset_ids"] else None
        return result

    @app.post("/addon/v1/agent/inspect")
    async def agent_inspect(request: Request) -> dict[str, Any]:
        await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        asset_id = payload.get("input", {}).get("asset_id")
        if not isinstance(asset_id, str):
            raise HTTPException(status_code=422, detail={"code": "invalid_asset_id"})
        try:
            asset = store.get_asset(asset_id)
            provenance = store.get_provenance(asset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        return {
            "asset": asset.model_dump(mode="json"),
            "provenance": {
                "operation": provenance.operation,
                "license": provenance.license,
                "parent_asset_ids": provenance.parent_asset_ids,
                "validation": provenance.validation,
                "warnings": provenance.warnings,
                "output_sha256": provenance.output_sha256,
            },
        }

    @app.post("/addon/v1/context/edit-image")
    async def context_edit_image(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        context = payload.get("context")
        if not isinstance(context, dict) or context.get("type") not in {"file", "project"}:
            raise HTTPException(status_code=422, detail={"code": "invalid_context"})
        resource_id = context.get("resource_id")
        grant_id = context.get("grant_id")
        source: dict[str, Any] | None = None
        if context["type"] == "file":
            if (
                not isinstance(resource_id, str)
                or not isinstance(grant_id, str)
                or resource_id != grant_id
            ):
                raise HTTPException(status_code=422, detail={"code": "scoped_grant_required"})
            try:
                metadata, content = await read_grant(
                    host,
                    identity,
                    require_grant_id(grant_id),
                    max_bytes=MAX_CONTEXT_IMAGE_BYTES,
                )
            except GrantContentTooLarge as exc:
                raise HTTPException(status_code=413, detail={"code": "context_image_too_large"}) from exc
            except (HostApiError, ValueError) as exc:
                status_code = exc.status_code if isinstance(exc, HostApiError) else 422
                code = exc.code if isinstance(exc, HostApiError) else "invalid_scoped_grant"
                raise HTTPException(status_code=status_code, detail={"code": code}) from exc
            try:
                with Image.open(BytesIO(content)) as image:
                    image.verify()
                with Image.open(BytesIO(content)) as image:
                    width, height = image.size
                    image_format = image.format
                    mode = image.mode
            except (UnidentifiedImageError, OSError, SyntaxError) as exc:
                raise HTTPException(status_code=422, detail={"code": "invalid_context_image"}) from exc
            if (
                image_format not in {"PNG", "JPEG"}
                or width <= 0
                or height <= 0
                or width * height > MAX_CONTEXT_IMAGE_PIXELS
            ):
                raise HTTPException(status_code=422, detail={"code": "unsupported_context_image"})
            source = {
                "name": metadata.get("name", "selected"),
                "size": len(content),
                "width": width,
                "height": height,
                "mode": mode,
            }
        elif not isinstance(resource_id, str) or not resource_id:
            raise HTTPException(status_code=422, detail={"code": "invalid_context"})
        return {
            "action": "open_route",
            "route": "/x/media-forge/workspace/create",
            "context": {"type": context["type"], "source": source},
        }

    @app.websocket("/ws")
    async def workspace_socket(websocket: WebSocket) -> None:
        try:
            identity = await require_host_service_headers(websocket.headers, host)
        except HTTPException:
            await websocket.close(code=4401, reason="invalid host service token")
            return
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                if len(raw.encode()) > 1024 * 1024:
                    await websocket.close(code=4409, reason="request too large")
                    return
                request_id = ""
                try:
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise ValueError("request must be an object")
                    request_id = str(payload.get("id", ""))[:128]
                    method = payload.get("method")
                    params = payload.get("params", {})
                    if not request_id or not isinstance(method, str) or not isinstance(params, dict):
                        raise ValueError("invalid workspace request")
                    reject_host_paths(params)
                    result: dict[str, Any]
                    if method == "jobs.create":
                        value = JobRequest.model_validate(params)
                        result = await submit_hosted(value, identity, workload_class="interactive")
                    elif method == "jobs.get":
                        result = store.get_job(str(params.get("job_id", ""))).model_dump(mode="json")
                    elif method == "jobs.cancel":
                        result = (await manager.cancel(str(params.get("job_id", "")))).model_dump(mode="json")
                    elif method == "jobs.list":
                        result = {"items": [item.model_dump(mode="json") for item in store.list_jobs(100)]}
                    elif method == "assets.list":
                        result = {"items": [item.model_dump(mode="json") for item in store.list_assets(100)]}
                    elif method == "assets.provenance":
                        result = store.get_provenance(str(params.get("asset_id", ""))).model_dump(mode="json")
                    elif method == "assets.content":
                        asset_id = str(params.get("asset_id", ""))
                        asset = store.get_asset(asset_id)
                        content = store.asset_path(asset_id).read_bytes()
                        if len(content) > 12 * 1024 * 1024:
                            raise ValueError("asset preview exceeds the workspace transport bound")
                        result = {"mime_type": asset.mime_type, "base64": base64.b64encode(content).decode("ascii")}
                    elif method == "models.list":
                        result = model_catalog()
                    else:
                        raise ValueError("workspace method is not supported")
                    await websocket.send_json({"id": request_id, "ok": True, "result": result})
                except (KeyError, ValueError, ValidationError) as exc:
                    await websocket.send_json({
                        "id": request_id,
                        "ok": False,
                        "error": {"code": "workspace_request_rejected", "message": str(exc)[:300]},
                    })
                except HTTPException as exc:
                    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "workspace_request_rejected"}
                    await websocket.send_json({"id": request_id, "ok": False, "error": detail})
        except WebSocketDisconnect:
            return

    @app.get("/")
    @app.get("/create")
    @app.get("/library")
    @app.get("/jobs")
    @app.get("/models")
    @app.get("/settings")
    async def workspace() -> HTMLResponse:
        nonlocal workspace_test_delay_pending
        delay_sec = workspace_test_response_delay_sec() if workspace_test_delay_pending else 0.0
        workspace_test_delay_pending = False
        if delay_sec:
            await asyncio.sleep(delay_sec)
        html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        stylesheet = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
        script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
        html = html.replace("<!-- MEDIA_FORGE_INLINE_STYLE -->", f"<style>{stylesheet}</style>")
        html = html.replace("<!-- MEDIA_FORGE_INLINE_SCRIPT -->", f"<script>{script}</script>")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
