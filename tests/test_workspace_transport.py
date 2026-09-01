"""PR-U0: bounded workspace transport additions.

These are regression evidence for the /ws implementation detail, not evidence
that the workspace UI works. Real browser observation belongs to PR-U7.
"""

from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conftest import wait_terminal
from mediaforge import library, preferences, thumbnails
from mediaforge.domain import JobRequest
from mediaforge.thumbnails import THUMBNAIL_BYTE_LIMIT
from test_host_execution import generate_input, host_client


def png_bytes(size: tuple[int, int] = (64, 48), color: tuple[int, int, int, int] = (12, 90, 80, 255)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def import_asset(client: TestClient, purpose: str = "source", size: tuple[int, int] = (64, 48)) -> dict:
    response = client.post(
        f"/api/v1/assets/import?purpose={purpose}",
        content=png_bytes(size),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def catalog_version() -> str:
    root = Path(__file__).parents[1] / "creative/templates.json"
    return json.loads(root.read_text(encoding="utf-8"))["catalog_version"]


def call(socket, method: str, params: dict | None = None) -> dict:
    """Send one request and skip any pushed events that arrive first."""
    socket.send_json({"id": method, "method": method, "params": params or {}})
    while True:
        message = socket.receive_json()
        if message.get("id") == method:
            return message


# ── capabilities.get ────────────────────────────────────────────────────────


def test_capabilities_get_matches_the_public_document_and_bounds_presets(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        public = client.get("/api/v1/capabilities").json()
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "capabilities.get")

    assert answer["ok"] is True
    result = answer["result"]
    assert result["capabilities"] == public["capabilities"]
    assert result["contract_version"] == public["contract_version"]
    # 動画は旗で固定せず実態から出す。動くモデルが登録されるまでは、
    # 「採用していない」ではなく「まだ入っていない」と言う。
    text_to_video = result["capabilities"]["video.text_to_video"]
    assert text_to_video["state"] == "unavailable"
    assert text_to_video["reason"] in {
        "video_runtime_not_installed", "capability_not_installed", "model_not_installed",
    }
    # 入力画像から動かす経路は worker にまだ無い。
    assert result["capabilities"]["video.image_to_video"] == {
        "state": "unavailable", "reason": "video_runtime_not_adopted",
    }

    envelope = result["envelope"]
    assert envelope["multiple_of"] == 16
    assert envelope["min_side"] <= envelope["max_side"]
    # The fake test manifest installs nothing, so the envelope must say so
    # rather than inventing measured bounds.
    assert envelope["envelope_source"] == "fallback"

    ids = [preset["id"] for preset in result["presets"]]
    assert ids == ["square", "landscape", "portrait"]
    for preset in result["presets"]:
        assert preset["width"] % 16 == 0 and preset["height"] % 16 == 0
        assert max(preset["width"], preset["height"]) <= envelope["max_side"]


def test_creative_templates_and_validation_stay_on_private_transport(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    original = generate_input("unchanged prompt")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        templates = call(socket, "creative.templates")
        unchanged = call(socket, "creative.validate", {
            "request": original,
            "creative_spec": {},
        })
        directed = call(socket, "creative.validate", {
            "request": original,
            "creative_spec": {"pose": {"preset": "wave"}},
        })

    assert templates["ok"] is True
    # 版そのものではなく、同梱カタログと一致することを見る。カタログを
    # 増やすたびにテストを書き換えるのは、守っている性質ではない。
    assert templates["result"]["catalog_version"] == catalog_version()
    assert unchanged["result"]["request"] == JobRequest.model_validate(original).model_dump(mode="json")
    assert unchanged["result"]["plan"]["active"] is False
    assert directed["ok"] is True
    assert directed["result"]["plan"]["pose"]["id"] == "wave"
    assert directed["result"]["request"]["model_id"] is None


def test_creative_batch_uses_private_transport_and_restores_children(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        created = call(socket, "creative.batches.create", {
            "request": generate_input("four deliberate poses"),
            "creative_spec": {"variation": {"axis": "pose"}},
            "count": 4,
        })
        assert created["ok"] is True
        batch_id = created["result"]["id"]
        child_ids = created["result"]["child_job_ids"]
        restored = call(socket, "creative.batches.get", {"batch_id": batch_id})
        listed = call(socket, "creative.batches.list")

    assert len(child_ids) == 4
    assert len(set(child_ids)) == 4
    assert restored["result"]["id"] == batch_id
    assert listed["result"]["items"][0]["id"] == batch_id
    assert len({plan["pose"]["id"] for plan in restored["result"]["child_plans"]}) == 4


def test_text_only_director_projects_custom_action_without_a_vision_call(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["ai_capabilities"]["text.generate"] = True
    state["ai_responses"].append(json.dumps({
        "subject": {"kind": "robot", "appearance_traits": ["orange shell"]},
        "primary_action": {
            "action": "opens its chest panel",
            "gesture": "holds a diagnostic cable in the left gripper",
        },
        "scene": "compact repair bay",
        "composition": "full body with room for tools",
        "camera": "eye level",
        "hard_constraints": ["orange shell"],
        "optional_suggestions": ["soft rim light"],
    }))
    original = generate_input("orange robot opens its chest panel")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        capabilities = call(socket, "capabilities.get")["result"]
        directed = call(socket, "creative.direct", {
            "intent": original["intent"],
            "director_mode": "refine",
            "creative_spec": {},
        })["result"]
        compiled = call(socket, "creative.validate", {
            "request": original,
            "creative_spec": directed["creative_spec"],
            "director_plan": directed["plan"],
        })["result"]

    assert capabilities["capabilities"]["creative.text_direction"]["state"] == "available"
    assert directed["assistance_used"] is True
    assert directed["creative_spec"]["pose"]["preset"] == "custom"
    assert compiled["request"]["intent"].startswith(original["intent"])
    assert compiled["plan"]["director"]["primary_action"]["action"] == "opens its chest panel"
    assert len(state["ai_calls"]) == 1
    assert state["ai_calls"][0]["capability"] == "text.generate"
    assert "image" not in json.dumps(state["ai_calls"][0]).lower()


def test_h3_prompt_recipe_projects_through_service_identity_without_skill_execution(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["ai_capabilities"]["text.generate"] = True
    state["ai_responses"].append(json.dumps({
        "integrated_multimodal_description": (
            "[Shot 1] 2D animation, a small blue robot waves beside a workbench for six seconds."
        ),
        "overall_soundscape": "A quiet workshop with one soft servo movement.",
        "non_diegetic_music": "N/A",
    }))
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        projected = call(socket, "creative.prompt_recipe", {
            "recipe_id": "minimax-h3-prompt-writing",
            "request": {
                "intent": "小さな青いロボットが作業台の横で手を振る",
                "mode": "t2va",
                "duration_seconds": 6,
                "references": [],
            },
        })

    assert projected["ok"] is True
    assert projected["result"]["capability"] == "text.generate"
    assert projected["result"]["reference_labels"] == []
    assert projected["result"]["rendered_prompt"].startswith("integrated_multimodal_description:")
    assert [item["capability"] for item in state["ai_calls"]] == ["text.generate"]
    user_message = state["ai_calls"][0]["messages"][1]["content"]
    assert "/data1tb/" not in user_message
    assert "skills/h3-prompt-writing" not in user_message
    assert "MiniMax-AI/MiniMax-H3" not in user_message


def test_reference_analysis_uses_one_cached_vision_call_and_passes_only_structured_context(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["ai_capabilities"].update({"vision.analyze": True, "text.generate": True})
    state["ai_responses"].append(json.dumps({
        "subject": {
            "kind": "robot", "count": 1,
            "identity_traits": ["round amber eyes"],
            "appearance_traits": ["orange shell"], "materials": ["painted metal"],
        },
        "action_state": {
            "action": "waving", "state": "cheerful", "orientation": "front",
            "gesture": "right arm raised", "gaze": "toward viewer", "motion_hint": "small wave",
            "body_or_part_relations": ["right hand above shoulder"], "confidence": 0.9,
        },
        "scene": "compact workshop", "composition": "full body centered",
        "style": ["anime illustration"], "clothing_props": ["tool belt"], "text_regions": [],
        "observations": [
            {"field": "pose", "value": "arm raised", "source": "observed", "confidence": 0.9}
        ],
        "inferences": [], "confidence_by_field": {"subject": 0.9},
    }))
    state["ai_responses"].append(json.dumps({
        "subject": {"kind": "robot", "appearance_traits": ["orange shell"]},
        "primary_action": {"action": "holds a small device"},
        "scene": "compact workshop", "composition": "full body centered",
        "camera": "eye level", "hard_constraints": ["orange shell"],
        "optional_suggestions": ["soft rim light"],
    }))

    with client:
        asset = import_asset(client, "source")
        with client.websocket_connect("/ws", headers=headers) as socket:
            first = call(socket, "references.analyze", {"asset_id": asset["id"]})["result"]
            second = call(socket, "references.analyze", {"asset_id": asset["id"]})["result"]
            directed = call(socket, "creative.direct", {
                "intent": "orange robot holds a device",
                "director_mode": "refine",
                "creative_spec": {},
                "reference_analysis": [{"asset_id": asset["id"], "focus": "identity"}],
            })["result"]
            compiled = call(socket, "creative.validate", {
                "request": generate_input("orange robot holds a device"),
                "creative_spec": directed["creative_spec"],
                "director_plan": directed["plan"],
                "reference_analysis": [{"asset_id": asset["id"], "focus": "identity"}],
            })["result"]

    assert first["analysis_cache_hit"] is False
    assert second["analysis_cache_hit"] is True
    assert first["asset_hash"] == second["asset_hash"]
    assert [item["capability"] for item in state["ai_calls"]] == ["vision.analyze", "text.generate"]
    vision_payload = json.dumps(state["ai_calls"][0])
    text_payload = json.dumps(state["ai_calls"][1])
    assert "data:image/jpeg;base64," in vision_payload
    assert "data:image" not in text_payload and "base64" not in text_payload
    assert first["asset_hash"] in text_payload
    assert directed["reference_context"][0]["focus"] == "identity"
    assert set(directed["reference_context"][0]) == {"asset_id", "asset_hash", "focus", "subject"}
    assert compiled["plan"]["director"]["reference_context"] == directed["reference_context"]


def test_original_prompt_route_calls_neither_text_nor_vision_without_references(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["ai_capabilities"].update({"vision.analyze": True, "text.generate": True})

    with client, client.websocket_connect("/ws", headers=headers) as socket:
        directed = call(socket, "creative.direct", {
            "intent": "use this prompt exactly",
            "director_mode": "original",
            "creative_spec": {},
        })["result"]

    assert directed["assistance_used"] is False
    assert directed["plan"]["original_intent"] == "use this prompt exactly"
    assert directed["skipped_reason"] == "original_mode"
    assert state["ai_calls"] == []


def test_cached_reference_analysis_is_reused_by_all_directed_batch_children(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["ai_capabilities"].update({"vision.analyze": True, "text.generate": True})
    state["ai_responses"].append(json.dumps({
        "subject": {"kind": "product", "count": 1},
        "action_state": {"state": "stationary"},
        "scene": "studio", "composition": "centered", "style": [],
        "clothing_props": [], "text_regions": [], "observations": [], "inferences": [],
        "confidence_by_field": {"subject": 0.8},
    }))
    state["ai_responses"].append(json.dumps({
        "plan": {
            "subject": {"kind": "product"},
            "primary_action": {"action": "showing the device"},
            "hard_constraints": ["same product identity"],
        },
        "actions": [
            {"action": "tilted toward viewer"},
            {"action": "rotated to rear ports"},
            {"action": "resting with lid open"},
        ],
    }))

    with client:
        asset = import_asset(client, "source")
        with client.websocket_connect("/ws", headers=headers) as socket:
            analyzed = call(socket, "references.analyze", {"asset_id": asset["id"]})["result"]
            created = call(socket, "creative.batches.create", {
                "request": generate_input("three useful product views"),
                "creative_spec": {"variation": {"axis": "pose"}},
                "count": 3,
                "director_mode": "refine",
                "reference_analysis": [{"asset_id": asset["id"], "focus": "identity"}],
            })["result"]

    assert analyzed["analysis"] is not None
    assert [item["capability"] for item in state["ai_calls"]] == ["vision.analyze", "text.generate"]
    contexts = [plan["director"]["reference_context"] for plan in created["child_plans"]]
    assert len(contexts) == 3
    assert all(context == contexts[0] for context in contexts)
    assert contexts[0][0]["asset_hash"] == analyzed["asset_hash"]


def test_directed_pose_batch_uses_one_text_call_and_normal_child_jobs(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["ai_capabilities"]["text.generate"] = True
    state["ai_responses"].append(json.dumps({
        "plan": {
            "subject": {"kind": "product"},
            "primary_action": {"action": "showing the device"},
            "hard_constraints": ["orange device"],
        },
        "actions": [
            {"action": "tilted toward the viewer", "orientation": "front three-quarter"},
            {"action": "rotated to expose the rear ports", "orientation": "rear three-quarter"},
            {"action": "resting flat while the lid opens", "motion_hint": "hinge opening"},
        ],
    }))
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        created = call(socket, "creative.batches.create", {
            "request": generate_input("three useful views of the orange device"),
            "creative_spec": {"variation": {"axis": "pose"}},
            "count": 3,
            "director_mode": "refine",
        })
        assert created["ok"] is True
        result = created["result"]

    assert len(state["ai_calls"]) == 1
    assert state["ai_calls"][0]["capability"] == "text.generate"
    assert len(result["child_job_ids"]) == 3
    assert all(plan["pose"]["id"] == "custom" for plan in result["child_plans"])
    assert [plan["director"]["child_action_state"]["action"] for plan in result["child_plans"]] == [
        "tilted toward the viewer",
        "rotated to expose the rear ports",
        "resting flat while the lid opens",
    ]


def test_multicut_children_use_hosted_job_submission_before_deterministic_composition(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        created = call(socket, "creative.compositions.create", {
            "request": generate_input("hosted three-cut poster"),
            "creative_spec": {"domain": "poster"},
            "layout": {"template": "poster", "title": "HOSTED", "caption": "three shots", "shot_count": 3},
        })
        assert created["ok"] is True
        for job_id in created["result"]["child_job_ids"]:
            assert wait_terminal(client, job_id)["status"] == "succeeded"
        restored = call(socket, "creative.compositions.get", {
            "composition_id": created["result"]["id"],
        })
        provenance = client.get(
            f"/api/v1/assets/{restored['result']['asset_ids'][0]}/provenance"
        ).json()

    assert restored["ok"] is True
    assert restored["result"]["state"] == "succeeded"
    assert len(restored["result"]["shot_asset_ids"]) == 3
    assert provenance["parent_asset_ids"] == restored["result"]["shot_asset_ids"]
    assert state["ai_calls"] == []


def test_directed_multicut_uses_one_text_call_and_existing_child_jobs(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["ai_capabilities"]["text.generate"] = True
    state["ai_responses"].append(json.dumps({
        "plan": {
            "subject": {"kind": "robot", "appearance_traits": ["orange shell"]},
            "primary_action": {"action": "repairing and presenting a terminal"},
            "scene": "compact workshop",
            "hard_constraints": ["same orange robot"],
        },
        "shots": [
            {
                "primary_action": {"action": "standing beside the damaged terminal"},
                "composition": "establishing view",
            },
            {
                "primary_action": {"action": "repairing exposed wiring with both grippers"},
                "camera": "close view of the tools",
            },
            {
                "primary_action": {"action": "presenting the repaired terminal"},
                "details": ["green status lights are visible"],
            },
        ],
    }))
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        created = call(socket, "creative.compositions.create", {
            "request": generate_input("orange robot repairs and presents a terminal"),
            "creative_spec": {"domain": "poster"},
            "layout": {
                "template": "poster",
                "title": "EXACT HOST TITLE",
                "caption": "EXACT HOST CAPTION",
                "shot_count": 3,
            },
            "director_mode": "refine",
            "reference_analysis": [],
        })
        assert created["ok"] is True
        result = created["result"]
        for job_id in result["child_job_ids"]:
            assert wait_terminal(client, job_id)["status"] == "succeeded"
        restored = call(socket, "creative.compositions.get", {"composition_id": result["id"]})

    assert len(state["ai_calls"]) == 1
    assert state["ai_calls"][0]["capability"] == "text.generate"
    ai_payload = json.dumps(state["ai_calls"][0])
    assert "EXACT HOST TITLE" not in ai_payload and "EXACT HOST CAPTION" not in ai_payload
    assert restored["result"]["state"] == "succeeded"
    assert restored["result"]["director"]["assistance_used"] is True
    assert [plan["director"]["shot_brief"]["role"] for plan in result["child_plans"]] == [
        "main", "coding", "device",
    ]
    assert "repairing exposed wiring" in result["child_plans"][1]["pose"]["details"]


# ── library.list ────────────────────────────────────────────────────────────


def test_library_list_classifies_origin_and_hides_masks(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        import_asset(client, "source")
        import_asset(client, "edit_mask")
        created = client.post("/api/v1/jobs", json=generate_input("library robot")).json()
        wait_terminal(client, created["id"])

        with client.websocket_connect("/ws", headers=headers) as socket:
            default = call(socket, "library.list")["result"]
            masks = call(socket, "library.list", {"include_masks": True})["result"]
            generated = call(socket, "library.list", {"kind": "generated"})["result"]

    kinds = {item["kind"] for item in default["items"]}
    assert "generated" in kinds and "imported" in kinds
    assert len(masks["items"]) == len(default["items"]) + 1
    assert all(item["kind"] == "generated" for item in generated["items"])

    produced = next(item for item in default["items"] if item["kind"] == "generated")
    assert produced["summary"] == "library robot"
    assert produced["width"] and produced["height"]
    assert "asset_id" in produced and produced["asset_id"].startswith("asset_")


def test_library_list_rejects_unknown_kind_and_pages_without_gaps(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        for _ in range(3):
            import_asset(client, "source")
        with client.websocket_connect("/ws", headers=headers) as socket:
            rejected = call(socket, "library.list", {"kind": "nope"})
            first = call(socket, "library.list", {"limit": 2})["result"]
            socket.send_json({
                "id": "page2",
                "method": "library.list",
                "params": {"limit": 2, "before": first["next_before"]},
            })
            while True:
                message = socket.receive_json()
                if message.get("id") == "page2":
                    second = message["result"]
                    break

    assert rejected["ok"] is False
    assert rejected["error"]["code"] == "workspace_request_rejected"
    assert len(first["items"]) == 2 and first["next_before"]
    seen = [item["asset_id"] for item in first["items"] + second["items"]]
    assert len(seen) == len(set(seen)) == 3
    assert second["next_before"] is None


def test_library_page_advances_when_every_row_is_filtered_out():
    from mediaforge.domain import Asset, Provenance

    def record(index: int, purpose: str) -> tuple[Asset, Provenance]:
        asset = Asset(
            id=f"asset_{index:032x}",
            job_id="job_1",
            parent_asset_ids=[],
            mime_type="image/png",
            size_bytes=1,
            sha256="0" * 64,
            suggested_filename="a.png",
            provenance_id=f"prov_{index}",
            created_at=f"2026-08-22T00:00:0{index}Z",
        )
        provenance = Provenance(
            id=f"prov_{index}",
            asset_id=asset.id,
            parent_asset_ids=[],
            operation="asset.import",
            intent="Import local edit mask asset",
            model_id="none",
            model_version="0",
            weights_hash="none",
            license="user-provided",
            runtime_adapter="import",
            runtime_version="0",
            tool_versions={},
            seed=0,
            parameters={"purpose": purpose},
            reference_asset_hashes={},
            postprocessing=[],
            validation=[],
            warnings=[],
            output_sha256="0" * 64,
            created_at=asset.created_at,
        )
        return asset, provenance

    records = [record(1, "edit_mask"), record(2, "edit_mask")]
    result = library.page(records, kind="all", include_masks=False, limit=2)
    assert result["items"] == []
    assert result["next_before"] == records[-1][0].created_at


# ── assets.thumbnail ────────────────────────────────────────────────────────


def test_thumbnail_is_bounded_cached_and_webp(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        asset = import_asset(client, "source", size=(900, 600))
        with client.websocket_connect("/ws", headers=headers) as socket:
            first = call(socket, "assets.thumbnail", {"asset_id": asset["id"]})["result"]
            cached_dir = client.app.state.store.thumbnail_dir
            files = sorted(cached_dir.iterdir())
            stamp = files[0].stat().st_mtime_ns
            second = call(socket, "assets.thumbnail", {"asset_id": asset["id"]})["result"]
            assert sorted(cached_dir.iterdir())[0].stat().st_mtime_ns == stamp

    assert first["mime_type"] == "image/webp"
    assert max(first["width"], first["height"]) == thumbnails.DEFAULT_MAX_SIDE
    assert len(base64.b64decode(first["base64"])) <= THUMBNAIL_BYTE_LIMIT
    assert second == first
    assert len(files) == 1


def test_thumbnail_clamps_requested_size_and_reports_unsupported_media(tmp_path: Path):
    assert thumbnails.clamp_max_side(9999) == thumbnails.MAX_MAX_SIDE
    assert thumbnails.clamp_max_side(1) == thumbnails.MIN_MAX_SIDE
    assert thumbnails.clamp_max_side("256") == thumbnails.DEFAULT_MAX_SIDE
    assert thumbnails.clamp_max_side(True) == thumbnails.DEFAULT_MAX_SIDE
    assert not thumbnails.is_thumbnailable("video/webm")

    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        asset = import_asset(client, "source")
        store = client.app.state.store
        store.asset_path(asset["id"]).write_bytes(b"not an image")
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "assets.thumbnail", {"asset_id": asset["id"]})

    assert answer["ok"] is False
    assert answer["error"]["code"] == "thumbnail_unavailable"


# ── preferences ─────────────────────────────────────────────────────────────


def test_preferences_round_trip_and_reject_unknown_keys(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        defaults = call(socket, "preferences.get")["result"]["values"]
        stored = call(socket, "preferences.set", {
            "values": {"mode": "advanced", "create_media": "video", "last_count": 4},
        })
        reloaded = call(socket, "preferences.get")["result"]["values"]
        unknown = call(socket, "preferences.set", {"values": {"api_token": "secret"}})
        bad_value = call(socket, "preferences.set", {"values": {"mode": "expert"}})
        oversized = call(socket, "preferences.set", {"values": {"mode": "x" * 5000}})

    assert defaults == preferences.DEFAULTS
    assert stored["ok"] is True
    assert reloaded["mode"] == "advanced" and reloaded["create_media"] == "video"
    assert reloaded["last_count"] == 4
    assert reloaded["last_preset"] == preferences.DEFAULTS["last_preset"]
    assert unknown["ok"] is False and unknown["error"]["code"] == "invalid_preference_key"
    assert bad_value["ok"] is False and bad_value["error"]["code"] == "invalid_preference_value"
    assert oversized["ok"] is False and oversized["error"]["code"] == "preferences_too_large"
    # A rejected write never leaks its value into an error message.
    assert "secret" not in unknown["error"]["message"]


def test_preferences_are_isolated_per_subject(tmp_path: Path):
    from mediaforge.store import Store

    store = Store(tmp_path / "prefs")
    store.initialize()
    store.set_preferences("7", {"mode": "advanced"})
    assert store.get_preferences("7") == {"mode": "advanced"}
    assert store.get_preferences("8") == {}
    assert preferences.merged(store.get_preferences("8"))["mode"] == "simple"
    # Values written by an older build are not handed back to the workspace.
    store.set_preferences("9", {"mode": "simple", "removed_key": 1})
    assert "removed_key" not in preferences.merged(store.get_preferences("9"))


# ── jobs.watch ──────────────────────────────────────────────────────────────


def test_jobs_watch_pushes_changes_and_releases_terminal_jobs(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        created = client.post("/api/v1/jobs", json=generate_input("watched robot")).json()
        watching = call(socket, "jobs.watch", {"job_ids": [created["id"]]})
        assert watching["result"]["watching"] == [created["id"]]

        statuses: list[str] = []
        for _ in range(40):
            message = socket.receive_json()
            if message.get("event") != "job.changed":
                continue
            assert message["data"]["id"] == created["id"]
            statuses.append(message["data"]["status"])
            if message["data"]["status"] in {"succeeded", "failed", "canceled"}:
                break
        assert statuses, "no job.changed event was pushed"
        assert statuses[-1] in {"succeeded", "failed", "canceled"}

        # The terminal job is released, so a later watch of nothing stays empty.
        still = call(socket, "jobs.unwatch", {"job_ids": [created["id"]]})
        assert still["result"]["watching"] == []


def test_jobs_watch_rejects_malformed_ids_and_bounds_the_watch_set(tmp_path: Path):
    from mediaforge.events import MAX_WATCHED_JOBS, JobEventBus
    import asyncio

    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        rejected = call(socket, "jobs.watch", {"job_ids": [1, 2]})
    assert rejected["ok"] is False
    assert rejected["error"]["code"] == "workspace_request_rejected"

    async def bounded() -> list[str]:
        bus = JobEventBus()
        subscription = bus.subscribe(asyncio.get_running_loop())
        return subscription.watch([f"job_{index}" for index in range(MAX_WATCHED_JOBS + 5)])

    assert len(asyncio.run(bounded())) == MAX_WATCHED_JOBS


def test_job_publication_survives_a_failing_listener(tmp_path: Path):
    from mediaforge.domain import JobRequest
    from mediaforge.store import Store

    store = Store(tmp_path / "listener")
    store.initialize()
    seen: list[str] = []
    store.observe(lambda job: (_ for _ in ()).throw(RuntimeError("subscriber exploded")))
    store.observe(lambda job: seen.append(job.status.value))

    request = JobRequest.model_validate(generate_input("listener robot"))
    job = store.create_job(request)
    store.update_job(job.id, phase="generating", progress=0.5)

    assert seen == ["queued", "queued"]


@pytest.mark.parametrize(
    "method",
    [
        "capabilities.get", "library.list", "assets.thumbnail", "preferences.get", "jobs.watch",
        "models.catalog", "models.install", "models.remove", "models.operations.list",
        "creative.templates", "creative.validate", "creative.batches.create",
        "creative.direct", "creative.prompt_recipe", "references.analyze",
        "creative.batches.get", "creative.batches.list", "creative.batches.cancel",
        "creative.compositions.create", "creative.compositions.get",
        "creative.compositions.list", "creative.compositions.update_text",
        "creative.compositions.cancel",
        "creative.evaluate",
    ],
)
def test_new_methods_reject_host_path_strings(tmp_path: Path, method: str):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        socket.send_json({"id": "path", "method": method, "params": {"hint": "/etc/passwd"}})
        while True:
            message = socket.receive_json()
            if message.get("id") == "path":
                break
    assert message["ok"] is False
    assert message["error"]["code"] == "unscoped_host_path"


def test_new_methods_require_the_host_service_identity(tmp_path: Path):
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        try:
            with client.websocket_connect("/ws"):
                pass
        except Exception:
            return
    raise AssertionError("workspace WebSocket accepted a request without a host token")


def test_binary_payloads_are_not_mistaken_for_host_paths(tmp_path: Path):
    """base64 の先頭が "/" になる chunk が拒否されると取り込みが途中で失敗する。

    実際に端末からの画像取り込みが不定期に失敗していた。
    """
    from mediaforge.host.security import reject_host_paths

    # "/" 始まりの base64 は普通に発生する（アルファベットに含まれるため）
    reject_host_paths({"upload_id": "upload_1", "offset": 0, "base64": "/9j/4AAQSkZJRgABAQ=="})
    # 通常フィールドの path 検査は変わらない
    with pytest.raises(Exception):
        reject_host_paths({"hint": "/etc/passwd"})

    client, headers, _state = host_client(tmp_path, token="valid-user")
    content = png_bytes((64, 64))
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        begin = call(socket, "assets.import.begin", {"purpose": "source", "size": len(content)})
        upload = begin["result"]
        socket.send_json({
            "id": "chunk",
            "method": "assets.import.chunk",
            "params": {
                "upload_id": upload["upload_id"],
                "offset": 0,
                # 先頭が "/" の base64 を意図的に送る
                "base64": base64.b64encode(content).decode("ascii"),
            },
        })
        while True:
            message = socket.receive_json()
            if message.get("id") == "chunk":
                break
    assert message["ok"] is True, message


# ── workspace.session ───────────────────────────────────────────────────────


SESSION_PARTS = {
    "preferences", "capabilities", "profiles", "reference_collections",
    "models", "model_catalog", "model_operations", "library",
    "creative_batches", "creative_compositions", "jobs",
}


def test_workspace_session_returns_the_whole_boot_state_in_one_request(tmp_path: Path):
    """boot は直列 10 往復だった。状態の正をサーバへ移し 1 往復にする。"""
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "workspace.session")

    assert answer["ok"] is True, answer
    result = answer["result"]
    assert result["session_version"] == 1
    assert SESSION_PARTS <= set(result)
    # 旧 boot が個別に取っていた値がそのまま入っていること
    assert isinstance(result["preferences"]["values"], dict)
    assert "capabilities" in result["capabilities"]
    assert "envelope" in result["capabilities"]
    assert isinstance(result["jobs"]["items"], list)
    # watch はサーバが張る。client から jobs.watch を送らせない。
    assert "watching" in result


def test_workspace_session_returns_only_the_requested_parts(tmp_path: Path):
    """session.changed を受けたら変わった部分だけ読み直せること。"""
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "workspace.session", {"parts": ["jobs", "creative_batches"]})

    result = answer["result"]
    assert result["parts"] == ["creative_batches", "jobs"]
    assert set(result) & SESSION_PARTS == {"jobs", "creative_batches"}


def test_workspace_session_rejects_an_unknown_part_list(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "workspace.session", {"parts": ["nonsense"]})

    assert answer["ok"] is False
    assert answer["error"]["code"] == "workspace_request_rejected"


def test_one_unavailable_session_part_does_not_cost_the_whole_session(tmp_path: Path, monkeypatch):
    """Host AI probe が落ちても session 全体を失わせない。"""
    from mediaforge.host.ai import HostAIError, HostAIGateway

    async def unavailable(*_args, **_kwargs):
        raise HostAIError("host_ai_unavailable", "ControlDeck AI is unavailable")

    monkeypatch.setattr(HostAIGateway, "capabilities", unavailable)
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "workspace.session")

    assert answer["ok"] is True, answer
    result = answer["result"]
    assert isinstance(result["jobs"]["items"], list)
    assert isinstance(result["preferences"]["values"], dict)


def test_session_changed_is_pushed_instead_of_polling(tmp_path: Path):
    """1 秒 polling をやめられる根拠。変わった部分の名前が push されること。"""
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            call(socket, "workspace.session")
            answer = call(socket, "profiles.create", {
                "kind": "character",
                "name": "session push",
                "character": {"appearance": "a short test character"},
            })
            assert answer["ok"] is True, answer
            for _ in range(20):
                message = socket.receive_json()
                if message.get("event") == "session.changed":
                    assert "profiles" in message["data"]["parts"]
                    break
            else:  # pragma: no cover - 受信できなければ polling を消せない
                raise AssertionError("session.changed was not pushed")


def test_session_library_carries_inline_thumbnails_so_the_grid_makes_no_extra_calls(tmp_path: Path):
    """カード 1 枚 1 往復のサムネイル要求をやめた根拠。

    実データ（asset 95 件）で boot が 104 要求・2.609 秒かかっていた原因の主因。
    """
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        imported = import_asset(client)
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "workspace.session", {"parts": ["library"]})

    items = answer["result"]["library"]["items"]
    assert any(item["asset_id"] == imported["id"] for item in items)
    for item in items:
        thumbnail = item["thumbnail"]
        assert thumbnail["mime_type"] == thumbnails.MIME_TYPE
        assert max(thumbnail["width"], thumbnail["height"]) <= library.GRID_THUMBNAIL_MAX_SIDE
        assert len(base64.b64decode(thumbnail["base64"])) <= THUMBNAIL_BYTE_LIMIT


def test_library_list_can_opt_out_of_inline_thumbnails(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        import_asset(client)
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "library.list", {"limit": 4, "thumbnails": False})

    assert all("thumbnail" not in item for item in answer["result"]["items"])


# ── 利用者が追加するモデル（G6 S6） ────────────────────────────────────


def test_custom_model_resolution_pins_the_revision_before_anything_is_fetched(tmp_path: Path):
    import httpx as httpx_module

    payload = {
        "sha": "9" * 40,
        "gated": False,
        "library_name": "diffusers",
        "pipeline_tag": "text-to-image",
        "cardData": {"license": "openrail++"},
        "siblings": [
            {"rfilename": "model_index.json", "size": 100},
            {
                "rfilename": "unet/diffusion_pytorch_model.safetensors",
                "size": 1_000,
                "lfs": {"sha256": "e" * 64, "size": 1_000},
            },
        ],
    }
    root = Path(__file__).parents[1]
    client, headers, _state = host_client(
        tmp_path,
        token="valid-user",
        model_download_transport=httpx_module.MockTransport(
            lambda request: httpx_module.Response(200, json=payload)
        ),
        model_catalog_manifest=root / "worker_packs/image/catalog.json",
        model_store_root=tmp_path / "model-store",
    )
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            resolved = call(socket, "models.custom.resolve", {
                "repo_id": "owner/sdxl", "revision": "main",
            })
            added = call(socket, "models.custom.add", {
                "repo_id": "owner/sdxl",
                "revision": "main",
                "display_name": "SDXL",
                "license_acceptance": "openrail++",
            })
            catalog = call(socket, "models.catalog")

    assert catalog["ok"] is True, catalog
    assert resolved["ok"] is True, resolved
    assert resolved["result"]["revision"] == "9" * 40
    assert resolved["result"]["requested_revision"] == "main"
    assert added["ok"] is True, added
    items = {item["model_id"]: item for item in catalog["result"]["items"]}
    assert "owner/sdxl" in items
    # 実測するまで routing 対象にしない。
    assert items["owner/sdxl"]["state"] == "experimental"


def test_custom_model_add_is_refused_without_accepting_the_shown_licence(tmp_path: Path):
    import httpx as httpx_module

    payload = {
        "sha": "9" * 40,
        "gated": False,
        "library_name": "diffusers",
        "pipeline_tag": "text-to-image",
        "cardData": {"license": "openrail++"},
        "siblings": [{
            "rfilename": "unet/diffusion_pytorch_model.safetensors",
            "size": 1_000,
            "lfs": {"sha256": "e" * 64, "size": 1_000},
        }],
    }
    client, headers, _state = host_client(
        tmp_path,
        token="valid-user",
        model_download_transport=httpx_module.MockTransport(
            lambda request: httpx_module.Response(200, json=payload)
        ),
    )
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "models.custom.add", {
                "repo_id": "owner/sdxl",
                "revision": "main",
                "display_name": "SDXL",
                "license_acceptance": "mit",
            })

    assert answer["ok"] is False
    assert answer["error"]["code"] == "custom_model_license_not_accepted"


def test_the_workspace_boot_catches_up_the_base_evaluations_it_owes() -> None:
    """埋め込みの boot は models.list を呼ばない。集約の session を通る。

    追従を models.list だけに掛けると、ControlDeck の中では一度も走らない。
    実機ではそれで、LoRA が連れてきた土台が未計測のまま残り続けた。
    session の models を作るところに置く理由がこれである。
    """
    source = (Path(__file__).parents[1] / "backend/mediaforge/app.py").read_text(encoding="utf-8")
    session = source[
        source.index("    async def session_snapshot("):source.index("        async def produce(")
    ]
    assert "start_pending_lora_base_evaluations(identity)" in session
    assert '"models": model_catalog,' in session


def test_a_finished_download_is_followed_up_without_waiting_for_a_person() -> None:
    """落とし終えた土台を、誰かが画面を開くまで放置しない。

    追従を LoRA 依存の経路だけに掛けていたので、checkpoint を単体で入れた
    ときは何も起きなかった。実機では Lykon/DreamShaper が 05:56 に落ち終えて
    そのまま未計測で残り、使える土台が無いままだった（2026-08-28）。
    """
    source = (Path(__file__).parents[1] / "backend/mediaforge/app.py").read_text(encoding="utf-8")
    install = source[
        source.index('elif method == "models.install":'):source.index('elif method == "models.remove":')
    ]
    assert "follow_install(installed.id, identity)" in install
    # 依存の経路も同じ追従を使う。2 つ持つとまた片方だけ直すことになる。
    assert source.count("follow_install(") >= 3


def test_a_clip_shows_its_first_frame_in_a_grid_of_stills(tmp_path: Path):
    """動画 1 本ぶんを一覧へ運ぶことはできない。1 枚目だけを静止画の経路に乗せる。

    ここが無いと、作った動画がライブラリで空の枠になる。
    """
    import subprocess

    from mediaforge import thumbnails

    assert thumbnails.is_thumbnailable("video/mp4")
    clip = tmp_path / "clip.mp4"
    built = subprocess.run(
        [
            "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "testsrc=size=128x96:rate=8:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip),
        ],
        check=False, capture_output=True, timeout=60,
    )
    if built.returncode != 0:
        pytest.skip("ffmpeg is unavailable in this environment")

    poster = thumbnails.render(clip, 256, "video/mp4")
    assert poster.mime_type == thumbnails.MIME_TYPE
    assert poster.width > 0 and poster.height > 0
    assert len(poster.content) <= thumbnails.THUMBNAIL_BYTE_LIMIT

    # 中身が動画でないものを動画として渡されても、枠だけ作って通さない。
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a clip")
    with pytest.raises(thumbnails.ThumbnailError):
        thumbnails.render(broken, 256, "video/mp4")


def test_a_video_entry_says_it_is_a_clip_and_how_long(tmp_path: Path):
    """一覧のカードは 1 枚目の静止画で、そのままでは動くものだと分からない。

    画面が印を出せるよう、種別と尺を entry が名指しする。
    """
    from mediaforge.domain import Asset, Provenance
    from mediaforge import library
    from mediaforge.store import utc_now

    now = utc_now()
    asset = Asset(
        id="asset_clip", job_id="job_clip", parent_asset_ids=[], mime_type="video/mp4",
        width=512, height=320, duration_sec=2.0625, frame_rate=16.0,
        size_bytes=29629, sha256="c" * 64,
        suggested_filename="media-forge-clip.mp4", provenance_id="prov_clip", created_at=now,
    )
    provenance = Provenance(
        id="prov_clip", asset_id="asset_clip", parent_asset_ids=[],
        operation="video.generate", intent="a small robot waves",
        model_id="Wan-AI/Wan2.1-T2V-1.3B-Diffusers", model_version="1",
        weights_hash="sha256:" + "0" * 64, license="apache-2.0",
        runtime_adapter="diffusers.wan2.1-t2v", runtime_version="0.40.0",
        tool_versions={}, seed=0, parameters={}, output_sha256="c" * 64, created_at=now,
        reference_asset_hashes={}, postprocessing=[], validation=[], warnings=[],
    )

    item = library.entry(asset, provenance)
    assert item["preview_kind"] == "video"
    assert item["duration_sec"] == 2.0625
    assert item["frame_rate"] == 16.0
    # 静止画と同じ種別にすると、画面が印を出す手がかりを失う。
    assert item["preview_kind"] != "image"


def test_the_workspace_document_is_compressed(tmp_path: Path):
    """workspace は markup と style と script を 1 応答へ畳んで返す。

    実機で 356,733 B を無圧縮で送っていた。手元では 15 ms でも、Tailscale の
    relay 越しではその差がそのまま待ち時間になる（2026-08-30 の指摘）。
    WebSocket は uvicorn の permessage-deflate が既定で効いているので、
    無圧縮で残っていたのはこの文書だけだった。
    """
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        plain = client.get("/")
        packed = client.get("/", headers={"Accept-Encoding": "gzip"})

    assert plain.status_code == 200 and packed.status_code == 200
    assert packed.headers.get("content-encoding") == "gzip"
    # 畳んだ分がそのまま効く。半分以下にならないなら効いていない。
    assert int(packed.headers["content-length"]) * 2 < len(plain.content)


def test_an_imported_clip_is_normalized_so_every_device_can_play_it(tmp_path: Path):
    """駆動系は webm/vp8 を書くものもあるが、iOS はそれを再生しない。

    取り込んだものをそのまま置くと、作った端末でだけ見える asset ができる。
    library に置くものは見られる形に揃える。
    """
    import subprocess

    from mediaforge.asset_import import import_video_asset

    source = tmp_path / "clip.webm"
    built = subprocess.run(
        [
            "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "testsrc=size=128x96:rate=12:duration=1",
            "-c:v", "libvpx", "-pix_fmt", "yuv420p", str(source),
        ],
        check=False, capture_output=True, timeout=120,
    )
    if built.returncode != 0:
        pytest.skip("ffmpeg cannot build a webm fixture here")

    client, _headers, _state = host_client(tmp_path / "instance", token="valid-user")
    with client:
        store = client.app.state.store
        asset = import_video_asset(store, source.read_bytes(), purpose="source",
                                   media_type="video/webm")

        assert asset.mime_type == "video/mp4"
        assert asset.width == 128 and asset.height == 96
        assert asset.duration_sec and asset.duration_sec > 0
        assert asset.frame_rate and asset.frame_rate > 0
        # 取り込んだ中間物を残さない。
        assert list(store.work_dir.iterdir()) == []

    # 中身が動画でないものは、枠だけ作って通さない。
    from mediaforge.asset_import import AssetImportError

    client2, _h2, _s2 = host_client(tmp_path / "other", token="valid-user")
    with client2:
        with pytest.raises(AssetImportError):
            import_video_asset(client2.app.state.store, b"not a clip", purpose="source",
                               media_type="video/mp4")


def test_a_photo_too_large_to_send_is_shown_reduced_rather_than_refused(tmp_path: Path):
    """原寸で預かった写真を、見られないままにしない。

    workspace は base64 でしか運べない。実測では 12.2MP の写真が PNG で
    13.6MiB になり、12MiB の転送上限を超える。断ると「透かしは消せたが
    見られない」で終わる。見るための縮小版を返し、縮めたことを言う。
    原寸は保存で取り出せる（export は host へファイルのまま渡る）。
    """
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        small = import_asset(client, "source", size=(64, 48))
        # 転送上限を超える資産を作る。乱数の PNG は圧縮が効かない。
        import os
        big_path = client.app.state.store.asset_path(small["id"])
        noise = Image.frombytes("RGBA", (2048, 1600), os.urandom(2048 * 1600 * 4))
        noise.save(big_path, format="PNG")
        assert big_path.stat().st_size > 12 * 1024 * 1024

        with client.websocket_connect("/ws", headers=headers) as socket:
            reduced = call(socket, "assets.content", {"asset_id": small["id"]})["result"]

    assert reduced["reduced"] is True
    assert reduced["mime_type"] == "image/webp"
    assert reduced["original_mime_type"] == "image/png"
    assert reduced["original_size_bytes"] > 12 * 1024 * 1024
    content = base64.b64decode(reduced["base64"])
    assert len(content) <= thumbnails.PREVIEW_BYTE_LIMIT
    # 一覧の 64KiB では拡大に耐えない。見るための予算は別に持つ。
    # 乱数の PNG は写真より圧縮が効かず、1600px では 2MiB に入らない。段を
    # 下りたことまで含めて正しい（実際の写真は 1600px / 220KiB で収まる）。
    assert thumbnails.DEFAULT_MAX_SIDE < max(reduced["width"], reduced["height"])
    assert max(reduced["width"], reduced["height"]) <= thumbnails.PREVIEW_MAX_SIDE


def test_an_asset_within_the_bound_is_still_sent_whole(tmp_path: Path):
    """縮小は上限を超えたときだけ。普通の生成物を毎回作り直さない。"""
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        asset = import_asset(client, "source", size=(64, 48))
        with client.websocket_connect("/ws", headers=headers) as socket:
            whole = call(socket, "assets.content", {"asset_id": asset["id"]})["result"]

    assert whole["reduced"] is False
    assert whole["mime_type"] == "image/png"
    assert base64.b64decode(whole["base64"]) == png_bytes((64, 48))


def test_a_photo_keeps_its_resolution_but_a_clip_keeps_the_old_bound(tmp_path: Path):
    """写真は撮ったままの寸法で預かる。動画は尺のぶんだけ復号するので別。

    2048x2048 は strict edit を入れたときの丸い数で、根拠は残っていなかった。
    「一部だけ直す」は塗った範囲＋64px しか生成せず、元画像の解像度はモデルに
    渡らない。縮めるのは、透かしを消すために写真全体の解像度を捨てることである。
    """
    from mediaforge.asset_import import MAX_IMPORT_PIXELS, MAX_VIDEO_IMPORT_PIXELS

    # 携帯の標準（12.2MP）も一眼の標準（24MP）も通る。
    assert 4032 * 3024 <= MAX_IMPORT_PIXELS
    assert 6000 * 4000 <= MAX_IMPORT_PIXELS
    # 1 ジョブが 1.6GB を抱える 48MP は取らない。
    assert 8000 * 6000 > MAX_IMPORT_PIXELS
    assert MAX_VIDEO_IMPORT_PIXELS == 2048 * 2048

    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        buffer = BytesIO()
        Image.new("RGBA", (4032, 3024), (20, 30, 40, 255)).save(buffer, format="PNG")
        response = client.post(
            "/api/v1/assets/import?purpose=source",
            content=buffer.getvalue(),
            headers={"Content-Type": "application/octet-stream"},
        )
    assert response.status_code == 201, response.text
    assert (response.json()["width"], response.json()["height"]) == (4032, 3024)


def test_an_upscale_takes_no_mask_and_no_chosen_size(tmp_path: Path):
    """拡大は塗る所も広げる所も無く、寸法も選べない。

    マスクを受けると「守られる所がある」ように見え、寸法を受けると倍率と
    食い違った値を選ばせることになる。出力は元画像と、重みが持つ倍率だけで
    決まる。掛け算は核が一度だけ行い、画面にも worker にもさせない。
    """
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        asset = import_asset(client, "source", size=(64, 48))
        mask = import_asset(client, "edit_mask", size=(64, 48))

        def submit(constraints: dict) -> dict:
            response = client.post("/api/v1/jobs", json={
                "operation": "image.edit", "local_only": True, "intent": "画質を上げる",
                "inputs": [{"asset_id": asset["id"]}],
                "constraints": {"edit_mode": "upscale", **constraints},
            })
            assert response.status_code == 202, response.text
            return wait_terminal(client, response.json()["id"])

        refused = submit({"editable_mask_asset_id": mask["id"]})
        assert refused["error"]["code"] == "invalid_constraint"
        assert "edit mask" in refused["error"]["message"]

        sized = submit({"width": 256, "height": 192})
        assert sized["error"]["code"] == "invalid_constraint"
        assert "scale" in sized["error"]["message"]

        protected = submit({"strict_edit": True})
        assert protected["error"]["code"] == "invalid_constraint"
        assert "strict_edit" in protected["error"]["message"]
