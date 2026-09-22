"""Reversible Library removal; immutable asset data remains authoritative."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from typing import TYPE_CHECKING, Any

from .scenes import SceneError, validate_scene_owner
from .paths import contained

if TYPE_CHECKING:
    from .store import Store

logger = logging.getLogger(__name__)


class LibraryTrash:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def validate_ids(value: object) -> list[str]:
        if (not isinstance(value, list) or not 1 <= len(value) <= 100
                or any(not isinstance(item, str) or not re.fullmatch(r"asset_[0-9a-f]{32}", item) for item in value)):
            raise SceneError("library_selection_invalid", "Select 1 to 100 assets")
        return list(dict.fromkeys(value))

    def _plan(
        self, connection: sqlite3.Connection, owner: str, asset_ids: list[str], action: str,
    ) -> dict[str, Any]:
        validate_scene_owner(owner)
        if not isinstance(action, str) or action not in {"trash", "restore", "purge"}:
            raise SceneError("library_selection_invalid", "Unknown Library action")
        affected = set(asset_ids)
        scenes: dict[str, dict[str, Any]] = {}
        revisions: dict[str, dict[str, Any]] = {}
        for asset_id in asset_ids:
            if connection.execute("SELECT 1 FROM assets WHERE id = ?", (asset_id,)).fetchone() is None:
                raise SceneError("asset_not_found", "A selected asset is no longer available")
            rows = connection.execute(
                """SELECT d.id, d.owner, d.value_json, r.value_json AS revision_json FROM scene_documents d
                   JOIN scene_revisions r ON r.scene_id = d.id
                   WHERE r.source_asset_id = ? OR r.preview_asset_id = ?""",
                (asset_id, asset_id),
            ).fetchall()
            for row in rows:
                if row["owner"] != owner:
                    raise SceneError("library_scene_owner_required", "Open this 3D with its owner's account")
                scenes[row["id"]] = json.loads(row["value_json"])
                revision = json.loads(row["revision_json"])
                revisions[revision["id"]] = revision
                affected.update((revision["source_asset_id"], revision["preview_asset_id"]))
        for scene_id in scenes:
            # Trash does not interrupt a running production or discard a working copy.
            if action in {"trash", "purge"}:
                working = connection.execute(
                    "SELECT 1 FROM scene_working_copies WHERE scene_id = ? AND state = 'active' LIMIT 1",
                    (scene_id,),
                ).fetchone()
                session = connection.execute(
                    """SELECT 1 FROM blender_web_sessions WHERE scene_id = ?
                       AND state NOT IN ('stopped', 'failed', 'interrupted') LIMIT 1""",
                    (scene_id,),
                ).fetchone()
                if working or session:
                    raise SceneError("library_production_busy", "Finish editing this 3D before removing it")
        if len(affected) > 5000:
            raise SceneError("library_selection_invalid", "Select fewer 3D productions")
        if action in {"trash", "purge"}:
            # Inspect persisted requests; unfinished Jobs may still publish another revision.
            for row in connection.execute(
                """SELECT jobs.request_json, task.request_json AS scene_request
                   FROM jobs LEFT JOIN scene_recipe_tasks task ON jobs.id = task.job_id
                   WHERE jobs.status NOT IN ('succeeded', 'failed', 'canceled')""",
            ):
                def references(value: object) -> bool:
                    if isinstance(value, str):
                        return value in affected or value in scenes
                    if isinstance(value, list):
                        return any(references(item) for item in value)
                    if isinstance(value, dict):
                        return any(references(item) for item in value.values())
                    return False
                if any(references(json.loads(raw)) for raw in row if raw):
                    raise SceneError("library_production_busy", "Wait for the running job or cancel it first")
        ids = sorted(affected)
        states = {row["asset_id"]: dict(row) for row in connection.execute(
            "SELECT * FROM library_trash"
        ) if row["asset_id"] in affected}
        if action == "purge" and any(asset_id not in states for asset_id in ids):
            raise SceneError("library_trash_required", "Move the selected assets to Trash first")
        if action != "purge" and any(row["purged_at"] for row in states.values()):
            raise SceneError("library_asset_purged", "Permanently deleted assets cannot be restored")
        # A finished Blender revision is self-contained (external_images == 0).
        # For purge, also guard active users of selected dependency images.
        if action == "purge":
            dependent_scenes = {row[0] for asset_id in ids for row in connection.execute(
                """SELECT r.scene_id FROM scene_revisions r JOIN scene_revision_dependencies d
                   ON d.revision_id = r.id WHERE d.asset_id = ?""", (asset_id,))}
            for asset_id in ids:
                for dependency in connection.execute(
                    """SELECT r.value_json FROM scene_revisions r JOIN scene_revision_dependencies d ON d.revision_id = r.id
                       WHERE d.asset_id = ? AND (d.role LIKE 'texture.%' OR d.role LIKE 'material.%')
                       AND r.source_asset_id NOT IN (SELECT asset_id FROM library_trash WHERE purged_at IS NOT NULL)""",
                    (asset_id,),
                ):
                    revision = json.loads(dependency[0])
                    if revision["source_asset_id"] in affected:
                        continue
                    packed = any(check.get("validator") == "blender.scene" and check.get("status") == "passed"
                                 and check.get("facts", {}).get("external_images") == 0
                                 for check in revision["validation"])
                    if not packed:
                        raise SceneError("library_texture_not_embedded", "A remaining 3D has no embedded-texture verification")
            for scene_id in dependent_scenes:
                if connection.execute(
                    "SELECT 1 FROM scene_working_copies WHERE scene_id = ? AND state = 'active'",
                    (scene_id,),
                ).fetchone():
                    raise SceneError("library_production_busy", "A dependent scene is being edited")
                if connection.execute(
                    """SELECT 1 FROM blender_web_sessions WHERE scene_id = ?
                       AND state NOT IN ('stopped','failed','interrupted') LIMIT 1""", (scene_id,),
                ).fetchone():
                    raise SceneError("library_production_busy", "A dependent Blender session is running")
            for row in connection.execute(
                """SELECT jobs.request_json, task.request_json AS scene_request FROM jobs
                   LEFT JOIN scene_recipe_tasks task ON jobs.id = task.job_id
                   WHERE jobs.status NOT IN ('succeeded','failed','canceled')"""
            ):
                def has_scene(value: object) -> bool:
                    if isinstance(value, str):
                        return value in dependent_scenes
                    if isinstance(value, dict):
                        return any(has_scene(v) for v in value.values())
                    if isinstance(value, list):
                        return any(has_scene(v) for v in value)
                    return False
                if any(has_scene(json.loads(raw)) for raw in row if raw):
                    raise SceneError("library_production_busy", "A dependent scene job is running")
        scope = {"action": action, "asset_ids": ids, "states": states,
                 "scenes": {key: value["current_revision_id"] for key, value in sorted(scenes.items())}}
        fingerprint = hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
        return {
            "action": action, "asset_ids": ids, "asset_count": len(ids),
            "scenes": [{"name": scenes[value["scene_id"]]["name"], "sequence": value["sequence"]}
                       for _, value in sorted(revisions.items())],
            "confirmation_fingerprint": fingerprint,
        }

    def _selection(self, connection: sqlite3.Connection, owner: str, payload: dict[str, Any], *, apply: bool = False) -> list[str]:
        extra = {"confirmation_fingerprint"} if apply else set()
        if set(payload) == {"asset_ids", "action"} | extra:
            return self.validate_ids(payload["asset_ids"])
        if (set(payload) != {"all_trashed", "action"} | extra
                or payload["all_trashed"] is not True or payload["action"] != "purge"):
            raise SceneError("library_selection_invalid", "Invalid Library fields")
        rows = connection.execute(
            """SELECT t.asset_id FROM library_trash t
               WHERE (t.purged_at IS NULL OR t.cleanup_pending = 1)
               AND NOT EXISTS (SELECT 1 FROM scene_revisions r JOIN scene_documents d ON d.id = r.scene_id
                   WHERE (r.source_asset_id = t.asset_id OR r.preview_asset_id = t.asset_id) AND d.owner != ?)
               ORDER BY t.asset_id LIMIT 5001""", (owner,),
        ).fetchall()
        if not rows:
            raise SceneError("library_trash_empty", "Trash is empty")
        if len(rows) > 5000:
            raise SceneError("library_selection_invalid", "Select smaller groups to empty Trash")
        return [row[0] for row in rows]

    def preview(self, owner: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.store._connect() as connection:
            connection.execute("BEGIN")
            ids = self._selection(connection, owner, payload)
            return self._plan(connection, owner, ids, payload["action"])

    def apply(self, owner: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .store import utc_now

        with self.store._lock, self.store._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            ids = self._selection(connection, owner, payload, apply=True)
            plan = self._plan(connection, owner, ids, payload["action"])
            if payload["confirmation_fingerprint"] != plan["confirmation_fingerprint"]:
                raise SceneError("library_selection_changed", "The selection changed; review it again")
            if plan["action"] == "trash":
                now = utc_now()
                connection.executemany(
                    "INSERT OR IGNORE INTO library_trash (asset_id, removed_at) VALUES (?, ?)",
                    [(asset_id, now) for asset_id in plan["asset_ids"]],
                )
            elif plan["action"] == "purge":
                connection.executemany(
                    "UPDATE library_trash SET purged_at = COALESCE(purged_at, ?), cleanup_pending = 1 WHERE asset_id = ?",
                    [(utc_now(), asset_id) for asset_id in plan["asset_ids"]],
                )
            else:
                connection.executemany(
                    "DELETE FROM library_trash WHERE asset_id = ?",
                    [(asset_id,) for asset_id in plan["asset_ids"]],
                )
            # Adopt the newest remaining revision after removal or restoration.
            # Revision sequence numbers and immutable revision/lineage records are retained.
            affected_scenes = {row[0] for asset_id in plan["asset_ids"] for row in connection.execute(
                "SELECT scene_id FROM scene_revisions WHERE source_asset_id = ? OR preview_asset_id = ?",
                (asset_id, asset_id),
            )}
            for scene_id in affected_scenes:
                remaining = connection.execute(
                    """SELECT id FROM scene_revisions WHERE scene_id = ?
                       AND source_asset_id NOT IN (SELECT asset_id FROM library_trash)
                       AND preview_asset_id NOT IN (SELECT asset_id FROM library_trash)
                       ORDER BY sequence DESC LIMIT 1""", (scene_id,),
                ).fetchone()
                if remaining is not None:
                    document = json.loads(connection.execute(
                        "SELECT value_json FROM scene_documents WHERE id = ?", (scene_id,)
                    ).fetchone()[0])
                    document["current_revision_id"] = remaining["id"]
                    document["updated_at"] = utc_now()
                    connection.execute(
                        "UPDATE scene_documents SET current_revision_id = ?, value_json = ?, updated_at = ? WHERE id = ?",
                        (remaining["id"], json.dumps(document), document["updated_at"], scene_id),
                    )
        try:
            if plan["action"] == "purge":
                pending = self.cleanup()
                if any(asset_id in pending for asset_id in plan["asset_ids"]):
                    raise SceneError("library_purge_cleanup_pending", "File cleanup is incomplete; retry permanent deletion")
        finally:
            self.store._notify_session("library")
            self.store._notify_session("scenes")
        return {"action": plan["action"], "asset_count": plan["asset_count"]}

    def cleanup(self) -> set[str]:
        """Resume only user-confirmed purges. A failed unlink remains retryable."""
        pending: set[str] = set()
        with self.store._lock, self.store._connect() as connection:
            rows = connection.execute(
                """SELECT t.asset_id, a.storage_name FROM library_trash t JOIN assets a ON a.id = t.asset_id
                   WHERE t.purged_at IS NOT NULL AND t.cleanup_pending = 1"""
            ).fetchall()
            for row in rows:
                asset_id = row["asset_id"]
                try:
                    targets = [contained(self.store.asset_dir, self.store.asset_dir / row["storage_name"]),
                               contained(self.store.asset_dir, self.store.asset_dir / f"{asset_id}.provenance.json")]
                    targets.extend(contained(self.store.thumbnail_dir, path)
                                   for path in self.store.thumbnail_dir.glob(f"{asset_id}*"))
                    for target in targets:
                        target.unlink(missing_ok=True)
                except (OSError, ValueError):
                    pending.add(asset_id)
                    continue
                connection.execute("UPDATE library_trash SET cleanup_pending = 0 WHERE asset_id = ?", (asset_id,))
        if pending:
            logger.warning("Library purge file cleanup remains pending for %d assets", len(pending))
        return pending
