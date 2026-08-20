from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import __version__
from .environment import setup_snapshot


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


def create_app() -> FastAPI:
    app = FastAPI(title="ControlDeck Media Forge", version=__version__)
    app.state.health_override = None

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
                    "job_runner_not_implemented", "Media jobs are introduced in MF0-2"
                ),
                "quick_action:create-media": _unavailable(
                    "job_runner_not_implemented", "Media jobs are introduced in MF0-2"
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
