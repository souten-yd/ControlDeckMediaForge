"""Purpose-level asset description and deterministic output geometry.

A real OpenCode run asked for a "wide landscape" game title background and got
1024x1024. The words were in the prose intent; nothing structural carried them.
The request reached the worker with ``constraints == {}``, and the worker's own
fallback (``worker.py``: 1024 when no size is given) decided the canvas — at the
bottom of the stack, where nothing knows what the image is for.

The consuming page then used ``object-fit: cover`` on a landscape element, so the
square image was cropped top and bottom: exactly the open sky and the crowd
silhouette the prompt had carefully asked for.

So geometry is resolved here, before generation, from what the asset is *for*.
Adjectives may inform a brief; they never decide a canvas. No model and no VLM
is asked to make a square "look wide".

The brief travels inside the existing ``JobRequest.constraints`` object, which is
already free-form, so no public schema changes and no second generation API.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetBriefError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# 用途。ここに増やすのは「幾何と alpha の既定が実際に変わる」ものだけにする。
# 語彙を増やすほど agent が選び間違える。
AssetRole = Literal[
    "background",
    "key_visual",
    "character_portrait",
    "sprite",
    "icon",
    "emblem",
    "texture",
    "ui_element",
    "general",
]

AspectIntent = Literal["auto", "square", "landscape", "portrait", "ratio"]
AlphaIntent = Literal["auto", "required", "forbidden"]
SafeAreaEdge = Literal["top", "bottom", "left", "right"]

_RATIO = re.compile(r"^(\d{1,3}):(\d{1,3})$")

# 用途ごとの既定比。あくまで fallback であり、明示指定と profile が常に勝つ。
# 「すべてのゲームは 16:9」のような普遍規則を焼き込まない。
_ROLE_DEFAULTS: dict[str, tuple[str, str]] = {
    # role: (aspect intent, alpha intent)
    "background": ("16:9", "forbidden"),
    "key_visual": ("16:9", "auto"),
    "character_portrait": ("2:3", "auto"),
    "sprite": ("square", "required"),
    "icon": ("square", "required"),
    # 重ね合わせ用の紋章。Hanabi の花火キーアートはこの用途なのに不透明な
    # 完成シーンとして生成され、背景の上に角の立った四角として乗った。
    "emblem": ("square", "required"),
    "texture": ("square", "forbidden"),
    "ui_element": ("auto", "required"),
    "general": ("auto", "auto"),
}


class SafeArea(BaseModel):
    """A region the composition should leave usable for something else.

    This is composition intent, not a pixel-level guarantee. Media Forge tells
    the Director to keep the region clear and the evaluator may flag obvious
    intrusion; neither claims proof that a subject covers less than N percent.
    """

    model_config = ConfigDict(extra="forbid")

    edge: SafeAreaEdge
    fraction: float = Field(default=0.33, gt=0.0, le=0.9)
    purpose: str = Field(default="", max_length=200)


class AssetBrief(BaseModel):
    """What the asset is for, in terms a coding agent already knows.

    Deliberately free of provider, model, sampler, and prompt-craft fields. An
    agent that has to know FLUX's preferred phrasing is an agent whose output
    quality changes when the routed model changes.
    """

    model_config = ConfigDict(extra="forbid")

    role: AssetRole = "general"
    target_surface: str = Field(default="", max_length=64)
    subject: str = Field(default="", max_length=2000)
    composition_intent: str = Field(default="", max_length=2000)
    aspect_intent: AspectIntent = "auto"
    aspect_ratio: str | None = Field(default=None, max_length=8)
    target_width: int | None = Field(default=None, ge=64, le=4096)
    target_height: int | None = Field(default=None, ge=64, le=4096)
    safe_areas: list[SafeArea] = Field(default_factory=list, max_length=4)
    alpha_intent: AlphaIntent = "auto"
    consistency_group: str | None = Field(default=None, max_length=128)
    hard_constraints: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_shape(self) -> "AssetBrief":
        if self.aspect_intent == "ratio":
            if self.aspect_ratio is None or _RATIO.fullmatch(self.aspect_ratio) is None:
                raise ValueError("aspect_intent 'ratio' requires aspect_ratio like '16:9'")
        if self.aspect_ratio is not None and _RATIO.fullmatch(self.aspect_ratio) is None:
            raise ValueError("aspect_ratio must look like '16:9'")
        if (self.target_width is None) != (self.target_height is None):
            raise ValueError("target_width and target_height must be given together")
        edges = [item.edge for item in self.safe_areas]
        if len(edges) != len(set(edges)):
            raise ValueError("safe_areas must not repeat an edge")
        return self


@dataclass(frozen=True)
class ResolvedLayout:
    """The geometry generation will actually use, and why."""

    width: int
    height: int
    alpha: bool
    # 「どの規則が決めたか」を残す。provenance と UI で理由を出せるようにする。
    source: str
    aspect_ratio: str
    safe_areas: tuple[dict[str, Any], ...] = field(default=())

    def as_constraints(self) -> dict[str, Any]:
        return {"width": self.width, "height": self.height}

    def document(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "alpha": self.alpha,
            "aspect_ratio": self.aspect_ratio,
            "source": self.source,
            "safe_areas": [dict(item) for item in self.safe_areas],
        }


def parse_brief(value: Any) -> AssetBrief | None:
    """Read a brief out of the free-form constraints object."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AssetBriefError("asset_brief_invalid", "asset_brief must be an object")
    try:
        return AssetBrief.model_validate(value)
    except ValueError as exc:
        raise AssetBriefError("asset_brief_invalid", str(exc)[:300]) from exc


def _ratio_of(brief: AssetBrief) -> tuple[str, str]:
    """Return (ratio, source) for the brief, before any envelope clamping."""
    if brief.aspect_intent == "ratio" and brief.aspect_ratio:
        return brief.aspect_ratio, "brief.aspect_ratio"
    if brief.aspect_intent == "square":
        return "1:1", "brief.aspect_intent"
    if brief.aspect_intent == "landscape":
        return "16:9", "brief.aspect_intent"
    if brief.aspect_intent == "portrait":
        return "2:3", "brief.aspect_intent"
    if brief.aspect_ratio:
        return brief.aspect_ratio, "brief.aspect_ratio"
    default_ratio, _alpha = _ROLE_DEFAULTS.get(brief.role, ("auto", "auto"))
    if default_ratio == "square":
        return "1:1", "role_default"
    if default_ratio == "auto":
        return "", "model_default"
    return default_ratio, "role_default"


def _snap(value: int, multiple: int) -> int:
    return max(multiple, int(round(value / multiple)) * multiple)


def _fit(
    ratio_w: int, ratio_h: int, *, min_side: int, max_side: int, max_pixels: int, multiple: int
) -> tuple[int, int]:
    """Largest canvas with this ratio that the routed models actually accept.

    Clamped by the envelope rather than by a hardcoded 1024, so a model with a
    wider or narrower envelope changes the answer without editing this table.
    """
    scale = min(max_side / ratio_w, max_side / ratio_h)
    width, height = ratio_w * scale, ratio_h * scale
    if width * height > max_pixels:
        shrink = math.sqrt(max_pixels / (width * height))
        width, height = width * shrink, height * shrink
    snapped_w = min(max_side, max(min_side, _snap(int(width), multiple)))
    snapped_h = min(max_side, max(min_side, _snap(int(height), multiple)))
    # 端数丸めで上限を越えることがある。越えたら短辺側から 1 段下げる。
    while snapped_w * snapped_h > max_pixels and (snapped_w > min_side or snapped_h > min_side):
        if snapped_w >= snapped_h and snapped_w - multiple >= min_side:
            snapped_w -= multiple
        elif snapped_h - multiple >= min_side:
            snapped_h -= multiple
        else:
            break
    return snapped_w, snapped_h


def resolve_layout(
    brief: AssetBrief | None,
    *,
    envelope: dict[str, Any],
    explicit_width: int | None = None,
    explicit_height: int | None = None,
) -> ResolvedLayout | None:
    """Decide the output canvas deterministically, or return None to keep today's behavior.

    Precedence, strongest first:

    1. explicit width/height already on the request (the caller meant exactly this)
    2. explicit target dimensions inside the brief
    3. the brief's aspect intent / ratio
    4. the role's default ratio
    5. nothing — the existing model-native default still applies

    An inferred landscape never overrides an explicit square. AI never enters
    this function.
    """
    multiple = int(envelope.get("multiple_of", 16) or 16)
    min_side = int(envelope.get("min_side", 256) or 256)
    max_side = int(envelope.get("max_side", 1024) or 1024)
    max_pixels = int(envelope.get("max_pixels", max_side * max_side) or max_side * max_side)

    alpha = _alpha_for(brief)
    safe_areas = tuple(item.model_dump(mode="json") for item in brief.safe_areas) if brief else ()

    if explicit_width is not None and explicit_height is not None:
        return ResolvedLayout(
            width=explicit_width,
            height=explicit_height,
            alpha=alpha,
            source="request.constraints",
            aspect_ratio=_describe(explicit_width, explicit_height),
            safe_areas=safe_areas,
        )
    if brief is None:
        return None
    if brief.target_width is not None and brief.target_height is not None:
        return ResolvedLayout(
            width=brief.target_width,
            height=brief.target_height,
            alpha=alpha,
            source="brief.target_dimensions",
            aspect_ratio=_describe(brief.target_width, brief.target_height),
            safe_areas=safe_areas,
        )

    ratio, source = _ratio_of(brief)
    if not ratio:
        return None
    matched = _RATIO.fullmatch(ratio)
    if matched is None:
        raise AssetBriefError("asset_brief_invalid", f"aspect ratio is unusable: {ratio}")
    ratio_w, ratio_h = int(matched.group(1)), int(matched.group(2))
    if ratio_w <= 0 or ratio_h <= 0:
        raise AssetBriefError("asset_brief_invalid", f"aspect ratio is unusable: {ratio}")
    width, height = _fit(
        ratio_w, ratio_h,
        min_side=min_side, max_side=max_side, max_pixels=max_pixels, multiple=multiple,
    )
    return ResolvedLayout(
        width=width,
        height=height,
        alpha=alpha,
        source=source,
        aspect_ratio=ratio,
        safe_areas=safe_areas,
    )


def _alpha_for(brief: AssetBrief | None) -> bool:
    if brief is None:
        return False
    if brief.alpha_intent == "required":
        return True
    if brief.alpha_intent == "forbidden":
        return False
    _ratio, default_alpha = _ROLE_DEFAULTS.get(brief.role, ("auto", "auto"))
    return default_alpha == "required"


def _describe(width: int, height: int) -> str:
    divisor = math.gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


# ── 既存の散文からの決定的な抽出 ────────────────────────────────────────
#
# 既存の呼び出し側は散文で用途を書く。Hanabi の実要求はこうだった。
#
#   "Key visual background for a Japanese fireworks festival game,
#    wide landscape composition. ..."
#
# ここには "background" と "wide landscape" という構造的な語がある。これを
# LLM に読ませる案もあるが、この GPU では LLM 常駐 31.5GB と画像 18.1GB が
# 共存できず、生成のたびに load/release の往復を払うことになる。語彙が
# 閉じている以上、決定的な抽出で足りる。曖昧なときだけ既存 Director の
# text.generate に相乗りすればよく、二つ目の LLM 層は要らない。
#
# 誤検出のほうが害が大きいので、語彙は狭く保ち、確信が持てないときは
# 何も推論しない。

_ROLE_PHRASES: tuple[tuple[str, str], ...] = (
    ("character portrait", "character_portrait"),
    # "key visual background for a game" は背景である。実際に置かれる面を
    # 名指す語のほうが、作り方を名指す語より用途を正確に表す。
    ("background", "background"),
    ("key visual", "key_visual"),
    ("keyart", "key_visual"),
    ("key art", "key_visual"),
    ("sprite sheet", "sprite"),
    ("sprite", "sprite"),
    ("app icon", "icon"),
    ("icon", "icon"),
    ("emblem", "emblem"),
    ("texture", "texture"),
)

_ASPECT_PHRASES: tuple[tuple[str, str], ...] = (
    ("wide landscape", "landscape"),
    ("landscape", "landscape"),
    ("widescreen", "landscape"),
    ("portrait orientation", "portrait"),
    ("vertical", "portrait"),
    ("square", "square"),
)

_ALPHA_PHRASES: tuple[tuple[str, str], ...] = (
    ("transparent background", "required"),
    ("alpha channel", "required"),
    ("no background", "required"),
)


def infer_brief_from_intent(intent: str) -> AssetBrief | None:
    """Recover structural intent that a caller expressed only in prose.

    Deliberately conservative: it fires on a small closed vocabulary and returns
    nothing when it is unsure. A wrong inference silently changes someone's
    output, which is worse than leaving today's behavior alone.

    This never outranks an explicit brief or explicit dimensions; callers of
    ``resolve_layout`` keep that precedence.
    """
    if not intent:
        return None
    text = " ".join(intent.lower().split())

    role: str | None = None
    for phrase, value in _ROLE_PHRASES:
        if phrase in text:
            role = value
            break

    aspect: str | None = None
    ratio: str | None = None
    explicit_ratio = re.search(r"\b(\d{1,2}):(\d{1,2})\b", text)
    if explicit_ratio is not None:
        ratio = f"{int(explicit_ratio.group(1))}:{int(explicit_ratio.group(2))}"
        aspect = "ratio"
    else:
        for phrase, value in _ASPECT_PHRASES:
            if phrase in text:
                aspect = value
                break

    alpha: str | None = None
    for phrase, value in _ALPHA_PHRASES:
        if phrase in text:
            alpha = value
            break

    if role is None and aspect is None and alpha is None:
        return None
    return AssetBrief(
        role=role or "general",
        aspect_intent=aspect or "auto",
        aspect_ratio=ratio,
        alpha_intent=alpha or "auto",
    )
