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


# ── 配布元の検索 ────────────────────────────────────────────────────────


def search_catalog(tmp_path: Path, payload):
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(payload, int):
            return httpx.Response(payload)
        return httpx.Response(200, json=payload, request=request)

    return CustomModelCatalog(
        tmp_path / "custom-models.json",
        origin="https://hub.test",
        transport=httpx.MockTransport(handler),
    )


def listing(repo_id: str, downloads: int = 10, likes: int = 1) -> dict:
    return {
        "id": repo_id,
        "author": repo_id.split("/")[0],
        "downloads": downloads,
        "likes": likes,
        "lastModified": "2026-01-02T03:04:05.000Z",
        "pipeline_tag": "text-to-image",
        "library_name": "diffusers",
        "gated": False,
        "tags": ["diffusers", "text-to-image", "license:openrail++"],
    }


def test_search_returns_the_facts_a_person_sorts_on(tmp_path: Path):
    store = search_catalog(tmp_path, [listing("owner/one", downloads=500, likes=9)])

    rows = asyncio.run(store.search("sd"))

    assert len(rows) == 1
    row = rows[0].document()
    assert row["repo_id"] == "owner/one"
    assert row["downloads"] == 500 and row["likes"] == 9
    assert row["last_modified"].startswith("2026-01-02")
    assert row["license"] == "openrail++"


@pytest.mark.parametrize("sort", ["downloads", "likes", "lastModified", "createdAt"])
def test_every_offered_sort_is_accepted(tmp_path: Path, sort: str):
    store = search_catalog(tmp_path, [listing("owner/one")])

    assert asyncio.run(store.search("sd", sort=sort))


def test_an_unknown_sort_is_refused_rather_than_silently_ignored(tmp_path: Path):
    """黙って別の順で返すと、利用者は並べ替えたつもりのまま誤った表を読む。"""
    store = search_catalog(tmp_path, [listing("owner/one")])

    with pytest.raises(CustomModelError) as exc:
        asyncio.run(store.search("sd", sort="stars"))

    assert exc.value.code == "custom_model_sort_invalid"


def test_search_only_offers_pipelines_that_can_actually_be_used(tmp_path: Path):
    store = search_catalog(tmp_path, [listing("owner/one")])

    with pytest.raises(CustomModelError) as exc:
        asyncio.run(store.search("sd", pipeline_tag="text-generation"))

    assert exc.value.code == "custom_model_pipeline_invalid"


def test_search_asks_the_source_only_for_usable_candidates(tmp_path: Path):
    """取り込めない形式ばかり並べても選べない。"""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=[])

    store = CustomModelCatalog(
        tmp_path / "custom-models.json",
        origin="https://hub.test",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(store.search("anything"))

    assert seen["library"] == "diffusers"
    assert seen["pipeline_tag"] == "text-to-image"


def test_a_malformed_entry_is_skipped_rather_than_failing_the_search(tmp_path: Path):
    store = search_catalog(tmp_path, ["not-an-object", {"id": "no-slash"}, listing("owner/ok")])

    rows = asyncio.run(store.search("sd"))

    assert [row.repo_id for row in rows] == ["owner/ok"]


def test_an_unreachable_source_is_reported_with_a_code(tmp_path: Path):
    store = search_catalog(tmp_path, 503)

    with pytest.raises(CustomModelError) as exc:
        asyncio.run(store.search("sd"))

    assert exc.value.code == "custom_model_source_unreachable"


def test_search_reports_the_weight_size_from_the_declared_dtypes():
    """押す前に知りたいのは容量である。一覧 API は容量を返さないので、
    safetensors の要素数と型から重みそのものの大きさを出す。"""
    from mediaforge.custom_models import _weights_from_safetensors

    assert _weights_from_safetensors(
        {"total": 11901408320, "parameters": {"BF16": 11901408320}}
    ) == (23802816640, "BF16")
    assert _weights_from_safetensors(
        {"parameters": {"F32": 1_000, "BF16": 2_000}}
    ) == (8_000, "BF16")
    # 知らない型を 0 バイトとして黙って足すと、総量が過少に出る。分からないと言う。
    assert _weights_from_safetensors({"parameters": {"MX6": 1_000}}) == (0, "")
    for missing in (None, {}, {"total": 5}, {"parameters": []}):
        assert _weights_from_safetensors(missing) == (0, "")


def test_gguf_repositories_report_their_distributed_size():
    """GGUF 配布は safetensors を持たない。容量が空欄のままになっていた。"""
    from mediaforge.custom_models import _weights_from_gguf

    assert _weights_from_gguf(
        {"total": 11901408320, "architecture": "flux", "totalFileSize": 23802870944}
    ) == (23802870944, "GGUF")
    for missing in (None, {}, {"total": 5}, {"totalFileSize": 0}, {"totalFileSize": "12"}):
        assert _weights_from_gguf(missing) == (0, "")


def _local_sdxl(root: Path, *, variant: str = "fp16") -> Path:
    root.mkdir(parents=True)
    (root / "model_index.json").write_text(
        json.dumps({"_class_name": "StableDiffusionXLPipeline", "_diffusers_version": "0.40.0"}),
        encoding="utf-8",
    )
    for component in ("unet", "vae"):
        (root / component).mkdir()
        (root / component / "config.json").write_text("{}", encoding="utf-8")
        (root / component / f"diffusion_pytorch_model.{variant}.safetensors").write_bytes(
            component.encode() * 32
        )
    return root


def test_a_local_directory_can_be_described_without_touching_the_network(tmp_path: Path):
    """既に手元にある重みが使えないと、別の道具で落としたものが死蔵される。"""
    catalog = CustomModelCatalog(tmp_path / "custom.json")
    resolved = catalog.resolve_local(str(_local_sdxl(tmp_path / "mine")), name="my-sdxl")

    assert resolved.repo_id == "local/my-sdxl"
    assert resolved.runtime_adapter == "diffusers.sdxl"
    assert resolved.capabilities == ("image.text_to_image",)
    assert [item.path for item in resolved.weights] == [
        "unet/diffusion_pytorch_model.fp16.safetensors",
        "vae/diffusion_pytorch_model.fp16.safetensors",
    ]
    assert all(len(item.sha256) == 64 for item in resolved.weights)
    assert "model_index.json" in resolved.required_files
    # 配布元 API が無いので digest の意味が変わる。黙って同じ顔をさせない。
    assert any("この機械で読み取った値" in warning for warning in resolved.warnings)
    # revision は中身から決める。フォルダは後から書き換わりうる。
    assert len(resolved.revision) == 64


def test_a_local_directory_that_is_not_a_pipeline_is_refused(tmp_path: Path):
    catalog = CustomModelCatalog(tmp_path / "custom.json")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CustomModelError) as failure:
        catalog.resolve_local(str(empty), name="nope")
    assert failure.value.code == "custom_model_not_diffusers"

    with pytest.raises(CustomModelError) as missing:
        catalog.resolve_local(str(tmp_path / "absent"), name="nope")
    assert missing.value.code == "custom_model_path_missing"

    with pytest.raises(CustomModelError) as relative:
        catalog.resolve_local("relative/path", name="nope")
    assert relative.value.code == "custom_model_path_invalid"

    for bad in ("", "has space", "a/b", "x" * 65):
        with pytest.raises(CustomModelError) as name:
            catalog.resolve_local(str(_local_sdxl(tmp_path / f"m{len(bad)}")), name=bad)
        assert name.value.code == "custom_model_name_invalid"


def test_an_unknown_pipeline_is_imported_but_not_claimed_to_be_runnable(tmp_path: Path):
    """取り込めることと生成に使えることは別。推測で adapter を割り当てない。"""
    catalog = CustomModelCatalog(tmp_path / "custom.json")
    root = _local_sdxl(tmp_path / "odd")
    (root / "model_index.json").write_text(
        json.dumps({"_class_name": "SomeFuturePipeline"}), encoding="utf-8"
    )
    resolved = catalog.resolve_local(str(root), name="odd")

    assert resolved.runtime_adapter == UNSUPPORTED_ADAPTER
    assert resolved.capabilities == ()
    assert not resolved.usable_for_generation
    assert any("生成には使えません" in warning for warning in resolved.warnings)


def test_the_sd_family_maps_to_the_measured_adapter():
    """diffusers.sdxl は AutoPipelineForText2Image の上に載っており、
    SD 1.x / 2.x / XL / 3.x を同じ入口で扱える。実測は SSD-1B（SDXL 系）。"""
    from mediaforge.custom_models import _PIPELINE_ADAPTERS

    for pipeline in (
        "StableDiffusionPipeline",          # SD 1.x / 2.x
        "StableDiffusionXLPipeline",        # SDXL
        "StableDiffusion3Pipeline",         # SD 3.x
        "StableDiffusionInpaintPipeline",
        "StableDiffusionXLImg2ImgPipeline",
    ):
        assert _PIPELINE_ADAPTERS[pipeline] == "diffusers.sdxl", pipeline


def test_another_family_is_not_swept_into_the_sd_adapter():
    """タグ（diffusers + text-to-image）だけで決めると、FLUX や Qwen-Image まで
    巻き込んで「入るが生成で落ちる」ものを作る。クラス名で見る。"""
    from mediaforge.custom_models import _PIPELINE_ADAPTERS

    for pipeline in ("FluxPipeline", "QwenImagePipeline", "WanPipeline", "SomeFuturePipeline"):
        assert pipeline not in _PIPELINE_ADAPTERS, pipeline
