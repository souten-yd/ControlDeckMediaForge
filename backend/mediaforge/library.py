"""Library projection for the embedded workspace.

The grid needs the origin of each asset, a readable summary, and whether the
protected-pixel guarantee held. Those facts live in provenance, so deriving them
here keeps the workspace from fetching a provenance document per card.
"""

from __future__ import annotations

from typing import Any, Literal

from .domain import Asset, Provenance

Kind = Literal["generated", "edited", "imported"]
KINDS: tuple[str, ...] = ("all", "generated", "edited", "imported")

SUMMARY_LIMIT = 80
MAX_LIMIT = 120
DEFAULT_LIMIT = 60


def classify(provenance: Provenance, asset: Asset) -> Kind:
    if provenance.operation == "asset.import":
        return "imported"
    if provenance.operation == "image.edit" or asset.parent_asset_ids:
        return "edited"
    return "generated"


def is_mask(provenance: Provenance) -> bool:
    return provenance.parameters.get("purpose") == "edit_mask"


def summarize(provenance: Provenance) -> str:
    text = " ".join(provenance.intent.split())
    return text if len(text) <= SUMMARY_LIMIT else f"{text[:SUMMARY_LIMIT]}…"


def _protected_pixel_diff(provenance: Provenance) -> int | None:
    """Surface the strict-edit guarantee when a validator actually measured it."""
    for entry in provenance.validation:
        for key in ("protected_pixel_diff", "source_pixel_diff"):
            value = entry.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def entry(asset: Asset, provenance: Provenance) -> dict[str, Any]:
    item: dict[str, Any] = {
        "asset_id": asset.id,
        "job_id": asset.job_id,
        "kind": classify(provenance, asset),
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "size_bytes": asset.size_bytes,
        "created_at": asset.created_at,
        "summary": summarize(provenance),
        "parent_asset_ids": list(asset.parent_asset_ids),
        "operation": provenance.operation,
        "warnings": list(provenance.warnings),
    }
    diff = _protected_pixel_diff(provenance)
    if diff is not None:
        item["protected_pixel_diff"] = diff
    return item


def clamp_limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def page(
    records: list[tuple[Asset, Provenance]],
    *,
    kind: str,
    include_masks: bool,
    limit: int,
) -> dict[str, Any]:
    """Filter a fetched page, keeping pagination anchored on real asset rows.

    ``next_before`` is the oldest row that was read, not the oldest row that
    survived filtering, so a page made entirely of masks still advances.
    """
    items: list[dict[str, Any]] = []
    for asset, provenance in records:
        if is_mask(provenance) and not include_masks:
            continue
        value = entry(asset, provenance)
        if kind != "all" and value["kind"] != kind:
            continue
        items.append(value)
    exhausted = len(records) < limit
    return {
        "items": items,
        "next_before": None if exhausted else records[-1][0].created_at,
    }
