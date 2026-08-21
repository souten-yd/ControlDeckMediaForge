from __future__ import annotations

import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from . import __version__
from .config import Settings
from .domain import JobRequest
from .environment import setup_snapshot
from .jobs import JobManager
from .host.security import reject_host_paths, require_host_service, require_host_service_headers
from .store import Store


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPOSITORY_ROOT / "schemas"
FRONTEND_DIR = REPOSITORY_ROOT / "frontend"
HealthState = Literal["healthy", "degraded", "unavailable", "setup_required"]


class HealthUpdate(BaseModel):
    status: HealthState


def _unavailable(reason: str, message: str) -> dict[str, Any]:
    return {
        "state": "unavailable",
        "reason_code": reason,
        "message": message,
        "action": {"kind": "open_route", "route": "/x/media-forge/workspace/settings"},
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    store = Store(resolved.data_dir)
    manager = JobManager(store, worker_timeout_sec=resolved.worker_timeout_sec)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.initialize()
        await manager.start()
        yield
        await manager.stop()

    app = FastAPI(title="ControlDeck Media Forge", version=__version__, lifespan=lifespan)
    app.state.health_override = None
    app.state.store = store
    app.state.jobs = manager
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    def authorize_host(request: Request) -> dict[str, Any]:
        return require_host_service(request, resolved)

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
        token_ready = resolved.host_token_key_file is not None and resolved.host_token_key_file.is_file()
        token_state: str | dict[str, Any] = "available" if token_ready else _unavailable(
            "setup_incomplete",
            "ControlDeck service token verification has not been provisioned",
        )
        service_bridge_unavailable = _unavailable(
            "dependency_unavailable",
            "ControlDeck does not expose the Add-on service resource/jobs bridge in the referenced host revision",
        )
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
                "workflow_executor:media.generate": service_bridge_unavailable,
                "agent_tool:media.capabilities": token_state,
                "agent_tool:media.generate": service_bridge_unavailable,
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
            "service_token_verifier": (
                "configured"
                if resolved.host_token_key_file is not None and resolved.host_token_key_file.is_file()
                else "unconfigured"
            ),
            "resource_lease_bridge": "unavailable_in_host_revision",
            "remote_jobs_bridge": "unavailable_in_host_revision",
            "scoped_files_bridge": "unavailable_in_host_revision",
            "fallback": "none",
        }

    @app.post("/test/health")
    async def set_health(update: HealthUpdate) -> dict[str, Any]:
        if os.environ.get("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS") != "1":
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        app.state.health_override = update.status
        return await health()

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
        authorize_host(request)
        return {"route": "/x/media-forge/workspace/create"}

    @app.post("/addon/v1/workflow/execute")
    async def workflow_execute(request: Request) -> dict[str, Any]:
        authorize_host(request)
        payload = await request.json()
        value = host_job_input(payload)
        return submitted_reference(manager.submit(value).model_dump(mode="json"))

    @app.post("/addon/v1/workflow/media.generate/execute")
    async def workflow_execute_compat(request: Request) -> dict[str, Any]:
        return await workflow_execute(request)

    @app.post("/addon/v1/workflow/media.generate/cancel")
    async def workflow_cancel(request: Request) -> dict[str, Any]:
        authorize_host(request)
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
        authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        return await capabilities()

    @app.post("/addon/v1/agent/generate")
    async def agent_generate(request: Request) -> dict[str, Any]:
        authorize_host(request)
        payload = await request.json()
        value = host_job_input(payload)
        job = manager.submit(value)
        terminal = await wait_for_terminal(job.id)
        result = submitted_reference(terminal)
        result["asset_id"] = terminal["asset_ids"][0] if terminal["asset_ids"] else None
        return result

    @app.post("/addon/v1/agent/inspect")
    async def agent_inspect(request: Request) -> dict[str, Any]:
        authorize_host(request)
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
        authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        context = payload.get("context")
        if not isinstance(context, dict) or context.get("type") not in {"file", "project"}:
            raise HTTPException(status_code=422, detail={"code": "invalid_context"})
        resource_id = context.get("resource_id")
        grant_id = context.get("grant_id")
        if not isinstance(resource_id, str) or not isinstance(grant_id, str) or not grant_id:
            raise HTTPException(status_code=422, detail={"code": "scoped_grant_required"})
        if context["type"] == "file" and not resource_id.startswith(("grant:", "asset:")):
            raise HTTPException(status_code=422, detail={"code": "scoped_grant_required"})
        return {
            "action": "open_workspace",
            "route": "/x/media-forge/workspace/create",
            "context": {"type": context["type"], "resource_id": resource_id},
        }

    @app.websocket("/ws")
    async def workspace_socket(websocket: WebSocket) -> None:
        try:
            require_host_service_headers(websocket.headers, resolved)
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
                        result = manager.submit(value).model_dump(mode="json")
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
        html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        stylesheet = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
        script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
        html = html.replace("<!-- MEDIA_FORGE_INLINE_STYLE -->", f"<style>{stylesheet}</style>")
        html = html.replace("<!-- MEDIA_FORGE_INLINE_SCRIPT -->", f"<script>{script}</script>")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
