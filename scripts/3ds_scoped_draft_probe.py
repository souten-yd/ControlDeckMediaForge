"""Run in the Host diagnostic venv; no executor, project or asset creation.

Use the normal service-token issuer for the existing dedicated mf-e2e user.
Only the scoped Add-on Runtime HTTP client performs inference. Credentials are
ephemeral and never printed or written. This is not OpenCode/MCP acceptance.
"""
from __future__ import annotations

import asyncio
import argparse
import importlib
import json
import math
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouped", action="store_true", help="Evaluate the unpublished grouped candidate")
    args = parser.parse_args(argv)
    from app.addons import tokens
    from app.database import SessionLocal
    from app.models import User

    sys.path.insert(0, str(ROOT / "backend"))
    from mediaforge.host.client import ControlDeckHostClient
    from mediaforge.scene_drafts import MeshDraftError, MeshDraftPreparer, MeshDraftRequest
    from mediaforge.host.ai import HostAIGateway, HostAIError
    from mediaforge.scene_grouped_drafts import GroupedMeshDraftPreparer

    # Sync issuer/ORM stays outside the async request path and outside MF core.
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active, "Dedicated acceptance user must be active"
        user_id = user.id
    headers = {
        "Authorization": "Bearer " + tokens.issue(
            "media-forge", subject=f"user:{user_id}", kind="service",
            actor_user_id=user_id, grant_ids=[],
        ),
        "X-Control-Deck-Addon-ID": "media-forge",
    }

    async def run() -> bool:
        host = ControlDeckHostClient("http://127.0.0.1:8765")
        started = time.monotonic()
        try:
            identity = await host.authenticate(headers)
            gateway = HostAIGateway(host)
            capabilities = await gateway.capabilities(identity)
            print(json.dumps({"scoped_capabilities": capabilities}), flush=True)
            preparer = GroupedMeshDraftPreparer(gateway) if args.grouped else MeshDraftPreparer(gateway)
            result = await preparer.prepare(identity, MeshDraftRequest(
                intent="Closed chest armor with a front ridge, width 0.4m, height 0.5m, "
                       "thickness 0.08m. Choose coordinates and faces yourself. "
                       "Name Armor, object_id armor, teal metallic material.",
                vertex_budget=10, require_closed=True,
            ))
            mesh = result.request.recipe.operations[0]
            dimensions = [max(point[axis] for point in mesh.vertices) - min(point[axis] for point in mesh.vertices)
                          for axis in range(3)]
            dimensions_match = all(math.isclose(actual, expected, abs_tol=1e-6)
                                   for actual, expected in zip(dimensions, (0.4, 0.08, 0.5)))
            non_cuboid = any(len({point[axis] for point in mesh.vertices}) > 2 for axis in range(3))
            shape = importlib.import_module("3ds_verify_opencode_flow").armor_shape_report(
                mesh.vertices, mesh.faces)
            print(json.dumps({
                "valid": True, "seconds": round(time.monotonic() - started, 3),
                "vertices": len(mesh.vertices), "faces": len(mesh.faces),
                "dimensions_meters": dimensions, "dimensions_match": dimensions_match,
                "non_cuboid_coordinates": non_cuboid,
                "shape": shape,
                "prepared_request": result.request.model_dump(mode="json"),
                "provenance": result.provenance,
            }), flush=True)
            return dimensions_match and non_cuboid and shape["connected_ridge"]
        except (MeshDraftError, HostAIError) as exc:
            print(json.dumps({"valid": False, "seconds": round(time.monotonic() - started, 3),
                              "code": exc.code,
                              "details": exc.details if isinstance(exc, MeshDraftError) else {}}), flush=True)
            return False
        finally:
            await host.close()

    raise SystemExit(0 if asyncio.run(run()) else 1)


if __name__ == "__main__":
    main()
