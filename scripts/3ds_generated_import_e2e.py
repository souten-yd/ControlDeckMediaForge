"""Real Blender import/validation of an existing GLB, in an isolated Store.

No inference, weights, GPU or Host calls. Input image and generation facts are
explicit fixtures; this verifies publication mechanics, not model generation.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
from pathlib import Path
import time

from PIL import Image

from mediaforge.asset_import import import_asset_bytes
from mediaforge.blender_runtime import BlenderRuntimeResolver
from mediaforge.config import REPOSITORY_ROOT
from mediaforge.domain import JobRequest
from mediaforge.glb import validate_glb_path
from mediaforge.scene_generation import GenerationFacts, SceneFromImageRequest
from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.store import Store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--managed-root', type=Path, required=True)
    parser.add_argument('--glb', type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    source = args.glb.resolve(strict=True)
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    spec = json.loads((REPOSITORY_ROOT/'config/blender-runtime.json').read_text())
    resolver = BlenderRuntimeResolver(
        registry_path=args.evidence_dir/'registry.json', managed_root=args.managed_root,
        legacy_root=args.evidence_dir/'absent-legacy',
        manifest_path=REPOSITORY_ROOT/'config/blender-runtime.json',
        catalog_path=REPOSITORY_ROOT/'config/blender-runtime-catalog.json',
        trusted_worker=REPOSITORY_ROOT/'worker_packs/blender/compile_asset.py',
    )
    runtime_id='blender-4.5.9-linux-x64'
    resolver.register_managed(runtime_id=runtime_id, version=spec['version'], location=runtime_id,
                              archive_sha256=spec['archive_sha256'])
    resolver.activate(runtime_id)
    store=Store(args.evidence_dir/'data')
    store.initialize()
    workspace=SceneWorkspace(store,resolver,REPOSITORY_ROOT/'worker_packs/blender/scene_document.py',
        generation_import_worker=REPOSITORY_ROOT/'worker_packs/blender/import_generated_glb.py')
    workspace.initialize()
    content=io.BytesIO()
    Image.new('RGB',(16,16),(80,120,160)).save(content,format='PNG')
    image=import_asset_bytes(store,content.getvalue(),purpose='source',media_type='image/png')
    request=SceneFromImageRequest(name='Existing GLB import acceptance fixture',input_asset_id=image.id)
    facts=GenerationFacts(model_id='acceptance/existing-glb-fixture',model_revision='0'*40,
        weights_sha256='0'*64,license='fixture-only; no model executed',runtime_adapter='native.trellis-cpp',
        runtime_version='fixture-not-executed',seed=request.seed,resolution=request.resolution,
        elapsed_sec=0,output_sha256=original_sha)
    job=store.create_job(JobRequest(operation='media.inspect',intent='Existing GLB import acceptance fixture'))
    report={'mode':'existing_glb_real_blender_isolated_store_fixture_metadata',
        'source_sha256':original_sha,'source_bytes':source.stat().st_size,
        'not_tested':['inference','real Host broker','installed API','browser rendering','visual quality']}
    start=time.monotonic()
    try:
        result=asyncio.run(workspace.import_generated_glb('user:acceptance',job.id,request,source,source.parent,facts,
            runtime_id=runtime_id,runtime_version=spec['version']))
        scene,revisions=workspace.catalog.get('user:acceptance',result['scene']['id'])
        assert len(revisions)==1 and revisions[0].dependencies[0].asset_id==image.id
        assets=[store.get_asset(aid) for aid in result['asset_ids']]
        assert {a.mime_type for a in assets}=={'application/x-blender','model/gltf-binary'}
        for asset in assets:
            assert hashlib.sha256(store.asset_path(asset.id).read_bytes()).hexdigest()==asset.sha256
            assert store.get_provenance(asset.id).output_sha256==asset.sha256
            if asset.mime_type=='model/gltf-binary':
                validate_glb_path(store.asset_path(asset.id),store.asset_dir)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==original_sha
        assert not list(workspace.recipe_root.iterdir()) and not list(workspace.validation_root.iterdir())
        assert resolver.live_reference_count(runtime_id)==0
        report.update(passed=True,result=result,assets=[a.model_dump(mode='json') for a in assets],
            source_unchanged=True,staging_empty=True,runtime_references=0)
    finally:
        report['elapsed_sec']=round(time.monotonic()-start,3)
        (args.evidence_dir/'observations.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in {'result','assets'}}),flush=True)


if __name__=='__main__':
    main()
