#!/usr/bin/env python3
"""CPU surface-export acceptance with synthetic data; never loads trained weights.

Runs native processes, actual FlexGEMM Torch sampling with only CPU hash adapters,
independent core GLB validation, and Blender import. Does not assert CuMesh,
nvdiffrast, OpenCV inpaint, learned quality, Vulkan or installed-Library parity.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import struct
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any
from convert_flow import PIXAL_REVISION, digest
from prepare_trellis import REVISION
from sparse_cpu_reference import FLEX_REVISION


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pixal-source', 'trellis-source', 'flex-source', 'mesh-fixtures', 'binary', 'core-python', 'blender', 'output-dir'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    for source, pin in ((a.pixal_source, PIXAL_REVISION), (a.trellis_source, REVISION), (a.flex_source, FLEX_REVISION)):
        if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != pin or subprocess.check_output(['git', '-C', str(source), 'diff', 'HEAD', '--']):
            parser.error('reference must have pinned HEAD and unchanged tracked files')
    if a.output_dir.exists(): parser.error('use a new output directory')
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1')
    import numpy as np
    import torch
    from PIL import Image
    torch.set_num_threads(2)
    a.output_dir.mkdir(parents=True)
    source_hash = digest(a.pixal_source / 'inference.py')
    reference = a.flex_source / 'flex_gemm/ops/grid_sample/grid_sample_torch.py'
    # Original class, unmodified arithmetic. Replace only its CUDA-only lookup.
    class CpuHash:
        def hashmap_insert_3d_idx_as_val(self, keys: Any, vals: Any, coords: Any, w: int, h: int, d: int) -> None:
            self.table = {tuple(row): i for i, row in enumerate(coords.tolist())}
        def hashmap_lookup_3d(self, keys: Any, vals: Any, coords: Any, w: int, h: int, d: int) -> Any:
            return torch.tensor([self.table.get(tuple(row), -1) if row[0] == 0 and all(0 <= x < n for x, n in zip(row[1:], (w, h, d))) else -1 for row in coords.tolist()], dtype=torch.int32)
    namespace = {'torch': torch, 'utils': SimpleNamespace(init_hashmap=lambda *_: (None, None)),
                 'grid_sample': SimpleNamespace(HASHMAP_RATIO=2), 'kernels': SimpleNamespace(cuda=CpuHash())}
    node = next(n for n in ast.parse(reference.read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'GridSample3dTorch')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(reference), 'exec'), namespace)
    sampler = namespace['GridSample3dTorch']._trilinear
    comparisons: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []
    def close(name: str, actual: Any, expected: Any, tolerance: float = 2e-6) -> None:
        actual, expected = np.asarray(actual), np.asarray(expected)
        np.testing.assert_allclose(actual, expected, atol=tolerance, rtol=0, err_msg=name)
        comparisons.append({'name': name, 'max_abs': float(np.max(np.abs(actual.astype(float)-expected.astype(float)), initial=0)), 'atol': tolerance})
    def save(directory: Path, values: dict[str, Any]) -> None:
        directory.mkdir()
        for key, value in values.items(): np.save(directory/(key+'.npy'), np.ascontiguousarray(value, dtype=np.float32))
    def input_hash(directory: Path) -> str:
        return hashlib.sha256(json.dumps({p.name: digest(p) for p in sorted(directory.glob('*.npy'))}, sort_keys=True).encode()).hexdigest()
    def command(directory: Path, output: Path, codec: str, fault: str | None = None) -> list[str]:
        cmd = [str(a.binary), str(directory), str(output), codec, 'synthetic', source_hash, input_hash(directory), '--diagnostics']
        return cmd + (['--fault', fault] if fault else [])
    def invoke(name: str, directory: Path, codec: str = 'png', fault: str | None = None, reason: str | None = None) -> Path:
        output = a.output_dir/name
        cmd = command(directory, output, codec, fault)
        start = time.monotonic()
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        (a.output_dir/(name+'.log')).write_text(result.stdout)
        (a.output_dir/(name+'.command.json')).write_text(json.dumps(cmd, indent=2)+'\n')
        if reason:
            assert result.returncode != 0 and reason in result.stdout, (name, result.stdout)
            assert not output.exists(), name
            negatives.append({'name': name, 'exit': result.returncode, 'reason': reason, 'output_exists': False})
        else:
            assert result.returncode == 0, (name, result.stdout)
            case = json.loads((output/'report.json').read_text())
            case.update(name=name, seconds=time.monotonic()-start, sha256=digest(output/'asset.glb'), input_sha256=input_hash(directory))
            cases.append(case)
        return output
    def sample(values: dict[str, Any], queries: Any) -> Any:
        coords = torch.tensor(np.column_stack((np.zeros(len(values['coords'])), values['coords'])), dtype=torch.int32)
        q = torch.tensor((np.asarray(queries, dtype=np.float32)+.5)*int(values['settings'][0]))
        assert torch.all(q >= .5), 'Torch reference truncates negative neighbors; only use interior queries'
        return sampler(torch.tensor(values['pbr'], dtype=torch.float32), coords, (1, 6, *([int(values['settings'][0])]*3)), q[None]).numpy()[0]
    def read_glb(output: Path, codec: str) -> dict[str, Any]:
        content = (output/'asset.glb').read_bytes()
        magic, version, total = struct.unpack_from('<III', content)
        assert (magic, version, total) == (0x46546C67, 2, len(content))
        size, kind = struct.unpack_from('<II', content, 12); assert kind == 0x4E4F534A
        model = json.loads(content[20:20+size]); bs, bt = struct.unpack_from('<II', content, 20+size)
        binary = content[28+size:]; assert bt == 0x004E4942 and bs == len(binary)
        def accessor(index: int) -> Any:
            row = model['accessors'][index]; view = model['bufferViews'][row['bufferView']]
            width = {'VEC3': 3, 'VEC2': 2, 'SCALAR': 1}[row['type']]
            return np.frombuffer(binary, dtype={5126: '<f4', 5125: '<u4'}[row['componentType']], count=row['count']*width, offset=view.get('byteOffset', 0)+row.get('byteOffset', 0)).reshape(-1, width)
        v = np.load(output/'vertices.npy'); uv = np.load(output/'uv.npy'); f = np.load(output/'faces.npy').astype(int)
        close(output.name+'/axis', accessor(0), v*np.array([-1, 1, -1]), 0)
        close(output.name+'/uv', accessor(2), uv, 0)
        close(output.name+'/faces', accessor(3).ravel(), f.ravel(), 0)
        normals = accessor(1); close(output.name+'/normal_length', np.linalg.norm(normals, axis=1), np.ones(len(v)), 2e-6)
        assert np.isfinite(normals).all()
        # Independent area-weighted normal recomputation on position-welded groups.
        pos = accessor(0); unique, inverse = np.unique(pos, axis=0, return_inverse=True)
        sums = np.zeros_like(unique, dtype=np.float64)
        face_normal = np.cross(pos[f[:, 1]].astype(float)-pos[f[:, 0]], pos[f[:, 2]].astype(float)-pos[f[:, 0]])
        for j in range(3): np.add.at(sums, inverse[f[:, j]], face_normal)
        lengths = np.linalg.norm(sums, axis=1); valid = lengths > 1e-15
        expected = sums / np.maximum(lengths[:, None], 1e-30)
        close(output.name+'/normals', normals[valid[inverse]], expected[inverse][valid[inverse]], 3e-5)
        p = model['asset']['extras']['pixal']; assert p['source_kind'] == 'synthetic' and p['source_sha256'] == source_hash and p['experimental'] is True
        assert p['input_sha256'] == next(c['input_sha256'] for c in cases if c['name'] == output.name)
        assert model['materials'][0]['alphaMode'] == 'OPAQUE'
        assert model['materials'][0]['doubleSided'] is (not next(c['remeshed'] for c in cases if c['name'] == output.name))
        assert model.get('extensionsRequired', []) == (['EXT_texture_webp'] if codec == 'webp' else [])
        image_errors = []
        for i, im in enumerate(model['images']):
            assert im['mimeType'] == 'image/'+codec and 'uri' not in im
            view = model['bufferViews'][im['bufferView']]; start = view.get('byteOffset', 0)
            with Image.open(io.BytesIO(binary[start:start+view['byteLength']])) as image:
                pixels = np.asarray(image.convert('RGBA')); assert image.size == (128, 128)
            expected_pixels = np.load(output/('base.npy' if i == 0 else 'mr.npy')).reshape(128, 128, 4)
            error = np.abs(pixels.astype(float)-expected_pixels)
            image_errors.append({'max_abs': float(error.max()), 'mean_abs': float(error.mean())})
            if codec == 'png': close(output.name+'/image'+str(i), pixels, expected_pixels, 0)
        return {'json': model, 'image_errors': image_errors}
    r = 16
    coords = np.stack(np.meshgrid(*([np.arange(r)]*3), indexing='ij'), -1).reshape(-1, 3)
    values = {'vertices': [[-.3, -.2, 0], [.25, -.2, 0], [.25, .3, 0], [-.3, .3, 0]], 'faces': [[0, 1, 2], [0, 2, 3]],
              'coords': coords, 'pbr': np.column_stack((coords/(r-1), np.full((len(coords), 3), [.25, .75, 1]))), 'settings': [r, 128, 1000, 0, 13],
              'queries': [[0, 0, 0], [.1, .1, .1], [-.1, .05, -.13], [-.499, -.499, -.499], [-1, -1, -1], [.5, .5, .5]]}
    source = a.output_dir/'plane-input'; save(source, values)
    exports: list[Path] = []
    for codec in ('png', 'webp'):
        out = invoke('plane-'+codec, source, codec); exports.append(out)
        result = read_glb(out, codec); cases[-1]['embedded_images'] = result['image_errors']
        raw = np.load(out/'sample_raw.npy'); snap = np.load(out/'sample_snap.npy')
        close(codec+'/sampler_raw', raw[:3], sample(values, values['queries'][:3]))
        queries = np.asarray(values['queries'], dtype=np.float32); projected = queries.copy(); projected[:, 0] = np.clip(projected[:, 0], -.3, .25); projected[:, 1] = np.clip(projected[:, 1], -.2, .3); projected[:, 2] = 0
        close(codec+'/sampler_always_project', snap, sample(values, projected))
        assert abs(raw[1, 2]-snap[1, 2]) > .05
        # Bounds/empty tests follow the CUDA floor semantics (Torch reference
        # truncates negative neighbors). Constant corner values are analytic.
        close(codec+'/corner', raw[3], values['pbr'][0]); close(codec+'/empty', raw[4], np.zeros(6), 0); close(codec+'/upper_corner', raw[5], values['pbr'][-1])
        if codec == 'webp': assert max(x['mean_abs'] for x in result['image_errors']) < 3
    # Pixel-level independent interpolation at safely interior atlas texels.
    out = exports[0]; verts = np.load(out/'vertices.npy'); uv = np.load(out/'uv.npy')*128; faces = np.load(out/'faces.npy').astype(int)
    tex = np.load(out/'base.npy').reshape(128, 128, 4); mr = np.load(out/'mr.npy').reshape(128, 128, 4)
    all_pixels, all_points = [], []
    yy, xx = np.mgrid[:128, :128]; pixels = np.column_stack((xx.ravel()+.5, yy.ravel()+.5))
    for face in faces:
        tri = uv[face].astype(float); mat = np.vstack((tri.T, np.ones(3)))
        bary = np.linalg.solve(mat, np.column_stack((pixels, np.ones(len(pixels)))).T).T
        select = (bary > .03).all(axis=1)
        all_pixels.extend(np.flatnonzero(select)); all_points.extend(bary[select]@verts[face])
    attrs = sample(values, all_points); packed = np.clip(attrs*255, 0, 255).astype(np.uint8)
    close('plane/base_interior', tex.reshape(-1, 4)[all_pixels], packed[:, [0, 1, 2, 5]], 1)
    expected_mr = np.column_stack((np.zeros(len(packed)), packed[:, 4], packed[:, 3], np.full(len(packed), 255)))
    close('plane/mr_interior', mr.reshape(-1, 4)[all_pixels], expected_mr, 1)
    # Normalization on missing sparse corners and clipping only at byte packing.
    sparse = dict(values); sparse['coords'] = coords[(coords.sum(1)%3) != 0]; sparse['pbr'] = np.tile([-1, .25, 2, .2, .8, .6], (len(sparse['coords']), 1))
    sparse['queries'] = values['queries'][:3]
    sp = a.output_dir/'sparse-input'; save(sp, sparse); out = invoke('sparse-png', sp); exports.append(out); read_glb(out, 'png')
    close('sparse/normalized', np.load(out/'sample_raw.npy'), sample(sparse, sparse['queries']))
    actual = np.load(out/'base.npy').reshape(128, 128, 4).reshape(-1, 4)[all_pixels]
    close('sparse/clipped_interior', actual, np.tile([0, 63, 255, 153], (len(actual), 1)), 1)
    # One open tetrahedron: small perimeter adds a reversed centroid fan;
    # a larger perimeter remains open. Compare geometry independent of UV splits.
    for size, filled in ((.004, 1), (.02, 0)):
        hole = dict(values); hole.pop('queries'); hole['vertices'] = np.array([[0, 0, 0], [size, 0, 0], [0, size, 0], [0, 0, -size]])
        hole['faces'] = np.array([[0, 1, 3], [1, 2, 3], [2, 0, 3]])
        hp = a.output_dir/('hole-input-'+str(filled)); save(hp, hole); out = invoke('hole-'+str(filled), hp); exports.append(out); read_glb(out, 'png')
        assert cases[-1]['holes_filled'] == filled and cases[-1]['atlas_faces'] == 3+3*filled
        if filled:
            vertices = np.load(out/'vertices.npy'); faces = np.load(out/'faces.npy').astype(int)
            center = np.array([size/3, size/3, 0]); assert np.min(np.linalg.norm(vertices-center, axis=1)) < 1e-8
            base_faces = vertices[faces][np.all(np.abs(vertices[faces, 2]) < 1e-8, axis=1)]
            assert len(base_faces) == 3 and np.all(np.cross(base_faces[:, 1]-base_faces[:, 0], base_faces[:, 2]-base_faces[:, 0])[:, 2] < 0)
    # Actual outputs of the preceding neural-decoder evaluation, not a second
    # model invocation. All those parameters are explicitly synthetic.
    prior_sources = {}
    for name in ('connected_f32', 'connected_full_depth_planar', 'connected_prior_image_shape_latent'):
        path = a.mesh_fixtures/name
        fixture = {key: np.load(path/('actual_'+key+'.npy')).reshape(-1, width) for key, width in (('vertices', 3), ('faces', 3), ('coords', 3), ('pbr', 6))}
        fixture['settings'] = [int(np.load(path/'actual_grid.npy').item()), 128, 300, 1, 7]
        src = a.output_dir/(name+'-input'); save(src, fixture)
        prior_sources[name] = {p.name: digest(p) for p in sorted(path.glob('actual_*.npy'))}
        out = invoke(name, src, 'webp'); exports.append(out); read_glb(out, 'webp')
        assert cases[-1]['remeshed'] and cases[-1]['remesh_faces'] > 0
    repeat = invoke('plane-repeat', source); read_glb(repeat, 'png')
    for key in ('vertices', 'faces', 'uv', 'base', 'mr'): close('repeat/'+key, np.load(repeat/(key+'.npy')), np.load(exports[0]/(key+'.npy')), 0)
    faults = {'nan_vertex': 'invalid surface vertex', 'nan_texture': 'non-finite surface texture', 'duplicate_voxel': 'duplicate surface texture coordinate', 'texture_extent': 'invalid surface texture dimensions', 'invalid_texture_size': 'invalid surface export options', 'byte_budget': 'surface GLB exceeds explicit byte budget', 'invalid_provenance': 'invalid surface provenance hash', 'existing_file': 'GLB destination exists', 'existing_symlink': 'GLB destination exists'}
    for phase in ('holes', 'bvh', 'simplify', 'uv', 'baked', 'encode', 'publish'): faults['cancel_'+phase] = 'surface export cancelled at '+phase
    before = input_hash(source)
    for fault, reason in faults.items(): invoke('negative-'+fault, source, fault=fault, reason=reason)
    assert input_hash(source) == before
    remesh_source = a.output_dir/'connected_full_depth_planar-input'
    invoke('negative-cancel_remesh', remesh_source, fault='cancel_remesh', reason='surface export cancelled at remesh')
    for kind in ('directory', 'symlink'):
        kept = a.output_dir/('existing-'+kind)
        if kind == 'directory':
            kept.mkdir(); (kept/'sentinel').write_bytes(b'preserve original')
        else: kept.symlink_to(source, target_is_directory=True)
        result = subprocess.run(command(source, kept, 'png'), text=True, capture_output=True, timeout=10)
        assert result.returncode == 1 and 'surface output directory exists' in result.stderr
        assert kept.exists() and input_hash(source) == before
        if kind == 'directory': assert (kept/'sentinel').read_bytes() == b'preserve original'
        else: assert kept.is_symlink()
        negatives.append({'name': 'existing-'+kind, 'exit': result.returncode, 'original_preserved': True})
    # Terminate an actually running high-resolution bake. No cooperative callback
    # substitutes for this lifecycle check. Parent owns cleanup after SIGTERM.
    kill_values = dict(values); kill_values.pop('queries'); kill_values['settings'] = [16, 4096, 1000, 0, 0]
    kp = a.output_dir/'termination-input'; save(kp, kill_values); ko = a.output_dir/'termination-output'
    proc = subprocess.Popen(command(kp, ko, 'png'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    stream = bytearray(); start = time.monotonic(); ready = False
    try:
        with selectors.DefaultSelector() as sel:
            sel.register(proc.stdout, selectors.EVENT_READ)
            while time.monotonic()-start < 30 and proc.poll() is None:
                for key, _ in sel.select(.1):
                    chunk = os.read(key.fileobj.fileno(), 4096); stream.extend(chunk)
                    if b'stage=uv\n' in stream: ready = True; break
                if ready: break
        assert ready and proc.poll() is None and not (ko/'asset.glb').exists()
        kill_start = time.monotonic(); os.killpg(proc.pid, signal.SIGTERM); code = proc.wait(timeout=5)
        assert code == -signal.SIGTERM
        assert not (ko/'asset.glb').exists()
        terminated = {'exit': code, 'observed_stage': 'uv', 'seconds_to_reap': time.monotonic()-kill_start, 'published_glb': False}
    finally:
        if proc.poll() is None: os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=5)
        if proc.stdout: stream.extend(proc.stdout.read()); proc.stdout.close()
        if ko.exists(): shutil.rmtree(ko)
        (a.output_dir/'termination.log').write_bytes(stream)
    # Core and Blender are separate processes and environments.
    manifest = a.output_dir/'glb-manifest.json'
    manifest.write_text(json.dumps([str(p/'asset.glb') for p in exports], indent=2)+'\n')
    core_script = 'import json,sys; from pathlib import Path; from mediaforge.glb import validate_glb; print(json.dumps({p:validate_glb(Path(p).read_bytes()) for p in json.loads(Path(sys.argv[1]).read_text())}))'
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2]/'backend'))
    result = subprocess.run([str(a.core_python), '-c', core_script, str(manifest)], env=env, text=True, capture_output=True, timeout=120)
    (a.output_dir/'core-validation.log').write_text(result.stdout+result.stderr); assert result.returncode == 0, result.stderr
    core_results = json.loads(result.stdout); assert len(core_results) == len(exports) and all(row['status'] == 'passed' for row in core_results.values())
    blender_result = a.output_dir/'blender-report.json'
    cmd = [str(a.blender), '--background', '--factory-startup', '--threads', '4', '--python', str(Path(__file__).with_name('check_surface_blender.py')), '--', str(manifest), str(blender_result)]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=180)
    (a.output_dir/'blender.log').write_text(result.stdout+result.stderr); (a.output_dir/'blender.command.json').write_text(json.dumps(cmd, indent=2)+'\n')
    assert result.returncode == 0 and blender_result.exists(), result.stdout+result.stderr
    br = json.loads(blender_result.read_text()); assert len(br['assets']) == len(exports)
    assert not torch.cuda.is_initialized()
    report = {'status': 'passed', 'source_kind': 'synthetic', 'gpu_initialized': torch.cuda.is_initialized(), 'binary_sha256': digest(a.binary), 'reference_sha256': digest(reference), 'prior_artifact_sha256': prior_sources, 'cases': cases, 'comparisons': comparisons, 'negative_cases': negatives, 'process_termination': terminated, 'core_validation': core_results, 'blender': br, 'not_tested': ['CuMesh/nvdiffrast/OpenCV pixel and topology parity', 'trained model and full-width inference', 'Vulkan', 'installed Library and browser', 'rigging']}
    (a.output_dir/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'cases': len(cases), 'comparisons': len(comparisons), 'negative_cases': len(negatives), 'blender_imports': len(exports), 'status': 'passed'}))
    return 0


if __name__ == '__main__': raise SystemExit(main())
