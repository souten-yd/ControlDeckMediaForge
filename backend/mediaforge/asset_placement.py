from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


MIME_SUFFIXES = {
    "image/png": {".png"},
    "image/webp": {".webp"},
    "image/jpeg": {".jpg", ".jpeg"},
    "application/zip": {".zip"},
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
