from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
from PIL import Image

from mediaforge.composer import (
    DeterministicComposer,
    LayoutCatalog,
    LayoutSpec,
    MultiCutPlanner,
    cache_composer_font,
)
from mediaforge.creative import CreativeCompiler, CreativeSpec
from mediaforge.creative_intelligence import ActionStateSpec, PromptPlan, ShotBrief, SubjectSpec
from mediaforge.domain import JobRequest
from mediaforge.evaluator import relevant_dimensions


ROOT = Path(__file__).parents[1]
CAPABILITIES = {"image.text_to_image": {"state": "available"}}
ENVELOPE = {"max_reference_assets": 4, "reference_roles": [], "supports_reference_strength": False}


def wait_composition(client, composition_id: str, timeout: float = 8) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        last = client.get(f"/workspace-api/creative/compositions/{composition_id}").json()
        if last.get("state") in {"succeeded", "partial", "failed", "canceled"}:
            return last
        time.sleep(0.02)
    raise AssertionError(f"composition did not finish: {last}")


def request() -> JobRequest:
    return JobRequest(
        operation="image.generate",
        intent="same orange companion in a designed sheet",
        constraints={"width": 256, "height": 256, "seed": 30},
    )


def test_multicut_planner_creates_explicit_ordinary_child_jobs():
    compiler = CreativeCompiler.load(ROOT / "creative/templates.json")
    planner = MultiCutPlanner(compiler, LayoutCatalog.load(ROOT / "creative/layouts.json"))
    source_request = request()
    source_request.constraints.update({
        "character_profile_id": "character_" + "a" * 32,
        "style_profile_id": "style_" + "b" * 32,
    })
    composition_id, requests, plans, snapshot = planner.plan(
        source_request,
        CreativeSpec.model_validate({"domain": "character_sheet"}),
        LayoutSpec(template="character_sheet", title="Rin", shot_count=4),
        capabilities=CAPABILITIES,
        envelope=ENVELOPE,
    )
    assert composition_id.startswith("composition_")
    assert [plan["multi_cut"]["role"] for plan in plans] == ["main", "coding", "device", "chibi"]
    assert [item.constraints["seed"] for item in requests] == [30, 31, 32, 33]
    assert all(item.operation == "image.generate" and item.output.count == 1 for item in requests)
    assert all(item.constraints["character_profile_id"] == "character_" + "a" * 32 for item in requests)
    assert all(item.constraints["style_profile_id"] == "style_" + "b" * 32 for item in requests)
    assert snapshot["width"] == 1536 and len(snapshot["shot_regions"]) == 4


def test_directed_shots_reuse_children_composer_and_existing_quality_budget():
    compiler = CreativeCompiler.load(ROOT / "creative/templates.json")
    planner = MultiCutPlanner(compiler, LayoutCatalog.load(ROOT / "creative/layouts.json"))
    source_value = request().model_dump(mode="json")
    source_value["qa"] = {
        "deterministic": True, "semantic": True, "max_regeneration_attempts": 1,
    }
    source = JobRequest.model_validate(source_value)
    parent = PromptPlan(
        original_intent=source.intent,
        subject=SubjectSpec(kind="robot", appearance_traits=["orange shell"]),
        primary_action=ActionStateSpec(action="maintaining a terminal"),
    )
    briefs = [
        ShotBrief(
            role="main", index=0,
            primary_action=ActionStateSpec(action="standing beside the damaged terminal"),
            composition="clear establishing view",
        ),
        ShotBrief(
            role="coding", index=1,
            primary_action=ActionStateSpec(action="repairing exposed wiring with both grippers"),
            camera="close view of the repair tools",
        ),
        ShotBrief(
            role="device", index=2,
            primary_action=ActionStateSpec(action="presenting the repaired terminal"),
            details=["green status lights are visible"],
        ),
    ]
    _composition_id, requests, plans, snapshot = planner.plan(
        source,
        CreativeSpec.model_validate({"domain": "poster"}),
        LayoutSpec(template="poster", title="EXACT TITLE", caption="EXACT CAPTION", shot_count=3),
        capabilities=CAPABILITIES,
        envelope=ENVELOPE,
        director_plan=parent,
        shot_briefs=briefs,
        reference_context=[{"focus": "identity", "subject": {"kind": "robot"}}],
    )

    assert len(requests) == 3 and len(plans) == 3
    assert all(item.output.count == 1 for item in requests)
    assert all(item.qa.semantic and item.qa.max_regeneration_attempts == 1 for item in requests)
    assert [plan["director"]["shot_brief"]["role"] for plan in plans] == [
        "main", "coding", "device",
    ]
    assert "repairing exposed wiring" in plans[1]["pose"]["details"]
    assert {"action_state", "composition"}.issubset(
        relevant_dimensions(plans[1], has_references=False)
    )
    assert snapshot["title_region"] and snapshot["caption_region"]
    assert all("EXACT TITLE" not in str(plan) and "EXACT CAPTION" not in str(plan) for plan in plans)


@pytest.mark.parametrize("count", [2, 3, 4])
def test_composer_is_byte_reproducible_for_two_to_four_shots(tmp_path: Path, count: int):
    catalog = LayoutCatalog.load(ROOT / "creative/layouts.json")
    spec = LayoutSpec(template="poster", title="ORANGE", caption="same companion", shot_count=count)
    sources = []
    for index in range(count):
        path = tmp_path / f"source-{index}.png"
        Image.new("RGBA", (91 + index, 73 + index), (40 * index, 80, 220, 255)).save(path)
        sources.append(path)
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    composer = DeterministicComposer()
    composer.compose(sources, spec, catalog.resolve(spec), first)
    composer.compose(sources, spec, catalog.resolve(spec), second)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    with Image.open(first) as image:
        assert image.size == (1024, 1536) and image.mode == "RGBA"


def test_composer_font_is_content_addressed_and_reused_without_source(tmp_path: Path, monkeypatch):
    source = tmp_path / "font.ttf"
    source.write_bytes(b"stable-font-fixture")
    monkeypatch.setenv("MEDIA_FORGE_COMPOSER_FONT", str(source))
    cached, digest = cache_composer_font(tmp_path / "data")
    assert cached is not None and cached.read_bytes() == b"stable-font-fixture"
    source.unlink()
    restored, restored_digest = cache_composer_font(tmp_path / "data", digest)
    assert restored == cached and restored_digest == digest


def test_standalone_composition_reuses_shots_when_only_text_changes(client):
    created = client.post("/workspace-api/creative/compositions", json={
        "request": request().model_dump(mode="json"),
        "creative_spec": {"domain": "poster"},
        "layout": {"template": "poster", "title": "FIRST TITLE", "caption": "before", "shot_count": 3},
    })
    assert created.status_code == 200
    first = wait_composition(client, created.json()["id"])
    assert first["state"] == "succeeded"
    assert len(first["child_job_ids"]) == 3 and len(first["shot_asset_ids"]) == 3
    first_asset = client.get(f"/api/v1/assets/{first['asset_ids'][0]}").json()
    first_provenance = client.get(f"/api/v1/assets/{first['asset_ids'][0]}/provenance").json()
    assert first_provenance["parent_asset_ids"] == first["shot_asset_ids"]

    updated = client.patch(f"/workspace-api/creative/compositions/{first['id']}", json={
        "title": "SECOND TITLE", "caption": "after",
    })
    assert updated.status_code == 200
    second = updated.json()
    second_asset = client.get(f"/api/v1/assets/{second['asset_ids'][0]}").json()
    assert second["child_job_ids"] == first["child_job_ids"]
    assert second["shot_asset_ids"] == first["shot_asset_ids"]
    assert len(second["final_asset_ids"]) == 2
    assert second_asset["sha256"] != first_asset["sha256"]
    image_jobs = [item for item in client.get("/api/v1/jobs").json()["items"]
                  if item["request"]["operation"] == "image.generate"]
    assert len(image_jobs) == 3
    assert "/workspace-api/creative/compositions" not in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("count", [2, 4])
def test_standalone_composes_two_or_four_generated_shots(client, count: int):
    created = client.post("/workspace-api/creative/compositions", json={
        "request": request().model_dump(mode="json"),
        "creative_spec": {"domain": "character_sheet"},
        "layout": {
            "template": "character_sheet", "title": f"{count} SHOTS", "caption": "bounded", "shot_count": count,
        },
    })
    assert created.status_code == 200
    result = wait_composition(client, created.json()["id"])
    assert result["state"] == "succeeded"
    assert len(result["child_job_ids"]) == count
    assert len(result["shot_asset_ids"]) == count
    provenance = client.get(f"/api/v1/assets/{result['asset_ids'][0]}/provenance").json()
    assert provenance["parent_asset_ids"] == result["shot_asset_ids"]
