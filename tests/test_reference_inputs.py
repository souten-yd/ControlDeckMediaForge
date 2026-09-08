"""参照画像の入口と、編集で寸法を名指しできること。

作った物しか参照にできないと、利用者が project へ置いた絵——下描き、既存の
キャラ表、UI の当たり——を渡す道が無い。取り込み口は Host の画面からしか届かず、
agent からは手が出せなかった。Host が出す読み取りの券をそのまま参照として
受け取る。
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

from conftest import wait_terminal
from test_host_execution import host_client


def _import(client, size=(320, 256), color=(40, 80, 120, 255)) -> str:
    encoded = io.BytesIO()
    Image.new("RGBA", size, color).save(encoded, format="PNG")
    response = client.post(
        "/api/v1/assets/import?purpose=source",
        content=encoded.getvalue(),
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_a_project_file_can_be_a_reference_through_a_read_grant(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
    with client:
        response = client.post(
            "/addon/v1/agent/generate",
            json={
                "input": {
                    "operation": "image.edit",
                    "intent": "the same character, walking",
                    "inputs": [{"grant_id": "grant:read-1"}],
                    "local_only": True,
                },
                "correlation": {"job_id": "host-agent"},
            },
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert response.json()["asset_id"].startswith("asset_")


def test_an_unreadable_grant_is_refused_before_anything_is_generated(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
    with client:
        response = client.post(
            "/addon/v1/agent/generate",
            json={
                "input": {
                    "operation": "image.edit",
                    "intent": "walking",
                    "inputs": [{"grant_id": "grant:missing"}],
                    "local_only": True,
                },
                "correlation": {"job_id": "host-agent"},
            },
            headers=headers,
        )
        assert response.status_code >= 400, response.text
        # 何も作らずに断る。
        assert client.get("/api/v1/assets").json()["items"] == []


def test_an_input_naming_only_a_grant_never_reaches_a_job():
    """券は「読んでよい」であって物ではない。取り込み前に走らせない。"""
    import pytest

    from mediaforge.domain import AssetInput, JobRequest
    from mediaforge.jobs import JobManager

    request = JobRequest(
        operation="image.edit",
        intent="walking",
        inputs=[AssetInput(grant_id="grant:read-1")],
    )
    with pytest.raises(ValueError, match="grant"):
        JobManager._require_resolved_inputs(request)


def test_a_batch_item_with_references_becomes_an_edit(tmp_path: Path):
    client, headers, state = host_client(tmp_path)
    with client:
        first = _import(client)
        second = _import(client, color=(220, 90, 30, 255))
        response = client.post(
            "/addon/v1/agent/generate/batch",
            json={
                "input": {"items": [
                    {"intent": "a slime", "role": "sprite"},
                    {"intent": "the same hero, walking", "references": [first]},
                    {"intent": "the same hero from behind", "references": [first, second]},
                    {"intent": "the same hero, from a project drawing", "references": ["grant:read-1"]},
                ]},
                "correlation": {"job_id": "host-agent"},
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["succeeded_count"] == 4, body
        edited = body["items"][1]["asset_id"]
        provenance = client.get(f"/api/v1/assets/{edited}/provenance").json()
    assert provenance["operation"] == "image.edit"
    assert provenance["parent_asset_ids"] == [first]


def test_a_batch_item_can_ask_for_several_takes(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
    with client:
        response = client.post(
            "/addon/v1/agent/generate/batch",
            json={
                "input": {"items": [{"intent": "a slime", "role": "sprite", "count": 3}]},
                "correlation": {"job_id": "host-agent"},
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["succeeded_count"] == 1, body
        assert len(body["items"][0]["asset_ids"]) == 3, body["items"][0]


def test_a_batch_refuses_an_unreadable_item_before_running_anything(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
    with client:
        response = client.post(
            "/addon/v1/agent/generate/batch",
            json={
                "input": {"items": [
                    {"intent": "a slime", "role": "sprite"},
                    {"intent": "too many", "references": ["a", "b", "c", "d", "e"]},
                ]},
                "correlation": {"job_id": "host-agent"},
            },
            headers=headers,
        )
        assert response.status_code == 422, response.text
        assert client.get("/api/v1/assets").json()["items"] == []


def test_an_edit_keeps_the_canvas_the_caller_named(client):
    """schema は「明示した width/height は常に勝つ」と書いている。書いたことは守る。

    編集の寸法は既定では元画像から導かれ、モデルの学習寸法のバケットで生成される。
    768x768 を頼んだのに 1024x1024 が返っていた。
    """
    source = _import(client, size=(320, 256))
    created = client.post("/api/v1/jobs", json={
        "operation": "image.edit",
        "intent": "the same subject, walking",
        "inputs": [{"asset_id": source}],
        "constraints": {"width": 512, "height": 512},
        "local_only": True,
    }).json()
    terminal = wait_terminal(client, created["id"])
    assert terminal["status"] == "succeeded", terminal
    asset = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}").json()
    assert (asset["width"], asset["height"]) == (512, 512), asset


def test_a_strict_edit_still_derives_its_canvas_from_the_source(client):
    """守る画素があるものは自前の不変量を持っている。そちらが先である。"""
    source = _import(client, size=(320, 256))
    mask = _import(client, size=(320, 256), color=(255, 255, 255, 255))
    created = client.post("/api/v1/jobs", json={
        "operation": "image.edit",
        "intent": "repaint the marked area",
        "inputs": [{"asset_id": source}],
        "constraints": {
            "strict_edit": True,
            "edit_mode": "inpaint",
            "editable_mask_asset_id": mask,
            "width": 512,
            "height": 512,
        },
        "local_only": True,
    }).json()
    terminal = wait_terminal(client, created["id"])
    # 元と違う画面を求めた strict edit は、今までどおり自分の規則で断られる。
    # 名指しの寸法を通す道を足しても、守る画素がある側の不変量は動かない。
    assert terminal["status"] == "failed", terminal
    assert terminal["error"]["code"] == "invalid_dimensions", terminal


def test_the_contract_tells_an_agent_that_these_exist():
    """動くのに契約に書いていなければ、agent からは無いのと同じである。"""
    root = Path(__file__).resolve().parents[1]
    job_request = json.loads((root / "schemas/job-request.json").read_text(encoding="utf-8"))
    constraints = job_request["properties"]["constraints"]["properties"]
    assert "multi_reference" in constraints["edit_mode"]["enum"]
    assert "variation" in constraints["edit_mode"]["enum"]
    assert constraints["edit_mode"]["description"]
    assert constraints["strict_edit"]["description"]
    assert job_request["$defs"]["output"]["properties"]["count"]["description"]
    asset_input = job_request["$defs"]["assetInput"]
    assert "grant_id" in asset_input["properties"]
    assert asset_input["oneOf"] == [{"required": ["asset_id"]}, {"required": ["grant_id"]}]

    batch = json.loads((root / "schemas/media-generate-batch.json").read_text(encoding="utf-8"))
    item = batch["$defs"]["batchItem"]["properties"]
    assert item["references"]["maxItems"] == 4
    assert item["count"]["maximum"] == 8
