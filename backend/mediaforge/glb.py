"""Bounded, Blender-independent validation for binary glTF 2.0 assets."""

from __future__ import annotations

import json
import math
from pathlib import Path
import struct
from typing import Any

from .paths import contained


GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
MAX_GLB_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_JSON_VALUES = 1_000_000
MAX_JSON_DEPTH = 128
VALIDATION_VERSION = "1.0.0"

ARRAY_LIMITS = {
    "scenes": 4_096,
    "nodes": 100_000,
    "meshes": 100_000,
    "materials": 65_536,
    "images": 65_536,
    "textures": 65_536,
    "samplers": 65_536,
    "accessors": 250_000,
    "bufferViews": 250_000,
    "buffers": 1,
    "skins": 16_384,
    "animations": 16_384,
    "cameras": 16_384,
}
MAX_PRIMITIVES = 200_000

# Additions require a Blender re-import measurement. Unknown required extensions
# fail closed; extensionsUsed remains descriptive unless it is also required.
ALLOWED_REQUIRED_EXTENSIONS: frozenset[str] = frozenset()

COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


class GlbValidationError(ValueError):
    pass


def _integer(value: object, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise GlbValidationError(f"{label} is outside its integer bound")
    if maximum is not None and value > maximum:
        raise GlbValidationError(f"{label} is outside its integer bound")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GlbValidationError(f"{label} must be an object")
    return value


def _array(document: dict[str, Any], name: str) -> list[Any]:
    value = document.get(name, [])
    if not isinstance(value, list) or len(value) > ARRAY_LIMITS[name]:
        raise GlbValidationError(f"{name} exceeds its array bound")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GlbValidationError(f"duplicate JSON member: {key[:80]}")
        value[key] = item
    return value


def _parse_json(content: bytes) -> dict[str, Any]:
    if not content or len(content) > MAX_JSON_BYTES:
        raise GlbValidationError("GLB JSON chunk exceeds its byte bound")
    try:
        text = content.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=lambda token: (_ for _ in ()).throw(GlbValidationError(f"non-finite number: {token}")),
        )
    except GlbValidationError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise GlbValidationError("GLB JSON chunk is invalid UTF-8 JSON") from exc
    document = _object(value, "GLB JSON root")
    stack: list[tuple[object, int]] = [(document, 1)]
    seen = 0
    while stack:
        item, depth = stack.pop()
        seen += 1
        if seen > MAX_JSON_VALUES or depth > MAX_JSON_DEPTH:
            raise GlbValidationError("GLB JSON structure exceeds its bound")
        if isinstance(item, float) and not math.isfinite(item):
            raise GlbValidationError("GLB JSON contains a non-finite number")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return document


def _index(value: object, items: list[Any], label: str) -> int:
    return _integer(value, label, maximum=len(items) - 1)


def _element_bytes(component_bytes: int, accessor_type: str) -> int:
    if not accessor_type.startswith("MAT"):
        return component_bytes * TYPE_COMPONENTS[accessor_type]
    columns = rows = int(accessor_type[-1])
    column_bytes = rows * component_bytes
    aligned_column_bytes = (column_bytes + 3) // 4 * 4
    return columns * aligned_column_bytes


def _bounded_extensions(document: dict[str, Any]) -> tuple[list[str], list[str]]:
    def names(field: str) -> list[str]:
        value = document.get(field, [])
        if not isinstance(value, list) or len(value) > 256:
            raise GlbValidationError(f"{field} exceeds its array bound")
        if any(not isinstance(item, str) or not 1 <= len(item) <= 128 for item in value):
            raise GlbValidationError(f"{field} contains an invalid name")
        if len(set(value)) != len(value):
            raise GlbValidationError(f"{field} contains duplicate names")
        return value

    used = names("extensionsUsed")
    required = names("extensionsRequired")
    if not set(required).issubset(used):
        raise GlbValidationError("extensionsRequired is not a subset of extensionsUsed")
    unsupported = sorted(set(required) - ALLOWED_REQUIRED_EXTENSIONS)
    if unsupported:
        raise GlbValidationError(f"required extension is not allowed: {unsupported[0]}")
    return used, required


def _validate_document(document: dict[str, Any], binary: bytes | None) -> dict[str, int]:
    asset = _object(document.get("asset"), "asset")
    if asset.get("version") != "2.0":
        raise GlbValidationError("glTF asset.version must be 2.0")

    arrays = {name: _array(document, name) for name in ARRAY_LIMITS}
    buffers = arrays["buffers"]
    if binary is None:
        if buffers:
            raise GlbValidationError("GLB declares a buffer without a BIN chunk")
        binary_length = 0
    else:
        if len(buffers) != 1:
            raise GlbValidationError("GLB BIN chunk requires exactly one buffer")
        buffer = _object(buffers[0], "buffers[0]")
        if "uri" in buffer:
            raise GlbValidationError("external buffer URI is not allowed")
        declared = _integer(buffer.get("byteLength"), "buffers[0].byteLength", minimum=1, maximum=MAX_GLB_BYTES)
        if not declared <= len(binary) <= declared + 3:
            raise GlbValidationError("BIN chunk length differs from buffers[0].byteLength")
        binary_length = declared

    buffer_views = arrays["bufferViews"]
    view_facts: list[tuple[int, int, int | None]] = []
    for index, raw in enumerate(buffer_views):
        view = _object(raw, f"bufferViews[{index}]")
        _index(view.get("buffer"), buffers, f"bufferViews[{index}].buffer")
        offset = _integer(view.get("byteOffset", 0), f"bufferViews[{index}].byteOffset")
        length = _integer(view.get("byteLength"), f"bufferViews[{index}].byteLength", minimum=1)
        if offset + length > binary_length:
            raise GlbValidationError(f"bufferViews[{index}] escapes its buffer")
        stride_value = view.get("byteStride")
        stride = None if stride_value is None else _integer(
            stride_value, f"bufferViews[{index}].byteStride", minimum=4, maximum=252
        )
        if stride is not None and stride % 4:
            raise GlbValidationError(f"bufferViews[{index}].byteStride is not 4-byte aligned")
        view_facts.append((offset, length, stride))

    accessors = arrays["accessors"]
    for index, raw in enumerate(accessors):
        accessor = _object(raw, f"accessors[{index}]")
        if "sparse" in accessor:
            raise GlbValidationError(f"accessors[{index}].sparse is not accepted by the B1 boundary")
        count = _integer(accessor.get("count"), f"accessors[{index}].count", minimum=1, maximum=10_000_000)
        component_type = accessor.get("componentType")
        accessor_type = accessor.get("type")
        if component_type not in COMPONENT_BYTES or accessor_type not in TYPE_COMPONENTS:
            raise GlbValidationError(f"accessors[{index}] has an unsupported component layout")
        element_bytes = _element_bytes(COMPONENT_BYTES[component_type], accessor_type)
        offset = _integer(accessor.get("byteOffset", 0), f"accessors[{index}].byteOffset")
        if offset % COMPONENT_BYTES[component_type]:
            raise GlbValidationError(f"accessors[{index}].byteOffset is misaligned")
        if "bufferView" not in accessor:
            raise GlbValidationError(f"accessors[{index}] has no bufferView")
        view_index = _index(accessor["bufferView"], buffer_views, f"accessors[{index}].bufferView")
        _, view_length, stride = view_facts[view_index]
        step = stride or element_bytes
        if step < element_bytes or offset + (count - 1) * step + element_bytes > view_length:
            raise GlbValidationError(f"accessors[{index}] escapes its bufferView")

    images = arrays["images"]
    for index, raw in enumerate(images):
        image = _object(raw, f"images[{index}]")
        if "uri" in image:
            raise GlbValidationError("external image URI is not allowed")
        if "bufferView" not in image:
            raise GlbValidationError(f"images[{index}] is not embedded")
        _index(image["bufferView"], buffer_views, f"images[{index}].bufferView")
        if image.get("mimeType") not in {"image/jpeg", "image/png", "image/webp", "image/ktx2"}:
            raise GlbValidationError(f"images[{index}].mimeType is unsupported")

    primitives = 0
    for mesh_index, raw in enumerate(arrays["meshes"]):
        mesh = _object(raw, f"meshes[{mesh_index}]")
        mesh_primitives = mesh.get("primitives")
        if not isinstance(mesh_primitives, list) or not mesh_primitives:
            raise GlbValidationError(f"meshes[{mesh_index}].primitives is invalid")
        primitives += len(mesh_primitives)
        if primitives > MAX_PRIMITIVES:
            raise GlbValidationError("mesh primitive count exceeds its bound")
        for primitive_index, raw_primitive in enumerate(mesh_primitives):
            primitive = _object(raw_primitive, f"meshes[{mesh_index}].primitives[{primitive_index}]")
            attributes = _object(primitive.get("attributes"), "primitive attributes")
            if not attributes:
                raise GlbValidationError("mesh primitive has no attributes")
            for semantic, accessor_index in attributes.items():
                if not isinstance(semantic, str) or len(semantic) > 128:
                    raise GlbValidationError("mesh attribute semantic is invalid")
                _index(accessor_index, accessors, f"attribute {semantic}")
            if "indices" in primitive:
                _index(primitive["indices"], accessors, "primitive indices")
            if "material" in primitive:
                _index(primitive["material"], arrays["materials"], "primitive material")

    node_children: list[list[int]] = []
    parent_counts = [0] * len(arrays["nodes"])
    has_parent = [False] * len(arrays["nodes"])
    for index, raw in enumerate(arrays["nodes"]):
        node = _object(raw, f"nodes[{index}]")
        if "mesh" in node:
            _index(node["mesh"], arrays["meshes"], f"nodes[{index}].mesh")
        children = node.get("children", [])
        if not isinstance(children, list) or len(children) > len(arrays["nodes"]):
            raise GlbValidationError(f"nodes[{index}].children is invalid")
        indexed_children: list[int] = []
        for child in children:
            child_index = _index(child, arrays["nodes"], f"nodes[{index}].children")
            indexed_children.append(child_index)
            parent_counts[child_index] += 1
            has_parent[child_index] = True
            if parent_counts[child_index] > 1:
                raise GlbValidationError(f"nodes[{child_index}] has multiple parents")
        node_children.append(indexed_children)

    pending = [index for index, parents in enumerate(parent_counts) if parents == 0]
    visited = 0
    while pending:
        node_index = pending.pop()
        visited += 1
        for child_index in node_children[node_index]:
            parent_counts[child_index] -= 1
            if parent_counts[child_index] == 0:
                pending.append(child_index)
    if visited != len(node_children):
        raise GlbValidationError("node hierarchy contains a cycle")

    for index, raw in enumerate(arrays["scenes"]):
        scene = _object(raw, f"scenes[{index}]")
        nodes = scene.get("nodes", [])
        if not isinstance(nodes, list) or len(nodes) > len(arrays["nodes"]):
            raise GlbValidationError(f"scenes[{index}].nodes is invalid")
        for node in nodes:
            node_index = _index(node, arrays["nodes"], f"scenes[{index}].nodes")
            if has_parent[node_index]:
                raise GlbValidationError(f"scenes[{index}] references a non-root node")
    if "scene" in document:
        _index(document["scene"], arrays["scenes"], "scene")

    return {**{name: len(values) for name, values in arrays.items()}, "primitives": primitives}


def validate_glb(content: bytes) -> dict[str, Any]:
    if not content or len(content) > MAX_GLB_BYTES:
        raise GlbValidationError("GLB import must be between 1 byte and 64 MiB")
    if len(content) < 20:
        raise GlbValidationError("GLB header is truncated")
    magic, version, declared_length = struct.unpack_from("<4sII", content)
    if magic != GLB_MAGIC or version != GLB_VERSION:
        raise GlbValidationError("GLB magic or version is invalid")
    if declared_length != len(content):
        raise GlbValidationError("GLB declared length differs")

    offset = 12
    chunks: list[tuple[int, bytes]] = []
    while offset < len(content):
        if offset + 8 > len(content):
            raise GlbValidationError("GLB chunk header is truncated")
        length, chunk_type = struct.unpack_from("<II", content, offset)
        offset += 8
        if length % 4 or offset + length > len(content):
            raise GlbValidationError("GLB chunk escapes or is not aligned")
        chunks.append((chunk_type, content[offset : offset + length]))
        offset += length
    if not chunks or chunks[0][0] != JSON_CHUNK:
        raise GlbValidationError("GLB first chunk must be JSON")
    if len(chunks) > 2 or any(kind not in {JSON_CHUNK, BIN_CHUNK} for kind, _ in chunks):
        raise GlbValidationError("GLB contains an unknown or duplicate chunk")
    if sum(kind == JSON_CHUNK for kind, _ in chunks) != 1 or sum(kind == BIN_CHUNK for kind, _ in chunks) > 1:
        raise GlbValidationError("GLB contains a duplicate chunk")
    if len(chunks) == 2 and chunks[1][0] != BIN_CHUNK:
        raise GlbValidationError("GLB second chunk must be BIN")

    document = _parse_json(chunks[0][1])
    used, required = _bounded_extensions(document)
    counts = _validate_document(document, chunks[1][1] if len(chunks) == 2 else None)
    return {
        "validator": "glb.structure",
        "status": "passed",
        "validation_version": VALIDATION_VERSION,
        "size_bytes": len(content),
        "json_bytes": len(chunks[0][1]),
        "bin_bytes": len(chunks[1][1]) if len(chunks) == 2 else 0,
        "counts": counts,
        "required_extensions": required,
        "used_extension_count": len(used),
    }


def validate_glb_path(path: Path, allowed_root: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GlbValidationError("GLB path is not a regular file")
    safe = contained(allowed_root, path)
    if safe.stat().st_size > MAX_GLB_BYTES:
        raise GlbValidationError("GLB file exceeds the 64 MiB bound")
    return validate_glb(safe.read_bytes())
