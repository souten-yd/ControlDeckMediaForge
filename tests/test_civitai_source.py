"""配布元として Civitai を扱う。

Civitai は diffusers repository を配らない。1 version = 1 safetensors で、
ファイル自身はどの系統か名乗らない。配布元の申告を持ち歩く必要がある。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from mediaforge.civitai import CivitaiError, CivitaiSource, repo_id_for
from mediaforge.custom_models import CustomModelCatalog, CustomModelError, source_of


def version_document(**overrides) -> dict:
    document = {
        "id": 128713,
        "name": "8",
        "baseModel": "SD 1.5",
        "publishedAt": "2024-01-01T00:00:00Z",
        "files": [{
            "name": "dreamshaper_8.safetensors",
            "type": "Model",
            "sizeKB": 2082642.47,
            "metadata": {"format": "SafeTensor", "fp": "fp16"},
            "hashes": {"SHA256": "8" * 64},
            "downloadUrl": "https://civitai.com/api/download/models/128713",
        }],
    }
    document.update(overrides)
    return document


def source_with(handler) -> CivitaiSource:
    return CivitaiSource(transport=httpx.MockTransport(handler))


def test_the_site_is_asked_with_a_user_agent_it_accepts():
    """実測: 既定の User-Agent は 403 で返る。認証の問題ではないので、そこで
    利用者に鍵を求めると嘘の理由を出すことになる。"""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={"items": []})

    asyncio.run(source_with(handler).search("anime"))

    assert "MediaForge" in seen["agent"]


def test_only_checkpoints_are_listed():
    """Civitai の大半は LoRA だが、Media Forge に LoRA の経路がまだ無い。
    並べると、取り込めても使えないものが結果を埋める。"""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"items": []})

    asyncio.run(source_with(handler).search("anime"))

    assert seen["types"] == "Checkpoint"
    assert seen["nsfw"] == "false"


def test_a_version_without_a_safetensors_body_is_not_listed():
    """押せない候補を並べない。"""
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [{
            "id": 1, "name": "x", "stats": {},
            "modelVersions": [version_document(files=[{
                "name": "x.ckpt", "type": "Model", "sizeKB": 10,
                "metadata": {"format": "PickleTensor"},
                "hashes": {"SHA256": "9" * 64},
                "downloadUrl": "https://civitai.com/api/download/models/1",
            }])],
        }]})

    assert asyncio.run(source_with(handler).search("x")) == []


def test_a_version_that_does_not_state_its_family_is_refused():
    """系統を当てて読むと、落ちるか、静かに違う絵が出る。"""
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=version_document(baseModel=""))

    with pytest.raises(CivitaiError) as failure:
        asyncio.run(source_with(handler).version(4384, 128713))

    assert failure.value.code == "custom_model_family_unknown"


def test_a_version_without_a_published_digest_is_refused():
    """手元で計算した digest は「壊れていない」しか言えない。配布元の意図した
    中身かどうかは言えない。"""
    def handler(_request: httpx.Request) -> httpx.Response:
        document = version_document()
        document["files"][0]["hashes"] = {}
        return httpx.Response(200, json=document)

    with pytest.raises(CivitaiError) as failure:
        asyncio.run(source_with(handler).version(4384, 128713))

    assert failure.value.code == "custom_model_digest_missing"


def test_the_model_id_is_the_number_not_the_name():
    """名前は作者が後から変えられる。来歴として意味を持つのは番号の方。"""
    assert repo_id_for(4384) == "civitai/4384"


def test_the_site_is_decided_by_the_shape_of_the_id():
    """検索の既定は Civitai だが、取り込みでその既定を当てると Hugging Face の
    repository を Civitai に問い合わせることになる。"""
    assert source_of("civitai/4384") == "civitai"
    assert source_of("stabilityai/stable-diffusion-xl-base-1.0") == "huggingface"
    # 名前が civitai で始まるだけの Hugging Face repository を取り違えない。
    assert source_of("civitai/some-model") == "huggingface"


def test_a_resolved_civitai_model_carries_what_the_runtime_needs(tmp_path: Path):
    """単一ファイルは config を持たない。寸法も系統も、ここで載せなければ
    実行時には分からない。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=version_document())

    catalog = CustomModelCatalog(tmp_path / "custom.json", transport=httpx.MockTransport(handler))
    resolution = asyncio.run(catalog.resolve_source("", "civitai/4384", "128713"))

    assert resolution.runtime_adapter == "diffusers.sdxl-single-file"
    assert resolution.runtime_options["base_model"] == "SD 1.5"
    # SD 1.5 は 512 で学習されている。1024 にすると構図が二重になる。
    assert resolution.runtime_options["native_width"] == 512
    assert resolution.weights[0].sha256 == "8" * 64


def test_the_options_reach_the_stored_entry(tmp_path: Path):
    """resolve では載っているのに entry に書き出されなければ、次に読んだ
    ときには消えている。"""
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=version_document())

    catalog = CustomModelCatalog(tmp_path / "custom.json", transport=httpx.MockTransport(handler))
    resolution = asyncio.run(catalog.resolve_source("", "civitai/4384", "128713"))
    entry = catalog.add(
        resolution, display_name="DreamShaper 8", license_acceptance=resolution.license
    )

    stored = json.loads((tmp_path / "custom.json").read_text(encoding="utf-8"))
    options = stored["entries"][0]["registry"]["runtime_options"]
    assert options["base_model"] == "SD 1.5"
    assert entry["registry"]["runtime_adapter"] == "diffusers.sdxl-single-file"


def test_an_unknown_site_is_refused(tmp_path: Path):
    catalog = CustomModelCatalog(tmp_path / "custom.json")

    with pytest.raises(CustomModelError) as failure:
        asyncio.run(catalog.search_source("elsewhere", "anime"))

    assert failure.value.code == "custom_model_source_invalid"


def test_the_download_url_follows_the_site(tmp_path: Path):
    """Hugging Face の経路を直書きしていたので、配布元を足すと必ずそちらへ
    流れていた。"""
    from mediaforge.model_manager import ModelOperationManager
    from mediaforge.models import ModelSource

    build = ModelOperationManager.__new__(ModelOperationManager)
    build.download_origin = "https://huggingface.co"
    build.civitai_origin = "https://civitai.com"

    civitai = build._download_url(ModelSource("civitai", "civitai/4384", "128713"), "x.safetensors")
    hugging = build._download_url(ModelSource("huggingface", "owner/model", "a" * 40), "x.safetensors")

    assert civitai == "https://civitai.com/api/download/models/128713"
    assert "huggingface.co/owner/model/resolve/" in hugging


def test_another_sites_token_is_never_sent(tmp_path: Path, monkeypatch):
    """他所の資格情報を、要求してもいない相手に渡さない。"""
    from mediaforge.model_manager import ModelOperationManager
    from mediaforge.models import ModelSource

    build = ModelOperationManager.__new__(ModelOperationManager)
    monkeypatch.setenv("HF_TOKEN", "hf-secret")
    monkeypatch.delenv("CIVITAI_TOKEN", raising=False)

    headers = build._download_headers(ModelSource("civitai", "civitai/4384", "128713"))

    assert "hf-secret" not in json.dumps(headers)
    assert "MediaForge" in headers["User-Agent"]
