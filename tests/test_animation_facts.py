from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mediaforge.animation_facts import AnimationSettingsFact
from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.scenes import SceneError

ROOT = Path(__file__).parents[1]


class Action(dict[str, Any]):
    frame_range = (0.0, 48.0)


def action(**changes: Any) -> Action:
    return Action(media_forge_clip_schema=1, media_forge_rig_id="rig",
                  media_forge_clip_id="idle", media_forge_loop=False, **changes)


def worker(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setitem(__import__("sys").modules, "bpy", SimpleNamespace())
    spec = importlib.util.spec_from_file_location("scene_document_facts", ROOT / "worker_packs/blender/scene_document.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base() -> dict[str, Any]:
    return {"schema_version": "media-forge.blender-scene-validation@1", "blender_version": "4.5.13",
            "background": True, "autoexec_disabled": True, "objects": 2, "meshes": 1,
            "vertices": 114, "triangles": 224, "materials": 0, "images": 0, "animations": 1,
            "text_blocks": 0, "linked_libraries": 0, "external_images": 0, "unit_meters": 1.0}


def test_saved_loop_false_not_inferred_from_matching_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    report = worker(monkeypatch).animation_settings([action()], 24.0)
    assert report["clips"][0] == {"object_id": "rig", "clip_id": "idle", "frame_start": 0.0,
                                  "frame_end": 48.0, "loop_requested": False}
    SceneWorkspace._validate_worker_result({**base(), "animation_settings": report}, "4.5.13")
    # Older worker/revision omission remains accepted, but is not a zero-clip report.
    SceneWorkspace._validate_worker_result(base(), "4.5.13")


@pytest.mark.parametrize("change", [{"media_forge_loop": "false"}, {"media_forge_loop": None},
    {"media_forge_clip_schema": 0}, {"media_forge_rig_id": "../private"}, {"media_forge_clip_id": "X"}])
def test_unreportable_actions_are_counted(monkeypatch: pytest.MonkeyPatch, change: dict[str, Any]) -> None:
    value = action()
    value.update(change)
    report = worker(monkeypatch).animation_settings([value], 24.0)
    assert report["clips"] == [] and report["unreported_actions"] == 1
    SceneWorkspace._validate_worker_result({**base(), "animation_settings": report}, "4.5.13")


def test_bounded_duplicate_and_true_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    actions = []
    for index in range(35):
        value = action()
        value.update(media_forge_clip_id=f"clip{index}", media_forge_loop=True)
        actions.append(value)
    actions.insert(1, actions[0])
    report = worker(monkeypatch).animation_settings(actions, 30.0)
    assert len(report["clips"]) == 32 and report["unreported_actions"] == 4
    assert all(item["loop_requested"] is True for item in report["clips"])
    SceneWorkspace._validate_worker_result({**base(), "animations": 36, "animation_settings": report}, "4.5.13")


@pytest.mark.parametrize("failure", ["count", "fps", "nan", "reversed", "boolean", "extra", "duplicate"])
def test_core_rejects_malformed_worker_facts(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    report = worker(monkeypatch).animation_settings([action()], 24.0)
    if failure == "count": report["unreported_actions"] = 1
    elif failure == "fps": report["fps"] = 0
    elif failure == "nan": report["clips"][0]["frame_end"] = float("nan")
    elif failure == "reversed": report["clips"][0]["frame_end"] = -1
    elif failure == "boolean": report["clips"][0]["loop_requested"] = "false"
    elif failure == "extra": report["path"] = "/private"
    else: report["clips"] *= 2
    with pytest.raises(SceneError, match="animation"):
        SceneWorkspace._validate_worker_result({**base(), "animation_settings": report}, "4.5.13")


def test_public_animation_settings_schema_matches_model() -> None:
    assert json.loads((ROOT / "schemas/scene-animation-settings.json").read_text()) == AnimationSettingsFact.model_json_schema()
