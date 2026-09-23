"""Direction requests for ordinary image-edit Jobs, never camera calibration."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ASSET_PATTERN = r"^asset_[0-9a-f]{32}$"
Direction = Literal["right", "back", "left"]


class ViewCandidateContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.view-candidate@1"] = "media-forge.view-candidate@1"
    source_asset_id: str = Field(pattern=ASSET_PATTERN)
    direction: Direction


class ViewCandidateBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_asset_id: str = Field(pattern=ASSET_PATTERN)
    directions: list[Direction] = Field(default_factory=lambda: ["right", "back", "left"], min_length=1, max_length=3)
    seed: int = Field(default=42, ge=0, le=2**31 - 4, strict=True)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def distinct_directions(self) -> "ViewCandidateBatchRequest":
        if len(set(self.directions)) != len(self.directions):
            raise ValueError("choose each direction only once")
        return self

    def requests(self, size: int) -> list[dict[str, Any]]:
        directions = {
            "right": "a strict right-side profile, camera rotated 90 degrees from the front; a person faces image left",
            "back": "a strict rear view, camera rotated 180 degrees from the front; no face is visible",
            "left": "a strict left-side profile, camera rotated 270 degrees from the front; a person faces image right",
        }
        result = []
        for index, direction in enumerate(self.directions):
            context = ViewCandidateContext(source_asset_id=self.source_asset_id, direction=direction)
            intent = (
                "Make one turntable reference candidate of the exact subject in the front reference, seen from "
                + directions[direction] + ". Only change the camera direction. Preserve the subject's identity, "
                "shape, proportions, colors, pose, attachments and accessories. Keep every object attached to "
                "the same anatomical side or hand. In a rear view, an attachment visible on the right of the "
                "front image must appear on the left. Keep the entire subject at the same size and position "
                "on the square canvas, with the same camera elevation and distance. Do not mirror or copy "
                "the front image, invent extra parts, crop, make a view sheet, or add text or ground shadows. "
                "Use a plain background. " + self.notes.strip()
            ).strip()
            result.append({
                "operation": "image.edit", "intent": intent,
                "inputs": [{"asset_id": self.source_asset_id}],
                "constraints": {"width": size, "height": size, "seed": self.seed + index,
                    "edit_mode": "reference", "strict_edit": False,
                    "asset_brief": {"role": "general", "aspect_intent": "square", "alpha_intent": "required"},
                    "view_candidate": context.model_dump(mode="json")},
                "output": {"format": "png", "count": 1}, "local_only": True, "model_policy": "auto",
            })
        return result


class ViewCandidateListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_asset_id: str = Field(pattern=ASSET_PATTERN)
    offset: int = Field(default=0, ge=0, le=1_000_000, strict=True)


class ViewCandidateSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_asset_id: str = Field(pattern=ASSET_PATTERN)
    asset_id: str = Field(pattern=ASSET_PATTERN)
    direction: Direction
