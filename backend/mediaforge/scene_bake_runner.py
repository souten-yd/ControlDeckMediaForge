"""Pinned CPU bake using existing scene Jobs and image Assets."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
from typing import Any, TYPE_CHECKING
import uuid

from PIL import Image
from pydantic import ValidationError

from . import __version__
from .domain import Asset, Provenance
from .paths import contained
from .scene_bake import SceneBakeRequest
from .scene_geometry import UvMapFact
from .scenes import SceneError
from .store import utc_now

if TYPE_CHECKING:
    from .scene_workspace import SceneWorkspace

MAX_IMAGE_BYTES=8*1024*1024


def validate_report(report: Any,value: SceneBakeRequest,version: str) -> None:
    if not isinstance(report,dict) or set(report)!={'schema_version','blender_version','spec','device','frame','samples','autoexec_disabled','uv','images'}:
        raise ValueError('invalid bake report')
    if report['schema_version']!='media-forge.scene-bake-result@1' or report['blender_version']!=version or report['spec']!=value.worker_spec():
        raise ValueError('bake identity differs')
    if report['device']!='CPU' or report['frame']!=0 or report['samples']!=16 or report['autoexec_disabled'] is not True:
        raise ValueError('bake execution differs')
    uv=UvMapFact.model_validate(report['uv'])
    # 面積ゼロの UV 三角形が少数あるのは、面を削った結果として普通に起きる
    # （実測: 24,900 三角形のうち 1 つ）。その三角形にテクセルが乗らないだけで
    # 他の面には影響しない。worker と同じ許容（1000 分の 1 か 64 の大きい方）で
    # 見る。ほとんどが潰れている UV は今までどおり断る。
    allowance=max(64,(uv.loops or 0)//1000)
    if (uv.name!=value.uv_map or not uv.finite or uv.degenerate_triangles is None
            or uv.degenerate_triangles>allowance
            or uv.bounds_min is None or uv.bounds_max is None
            or min(uv.bounds_min)<-1e-5 or max(uv.bounds_max)>1.00001):
        raise ValueError('bake UV facts differ')
    images=report['images']
    if not isinstance(images,list) or len(images)!=len(value.channels):raise ValueError('bake image count differs')
    for channel,row in zip(value.channels,images,strict=True):
        if not isinstance(row,dict) or set(row)!={'channel','filename','sha256','nontransparent_pixels','color_space','normal_convention'}:
            raise ValueError('invalid baked image')
        if row['channel']!=channel or row['filename']!=f'{channel}.png' or row['color_space']!='non_color' or row['normal_convention']!=('open_gl' if channel=='normal' else None):
            raise ValueError('bake image identity differs')
        if type(row['nontransparent_pixels']) is not int or not 0<row['nontransparent_pixels']<=value.resolution**2:
            raise ValueError('bake image is empty')
        import re
        if not isinstance(row['sha256'],str) or re.fullmatch('[a-f0-9]{64}',row['sha256']) is None:raise ValueError('bake image hash differs')


async def bake(workspace: SceneWorkspace,owner: str,job_id: str,value: SceneBakeRequest,
               *,runtime_id: str,runtime_version: str) -> dict[str,Any]:
    from .scene_workspace import _bounded_read,_stop_process
    document,revisions=workspace.catalog.get(owner,value.scene_id)
    revision=next((r for r in revisions if r.id==value.revision_id),None)
    if revision is None:raise SceneError('scene_revision_not_found','bake revision is unavailable')
    if (revision.runtime_id,revision.runtime_version)!=(runtime_id,runtime_version):
        raise SceneError('scene_runtime_unavailable','bake runtime differs')
    source,_,path=workspace._verified_revision_asset(revision.source_asset_id,'application/x-blender')
    sources=[(source,path,'source.blend')]
    if value.high_source:
        _,high_revisions=workspace.catalog.get(owner,value.high_source.scene_id)
        high=next((r for r in high_revisions if r.id==value.high_source.revision_id),None)
        if high is None:raise SceneError('scene_revision_not_found','high bake revision is unavailable')
        if (high.runtime_id,high.runtime_version)!=(runtime_id,runtime_version):
            raise SceneError('scene_runtime_unavailable','high bake runtime differs')
        asset,_,high_path=workspace._verified_revision_asset(high.source_asset_id,'application/x-blender')
        sources.append((asset,high_path,'high.blend'))
    worker=workspace.bake_worker
    if worker is None or worker.is_symlink() or not worker.is_file():
        raise SceneError('scene_bake_worker_unavailable','trusted bake worker is unavailable')
    root=contained(workspace.bake_root,workspace.bake_root/f'bake_{uuid.uuid4().hex}');root.mkdir(mode=0o700)
    registered=[]
    try:
        hashes={asset.id:asset.sha256 for asset,_,_ in sources}
        for asset,path,name in sources:
            staged=root/name;shutil.copyfile(path,staged);staged.chmod(0o600)
            if workspace._sha256(staged)!=asset.sha256:raise SceneError('scene_bake_input_changed','staged bake source changed')
        (root/'bake.json').write_text(json.dumps(value.worker_spec(),sort_keys=True,separators=(',',':')))
        sandbox=root/'blender-user';sandbox.mkdir(mode=0o700)
        environment={'PATH':'/usr/bin:/bin','PYTHONNOUSERSITE':'1','HOME':str(sandbox),
            'XDG_CACHE_HOME':str(sandbox/'cache'),'XDG_CONFIG_HOME':str(sandbox/'config'),'XDG_DATA_HOME':str(sandbox/'data'),
            'BLENDER_USER_CONFIG':str(sandbox/'blender-config'),'BLENDER_USER_SCRIPTS':str(sandbox/'blender-scripts'),
            'BLENDER_USER_DATAFILES':str(sandbox/'blender-data'),'LIBGL_ALWAYS_SOFTWARE':'1',
            'CUDA_VISIBLE_DEVICES':'','HIP_VISIBLE_DEVICES':'','ROCR_VISIBLE_DEVICES':''}
        with workspace.resolver.runtime_reference(runtime_id) as runtime:
            if runtime is None or runtime.version!=runtime_version:raise SceneError('scene_runtime_unavailable','bake runtime is unavailable')
            process=await asyncio.create_subprocess_exec(str(runtime.executable),'--background','--factory-startup','--disable-autoexec',
                '--python-exit-code','1','--python',str(worker),'--','--expected-version',runtime_version,
                cwd=root,stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
                env=environment,start_new_session=True)
            readers=[asyncio.create_task(_bounded_read(stream)) for stream in (process.stdout,process.stderr)]
            try:
                _,_,code=await asyncio.wait_for(asyncio.gather(*readers,process.wait()),timeout=workspace.process_timeout_sec)
            except BaseException as exc:
                from .scene_recipe_jobs import _finish_cleanup
                await _finish_cleanup(asyncio.create_task(_stop_process(process)))
                for reader in readers:
                    if not reader.done():reader.cancel()
                await asyncio.gather(*readers,return_exceptions=True)
                if isinstance(exc,TimeoutError):raise SceneError('scene_bake_timeout','scene bake timed out') from exc
                raise
            if code!=0:raise SceneError('scene_bake_failed','Blender rejected the bounded bake request')
        result_path=root/'result.json'
        if result_path.is_symlink() or not result_path.is_file() or result_path.stat().st_size>128*1024:
            raise SceneError('scene_bake_invalid','bake report is unavailable or exceeds its bound')
        try:
            report=json.loads(result_path.read_text());validate_report(report,value,runtime_version)
        except (ValueError,TypeError,KeyError,ValidationError) as exc:
            raise SceneError('scene_bake_invalid','bake report differs from request') from exc
        outputs=[]
        for row in report['images']:
            path=root/f"{row['channel']}.png"
            if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_IMAGE_BYTES:
                raise SceneError('scene_bake_invalid','baked image is unavailable or exceeds its bound')
            if workspace._sha256(path)!=row['sha256']:raise SceneError('scene_bake_invalid','baked image hash differs')
            try:
                with Image.open(path) as image:
                    if image.format!='PNG' or image.size!=(value.resolution,)*2 or image.n_frames!=1:raise ValueError('bake PNG dimensions differ')
                    image.verify()
                with Image.open(path) as image:
                    clean=Image.new('RGBA',image.size);clean.paste(image.convert('RGBA'))
                    if sum(clean.getchannel('A').histogram()[128:])!=row['nontransparent_pixels']:raise ValueError('bake alpha count differs')
                    clean.save(path,format='PNG')
                if path.stat().st_size>MAX_IMAGE_BYTES:raise ValueError('normalized bake exceeds bound')
            except (OSError,ValueError) as exc:
                raise SceneError('scene_bake_invalid','baked image is invalid') from exc
            outputs.append((row,path))
        # Retain immutable source identity across long CPU work before publication.
        for asset,_,_ in sources:
            verified,_,_=workspace._verified_revision_asset(asset.id,'application/x-blender')
            if verified.sha256!=asset.sha256:raise SceneError('scene_bake_input_changed','bake source changed')
        images=[]
        for row,path in outputs:
            now=utc_now();digest=workspace._sha256(path)
            asset=Asset(id=f'asset_{uuid.uuid4().hex}',job_id=job_id,parent_asset_ids=sorted(hashes),mime_type='image/png',
                width=value.resolution,height=value.resolution,size_bytes=path.stat().st_size,sha256=digest,
                suggested_filename=f"scene-{revision.id[9:17]}-{row['channel']}.png",provenance_id=f'prov_{uuid.uuid4().hex}',created_at=now)
            provenance=Provenance(id=asset.provenance_id,asset_id=asset.id,parent_asset_ids=asset.parent_asset_ids,
                operation='scene.bake',intent='Bake verified immutable 3D source geometry on CPU',
                model_id='none',model_version='0',weights_hash='none',license='derived',runtime_adapter='blender.scene-bake',
                runtime_version=runtime_version,tool_versions={'media-forge':__version__,'blender':runtime_version},seed=0,
                parameters={'scene_id':value.scene_id,'revision_id':value.revision_id,'high_source':value.high_source.model_dump(mode='json') if value.high_source else None,
                    'bake':value.worker_spec(),'channel':row['channel'],'worker_sha256':row['sha256'],'nontransparent_pixels':row['nontransparent_pixels'],'uv':report['uv']},
                reference_asset_hashes=hashes,postprocessing=['png-metadata-removed'],
                validation=[{'validator':'scene.bake','status':'passed','device':'CPU','frame':0,'samples':16}],
                warnings=['Baking is not visual, UV overlap, surface or deformation approval'],output_sha256=digest,created_at=now)
            workspace.store.register_asset(asset,provenance,path);registered.append(asset.id)
            images.append({**row,'asset_id':asset.id,'sha256':digest})
        return {'scene':document.model_dump(mode='json'),'revision':revision.model_dump(mode='json'),'asset_ids':registered,
            'bake':value.worker_spec(),'images':images,'uv':report['uv'],'device':'CPU','frame':0,'samples':16,'surface_approval':'not_granted','ray_hit_coverage':'not_measured','uv_overlap':'not_checked'}
    except BaseException:
        workspace._rollback_assets(registered);raise
    finally:workspace._remove_tree(root,workspace.bake_root)
