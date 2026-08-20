from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import __version__
from .config import Settings
from .domain import JobRequest
from .environment import setup_snapshot
from .jobs import JobManager
from .store import Store


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPOSITORY_ROOT / "schemas"
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

    @app.get("/health")
    async def health() -> dict[str, Any]:
        environment = setup_snapshot()
        status: HealthState = app.state.health_override or (
            environment.get("status", "setup_required") if environment else "setup_required"
        )
        payload: dict[str, Any] = {
            "status": status,
            "contract_version": "2.0",
            "contributions": {
                "navigation:workspace": "available",
                "embedded_view:workspace": _unavailable(
                    "workspace_not_implemented", "The embedded workspace is introduced in MF0-5"
                ),
                "command:create-media": _unavailable(
                    "host_command_not_implemented", "Host commands are introduced in MF0-6"
                ),
                "quick_action:create-media": _unavailable(
                    "host_command_not_implemented", "Host commands are introduced in MF0-6"
                ),
                "settings:settings": "available",
                "workflow_executor:media.generate": _unavailable(
                    "workflow_not_implemented", "Workflow execution is introduced in MF0-6"
                ),
                "agent_tool:media.capabilities": _unavailable(
                    "agent_tools_not_implemented", "Agent tools are introduced in MF0-6"
                ),
                "agent_tool:media.generate": _unavailable(
                    "agent_tools_not_implemented", "Agent tools are introduced in MF0-6"
                ),
                "agent_tool:media.inspect": _unavailable(
                    "agent_tools_not_implemented", "Agent tools are introduced in MF0-6"
                ),
                "context_action:edit-image": _unavailable(
                    "context_action_not_implemented", "Context actions are introduced in MF0-6"
                ),
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

    @app.get("/", response_class=HTMLResponse)
    @app.get("/settings", response_class=HTMLResponse)
    async def service_placeholder() -> str:
        return (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>Media Forge setup</title><body><h1>Media Forge</h1>"
            "<p>The embedded workspace is introduced in MF0-5.</p></body></html>"
        )

    return app


app = create_app()
