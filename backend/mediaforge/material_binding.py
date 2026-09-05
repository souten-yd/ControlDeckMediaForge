"""Typed, bounded material texture bindings for private 3D Studio operations."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MaterialChannel = Literal["base_color", "roughness", "metallic", "normal", "emission"]


class SceneTextureRequest(BaseModel):
    """Durable job context used to return a generated image to 3D Studio."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.scene-texture-request@1"] = (
        "media-forge.scene-texture-request@1"
    )
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    source_revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    object_name: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f]+$")
    material_slot: int = Field(ge=0, le=255)
    channel: MaterialChannel = "base_color"
    uv_map: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f]+$")


class MaterialBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.material-binding@1"] = (
        "media-forge.material-binding@1"
    )
    source_revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    image_asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    object_name: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f]+$")
    material_slot: int = Field(ge=0, le=255)
    channel: MaterialChannel = "base_color"
    uv_map: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[^\x00-\x1f]+$"
    )
    wrap: Literal["repeat", "extend", "clip"] = "repeat"
    color_space: Literal["srgb", "non_color"] = "srgb"
    normal_convention: Literal["open_gl", "direct_x"] = "open_gl"

    @model_validator(mode="after")
    def validate_channel_options(self) -> "MaterialBinding":
        expects_color = self.channel in {"base_color", "emission"}
        if expects_color != (self.color_space == "srgb"):
            raise ValueError("material channel and color space differ")
        if self.channel != "normal" and self.normal_convention != "open_gl":
            raise ValueError("normal convention only applies to a normal map")
        return self

    def dependency_role(self) -> str:
        target = hashlib.sha256(self.object_name.encode("utf-8")).hexdigest()[:12]
        return f"material.{self.channel}.{target}.{self.material_slot}"

    def worker_value(self, *, texture_sha256: str) -> dict[str, object]:
        return {
            **self.model_dump(mode="json"),
            "texture_sha256": texture_sha256,
        }
