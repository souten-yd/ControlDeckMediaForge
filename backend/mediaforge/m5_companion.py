from __future__ import annotations

import hashlib
import io
import json
import re
import struct
import sys
import zipfile
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .config import REPOSITORY_ROOT


CANVAS = (1280, 960)
DEVICE_CANVAS = (320, 240)
SAFE_RECT = (40, 40, 1240, 736)
EYE_RECT = (384, 328, 896, 504)
MOUTH_RECT = (512, 496, 768, 656)
PUPIL_ANCHORS = ((544, 448), (736, 448))
EYE_SLOTS = (
    "open_center", "open_left", "open_right", "open_up", "open_down",
    "soft_lower", "half", "almost_closed", "closed", "wide",
    "sleepy_half", "sleepy_closed",
)
MOUTH_SLOTS = (
    "rest", "tiny", "small", "medium", "wide", "rounded",
    "smile_closed", "smile_open",
)
PROFILE_IDS = (
    "m5.companion.base", "m5.companion.eyes", "m5.companion.mouth",
    "m5.companion.expression", "m5.companion.pose", "m5.companion.pack",
)
PROFILE_ROOT = REPOSITORY_ROOT / "profiles" / "m5"
PACK_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class M5CompanionError(ValueError):
    pass


@dataclass(frozen=True)
class PackEntry:
    asset_id: str
    name: str
    layer: str

    @property
    def archive_name(self) -> str:
        directory = "mouths" if self.layer == "mouth" else self.layer
        return f"{directory}/{self.name}.png"


def is_m5_profile(profile: str | None) -> bool:
    return profile in PROFILE_IDS


def profile_documents(root: Path = PROFILE_ROOT) -> list[dict[str, Any]]:
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.json"))]
    if tuple(sorted(str(item.get("id")) for item in documents)) != tuple(sorted(PROFILE_IDS)):
        raise M5CompanionError("bundled M5 companion profile catalog is incomplete")
    return documents


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").point(lambda value: 255 if value > 40 else 0).getbbox()
    if bbox is None:
        raise M5CompanionError("M5 companion asset is empty")
    return bbox


def _inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    return (
        inner[0] >= outer[0] and inner[1] >= outer[1]
        and inner[2] <= outer[2] and inner[3] <= outer[3]
    )


def _pupil_centers(image: Image.Image) -> tuple[tuple[float, float], tuple[float, float]]:
    pixels = image.load()
    centers: list[tuple[float, float]] = []
    for x0, x1 in ((EYE_RECT[0], 640), (640, EYE_RECT[2])):
        points: list[tuple[int, int]] = []
        for y in range(EYE_RECT[1], EYE_RECT[3]):
            for x in range(x0, x1):
                red, green, blue, alpha = pixels[x, y]
                if alpha > 60 and blue - red > 6 and 90 < red + green + blue < 600:
                    points.append((x, y))
        if len(points) < 40:
            raise M5CompanionError("M5 companion open eyes do not contain two measurable pupils")
        centers.append((
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        ))
    return centers[0], centers[1]


def validate_image(
    path: Path,
    profile: str,
    *,
    require_pupil_anchors: bool = False,
) -> list[dict[str, Any]]:
    if profile not in PROFILE_IDS or profile == "m5.companion.pack":
        raise M5CompanionError("unsupported M5 companion image profile")
    with Image.open(path) as opened:
        opened.load()
        if opened.format != "PNG" or opened.mode != "RGBA" or opened.size != CANVAS:
            raise M5CompanionError("M5 companion assets must be exact 1280x960 RGBA PNG")
        image = opened.copy()
    alpha = image.getchannel("A")
    minimum, maximum = alpha.getextrema()
    if minimum != 0 or maximum == 0:
        raise M5CompanionError("M5 companion assets require real transparency and non-empty content")
    histogram = alpha.histogram()
    faint_pixels = sum(histogram[5:41])
    if faint_pixels / (CANVAS[0] * CANVAS[1]) > 0.25:
        raise M5CompanionError("M5 companion background contains a low-alpha wash")
    bbox = _alpha_bbox(image)
    allowed = SAFE_RECT
    anchors: list[list[int]] = []
    if profile == "m5.companion.eyes":
        allowed = EYE_RECT
        anchors = [list(point) for point in PUPIL_ANCHORS]
    elif profile == "m5.companion.mouth":
        allowed = MOUTH_RECT
        anchors = [[640, 576]]
    elif profile == "m5.companion.pose":
        allowed = (40, 40, 1240, 920)
    if not _inside(bbox, allowed):
        raise M5CompanionError(f"M5 companion content bounds {bbox} escape allowed rectangle {allowed}")
    measured_anchors: list[list[float]] = []
    if require_pupil_anchors:
        centers = _pupil_centers(image)
        for measured, expected in zip(centers, PUPIL_ANCHORS, strict=True):
            if abs(measured[0] - expected[0]) > 4 or abs(measured[1] - expected[1]) > 4:
                raise M5CompanionError(
                    f"M5 companion pupil center {measured} is not registered to anchor {expected}"
                )
        measured_anchors = [[round(value, 3) for value in point] for point in centers]
    return [{
        "validator": "m5.companion.profile",
        "status": "passed",
        "profile": profile,
        "canvas": list(CANVAS),
        "content_bounds": list(bbox),
        "safe_rectangle": list(allowed),
        "anchors": anchors,
        "measured_anchors": measured_anchors,
        "transparent_background": True,
    }]


def validate_edit_mask(path: Path, profile: str, *, max_change_fraction: float = 0.20) -> dict[str, Any]:
    allowed = {
        "m5.companion.eyes": EYE_RECT,
        "m5.companion.mouth": MOUTH_RECT,
        "m5.companion.expression": SAFE_RECT,
        "m5.companion.base": SAFE_RECT,
        "m5.companion.pose": (40, 40, 1240, 920),
    }.get(profile)
    if allowed is None:
        raise M5CompanionError("M5 companion profile does not accept an edit mask")
    with Image.open(path) as opened:
        opened.load()
        if opened.size != CANVAS:
            raise M5CompanionError("M5 companion edit masks must match the 1280x960 canvas")
        alpha = opened.convert("RGBA").getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None or not _inside(bbox, allowed):
        raise M5CompanionError("M5 companion edit mask escapes its profile layer boundary")
    changed = sum(alpha.histogram()[1:])
    fraction = changed / (CANVAS[0] * CANVAS[1])
    if fraction > max_change_fraction:
        raise M5CompanionError("M5 companion edit mask exceeds the maximum change area")
    return {
        "validator": "m5.companion.edit_mask",
        "status": "passed",
        "bounds": list(bbox),
        "maximum_change_fraction": max_change_fraction,
        "change_fraction": fraction,
    }


def parse_pack_entries(value: Any) -> list[PackEntry]:
    if not isinstance(value, list) or len(value) != 1 + len(EYE_SLOTS) + len(MOUTH_SLOTS):
        raise M5CompanionError("M5 companion pack requires one base, 12 eyes, and 8 mouths")
    entries: list[PackEntry] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"asset_id", "layer", "name"}:
            raise M5CompanionError("M5 companion pack entries require asset_id, layer, and name")
        asset_id, layer, name = item["asset_id"], item["layer"], item["name"]
        if not isinstance(asset_id, str) or not re.fullmatch(r"asset_[0-9a-f]{32}", asset_id):
            raise M5CompanionError("M5 companion pack entry has an invalid asset ID")
        if layer not in {"base", "eyes", "mouth"} or not isinstance(name, str):
            raise M5CompanionError("M5 companion pack entry has an invalid layer or name")
        entries.append(PackEntry(asset_id=asset_id, layer=layer, name=name))
    expected = {("base", "front")}
    expected.update(("eyes", name) for name in EYE_SLOTS)
    expected.update(("mouth", name) for name in MOUTH_SLOTS)
    actual = {(entry.layer, entry.name) for entry in entries}
    if actual != expected or len(actual) != len(entries):
        raise M5CompanionError("M5 companion pack filenames do not match the fixed runtime slots")
    return sorted(entries, key=lambda entry: entry.archive_name)


def _rgb565be(image: Image.Image) -> bytes:
    values = array("H")
    values.extend(
        ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        for red, green, blue in image.convert("RGB").get_flattened_data()
    )
    if sys.byteorder == "little":
        values.byteswap()
    return values.tobytes()


def _m5a(frames: list[Image.Image], *, fps: int = 0) -> bytes:
    if not frames or any(frame.size != frames[0].size for frame in frames):
        raise M5CompanionError("M5A frames must be non-empty and have one geometry")
    width, height = frames[0].size
    frame_bytes = width * height * 2
    header = struct.pack(
        "<IHHHHHHIB3sII",
        0x3141354D,
        1,
        0,
        width,
        height,
        len(frames),
        fps,
        frame_bytes,
        0,
        b"\0\0\0",
        0,
        0,
    )
    if len(header) != 32:
        raise AssertionError("M5A header size changed")
    return header + b"".join(_rgb565be(frame) for frame in frames)


def _device_pack(
    pack_name: str,
    full_images: dict[tuple[str, str], Image.Image],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    backdrop = Image.new("RGBA", CANVAS, (10, 13, 17, 255))
    base_layer = full_images[("base", "front")]
    base = Image.alpha_composite(backdrop, base_layer)
    base_frame = base.convert("RGB").resize(DEVICE_CANVAS, Image.Resampling.LANCZOS)
    eye_frames = [
        Image.alpha_composite(base, full_images[("eyes", name)])
        .crop(EYE_RECT)
        .convert("RGB")
        .resize((128, 44), Image.Resampling.LANCZOS)
        for name in EYE_SLOTS
    ]
    with_open_eyes = Image.alpha_composite(base, full_images[("eyes", "open_center")])
    mouth_frames = [
        Image.alpha_composite(with_open_eyes, full_images[("mouth", name)])
        .crop(MOUTH_RECT)
        .convert("RGB")
        .resize((64, 40), Image.Resampling.LANCZOS)
        for name in MOUTH_SLOTS
    ]
    root = f"companion/packs/{pack_name}"
    files = {
        f"{root}/base/neutral.m5a": _m5a([base_frame]),
        f"{root}/eyes/neutral.m5a": _m5a(eye_frames),
        f"{root}/mouth/neutral.m5a": _m5a(mouth_frames),
    }
    manifest = {
        "pack": pack_name,
        "character": pack_name,
        "version": 2,
        "format": "rgb565be",
        "theme": "dark",
        "screen": {"w": 320, "h": 240},
        "eye_center": {"x": 160, "y": 112},
        "sway_rect": {"x": 0, "y": 0, "w": 0, "h": 0},
        "eye_rect": {"x": 96, "y": 82, "w": 128, "h": 44},
        "mouth_rect": {"x": 128, "y": 124, "w": 64, "h": 40},
        "sway_frames": 1,
        "eye_slots": list(EYE_SLOTS),
        "viseme_frames": len(MOUTH_SLOTS),
        "visemes": list(MOUTH_SLOTS),
        "expressions": {
            "neutral": {
                "base": "base/neutral.m5a",
                "sway": "",
                "eyes": "eyes/neutral.m5a",
                "mouth": "mouth/neutral.m5a",
            }
        },
        "clips": {},
    }
    manifest_content = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    files[f"{root}/manifest.json"] = manifest_content
    return manifest, files


def build_pack(
    output: Path,
    *,
    pack_name: str,
    entries: list[PackEntry],
    asset_paths: dict[str, Path],
    asset_hashes: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not PACK_NAME.fullmatch(pack_name):
        raise M5CompanionError("M5 companion pack name must be lowercase snake case")
    validations: list[dict[str, Any]] = []
    images: list[tuple[PackEntry, Image.Image]] = []
    full_images: dict[tuple[str, str], Image.Image] = {}
    for entry in entries:
        profile = {
            "base": "m5.companion.base",
            "eyes": "m5.companion.eyes",
            "mouth": "m5.companion.mouth",
        }[entry.layer]
        validations.extend(validate_image(
            asset_paths[entry.asset_id],
            profile,
            require_pupil_anchors=entry.layer == "eyes" and entry.name == "open_center",
        ))
        with Image.open(asset_paths[entry.asset_id]) as opened:
            full = opened.convert("RGBA")
            full_images[(entry.layer, entry.name)] = full.copy()
            images.append((entry, full.resize(DEVICE_CANVAS, Image.Resampling.LANCZOS)))

    columns = 4
    rows = (len(images) + columns - 1) // columns
    atlas = Image.new("RGBA", (DEVICE_CANVAS[0] * columns, DEVICE_CANVAS[1] * rows), (0, 0, 0, 0))
    manifest_entries: list[dict[str, Any]] = []
    for index, (entry, image) in enumerate(images):
        x = (index % columns) * DEVICE_CANVAS[0]
        y = (index // columns) * DEVICE_CANVAS[1]
        atlas.alpha_composite(image, (x, y))
        manifest_entries.append({
            "name": entry.archive_name,
            "asset_id": entry.asset_id,
            "sha256": asset_hashes[entry.asset_id],
            "atlas_rect": [x, y, DEVICE_CANVAS[0], DEVICE_CANVAS[1]],
        })
    atlas_bytes = io.BytesIO()
    atlas.save(atlas_bytes, format="PNG", optimize=False, compress_level=9)
    atlas_content = atlas_bytes.getvalue()
    device_manifest, device_files = _device_pack(pack_name, full_images)
    manifest = {
        "schema_version": "1.0",
        "profile": "m5.companion.pack",
        "name": pack_name,
        "source_canvas": {"width": CANVAS[0], "height": CANVAS[1], "mode": "RGBA"},
        "device_canvas": {"width": DEVICE_CANVAS[0], "height": DEVICE_CANVAS[1]},
        "registration": {
            "face_center_x": 640,
            "pupil_centers": [list(point) for point in PUPIL_ANCHORS],
            "mouth_center": [640, 576],
            "safe_rectangle": list(SAFE_RECT),
        },
        "eye_slots": list(EYE_SLOTS),
        "mouth_slots": list(MOUTH_SLOTS),
        "atlas": {"name": "atlas.png", "width": atlas.width, "height": atlas.height,
                  "sha256": hashlib.sha256(atlas_content).hexdigest()},
        "device_pack": {
            "root": f"companion/packs/{pack_name}",
            "format": "m5a-rgb565be-v1",
            "manifest": device_manifest,
            "files": [
                {"name": name, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
                for name, content in sorted(device_files.items())
            ],
        },
        "entries": manifest_entries,
    }
    manifest_content = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in [("manifest.json", manifest_content), ("atlas.png", atlas_content)]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        for name, content in sorted(device_files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        for entry in entries:
            info = zipfile.ZipInfo(entry.archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info,
                asset_paths[entry.asset_id].read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    validations.append({
        "validator": "m5.companion.pack",
        "status": "passed",
        "entry_count": len(entries),
        "expected_filenames": [entry.archive_name for entry in entries],
        "manifest_schema_version": "1.0",
        "atlas_sha256": manifest["atlas"]["sha256"],
        "device_pack_files": len(device_files),
        "device_format": "m5a-rgb565be-v1",
        "reproducible_zip": True,
    })
    return manifest, validations
