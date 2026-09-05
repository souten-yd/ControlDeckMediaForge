# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted Blender operator for bounded material inspection and image binding."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy


MAX_TARGETS = 2_000
MAX_SLOTS = 256
MAX_UV_MAPS = 64
CHANNELS = {"base_color", "roughness", "metallic", "normal", "emission"}
WRAP = {"repeat": "REPEAT", "extend": "EXTEND", "clip": "CLIP"}
FIXED_FILES = {
    "source": "scene.blend",
    "texture": "texture.png",
    "binding": "binding.json",
    "output": "bound.blend",
    "result": "result.json",
}


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("inspect", "apply"), required=True)
    parser.add_argument("--source", choices=(FIXED_FILES["source"],), required=True)
    parser.add_argument("--result", choices=(FIXED_FILES["result"],), required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--texture", choices=(FIXED_FILES["texture"],))
    parser.add_argument("--binding", choices=(FIXED_FILES["binding"],))
    parser.add_argument("--output", choices=(FIXED_FILES["output"],))
    return parser.parse_args(values)


def read_binding(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "source_revision_id", "image_asset_id", "object_name", "material_slot", "channel",
        "uv_map", "wrap", "color_space", "normal_convention", "texture_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise RuntimeError("material binding fields differ")
    if value["schema_version"] != "media-forge.material-binding@1":
        raise RuntimeError("material binding version differs")
    if value["channel"] not in CHANNELS or value["wrap"] not in WRAP:
        raise RuntimeError("material binding option is invalid")
    if (
        not isinstance(value["source_revision_id"], str)
        or not value["source_revision_id"].startswith("revision_")
        or len(value["source_revision_id"]) != 41
        or not isinstance(value["image_asset_id"], str)
        or not value["image_asset_id"].startswith("asset_")
        or len(value["image_asset_id"]) != 38
        or not isinstance(value["object_name"], str)
        or not 1 <= len(value["object_name"]) <= 128
        or isinstance(value["material_slot"], bool)
        or not isinstance(value["material_slot"], int)
        or not 0 <= value["material_slot"] <= 255
        or not isinstance(value["uv_map"], str)
        or not 1 <= len(value["uv_map"]) <= 128
        or value["color_space"] not in {"srgb", "non_color"}
        or value["normal_convention"] not in {"open_gl", "direct_x"}
        or not isinstance(value["texture_sha256"], str)
        or len(value["texture_sha256"]) != 64
    ):
        raise RuntimeError("material binding value is invalid")
    expects_color = value["channel"] in {"base_color", "emission"}
    if expects_color != (value["color_space"] == "srgb"):
        raise RuntimeError("material color space differs")
    if value["channel"] != "normal" and value["normal_convention"] != "open_gl":
        raise RuntimeError("material normal convention differs")
    return value


def material_targets() -> list[dict[str, object]]:
    targets: list[dict[str, object]] = []
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        if obj.type != "MESH":
            continue
        if len(targets) >= MAX_TARGETS:
            raise RuntimeError("material target count exceeds its bound")
        slots = [
            {"index": index, "name": slot.material.name if slot.material is not None else ""}
            for index, slot in enumerate(obj.material_slots)
        ]
        if not slots:
            slots = [{"index": 0, "name": ""}]
        if len(slots) > MAX_SLOTS:
            raise RuntimeError("material slot count exceeds its bound")
        uv_maps = [layer.name for layer in obj.data.uv_layers]
        if len(uv_maps) > MAX_UV_MAPS:
            raise RuntimeError("UV map count exceeds its bound")
        targets.append({"object_name": obj.name, "material_slots": slots, "uv_maps": uv_maps})
    return targets


def principled(material: bpy.types.Material) -> bpy.types.ShaderNodeBsdfPrincipled:
    material.use_nodes = True
    nodes = material.node_tree.nodes
    shader = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        shader = nodes.new("ShaderNodeBsdfPrincipled")
        output = next((node for node in nodes if node.type == "OUTPUT_MATERIAL"), None)
        if output is None:
            output = nodes.new("ShaderNodeOutputMaterial")
        material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return shader


def clear_channel_nodes(material: bpy.types.Material, channel: str) -> None:
    nodes = material.node_tree.nodes
    for node in list(nodes):
        if node.get("mediaforge_channel") == channel:
            nodes.remove(node)


def tagged_node(material: bpy.types.Material, kind: str, channel: str):
    node = material.node_tree.nodes.new(kind)
    node["mediaforge_channel"] = channel
    return node


def bind_texture(root: Path, binding: dict[str, object]) -> dict[str, object]:
    object_name = str(binding["object_name"])
    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise RuntimeError("material target object is unavailable")
    slot_index = int(binding["material_slot"])
    if slot_index < 0 or slot_index >= max(1, len(obj.material_slots)):
        raise RuntimeError("material slot is unavailable")
    uv_maps = obj.data.uv_layers
    requested_uv = binding["uv_map"]
    uv = uv_maps.get(str(requested_uv)) if requested_uv is not None else uv_maps.active
    if uv is None:
        raise RuntimeError("material target has no selected UV map")

    if not obj.material_slots:
        obj.data.materials.append(bpy.data.materials.new(name="MediaForge Material"))
    current = obj.material_slots[slot_index].material
    managed_target = f"{obj.name}:{slot_index}"
    if current is not None and current.get("mediaforge_managed_target") == managed_target:
        material = current
    else:
        material = (
            current.copy()
            if current is not None
            else bpy.data.materials.new(name="MediaForge Material")
        )
        if "· MediaForge" not in material.name:
            material.name = f"{material.name[:48]} · MediaForge"
        material["mediaforge_managed_target"] = managed_target
    obj.material_slots[slot_index].material = material
    shader = principled(material)
    channel = str(binding["channel"])
    clear_channel_nodes(material, channel)

    texture_path = root / FIXED_FILES["texture"]
    digest = hashlib.sha256(texture_path.read_bytes()).hexdigest()
    if digest != binding["texture_sha256"]:
        raise RuntimeError("material texture identity changed")
    color_space = "sRGB" if binding["color_space"] == "srgb" else "Non-Color"
    image = next(
        (
            candidate
            for candidate in bpy.data.images
            if candidate.get("mediaforge_asset_sha256") == digest
            and candidate.colorspace_settings.name == color_space
            and candidate.packed_file is not None
        ),
        None,
    )
    if image is None:
        image = bpy.data.images.load(str(texture_path), check_existing=False)
        image.name = f"MediaForge {digest[:12]}"
        image.colorspace_settings.name = color_space
        image["mediaforge_asset_sha256"] = digest
        image.pack()

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    texture = tagged_node(material, "ShaderNodeTexImage", channel)
    texture.label = f"Media Forge {channel}"
    texture.image = image
    texture.extension = WRAP[str(binding["wrap"])]
    uv_node = tagged_node(material, "ShaderNodeUVMap", channel)
    uv_node.uv_map = uv.name
    links.new(uv_node.outputs["UV"], texture.inputs["Vector"])

    socket_name = {
        "base_color": "Base Color",
        "roughness": "Roughness",
        "metallic": "Metallic",
        "emission": "Emission Color",
    }.get(channel)
    if socket_name is not None:
        links.new(texture.outputs["Color"], shader.inputs[socket_name])
    else:
        normal_color = texture.outputs["Color"]
        if binding["normal_convention"] == "direct_x":
            separate = tagged_node(material, "ShaderNodeSeparateColor", channel)
            invert = tagged_node(material, "ShaderNodeMath", channel)
            combine = tagged_node(material, "ShaderNodeCombineColor", channel)
            invert.operation = "SUBTRACT"
            invert.inputs[0].default_value = 1.0
            links.new(texture.outputs["Color"], separate.inputs["Color"])
            links.new(separate.outputs["Red"], combine.inputs["Red"])
            links.new(separate.outputs["Green"], invert.inputs[1])
            links.new(invert.outputs[0], combine.inputs["Green"])
            links.new(separate.outputs["Blue"], combine.inputs["Blue"])
            normal_color = combine.outputs["Color"]
        normal = tagged_node(material, "ShaderNodeNormalMap", channel)
        normal.uv_map = uv.name
        links.new(normal_color, normal.inputs["Color"])
        links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    material[f"mediaforge_{channel}_asset_sha256"] = digest
    return {
        "object_name": obj.name,
        "material_slot": slot_index,
        "material_name": material.name,
        "channel": channel,
        "uv_map": uv.name,
        "packed": image.packed_file is not None,
        "texture_sha256": digest,
    }


def main() -> None:
    args = arguments()
    expected = tuple(int(part) for part in args.expected_version.split("."))
    if tuple(bpy.app.version[:3]) != expected or not bpy.app.background:
        raise RuntimeError("Blender material worker runtime identity differs")
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    root = Path.cwd()
    bpy.ops.wm.open_mainfile(
        filepath=str(root / args.source), load_ui=False, use_scripts=False
    )
    result: dict[str, object] = {
        "schema_version": "media-forge.material-operation-result@1",
        "blender_version": args.expected_version,
        "background": True,
        "autoexec_disabled": not bpy.context.preferences.filepaths.use_scripts_auto_execute,
        "action": args.action,
    }
    if args.action == "inspect":
        if args.texture or args.binding or args.output:
            raise RuntimeError("inspect material arguments differ")
        result["targets"] = material_targets()
        result["binding"] = None
    else:
        if not args.texture or not args.binding or not args.output:
            raise RuntimeError("apply material arguments differ")
        binding = read_binding(root / args.binding)
        result["binding"] = bind_texture(root, binding)
        result["targets"] = None
        # SceneWorkspace intentionally accepts only the canonical BLENDER header.
        # Blender's compressed save is gzip-wrapped and would bypass that shared
        # immutable-revision validation path.
        bpy.ops.wm.save_as_mainfile(filepath=str(root / args.output), compress=False)
    (root / args.result).write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
