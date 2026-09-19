"""Independent Blender CPU import acceptance; run through Blender --python."""
from __future__ import annotations
import json
from pathlib import Path
import struct
import sys
import bpy
import numpy as np


def main() -> None:
    manifest, destination = map(Path, sys.argv[sys.argv.index('--')+1:])
    assets = []
    for path in json.loads(manifest.read_text()):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        result = bpy.ops.import_scene.gltf(filepath=path)
        assert result == {'FINISHED'}
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        assert len(meshes) == 1 and not any(o.type == 'ARMATURE' for o in bpy.context.scene.objects)
        mesh = meshes[0].data; mesh.calc_loop_triangles()
        expected = json.loads((Path(path).parent/'report.json').read_text())
        assert len(mesh.loop_triangles) == expected['atlas_faces'] and len(mesh.uv_layers) == 1
        assert len(mesh.materials) == 1
        images = [node.image for node in mesh.materials[0].node_tree.nodes if node.type == 'TEX_IMAGE']
        assert len(images) == 2 and all(tuple(im.size) == (128, 128) for im in images)
        raw = Path(path).read_bytes(); js = struct.unpack_from('<I', raw, 12)[0]
        doc = json.loads(raw[20:20+js]); binary = raw[28+js:]
        accessor = doc['accessors'][0]; view = doc['bufferViews'][accessor['bufferView']]
        positions = np.frombuffer(binary, dtype='<f4', count=accessor['count']*3, offset=view.get('byteOffset', 0)).reshape(-1, 3)
        # Blender maps glTF Y-up to Z-up by (x,-z,y); importer can split vertices.
        target = positions[:, [0, 2, 1]]*np.array([1, -1, 1])
        actual = np.array([tuple(meshes[0].matrix_world@v.co) for v in mesh.vertices])
        np.testing.assert_allclose(actual.min(0), target.min(0), atol=2e-6, rtol=0)
        np.testing.assert_allclose(actual.max(0), target.max(0), atol=2e-6, rtol=0)
        principled = next(n for n in mesh.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        assert all(principled.inputs[name].is_linked for name in ('Base Color', 'Metallic', 'Roughness'))
        assets.append({'path': path, 'triangles': len(mesh.loop_triangles), 'vertices': len(mesh.vertices), 'uv_layers': len(mesh.uv_layers), 'images': [{'size': list(im.size), 'colorspace': im.colorspace_settings.name} for im in images], 'bounds': [actual.min(0).tolist(), actual.max(0).tolist()], 'material_channels_linked': True, 'armatures': 0})
    destination.write_text(json.dumps({'version': bpy.app.version_string, 'assets': assets}, indent=2)+'\n')


if __name__ == '__main__': main()
