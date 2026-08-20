from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings
from .domain import JobRequest
from .environment import setup_snapshot
from .jobs import JobManager
from .store import Store


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPOSITORY_ROOT / "schemas"
FRONTEND_DIR = REPOSITORY_ROOT / "frontend"


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
    app.state.store = store
    app.state.jobs = manager
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "healthy",
            "contract_version": "2.0",
            "contributions": {
                "navigation:workspace": "available",
                "embedded_view:workspace": "available",
                "command:create-media": "available",
                "quick_action:create-media": "available",
                "settings:settings": "available",
                "workflow_executor:media.generate": "available",
                "agent_tool:media.capabilities": "available",
                "agent_tool:media.generate": "available",
                "agent_tool:media.inspect": "available",
                "context_action:edit-image": {
                    "state": "unavailable",
                    "reason_code": "worker_not_installed",
                    "message": "Image editing is introduced in G2",
                    "action": {"kind": "open_route", "route": "/x/media-forge/workspace"},
                },
            },
            "setup": [{"id": "core", "label": "Media Forge service", "state": "ok"}],
        }
        environment = setup_snapshot()
        if environment is not None:
            payload["status"] = environment.get("status", "setup_required")
            payload["setup"] = environment["setup"]
        return payload

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
        jobs = store.list_jobs(limit)
        return {"items": [item.model_dump(mode="json") for item in jobs]}

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
        assets = store.list_assets(limit)
        return {"items": [item.model_dump(mode="json") for item in assets]}

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

    @app.post("/addon/v1/commands/create")
    async def command_create(_: dict[str, Any] | None = None) -> dict[str, str]:
        return {"action": "open_route", "route": "/x/media-forge/workspace"}

    @app.post("/addon/v1/workflow/execute")
    async def workflow_execute(payload: dict[str, Any]) -> dict[str, Any]:
        job_request = _addon_job_request(payload)
        job = manager.submit(job_request)
        return {"job_id": job.id, "status": job.status, "asset_ids": job.asset_ids}

    @app.post("/addon/v1/agent/capabilities")
    async def agent_capabilities(_: dict[str, Any]) -> dict[str, Any]:
        catalog = await capabilities()
        return {
            "content": [{"type": "text", "text": "Media Forge capability catalog"}],
            "capabilities": catalog["capabilities"],
        }

    @app.post("/addon/v1/agent/generate")
    async def agent_generate(payload: dict[str, Any]) -> dict[str, Any]:
        job = manager.submit(_addon_job_request(payload))
        return {
            "content": [{"type": "text", "text": "Media generation job accepted"}],
            "job_id": job.id,
            "asset_ids": [],
        }

    @app.post("/addon/v1/agent/inspect")
    async def agent_inspect(payload: dict[str, Any]) -> dict[str, Any]:
        value = payload.get("input", payload)
        asset_id = value.get("asset_id") if isinstance(value, dict) else None
        if not isinstance(asset_id, str):
            raise HTTPException(status_code=422, detail={"code": "asset_id_required"})
        try:
            asset = store.get_asset(asset_id)
            provenance = store.get_provenance(asset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        return {
            "content": [{"type": "text", "text": f"Asset {asset.id}: {asset.mime_type}, {asset.width}x{asset.height}"}],
            "asset": asset.model_dump(mode="json"),
            "provenance": provenance.model_dump(mode="json"),
        }

    @app.post("/addon/v1/context/edit-image")
    async def context_edit(payload: dict[str, Any]) -> dict[str, Any]:
        context = payload.get("context")
        if not isinstance(context, dict) or not str(context.get("grant_id", "")).startswith("grant:"):
            raise HTTPException(status_code=422, detail={"code": "scoped_grant_required"})
        if _contains_raw_path(payload):
            raise HTTPException(status_code=422, detail={"code": "raw_path_rejected"})
        raise HTTPException(status_code=409, detail={"code": "capability_unavailable", "message": "Editing is introduced in G2"})

    @app.get("/schemas/{schema_name}")
    async def schema(schema_name: str) -> FileResponse:
        allowed = {item.name for item in SCHEMAS_DIR.glob("*.json")}
        if schema_name not in allowed:
            raise HTTPException(status_code=404, detail={"code": "schema_not_found"})
        return FileResponse(SCHEMAS_DIR / schema_name, media_type="application/schema+json")

    @app.get("/")
    @app.get("/settings")
    async def workspace(_: Request) -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html", media_type="text/html")

    return app


def _addon_job_request(payload: dict[str, Any]) -> JobRequest:
    value = payload.get("input", payload)
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail={"code": "invalid_input"})
    try:
        return JobRequest.model_validate(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_job_request", "message": str(exc)}) from exc


def _contains_raw_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_raw_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_raw_path(item) for item in value)
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return value.startswith(("/", "\\\\")) or "../" in value or lowered.startswith("file:") or (
        len(value) >= 3 and value[1:3] in {":\\", ":/"} and value[0].isalpha()
    )


app = create_app()
