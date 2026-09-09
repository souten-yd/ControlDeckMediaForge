"""Isolated real-Blender/domain acceptance; no installed Host or global setting writes."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


def inspect_blend(source: Path, destination: Path) -> None:
    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    objects = {obj.get("media_forge_id"): obj for obj in bpy.data.objects}
    post, copy, beam = (objects[key] for key in ("post", "copy", "beam"))
    assert post.data is not copy.data
    assert post.data.materials[0] is not copy.data.materials[0]
    original_vertex = tuple(post.data.vertices[0].co)
    copy.data.vertices[0].co.x += 0.25
    assert tuple(post.data.vertices[0].co) == original_vertex
    copy.data.vertices[0].co.x -= 0.25
    assert post.modifiers[0].mirror_object is beam
    assert copy.modifiers[0].mirror_object is beam
    vertices = []
    triangles = 0
    for obj in (post, copy, beam):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            triangles += len(mesh.loop_triangles)
            vertices.extend(tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices)
        finally:
            evaluated.to_mesh_clear()
    assert triangles == 60, triangles
    bounds = [[min(v[i] for v in vertices), max(v[i] for v in vertices)] for i in range(3)]
    assert abs(bounds[0][0]+1.2) < 1e-5 and abs(bounds[0][1]-1.2) < 1e-5
    destination.write_text(json.dumps({"blender": bpy.app.version_string, "triangles": triangles,
        "bounds": bounds, "independent_mesh_and_material_slots": True,
        "reference_mirrors_preserved": True}, indent=2) + "\n")


def run(args: argparse.Namespace) -> None:
    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.config import REPOSITORY_ROOT
    from mediaforge.domain import JobRequest, JobStatus
    from mediaforge.scene_recipes import SceneCreateRequest, SceneEditRequest

    args.evidence_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    app = create_app(Settings(data_dir=args.evidence_dir / "data",
                              blender_legacy_runtime_root=args.runtime_root,
                              blender_managed_runtime_root=args.managed_root))
    store, workspace = app.state.store, app.state.scene_workspace
    store.initialize()
    workspace.initialize()
    assert workspace.resolver.register_legacy()
    if args.managed_root:
        catalog = json.loads((REPOSITORY_ROOT / "config/blender-runtime-catalog.json").read_text())
        entry = next(r for r in catalog["runtimes"] if r["runtime_id"] == args.runtime_id)
        workspace.resolver.register_managed(runtime_id=args.runtime_id, version=entry["spec"]["version"],
            location=args.runtime_id, archive_sha256=entry["spec"]["archive_sha256"])
        workspace.resolver.activate(args.runtime_id)
    runtime = workspace.resolver.resolve_active()
    assert runtime is not None
    with runtime.executable.open("rb") as stream:
        runtime_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    operations = [
        {"type":"primitive.add","object_id":"beam","primitive":"cube","name":"Beam","dimensions":[2.4,0.2,0.2],"location":[0,0,0.5]},
        {"type":"primitive.add","object_id":"post","primitive":"cube","name":"Post","dimensions":[0.2,0.2,1],"location":[1,0,0]},
        {"type":"material.set","object_id":"post","base_color":[0.2,0.3,0.4,1]},
        {"type":"modifier.mirror","object_id":"post","reference_object_id":"beam","axes":["X"]},
        {"type":"object.duplicate","object_id":"copy","source_object_id":"post","name":"Second pair",
         "location":[1,1,0],"dimensions":[0.4,0.2,1]},
        {"type":"material.set","object_id":"copy","base_color":[0.8,0.1,0.1,1]},
    ]
    if args.fixture == "robot":
        from robot_fixture import recipe
        operations = recipe()
    elif args.fixture == "rig":
        from rig_fixture import recipe
        operations = recipe()
    create = SceneCreateRequest.model_validate({"name":"Game " + args.fixture + " acceptance","recipe":{"operations":operations}})
    evidence: dict[str, Any] = {"mode":"source_domain_real_blender", "runtime":runtime.version}
    began = time.monotonic()

    async def apply(value: Any) -> dict[str, Any]:
        job = await asyncio.to_thread(store.create_job, JobRequest(operation="media.inspect",
            intent="Game static domain acceptance", constraints={"scene_recipe": value.model_dump(mode="json")}))
        result = await workspace.apply_recipe("local", job.id, value, runtime_id=runtime.runtime_id,
                                              runtime_version=runtime.version)
        await asyncio.to_thread(store.update_job, job.id, status=JobStatus.SUCCEEDED, phase="complete",
                                progress=1, asset_ids=result["asset_ids"])
        return result

    try:
        created = asyncio.run(apply(create))
        evidence["created"] = created
        source = store.asset_path(created["revision"]["source_asset_id"])
        old_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        completed = subprocess.run([str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
            "--python-exit-code", "1",
            "--python", str(Path(__file__).resolve()), "--", "--inspect", "--source", str(source),
            "--evidence-dir", str(args.evidence_dir), "--fixture", args.fixture,
            "--glb", str(store.asset_path(created["revision"]["preview_asset_id"]))],
            capture_output=True, text=True, timeout=180, check=False)
        assert completed.returncode == 0, (completed.stdout + completed.stderr)[-4000:]
        evidence["inspection"] = json.loads((args.evidence_dir / "inspection.json").read_text())
        edit_operation = {"type":"transform.set","object_id":"copy" if args.fixture == "gate" else "forearm",
                          "location":[1,2,0] if args.fixture == "gate" else [0.46,-0.025,0.91]}
        if args.fixture == "rig":
            edit_operation = {"type":"pose.set", "object_id":"rig", "bones":[
                {"bone_id":"forearm", "rotation_degrees":[60,0,0]}]}
        edit = SceneEditRequest.model_validate({"scene_id": created["scene"]["id"],
            "base_revision_id":created["revision"]["id"], "recipe":{"operations":[
                edit_operation]}})
        evidence["edited"] = asyncio.run(apply(edit))
        if args.fixture == "rig":
            revision = evidence["edited"]["revision"]
            checked = subprocess.run([str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
                "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--", "--inspect",
                "--source", str(store.asset_path(revision["source_asset_id"])),
                "--glb", str(store.asset_path(revision["preview_asset_id"])),
                "--evidence-dir", str(args.evidence_dir), "--fixture", "rig", "--posed"],
                capture_output=True, text=True, timeout=60)
            assert checked.returncode == 0, (checked.stdout+checked.stderr)[-4000:]
            evidence["posed_inspection"] = json.loads((args.evidence_dir / "posed-inspection.json").read_text())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == old_hash
        for result in (created, evidence["edited"]):
            for aid in result["asset_ids"]:
                asset = store.get_asset(aid)
                assert hashlib.sha256(store.asset_path(aid).read_bytes()).hexdigest() == asset.sha256
                assert store.get_provenance(aid).asset_id == aid
        with runtime.executable.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == runtime_hash
        evidence.update(passed=True, original_source_unchanged=True,
            not_tested=["installed MCP/OpenCode", "engine import", "whole GA-1 or GA roadmap"])
    finally:
        evidence["elapsed_sec"] = round(time.monotonic()-began,3)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence,indent=2)+"\n")
        print(json.dumps({k:evidence.get(k) for k in ("passed","mode","runtime","elapsed_sec")}),flush=True)


if __name__ == "__main__":
    values = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir",type=Path,required=True)
    parser.add_argument("--runtime-root",type=Path)
    parser.add_argument("--managed-root",type=Path)
    parser.add_argument("--runtime-id",default="blender-4.5.13-linux-x64")
    parser.add_argument("--inspect",action="store_true")
    parser.add_argument("--source",type=Path)
    parser.add_argument("--fixture",choices=("gate", "robot", "rig"),default="gate")
    parser.add_argument("--glb",type=Path)
    parser.add_argument("--posed",action="store_true")
    args = parser.parse_args(values)
    if args.inspect:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        if args.fixture == "rig":
            from rig_fixture import inspect_blend as inspect_rig
            inspect_rig(args.source, args.glb, args.evidence_dir, posed=args.posed)
        elif args.fixture == "robot":
            from robot_fixture import inspect_blend as inspect_robot
            inspect_robot(args.source,args.evidence_dir / "inspection.json")
        else:
            inspect_blend(args.source,args.evidence_dir / "inspection.json")
    else:
        run(args)
