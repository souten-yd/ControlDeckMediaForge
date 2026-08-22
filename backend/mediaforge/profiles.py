from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AssetId = str
ShortTrait = Annotated[str, Field(min_length=1, max_length=200)]
ReferenceRoleName = Literal[
    "identity", "style", "pose", "composition", "clothing", "palette", "prop", "environment"
]


class ReferenceCollectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    asset_ids: list[AssetId] = Field(min_length=1, max_length=4)
    roles: dict[AssetId, ReferenceRoleName] = Field(default_factory=dict, max_length=4)

    @model_validator(mode="after")
    def validate_assets(self) -> "ReferenceCollectionInput":
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("reference collection asset IDs must be unique")
        if any(not value.startswith("asset_") or len(value) != 38 for value in self.asset_ids):
            raise ValueError("reference collection contains an invalid asset ID")
        if set(self.roles) - set(self.asset_ids):
            raise ValueError("reference collection role references an asset outside the collection")
        return self


class ReferenceCollection(ReferenceCollectionInput):
    id: str = Field(pattern=r"^refs_[0-9a-f]{32}$")
    created_at: str
    updated_at: str


class CharacterDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appearance: str = Field(min_length=1, max_length=2000)
    clothing: str = Field(default="", max_length=2000)
    colors: list[ShortTrait] = Field(default_factory=list, max_length=16)
    distinguishing_features: list[ShortTrait] = Field(default_factory=list, max_length=16)
    negative_traits: list[ShortTrait] = Field(default_factory=list, max_length=16)


class StyleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    art_style: str = Field(min_length=1, max_length=2000)
    linework: str = Field(default="", max_length=1000)
    coloring: str = Field(default="", max_length=1000)
    texture: str = Field(default="", max_length=1000)
    negative_traits: list[ShortTrait] = Field(default_factory=list, max_length=16)


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["character", "style"]
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    reference_collection_id: str | None = Field(
        default=None,
        pattern=r"^refs_[0-9a-f]{32}$",
    )
    character: CharacterDefinition | None = None
    style: StyleDefinition | None = None

    @model_validator(mode="after")
    def validate_definition(self) -> "ProfileInput":
        if self.kind == "character" and (self.character is None or self.style is not None):
            raise ValueError("character profile requires only a character definition")
        if self.kind == "style" and (self.style is None or self.character is not None):
            raise ValueError("style profile requires only a style definition")
        return self


class Profile(ProfileInput):
    id: str = Field(pattern=r"^(character|style)_[0-9a-f]{32}$")
    created_at: str
    updated_at: str


def profile_prompt(profile: Profile) -> str:
    if profile.kind == "character":
        assert profile.character is not None
        value = profile.character
        parts = [f"Character identity ({profile.name}): {value.appearance}"]
        if value.clothing:
            parts.append(f"Clothing: {value.clothing}")
        if value.colors:
            parts.append("Required colors: " + ", ".join(value.colors))
        if value.distinguishing_features:
            parts.append("Distinguishing features: " + ", ".join(value.distinguishing_features))
        if value.negative_traits:
            parts.append("Do not introduce: " + ", ".join(value.negative_traits))
        return ". ".join(parts)
    assert profile.style is not None
    value = profile.style
    parts = [f"Visual style ({profile.name}): {value.art_style}"]
    if value.linework:
        parts.append(f"Linework: {value.linework}")
    if value.coloring:
        parts.append(f"Coloring: {value.coloring}")
    if value.texture:
        parts.append(f"Texture: {value.texture}")
    if value.negative_traits:
        parts.append("Avoid style traits: " + ", ".join(value.negative_traits))
    return ". ".join(parts)
