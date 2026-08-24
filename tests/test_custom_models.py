"""G6 S6: 利用者が追加する Hugging Face モデル。

curated な catalog を信頼経路として保ったまま、明示的な第 2 経路を足す。
検証可能性を作っている規則（revision 固定、digest 検証、ライセンス明示承諾、
実測前は unroutable）は、追加分にもそのまま適用する。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from mediaforge.custom_models import (
    UNSUPPORTED_ADAPTER,
    CustomModelCatalog,
    CustomModelError,
)
from mediaforge.models import ModelRegistry, ModelState

COMMIT = "7" * 40


def hub_payload(**overrides) -> dict:
    value = {
        "sha": COMMIT,
        "gated": False,
        "library_name": "diffusers",
        "pipeline_tag": "text-to-image",
        "cardData": {"license": "openrail++"},
        "siblings": [
            {"rfilename": "model_index.json", "size": 500},
            {"rfilename": "unet/config.json", "size": 900},
            {
                "rfilename": "unet/diffusion_pytorch_model.safetensors",
                "size": 5_000_000_000,
                "lfs": {"sha256": "a" * 64, "size": 5_000_000_000},
            },
            {
                "rfilename": "vae/diffusion_pytorch_model.safetensors",
                "size": 300_000_000,
                "lfs": {"sha256": "b" * 64, "size": 300_000_000},
            },
        ],
    }
    value.update(overrides)
    return value


def catalog(tmp_path: Path, payload: dict | int) -> CustomModelCatalog:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(payload, int):
            return httpx.Response(payload)
        return httpx.Response(200, json=payload)

    return CustomModelCatalog(
        tmp_path / "custom-models.json",
        origin="https://hub.test",
        transport=httpx.MockTransport(handler),
    )


def resolve(store: CustomModelCatalog, repo: str = "owner/sdxl", revision: str = "main"):
    return asyncio.run(store.resolve(repo, revision))


# ── 解決 ────────────────────────────────────────────────────────────────


def test_a_moving_revision_is_pinned_to_an_immutable_commit(tmp_path: Path):
    """main のまま取り込むと、次に取得したときの中身が変わる。"""
    resolution = resolve(catalog(tmp_path, hub_payload()), revision="main")

    assert resolution.requested_revision == "main"
    assert resolution.revision == COMMIT


def test_every_weight_carries_the_digest_the_hub_reported(tmp_path: Path):
    resolution = resolve(catalog(tmp_path, hub_payload()))

    assert [item.path for item in resolution.weights] == [
        "unet/diffusion_pytorch_model.safetensors",
        "vae/diffusion_pytorch_model.safetensors",
    ]
    assert all(len(item.sha256) == 64 for item in resolution.weights)
    assert resolution.total_bytes == 5_300_000_000


def test_a_weight_without_a_digest_is_refused(tmp_path: Path):
    """検証できないものを取り込まない。curated 経路と同じ基準を守る。"""
    payload = hub_payload(siblings=[
        {"rfilename": "unet/diffusion_pytorch_model.safetensors", "size": 10, "lfs": {"size": 10}},
    ])

    with pytest.raises(CustomModelError) as exc:
        resolve(catalog(tmp_path, payload))

    assert exc.value.code == "custom_model_digest_missing"


def test_a_repository_without_weights_is_refused(tmp_path: Path):
    payload = hub_payload(siblings=[{"rfilename": "README.md", "size": 10}])

    with pytest.raises(CustomModelError) as exc:
        resolve(catalog(tmp_path, payload))

    assert exc.value.code == "custom_model_no_weights"


def test_an_unknown_repository_is_reported_as_not_found(tmp_path: Path):
    with pytest.raises(CustomModelError) as exc:
        resolve(catalog(tmp_path, 404))

    assert exc.value.code == "custom_model_not_found"


def test_a_gated_repository_is_reported_instead_of_retried(tmp_path: Path):
    with pytest.raises(CustomModelError) as exc:
        resolve(catalog(tmp_path, 403))

    assert exc.value.code == "custom_model_access_denied"


def test_an_unusable_runtime_is_named_before_anything_is_downloaded(tmp_path: Path):
    """推測で adapter を割り当てない。導入してから生成で落ちるより先に言う。"""
    resolution = resolve(catalog(tmp_path, hub_payload(library_name="transformers")))

    assert resolution.runtime_adapter == UNSUPPORTED_ADAPTER
    assert resolution.usable_for_generation is False
    assert any("Diffusers" in warning for warning in resolution.warnings)


def test_a_path_escape_in_the_file_list_is_refused(tmp_path: Path):
    payload = hub_payload(siblings=[
        {"rfilename": "../escape.safetensors", "size": 10, "lfs": {"sha256": "c" * 64, "size": 10}},
    ])

    with pytest.raises(CustomModelError) as exc:
        resolve(catalog(tmp_path, payload))

    assert exc.value.code == "custom_model_path_invalid"


# ── 追加 ────────────────────────────────────────────────────────────────


def test_adding_requires_accepting_the_licence_that_was_shown(tmp_path: Path):
    store = catalog(tmp_path, hub_payload())
    resolution = resolve(store)

    with pytest.raises(CustomModelError) as exc:
        store.add(resolution, display_name="SDXL", license_acceptance="whatever")

    assert exc.value.code == "custom_model_license_not_accepted"
    assert store.entries() == []


def test_an_added_model_is_not_routable_until_it_is_measured(tmp_path: Path):
    """実測しないと使わせない gate を、追加分にもそのまま適用する。"""
    store = catalog(tmp_path, hub_payload())
    resolution = resolve(store)

    entry = store.add(resolution, display_name="SDXL", license_acceptance="openrail++")

    assert entry["registry"]["state"] == "experimental"
    assert entry["registry"]["measurement_confidence"] == "low"
    assert entry["catalog"]["source"]["revision"] == COMMIT


def test_the_same_model_cannot_be_added_twice(tmp_path: Path):
    store = catalog(tmp_path, hub_payload())
    resolution = resolve(store)
    store.add(resolution, display_name="SDXL", license_acceptance="openrail++")

    with pytest.raises(CustomModelError) as exc:
        store.add(resolution, display_name="SDXL", license_acceptance="openrail++")

    assert exc.value.code == "custom_model_exists"


def test_removing_an_entry_leaves_the_rest(tmp_path: Path):
    store = catalog(tmp_path, hub_payload())
    store.add(resolve(store, "owner/one"), display_name="one", license_acceptance="openrail++")
    store.add(resolve(store, "owner/two"), display_name="two", license_acceptance="openrail++")

    store.remove("owner/one")

    assert [item["registry"]["model_id"] for item in store.entries()] == ["owner/two"]


def test_an_unreadable_custom_file_never_costs_the_shipped_catalog(tmp_path: Path):
    """追加分が壊れていても、同梱 catalog まで失わせない。"""
    path = tmp_path / "custom-models.json"
    path.write_text("{ not json", encoding="utf-8")
    store = CustomModelCatalog(path)

    assert store.entries() == []
    assert store.manifests() == ([], [])


# ── registry への合流 ───────────────────────────────────────────────────


def test_an_added_entry_passes_the_same_parser_as_a_shipped_one(tmp_path: Path):
    """追加分に弱い検証を用意しない。同じ parser を通す。"""
    store = catalog(tmp_path, hub_payload())
    store.add(resolve(store), display_name="SDXL", license_acceptance="openrail++")
    extra_models, extra_catalog = store.manifests()

    shipped = tmp_path / "models.json"
    shipped.write_text(json.dumps({"schema_version": "1.0", "models": []}), encoding="utf-8")
    shipped_catalog = tmp_path / "catalog.json"
    shipped_catalog.write_text(json.dumps({"schema_version": "1.0", "models": []}), encoding="utf-8")

    registry = ModelRegistry.load(
        shipped,
        catalog_manifest=shipped_catalog,
        extra_models=extra_models,
        extra_catalog=extra_catalog,
    )

    descriptors = registry.all()
    assert [item.model_id for item in descriptors] == ["owner/sdxl"]
    assert descriptors[0].state == ModelState.EXPERIMENTAL
    assert descriptors[0].revision == COMMIT
    assert len(descriptors[0].weights) == 2


def test_a_repository_over_the_download_cap_is_named_before_adding(tmp_path: Path):
    """実測: stabilityai/sdxl-turbo は全 variant を数えると 42.5GB で上限 32GB を超える。
    取得を始めてから落とすより先に伝える。"""
    payload = hub_payload(siblings=[
        {"rfilename": "model_index.json", "size": 500},
        {
            "rfilename": "huge.safetensors",
            "size": 40_000_000_000,
            "lfs": {"sha256": "d" * 64, "size": 40_000_000_000},
        },
    ])
    store = catalog(tmp_path, payload)
    resolution = resolve(store)

    assert resolution.within_download_cap is False
    assert any("上限" in warning for warning in resolution.warnings)
    with pytest.raises(CustomModelError) as exc:
        store.add(resolution, display_name="huge", license_acceptance="openrail++")
    assert exc.value.code == "custom_model_too_large"


# ── variant 選択 ────────────────────────────────────────────────────────

# 実測: stabilityai/stable-diffusion-xl-base-1.0 の全ファイルは 49,952,537,087 バイト。
# その大半は同じ重みの Flax / ONNX / OpenVINO 版と fp32 / fp16 の二重持ちで、
# ひとつ選ぶと 7,105,346,772 バイトになる。選ばないと導入上限 32GB を超え、
# まともな repository がひとつも入らない。


def weight(path: str, size: int) -> dict:
    return {"rfilename": path, "size": size, "lfs": {"sha256": "f" * 64, "size": size}}


def test_only_one_runtime_variant_of_each_component_is_taken(tmp_path: Path):
    payload = hub_payload(siblings=[
        weight("unet/diffusion_pytorch_model.safetensors", 10_000),
        weight("unet/diffusion_pytorch_model.fp16.safetensors", 5_000),
        weight("unet/diffusion_flax_model.msgpack", 10_000),
        weight("unet/model.onnx_data", 10_000),
        weight("unet/openvino_model.bin", 10_000),
        weight("vae/diffusion_pytorch_model.fp16.safetensors", 100),
    ])

    resolution = resolve(catalog(tmp_path, payload))

    assert [item.path for item in resolution.weights] == [
        "unet/diffusion_pytorch_model.fp16.safetensors",
        "vae/diffusion_pytorch_model.fp16.safetensors",
    ]
    assert resolution.total_bytes == 5_100
    assert any("重複する重み" in warning for warning in resolution.warnings)


def test_a_single_file_checkpoint_is_skipped_when_component_folders_exist(tmp_path: Path):
    payload = hub_payload(siblings=[
        weight("sd_xl_base_1.0.safetensors", 6_000),
        weight("unet/diffusion_pytorch_model.fp16.safetensors", 500),
    ])

    resolution = resolve(catalog(tmp_path, payload))

    assert [item.path for item in resolution.weights] == [
        "unet/diffusion_pytorch_model.fp16.safetensors"
    ]


def test_a_single_file_repository_still_keeps_its_only_weight(tmp_path: Path):
    payload = hub_payload(siblings=[weight("model.safetensors", 6_000)])

    resolution = resolve(catalog(tmp_path, payload))

    assert [item.path for item in resolution.weights] == ["model.safetensors"]


def test_every_shard_of_a_sharded_weight_survives(tmp_path: Path):
    """shard を variant と取り違えて落とすと、モデルが壊れて届く。"""
    payload = hub_payload(siblings=[
        weight("text_encoder/model-00001-of-00002.safetensors", 100),
        weight("text_encoder/model-00002-of-00002.safetensors", 200),
    ])

    resolution = resolve(catalog(tmp_path, payload))

    assert [item.path for item in resolution.weights] == [
        "text_encoder/model-00001-of-00002.safetensors",
        "text_encoder/model-00002-of-00002.safetensors",
    ]
    assert resolution.total_bytes == 300
