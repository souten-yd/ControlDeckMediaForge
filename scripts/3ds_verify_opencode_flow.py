"""Read-only verification of one real OpenCode run and its installed artifacts.

No Host imports, API writes, archive extraction, or inference requests. Output is
a JSON report on stdout; input event logs and the installed DB remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Any


def verify_director_read(calls: list[dict[str, Any]], *, compose: bool = False) -> dict[str, Any]:
    """Discovery and text promises are not evidence of skill/operation execution."""
    skills = [call for call in calls if call["tool"] == "skill"]
    assert skills, "No actual skill invocation"
    for call in skills:
        state = call["state"]
        assert state["status"] == "completed"
        assert state["input"] == {"name": "blender-director"}
        assert "Blender Director" in state["output"] and "media.scene" in state["output"]
    creator = "controldeck_addons_media_scene_compose" if compose else "controldeck_addons_media_scene_create"
    creates = [call for call in calls if call["tool"] == creator]
    if compose:
        assert not any(c["tool"] == "controldeck_addons_media_scene_create" for c in calls), "No typed-create substitution"
    assert len(creates) == 1, "Expected exactly one new scene"
    assert calls.index(skills[0]) < calls.index(creates[0]), "Skill must be read before creation"
    state = creates[0]["state"]
    assert state["status"] == "completed"
    return creates[0]


def verify_director_static(calls: list[dict[str, Any]]) -> None:
    state = verify_director_read(calls)["state"]
    operations = state["input"]["recipe"]["operations"]
    assert {"object.duplicate", "modifier.mirror"} <= {op["type"] for op in operations}
    assert any(op.get("reference_object_id") == "handle" and op.get("axes") == ["X"]
               for op in operations if op["type"] == "modifier.mirror"), "Guard must mirror about the handle"


def verify_array_recipe(operations: list[dict[str, Any]]) -> None:
    assert {op['type'] for op in operations} == {'primitive.add', 'material.set', 'modifier.array'}
    assert len(operations) == 3
    primitive, = [op for op in operations if op['type'] == 'primitive.add']
    array, = [op for op in operations if op['type'] == 'modifier.array']
    material, = [op for op in operations if op['type'] == 'material.set']
    assert primitive['object_id'] == array['object_id'] == material['object_id'] == 'step'
    assert primitive['primitive'] == 'cube' and primitive['dimensions'] == [.4, .8, .2]
    assert primitive.get('location', [0, 0, 0]) == [0, 0, 0]
    assert primitive.get('rotation_degrees', [0, 0, 0]) == [0, 0, 0]
    assert array['count'] == 6 and array['local_offset'] == [1.5, 0, 1.5]
    assert operations.index(primitive) < operations.index(array)
    assert operations.index(primitive) < operations.index(material)


def verify_auto_skin_recipe(operations: list[dict[str, Any]]) -> None:
    assert len(operations) == 5
    primitive, rig, binding, *clips = operations
    assert primitive['type'] == 'primitive.add' and primitive['primitive'] == 'uv_sphere'
    assert primitive['object_id'] == 'body' and primitive['name'] == 'Body'
    assert primitive['dimensions'] == [.3, .3, 1.3] and primitive['location'] == [0, 0, .5]
    assert primitive.get('rotation_degrees', [0, 0, 0]) == [0, 0, 0] and primitive['vertices'] == 16
    assert rig['type'] == 'armature.create' and rig['object_id'] == 'rig' and rig['name'] == 'Rig'
    lower, upper = rig['bones']
    assert lower['bone_id'] == 'lower' and lower['head'] == [0, 0, 0] and lower['tail'] == [0, 0, .5]
    assert lower.get('parent_bone_id') is None
    assert upper['bone_id'] == 'upper' and upper['head'] == [0, 0, .5] and upper['tail'] == [0, 0, 1]
    assert upper['parent_bone_id'] == 'lower'
    assert binding['type'] == 'skin.bind_auto' and binding['object_id'] == 'rig'
    assert binding['mesh_object_ids'] == ['body'], 'Rigid binding is not distributed weight acceptance'
    assert {clip['clip_id'] for clip in clips} == {'idle', 'bend'}
    for clip in clips:
        assert clip['type'] == 'animation.clip' and clip['object_id'] == 'rig'
        assert clip.get('fps', 24) == 24 and clip['frame_count'] == 48 and clip.get('loop') is True
        track, = clip['tracks']
        assert track['bone_id'] == 'upper'
        assert track['keys'] == [
            {'frame': 0, 'rotation_degrees': [0, 0, 0]},
            {'frame': 24, 'rotation_degrees': [5 if clip['clip_id'] == 'idle' else 60, 0, 0]},
            {'frame': 48, 'rotation_degrees': [0, 0, 0]}]


def armor_shape_report(vertices: list[Any], faces: list[Any]) -> dict[str, Any]:
    """Minimum M1 fixture shape checks, not an aesthetic or solid-volume verdict.

    Check local X width/Y depth/Z height and a connected vertical ridge inside
    the width, on either depth extreme. Coordinates remain authored by the LLM.
    """
    lows = [min(p[a] for p in vertices) for a in range(3)]
    highs = [max(p[a] for p in vertices) for a in range(3)]
    dimensions = [hi - lo for lo, hi in zip(lows, highs)]
    dimensions_match = all(math.isclose(got, expected, rel_tol=.05, abs_tol=1e-6)
                           for got, expected in zip(dimensions, (.4, .08, .5)))
    ridge = False
    for face in faces:
        for first, second in zip(face, [*face[1:], face[0]]):
            a, b = vertices[first], vertices[second]
            if (lows[0] + .1 * dimensions[0] < a[0] < highs[0] - .1 * dimensions[0]
                    and math.isclose(a[0], b[0], abs_tol=1e-6)
                    and math.isclose(a[1], b[1], abs_tol=1e-6)
                    and abs(a[2] - b[2]) >= .5 * dimensions[2]
                    and any(math.isclose(a[1], depth, abs_tol=1e-6) for depth in (lows[1], highs[1]))):
                # A subdivided flat box face is not a protruding ridge.
                same_level = [p for p in vertices if math.isclose(p[2], a[2], abs_tol=1e-6)]
                left = [p for p in same_level if p[0] < a[0] - 1e-6]
                right = [p for p in same_level if p[0] > a[0] + 1e-6]
                if left and right and all(abs(p[1] - a[1]) > 1e-6 for p in left + right):
                    ridge = True
    return {"dimensions_meters": dimensions, "dimensions_match": dimensions_match,
            "connected_ridge": ridge, "visual_quality": "NOT TESTED"}


def verify_authored_mesh_calls(calls: list[dict[str, Any]], *, compose: bool = False) -> None:
    """Prove actual new-operation use, not schema discovery or quality claims."""
    from mediaforge.scene_recipes import MeshCreate, SceneCreateRequest

    def output(call: dict[str, Any]) -> dict[str, Any]:
        assert call["state"]["status"] == "completed"
        value = json.loads(call["state"]["output"])
        return value.get("output", value)

    create = verify_director_read(calls, compose=compose)
    job_id = output(create)["job_id"]
    terminals = [c for c in calls if c["tool"] == "controldeck_addons_media_job_status"
                 and output(c).get("job_id") == job_id and output(c).get("status") == "succeeded"]
    assert terminals
    if compose:
        from mediaforge.scene_drafts import SceneComposeRequest
        request = SceneComposeRequest.model_validate(create["state"]["input"])
        assert request.require_closed and request.vertex_budget <= 10 and request.retry_job_id is None
        result = output(terminals[-1])["result"]
        parsed = SceneCreateRequest.model_validate(result["prepared_request"])
        assert parsed.name == request.name and parsed.tags == request.tags and parsed.collection == request.collection
        preparation = result["preparation"]
        assert preparation["schema_version"] == "media-forge.grouped-mesh-draft@1"
        assert preparation["execution_status"] == "executed" and preparation["requested_thinking"] is True
        assert preparation["quality_status"] == "NOT TESTED", "Structural proof is not quality acceptance"
        assert preparation["execution_request_sha256"] == hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
        attempts = preparation["attempts"]
        assert 2 <= len(attempts) <= 3 and attempts[0]["valid"] and attempts[-1]["valid"]
        assert [a["response_kind"] for a in attempts] == ["layout", "faces", "face_group_correction"][:len(attempts)]
    else:
        parsed = SceneCreateRequest.model_validate(create["state"]["input"])
    assert len(parsed.recipe.operations) == 2
    mesh, material = parsed.recipe.operations
    assert isinstance(mesh, MeshCreate) and mesh.object_id == "armor" and mesh.name == "Armor"
    assert mesh.require_closed is True, "Closed armor must request the execution-time guard"
    assert len(mesh.vertices) <= 10, "M1 diagnostic requires a small authored mesh, not a complex asset"
    assert material.type == "material.set" and material.object_id == "armor"
    # This fixture requires a closed shell. General mesh.create permits open cloth.
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for face in mesh.faces:
        for a, b in zip(face, face[1:] + face[:1]):
            edges.setdefault(tuple(sorted((a, b))), []).append((a, b))
    assert all(len(pair) == 2 and pair[0] == pair[1][::-1] for pair in edges.values()), "Armor shell must be closed with consistent winding"
    shape = armor_shape_report(mesh.vertices, mesh.faces)
    assert shape["dimensions_match"], "Armor must match local X/Y/Z dimensions within 5 percent"
    assert shape["connected_ridge"], "A box or tetrahedron is not the requested ridged chest plate"

    capability_calls = [c for c in calls if c["tool"] == "controldeck_addons_media_capabilities"]
    assert capability_calls
    for call in capability_calls:
        assert calls.index(call) < calls.index(create), "Discover before creating"
        capability = output(call)["capabilities"]["3d.scene_recipe"]
        assert capability["state"] == "available" and "mesh.create" in capability["supported_operations"]
        assert capability["authoring_guidance"]["version"] == "media-forge.scene-authoring-guidance@1"
        if compose:
            assert output(call)["capabilities"]["3d.scene_compose"]["state"] == "available"
    snapshot, = [c for c in calls if c["tool"] == "controldeck_addons_media_scene_snapshot"]
    export, = [c for c in calls if c["tool"] == "controldeck_addons_media_scene_export"]
    assert calls.index(create) < calls.index(terminals[-1]) < calls.index(snapshot) < calls.index(export)
    revision = output(terminals[-1])["result"]["revision"]
    assert output(snapshot)["revision"]["id"] == output(export)["revision_id"] == revision["id"]
    for saved in (revision, output(snapshot)["revision"]):
        assert {item["validator"] for item in saved["validation"] if item["status"] == "passed"} >= {"blender.scene", "glb.structure"}


def verify_motion(evidence_dir: Path, database: Path, *, array: bool = False, auto_skin: bool = False,
                  authored_mesh: bool = False, compose: bool = False) -> dict[str, Any]:
    """Check actual tool execution and delivered bytes; deformation needs Blender inspection."""
    observations = json.loads((evidence_dir / "observations.json").read_text())
    mode = "director_compose" if compose else "director_authored_mesh" if authored_mesh else (
        "director_auto_skin" if auto_skin else ("director_array" if array else "director_motion"))
    assert observations.get(mode) is True and observations["exit_code"] == 0
    filename = "armor.glb" if authored_mesh or compose else ("weighted.glb" if auto_skin else ("stairs.glb" if array else "robot.glb"))
    events = [json.loads(line) for line in (evidence_dir / "events.jsonl").read_text().splitlines()]
    assert not any(event.get("type") == "error" for event in events)
    calls = [event["part"] for event in events if event.get("type") == "tool_use"]
    allowed = {"skill"} | {"controldeck_addons_" + name for name in (
        "media_capabilities", "media_inspect", "media_scene_create", "media_scene_snapshot",
        "media_scene_export", "media_job_status", "media_pack", "control_deck_project_output_grant")}
    if compose:
        allowed.remove("controldeck_addons_media_scene_create")
        allowed.add("controldeck_addons_media_scene_compose")
    assert all(call["tool"] in allowed and call["state"]["status"] == "completed" for call in calls)
    create_call = verify_director_read(calls, compose=compose)
    operations = [] if compose else create_call["state"]["input"]["recipe"]["operations"]
    if authored_mesh or compose:
        verify_authored_mesh_calls(calls, compose=compose)
    elif auto_skin:
        verify_auto_skin_recipe(operations)
    elif array:
        verify_array_recipe(operations)
    else:
        assert {"armature.create", "skin.bind", "animation.clip"} <= {op["type"] for op in operations}
        clips = [op for op in operations if op["type"] == "animation.clip"]
        assert len(clips) == 2 and {op["clip_id"] for op in clips} == {"idle", "arm_swing"}
        for op in clips:
            assert op.get("fps", 24) == 24 and op["frame_count"] == (48 if op["clip_id"] == "idle" else 24)
            assert op.get("loop", False) is True, "Clip must explicitly enable loop endpoint validation"

    def outputs(name: str) -> list[dict[str, Any]]:
        result = []
        for call in calls:
            if call["tool"] == "controldeck_addons_" + name:
                value = json.loads(call["state"]["output"])
                result.append(value.get("output", value))
        return result

    assert outputs("media_capabilities") and outputs("media_scene_snapshot")
    created = outputs("media_scene_compose" if compose else "media_scene_create")[0]
    terminal = next(row for row in outputs("media_job_status")
                    if row["job_id"] == created["job_id"] and row["status"] == "succeeded")
    revision = terminal["result"]["revision"]
    exported, = outputs("media_scene_export")
    assert exported["revision_id"] == revision["id"]
    if auto_skin and observations.get('saved_settings'):
        snapshot, = outputs('media_scene_snapshot')
        assert snapshot['revision']['id'] == revision['id']
        reports = []
        for saved in (revision, snapshot['revision']):
            check, = [item for item in saved.get('validation', []) if item['validator'] == 'blender.scene']
            assert check['status'] == 'passed'
            report = check['facts'].get('animation_settings')
            assert isinstance(report, dict), 'Missing saved settings are not zero clips'
            assert report['schema_version'] == 'media-forge.animation-settings@1'
            assert report['fps'] == 24 and report['unreported_actions'] == 0
            assert all(item.get('loop_requested') is True for item in report['clips'])
            assert sorted(report['clips'], key=lambda item: item['clip_id']) == [
                {'object_id': 'rig', 'clip_id': key, 'frame_start': 0.0, 'frame_end': 48.0,
                 'loop_requested': True} for key in ('bend', 'idle')]
            reports.append(report)
        assert reports[0] == reports[1]
        snapshot_index, = [i for i, call in enumerate(calls) if call['tool'] == 'controldeck_addons_media_scene_snapshot']
        export_index, = [i for i, call in enumerate(calls) if call['tool'] == 'controldeck_addons_media_scene_export']
        assert max(i for i, call in enumerate(calls) if call['tool'] == 'controldeck_addons_media_job_status') < snapshot_index < export_index
    if auto_skin or authored_mesh or compose:
        grant, = outputs("control_deck_project_output_grant")
        grant_call, = [call for call in calls if call['tool'] == 'controldeck_addons_control_deck_project_output_grant']
        export_call, = [call for call in calls if call['tool'] == 'controldeck_addons_media_scene_export']
        pack_call, = [call for call in calls if call['tool'] == 'controldeck_addons_media_pack']
        assert calls.index(export_call) < calls.index(grant_call) < calls.index(pack_call), 'Acquire a fresh grant after export'
        assert grant_call['state']['input'] == {'addon_id': 'media-forge', 'relative_directory': 'exports'}
        assert pack_call['state']['input']['output_grant_id'] == grant['grant_id']
    placed, = outputs("media_pack")
    if "receipt" in placed:
        receipt = placed["receipt"]
        assert placed["media_asset_id"] == receipt["source_asset_id"]
        assert placed["name"] == receipt["filename"]
        assert placed["sha256"] == receipt["sha256"] and placed["size"] == receipt["size_bytes"]
    else:
        assert placed["committed_count"] == placed["requested_count"] == 1 and placed["partial"] is False
        receipt, = placed["receipts"]
    assert receipt["filename"] == filename and receipt["committed"] and receipt["error"] is None
    assert receipt["source_asset_id"] == exported["asset"]["id"]
    root = (Path(observations["project_path"]) / "exports").resolve(strict=True)
    assert {p.name for p in root.iterdir()} == {filename}
    path = (root / filename).resolve(strict=True)
    assert path.parent == root and path.is_file()
    data = path.read_bytes()
    with closing(sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as db:
        assert db.execute("SELECT status FROM jobs WHERE id=?", (created["job_id"],)).fetchone() == ("succeeded",)
        if compose:
            from mediaforge.scene_drafts import SceneComposeRequest
            row = db.execute("SELECT operation, result_json, request_json FROM scene_recipe_tasks WHERE job_id=?", (created["job_id"],)).fetchone()
            assert row is not None and row[0] == "scene.compose"
            assert json.loads(row[1]) == terminal["result"], "MCP result must match executed database record"
            assert json.loads(row[2]) == SceneComposeRequest.model_validate(create_call["state"]["input"]).model_dump(mode="json", exclude={"retry_job_id"})
            source = db.execute("SELECT provenance_json FROM assets WHERE id=?", (revision["source_asset_id"],)).fetchone()
            assert source is not None
            assert json.loads(source[0])["parameters"]["preparation"] == terminal["result"]["preparation"]
        row = db.execute("SELECT metadata_json, provenance_json FROM assets WHERE id=?",
                         (receipt["source_asset_id"],)).fetchone()
        assert row is not None
        metadata, provenance = map(json.loads, row)
        assert hashlib.sha256(data).hexdigest() == receipt["sha256"] == metadata["sha256"] == provenance["output_sha256"]
        assert len(data) == receipt["size_bytes"] == metadata["size_bytes"]
    return {"verified": True, "scope": "actual director read, compose Job and GLB delivery" if compose else "actual director read, authored mesh, guidance and GLB delivery" if authored_mesh else (
                "actual director read, automatic skin binding and GLB delivery" if auto_skin else (
                "actual director read, typed array creation and GLB delivery" if array else "actual director read, typed clip creation and GLB delivery")),
            "scene_id": exported["scene_id"], "revision_id": revision["id"], "job_id": created["job_id"],
            "source_asset_id": revision["source_asset_id"], "receipt": receipt,
            "elapsed_sec": observations["elapsed_sec"],
            "not_tested": ["actual GLB deformation (run Blender inspector)", "artistic quality",
                           "walking/root motion", "engine playback", "image generation"]}


def verify(evidence_dir: Path, database: Path) -> dict[str, Any]:
    observations = json.loads((evidence_dir / "observations.json").read_text())
    if observations.get("director_compose"):
        return verify_motion(evidence_dir, database, compose=True)
    if observations.get("director_authored_mesh"):
        return verify_motion(evidence_dir, database, authored_mesh=True)
    if observations.get("director_auto_skin"):
        return verify_motion(evidence_dir, database, auto_skin=True)
    if observations.get("director_array"):
        return verify_motion(evidence_dir, database, array=True)
    if observations.get("director_motion"):
        return verify_motion(evidence_dir, database)
    assert observations["exit_code"] == 0
    events = [json.loads(line) for line in (evidence_dir / "events.jsonl").read_text().splitlines()]
    assert not any(event.get("type") == "error" for event in events)
    calls = [event["part"] for event in events if event.get("type") == "tool_use"]
    allowed = {
        "media_capabilities", "media_inspect", "media_scene_create", "media_generate", "media_job_status",
        "media_scene_snapshot", "media_scene_material", "media_scene_export", "media_pack",
        "control_deck_project_output_grant",
    }
    allowed_tools = {"controldeck_addons_" + name for name in allowed}
    if observations.get("director_static"):
        verify_director_static(calls)
        allowed_tools.add("skill")
    assert all(call["tool"] in allowed_tools for call in calls)
    assert all(call["state"]["status"] == "completed" for call in calls)

    def outputs(name: str) -> list[dict[str, Any]]:
        result = []
        for call in calls:
            if call["tool"] == "controldeck_addons_" + name:
                value = json.loads(call["state"]["output"])
                result.append(value.get("output", value))
        return result

    assert outputs("media_capabilities")
    create = outputs("media_scene_create")[0]
    material = outputs("media_scene_material")[0]
    generation = outputs("media_generate")
    statuses = outputs("media_job_status") + generation
    jobs = [create["job_id"], material["job_id"]] + [item["job_id"] for item in generation]
    assert len(jobs) == len(set(jobs)) == 4
    assert all(any(row["job_id"] == job and row["status"] == "succeeded" for row in statuses) for job in jobs)
    revision = next(row["result"]["revision"] for row in statuses
                    if row["job_id"] == material["job_id"] and row["status"] == "succeeded")
    exported = outputs("media_scene_export")[0]
    assert exported["revision_id"] == revision["id"]
    placement = outputs("media_pack")[0]
    assert placement["committed_count"] == placement["requested_count"] == 3
    assert placement["partial"] is False
    receipts = {item["filename"]: item for item in placement["receipts"]}
    assert set(receipts) == {"sword.glb", "blade.png", "sword-project.zip"}
    export_root = (Path(observations["project_path"]) / "exports").resolve(strict=True)
    assert {path.name for path in export_root.iterdir()} == set(receipts)
    connection = sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    try:
        def asset(asset_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
            row = connection.execute("SELECT metadata_json, provenance_json FROM assets WHERE id=?", (asset_id,)).fetchone()
            assert row is not None, asset_id
            return json.loads(row[0]), json.loads(row[1])

        for job in jobs:
            row = connection.execute("SELECT status FROM jobs WHERE id=?", (job,)).fetchone()
            assert row == ("succeeded",), (job, row)
        for filename, receipt in receipts.items():
            path = (export_root / filename).resolve(strict=True)
            assert path.parent == export_root and path.is_file()
            data = path.read_bytes()
            metadata, provenance = asset(receipt["source_asset_id"])
            assert receipt["committed"] and receipt["error"] is None
            assert hashlib.sha256(data).hexdigest() == receipt["sha256"] == metadata["sha256"] == provenance["output_sha256"]
            assert len(data) == receipt["size_bytes"] == metadata["size_bytes"]
        image_id = receipts["blade.png"]["source_asset_id"]
        image_metadata, image_provenance = asset(image_id)
        assert image_provenance["operation"] == "image.generate"
        assert image_provenance["weights_hash"].startswith("sha256:")
        assert "fake" not in image_provenance["runtime_adapter"].lower()
        _, source_provenance = asset(revision["source_asset_id"])
        assert image_id in source_provenance["parent_asset_ids"]
        assert source_provenance["reference_asset_hashes"][image_id] == image_metadata["sha256"]
        assert any(dep["asset_id"] == image_id and dep["sha256"] == image_metadata["sha256"] for dep in revision["dependencies"])
        with zipfile.ZipFile(export_root / "sword-project.zip") as archive:
            assert sorted(archive.namelist()) == ["asset.glb", "manifest.json", "preview.png"]
            assert all(info.file_size < 64 * 1024 * 1024 for info in archive.infolist())
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["profile"] == "3d.project.glb"
            assert manifest["source"]["sha256"] == receipts["sword.glb"]["sha256"]
            for key in ("asset", "preview"):
                item = manifest[key]
                data = archive.read(item["filename"])
                assert len(data) == item["size_bytes"]
                assert hashlib.sha256(data).hexdigest() == item["sha256"]
        stats = manifest["statistics"]
        dimensions = [hi - lo for hi, lo in zip(stats["bounds_max"], stats["bounds_min"], strict=True)]
        assert stats["triangles"] <= 2000 and 0.9 <= max(dimensions) <= 1.1
        return {"scene_id": exported["scene_id"], "revision_id": revision["id"], "jobs": jobs,
                "elapsed_sec": observations["elapsed_sec"], "receipts": list(receipts.values()),
                "dimensions_m": dimensions, "compiled_triangles": stats["triangles"],
                "compiler": manifest["compiler"], "image_model": image_provenance["model_id"],
                "image_warnings": image_provenance["warnings"], "verified": True,
                "director_static": observations.get("director_static", False),
                "not_tested": ["same-scene existing-image comparison/adoption and GUI/restore flow",
                               "image semantic constraints", "long credential refresh"]}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence_dir, args.database), ensure_ascii=False, indent=2))
