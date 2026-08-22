from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Literal, Mapping

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field

from .creative import CreativeCompiler, CreativeSpec, CreativeValidationError
from .domain import JobRequest


class LayoutSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template: Literal["poster", "character_sheet"]
    title: str = Field(default="", max_length=120)
    caption: str = Field(default="", max_length=500)
    shot_count: int = Field(ge=2, le=4)


class CreativeCompositionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^composition_[0-9a-f]{32}$")
    layout: LayoutSpec
    layout_snapshot: dict[str, Any]
    child_plans: list[dict[str, Any]]
    child_job_ids: list[str] = Field(default_factory=list)
    final_asset_ids: list[str] = Field(default_factory=list)
    submission_errors: list[dict[str, str]] = Field(default_factory=list)
    composition_error: dict[str, str] | None = None
    created_at: str
    updated_at: str


class LayoutCatalog:
    def __init__(self, value: dict[str, Any]):
        if value.get("schema_version") != "1.0" or not isinstance(value.get("layouts"), dict):
            raise ValueError("layout catalog is invalid")
        self.catalog_version = str(value.get("catalog_version", ""))
        self.layouts = value["layouts"]

    @classmethod
    def load(cls, path: Path) -> "LayoutCatalog":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def resolve(self, spec: LayoutSpec) -> dict[str, Any]:
        value = self.layouts.get(spec.template)
        if not isinstance(value, dict):
            raise ValueError("layout template is unavailable")
        regions = value.get("shot_regions", {}).get(str(spec.shot_count))
        if not isinstance(regions, list) or len(regions) != spec.shot_count:
            raise ValueError("layout shot count is unavailable")
        width, height, margin = value.get("width"), value.get("height"), value.get("safe_margin")
        rectangles = [value.get("title_region"), value.get("caption_region"), *regions]
        if (
            not all(isinstance(item, int) and not isinstance(item, bool) and item > 0
                    for item in (width, height, margin))
            or any(not self._contained_rectangle(region, width, height, margin) for region in rectangles)
        ):
            raise ValueError("layout regions violate the safe canvas")
        return {
            "catalog_version": self.catalog_version,
            "template": spec.template,
            **value,
            "shot_regions": regions,
        }

    @staticmethod
    def _contained_rectangle(region: Any, width: int, height: int, margin: int) -> bool:
        if (
            not isinstance(region, list)
            or len(region) != 4
            or any(not isinstance(item, int) or isinstance(item, bool) for item in region)
        ):
            return False
        x, y, region_width, region_height = region
        return (
            region_width > 0
            and region_height > 0
            and x >= margin
            and y >= margin
            and x + region_width <= width - margin
            and y + region_height <= height - margin
        )


class MultiCutPlanner:
    SHOTS = (
        ("main", "standing_intro", "arms_crossed", "full_body_off_center", "eye_level"),
        ("coding", "coding_at_desk", "typing", "bust_up", "over_shoulder"),
        ("device", "presenting_device", "holding_item", "three_quarter", "eye_level"),
        ("chibi", "chibi_greeting", "wave", "full_body_center", "high_angle"),
    )

    def __init__(self, compiler: CreativeCompiler, layouts: LayoutCatalog):
        self.compiler = compiler
        self.layouts = layouts

    def plan(
        self,
        request: JobRequest,
        creative: CreativeSpec,
        layout: LayoutSpec,
        *,
        capabilities: Mapping[str, Mapping[str, Any]],
        envelope: Mapping[str, Any],
        available_reference_ids: set[str] | None = None,
    ) -> tuple[str, list[JobRequest], list[dict[str, Any]], dict[str, Any]]:
        if request.operation != "image.generate":
            raise CreativeValidationError(
                "creative_composition_operation_invalid",
                "複数カットは新しい画像を作るときだけ使えます。",
                field="operation",
            )
        composition_id = f"composition_{uuid.uuid4().hex}"
        requests: list[JobRequest] = []
        plans: list[dict[str, Any]] = []
        base_seed = self._base_seed(request, creative, layout)
        for index, (role, scene, pose, composition, camera) in enumerate(self.SHOTS[:layout.shot_count]):
            child = creative.model_copy(deep=True)
            child.variation = child.variation.model_copy(update={"axis": "auto"})
            child.scene = child.scene.model_copy(update={"preset": scene, "details": ""})
            child.pose = child.pose.model_copy(update={"preset": pose, "details": ""})
            child.composition = child.composition.model_copy(update={"preset": composition, "details": ""})
            child.camera = child.camera.model_copy(update={"preset": camera, "details": ""})
            compiled = self.compiler.compile(
                request.model_copy(update={"output": request.output.model_copy(update={"count": 1})}),
                child,
                capabilities=capabilities,
                envelope=envelope,
                available_reference_ids=available_reference_ids,
            )
            plan = compiled.plan
            plan["multi_cut"] = {
                "composition_id": composition_id,
                "role": role,
                "index": index,
                "total": layout.shot_count,
                "seed": base_seed + index,
            }
            value = compiled.request.model_dump(mode="json")
            value["constraints"] = {
                **value["constraints"], "seed": base_seed + index, "creative_plan": plan,
            }
            value["output"]["count"] = 1
            requests.append(JobRequest.model_validate(value))
            plans.append(plan)
        return composition_id, requests, plans, self.layouts.resolve(layout)

    @staticmethod
    def _base_seed(request: JobRequest, creative: CreativeSpec, layout: LayoutSpec) -> int:
        requested = request.constraints.get("seed")
        if isinstance(requested, int) and not isinstance(requested, bool) and requested >= 0:
            return requested
        canonical = json.dumps(
            {
                "request": request.model_dump(mode="json"),
                "creative": creative.model_dump(mode="json"),
                "layout": layout.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return int.from_bytes(hashlib.sha256(canonical).digest()[:4], "big")


class DeterministicComposer:
    def compose(
        self,
        sources: list[Path],
        layout: LayoutSpec,
        snapshot: Mapping[str, Any],
        output: Path,
        *,
        font_path: Path | None = None,
    ) -> None:
        if len(sources) != layout.shot_count:
            raise ValueError("composer source count does not match layout")
        width, height = int(snapshot["width"]), int(snapshot["height"])
        canvas = Image.new("RGBA", (width, height), str(snapshot["background"]))
        draw = ImageDraw.Draw(canvas)
        accent = str(snapshot["accent"])
        for source, region in zip(sources, snapshot["shot_regions"], strict=True):
            x, y, region_width, region_height = (int(value) for value in region)
            with Image.open(source) as opened:
                shot = ImageOps.fit(
                    opened.convert("RGBA"), (region_width, region_height),
                    method=Image.Resampling.LANCZOS, centering=(0.5, 0.5),
                )
            canvas.alpha_composite(shot, (x, y))
            draw.rounded_rectangle(
                (x, y, x + region_width - 1, y + region_height - 1),
                radius=12, outline=accent, width=4,
            )
        self._draw_text(
            draw, layout.title, snapshot["title_region"], int(snapshot["safe_margin"]), 44,
            str(snapshot["foreground"]), font_path,
        )
        self._draw_text(
            draw, layout.caption, snapshot["caption_region"], int(snapshot["safe_margin"]), 24,
            str(snapshot["foreground"]), font_path,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output, format="PNG", optimize=False, compress_level=9)

    @staticmethod
    def _draw_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        region: list[int],
        safe_margin: int,
        size: int,
        color: str,
        font_path: Path | None,
    ) -> None:
        if not text:
            return
        x, y, width, height = (int(value) for value in region)
        if x < safe_margin or y < 0 or width < 1 or height < 1:
            raise ValueError("text region violates safe margin")
        font = ImageFont.truetype(font_path, size=size) if font_path else ImageFont.load_default(size=size)
        original = text.replace("\n", " ")
        clipped = original
        if draw.textbbox((0, 0), clipped, font=font)[2] > width:
            while clipped and draw.textbbox((0, 0), clipped + "…", font=font)[2] > width:
                clipped = clipped[:-1]
            clipped += "…"
        draw.text((x, y + max(0, (height - size) // 2)), clipped, font=font, fill=color)


def cache_composer_font(
    data_dir: Path, preferred_sha256: str | None = None
) -> tuple[Path | None, str]:
    root = data_dir / "composer" / "fonts"
    if preferred_sha256 == "pillow-default":
        return None, preferred_sha256
    if preferred_sha256:
        matches = list(root.glob(f"{preferred_sha256}.*")) if root.is_dir() else []
        if len(matches) != 1 or not matches[0].is_file():
            raise ValueError("cached composer font is unavailable")
        return matches[0], preferred_sha256
    configured = os.environ.get("MEDIA_FORGE_COMPOSER_FONT")
    candidates = [
        Path(configured) if configured else None,
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    source = next((path.resolve() for path in candidates if path is not None and path.is_file()), None)
    if source is None:
        return None, "pillow-default"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{digest}{source.suffix.lower()}"
    if not destination.exists():
        temporary = root / f".{digest}.{uuid.uuid4().hex}.partial"
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
        destination.chmod(0o600)
    return destination, digest
