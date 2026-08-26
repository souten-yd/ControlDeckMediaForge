from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MIME_SUFFIXES = {
    "image/png": {".png"},
    "image/webp": {".webp"},
    "image/jpeg": {".jpg", ".jpeg"},
    "application/zip": {".zip"},
    "model/gltf-binary": {".glb"},
}


class ProjectAssetPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    output_grant_id: str = Field(pattern=r"^grant:[A-Za-z0-9._:-]{1,256}$")
    filename: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if (
            Path(value).name != value
            or value in {".", ".."}
            or "\\" in value
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise ValueError("filename must be one safe file name")
        return value


def placement_filename(*, requested: str | None, suggested: str, mime_type: str) -> str:
    value = ProjectAssetPlacement.safe_filename(requested or suggested)
    if value is None:
        raise ValueError("asset has no suggested filename")
    suggested_suffix = Path(suggested).suffix.casefold()
    allowed = MIME_SUFFIXES.get(mime_type, {suggested_suffix} if suggested_suffix else set())
    if Path(value).suffix.casefold() not in allowed:
        raise ValueError("filename extension does not match the asset media type")
    return value


# ── 複数資産の配置 ──────────────────────────────────────────────────────
#
# 実使用では、関連する資産を 1 個ずつ media.pack へ渡して配置していた。呼び出し
# 側から見ると、何が配置されたのかが応答から確定できず、最後に shell の
# ls / file で確かめる必要があった。応答が受領書として不足していたためである。
#
# ここで足すのは意味の層だけで、Host の書き込み契約は変えない。Host が
# 原子的に扱えるのは 1 ファイルなので、N 件をまとめて「全部か無か」とは
# 呼ばない。呼べば嘘になる。


MAX_PLACEMENT_ITEMS = 32


class PlacementItem(BaseModel):
    """One asset and where it should land."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=64)

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str | None) -> str | None:
        return ProjectAssetPlacement.safe_filename(value)


class PlacementManifest(BaseModel):
    """A logical batch of placements under one output grant.

    Logical, not transactional. Each file is committed on its own; nothing here
    promises that a later failure undoes an earlier write.
    """

    model_config = ConfigDict(extra="forbid")

    output_grant_id: str = Field(pattern=r"^grant:[A-Za-z0-9._:-]{1,256}$")
    items: list[PlacementItem] = Field(min_length=1, max_length=MAX_PLACEMENT_ITEMS)

    @model_validator(mode="after")
    def validate_items(self) -> "PlacementManifest":
        asset_ids = [item.asset_id for item in self.items]
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("placement manifest repeats an asset")
        return self


class PlacementReceipt(BaseModel):
    """Enough non-path evidence that the caller need not go looking on disk.

    Deliberately carries no project path: the caller learns exactly which bytes
    landed under which name, and nothing about where the project lives.
    """

    model_config = ConfigDict(extra="forbid")

    committed: bool
    source_asset_id: str
    filename: str
    media_type: str
    sha256: str
    size_bytes: int
    host_asset_id: str | None = None
    width: int | None = None
    height: int | None = None
    role: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: dict[str, str] | None = None


@dataclass(frozen=True)
class PlannedPlacement:
    """One preflighted item: the name is settled and the asset is known good."""

    item: PlacementItem
    filename: str
    mime_type: str
    sha256: str
    size_bytes: int
    width: int | None
    height: int | None


class PlacementPlanError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def plan_placements(
    manifest: PlacementManifest, resolve: Callable[[str], Any]
) -> list[PlannedPlacement]:
    """Settle every destination name before the first byte is written.

    Preflighting the whole manifest matters more than it looks: discovering a
    duplicate name or a missing asset after three files are already committed
    leaves the project in a state nobody asked for, and Media Forge cannot undo
    a Host commit.
    """
    planned: list[PlannedPlacement] = []
    taken: dict[str, str] = {}
    for item in manifest.items:
        try:
            asset = resolve(item.asset_id)
        except KeyError as exc:
            raise PlacementPlanError("asset_not_found", f"unknown asset: {item.asset_id}") from exc
        try:
            filename = placement_filename(
                requested=item.filename,
                suggested=asset.suggested_filename,
                mime_type=asset.mime_type,
            )
        except ValueError as exc:
            raise PlacementPlanError("asset_placement_rejected", str(exc)) from exc
        folded = filename.casefold()
        if folded in taken:
            raise PlacementPlanError(
                "duplicate_placement_filename",
                f"{filename} is requested by more than one asset",
            )
        taken[folded] = item.asset_id
        planned.append(PlannedPlacement(
            item=item,
            filename=filename,
            mime_type=asset.mime_type,
            sha256=asset.sha256,
            size_bytes=asset.size_bytes,
            width=asset.width,
            height=asset.height,
        ))
    return planned
