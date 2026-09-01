"""高画質化で、出す大きさを選ぶ。

重みは 1 つの倍率しか持たない。それを唯一の出す寸法にすると、荒い写真を持って
きた人は「4 倍にする」しか選べない。もう十分に大きい写真の荒さだけ取りたい
ときに、4 倍は要らないものである。

倍率は重みの倍率の約数までを受ける。約数に限るのは、割り切れる縮小だけが画素の
格子を保つからで、そこに補間の種類を選ぶ余地は無い（同じ絵を入れれば同じ絵が
出る、という直しの前提が崩れる）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from mediaforge.domain import Asset, JobRequest, Provenance
from mediaforge.jobs import JobManager, WorkerFailure
from mediaforge.store import Store, utc_now

MANIFESTS = Path(__file__).parents[1] / "worker_packs" / "image"


def _manager(tmp_path: Path) -> tuple[JobManager, Store]:
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(
        store,
        model_manifest=MANIFESTS / "models.json",
        model_catalog_manifest=MANIFESTS / "catalog.json",
        hf_home=tmp_path / "hf",
        model_store_root=tmp_path / "models",
    )
    return manager, store


def _source(store: Store, tmp_path: Path, size: tuple[int, int]) -> str:
    """幅と高さだけが要る。中身は読まれない（寸法は核が資産から取る）。"""
    path = tmp_path / f"source-{size[0]}x{size[1]}.png"
    Image.new("RGBA", size, (10, 20, 30, 255)).save(path, format="PNG")
    owner = store.create_job(JobRequest(operation="image.generate", intent="fixture")).id
    # 資産 ID の形は core が検証する。寸法から作った目印を 32 桁の 16 進へ収める。
    asset_id = "asset_" + f"{size[0]:04x}{size[1]:04x}".ljust(32, "0")
    provenance_id = "prov_" + asset_id.removeprefix("asset_")
    now = utc_now()
    asset = Asset(
        id=asset_id,
        job_id=owner,
        parent_asset_ids=[],
        mime_type="image/png",
        width=size[0],
        height=size[1],
        size_bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        suggested_filename="source.png",
        provenance_id=provenance_id,
        created_at=now,
    )
    provenance = Provenance(
        id=provenance_id,
        asset_id=asset_id,
        parent_asset_ids=[],
        operation="asset.import",
        intent="test source",
        model_id="media-forge/test-fixture",
        model_version="1",
        weights_hash="sha256:" + "0" * 64,
        license="CC0-1.0",
        runtime_adapter="test-fixture",
        runtime_version="1",
        tool_versions={"media-forge": "test"},
        seed=0,
        parameters={},
        reference_asset_hashes={},
        postprocessing=[],
        validation=[],
        warnings=[],
        output_sha256=asset.sha256,
        created_at=now,
    )
    store.register_asset(asset, provenance, path)
    return asset_id


def _descriptor(**upscale):
    from tests.test_image_evaluation import descriptor

    return descriptor(
        runtime_adapter="spandrel.upscale",
        capabilities=("image.upscale",),
        upscale=upscale,
    )


def _resolve(manager: JobManager, store: Store, asset_id: str, selected, **constraints):
    request = JobRequest(
        operation="image.edit",
        intent="画質を上げる",
        inputs=[{"asset_id": asset_id}],
        constraints={"edit_mode": "upscale", **constraints},
    )
    job = store.get_job(store.create_job(request).id)
    return manager._resolved_request(job, selected)["constraints"]


def test_without_a_choice_the_weights_own_scale_is_used(tmp_path: Path):
    """宣言が無ければ今までどおり。倍率を選べるようにしても既定は動かさない。"""
    manager, store = _manager(tmp_path)
    asset = _source(store, tmp_path, (640, 480))
    selected = _descriptor(scale=4, target_scales=[1, 2, 4])

    resolved = _resolve(manager, store, asset, selected)

    assert (resolved["width"], resolved["height"]) == (2560, 1920)
    assert resolved["upscale_scale"] == 4


def test_the_original_size_can_be_asked_for(tmp_path: Path):
    """荒さだけ取りたい人は、大きくしたいわけではない。"""
    manager, store = _manager(tmp_path)
    asset = _source(store, tmp_path, (640, 480))
    selected = _descriptor(scale=4, target_scales=[1, 2, 4])

    resolved = _resolve(manager, store, asset, selected, upscale_scale=1)

    assert (resolved["width"], resolved["height"]) == (640, 480)
    assert resolved["upscale_scale"] == 1
    # 標本化しないものに歩数を渡さない。worker が使わない値を検査することになる。
    assert "steps" not in resolved


def test_a_scale_of_one_model_is_not_refused_for_having_no_scale(tmp_path: Path):
    """ブレ補正と消して埋めるは倍率 1 で、拡大と同じ経路を通る。

    2 以上を求める門を置くと、その 2 つが「倍率を宣言していません」で必ず
    落ちる。画面には出ているのに押すと失敗する、という形で表に出る。
    """
    manager, store = _manager(tmp_path)
    asset = _source(store, tmp_path, (640, 480))
    selected = _descriptor(scale=1, max_source_pixels=24_000_000)

    resolved = _resolve(manager, store, asset, selected)

    assert (resolved["width"], resolved["height"]) == (640, 480)
    assert resolved["upscale_scale"] == 1


def test_a_scale_the_weights_cannot_divide_is_refused_by_name(tmp_path: Path):
    """3 倍は割り切れない。断るときは、代わりに選べるものを名指す。"""
    manager, store = _manager(tmp_path)
    asset = _source(store, tmp_path, (640, 480))
    selected = _descriptor(scale=4, target_scales=[1, 2, 4])

    with pytest.raises(WorkerFailure) as raised:
        _resolve(manager, store, asset, selected, upscale_scale=3)

    assert raised.value.code == "invalid_constraint"
    assert "1 倍・2 倍・4 倍" in str(raised.value)


def test_a_big_photo_keeps_the_scales_that_still_fit(tmp_path: Path):
    """4032x3024 は 12.2MP。4 倍は 195MP で上限を超え、原寸なら収まる。

    大きい写真をまるごと断らない。断るのは、その写真に対して出せない倍率の方
    である（前は入力の上限が倍率で決まっていたので、写真ごと断っていた）。
    """
    manager, store = _manager(tmp_path)
    asset = _source(store, tmp_path, (4032, 3024))
    selected = _descriptor(scale=4, target_scales=[1, 2, 4], max_source_pixels=24_000_000)

    resolved = _resolve(manager, store, asset, selected, upscale_scale=1)
    assert (resolved["width"], resolved["height"]) == (4032, 3024)

    with pytest.raises(WorkerFailure) as raised:
        _resolve(manager, store, asset, selected, upscale_scale=4)
    assert raised.value.code == "resource_limit"
    assert "1 倍" in str(raised.value)
    assert "24,000,000" in str(raised.value)


def test_a_photo_past_what_the_model_takes_is_refused_without_naming_a_scale(tmp_path: Path):
    """通せる大きさの上限は、もう倍率に依らない。"""
    manager, store = _manager(tmp_path)
    asset = _source(store, tmp_path, (4032, 3024))
    selected = _descriptor(scale=4, target_scales=[1, 2, 4], max_source_pixels=1_500_000)

    with pytest.raises(WorkerFailure) as raised:
        _resolve(manager, store, asset, selected, upscale_scale=1)

    assert raised.value.code == "resource_limit"
    assert "1,500,000" in str(raised.value)


def test_the_idle_budget_follows_the_area_not_a_single_measurement(tmp_path: Path):
    """直しの費用は面積に比例し、その係数はモデルが実測値として宣言している。

    1 枚ぶんの実測（SwinIR で 35.6 秒）だけで打ち切りを組むと、12MP の写真は
    4 分掛かるので必ず途中で切られる。上限を上げるだけでは足りない。
    """
    manager, store = _manager(tmp_path)
    small = _source(store, tmp_path, (640, 480))
    large = _source(store, tmp_path, (4032, 3024))
    from tests.test_image_evaluation import descriptor

    selected = descriptor(
        runtime_adapter="spandrel.upscale",
        capabilities=("image.upscale",),
        measured_runtime_sec=35.6,
        upscale={
            "scale": 4, "target_scales": [1, 2, 4],
            "max_source_pixels": 24_000_000, "per_source_megapixel_sec": 21.5,
        },
    )

    def expected(asset_id: str) -> float:
        job = store.get_job(store.create_job(JobRequest(
            operation="image.edit", intent="画質を上げる",
            inputs=[{"asset_id": asset_id}],
            constraints={"edit_mode": "upscale"},
        )).id)
        return manager._expected_runtime_sec(job, selected)

    # 実測より短くはならない。読み込みの時間はどの大きさでも掛かる。
    assert expected(small) == pytest.approx(35.6)
    assert expected(large) == pytest.approx(21.5 * 4032 * 3024 / 1_000_000, rel=1e-6)
    assert expected(large) > 250


@pytest.mark.parametrize("model_id,mode", [
    ("tog/nafnet-models", "deblur"),
    ("AEmotionStudio/lama-inpainting", "erase"),
])
def test_the_shipped_scale_of_one_models_resolve_on_the_real_registry(
    tmp_path: Path, model_id: str, mode: str,
) -> None:
    """出荷している倍率 1 のモデルが、実際の一覧のまま解決できる。

    stub では通っても、models.json の宣言が変われば実機で落ちる。ここは
    差し替えのない descriptor で通す。
    """
    from mediaforge.models import ModelRegistry

    manager, store = _manager(tmp_path)
    asset = _source(store, tmp_path, (800, 600))
    selected = next(
        item for item in ModelRegistry.load(
            MANIFESTS / "models.json", catalog_manifest=MANIFESTS / "catalog.json",
        ).all() if item.model_id == model_id
    )

    request = JobRequest(
        operation="image.edit", intent=mode,
        inputs=[{"asset_id": asset}],
        constraints={"edit_mode": mode},
    )
    resolved = manager._resolved_request(
        store.get_job(store.create_job(request).id), selected,
    )["constraints"]

    # 寸法を変えない直しである。倍率 1 のまま通り、寸法も動かない。
    assert (resolved["width"], resolved["height"]) == (800, 600)
    assert resolved["upscale_scale"] == 1


def _manifest(tmp_path: Path, upscale: dict) -> Path:
    import json

    manifest = tmp_path / "models.json"
    manifest.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [{
            "model_id": "owner/model", "family": "test", "version": "1", "revision": "d" * 40,
            "weights_hash": "sha256:" + "e" * 64, "license": "Apache-2.0",
            "runtime_adapter": "spandrel.upscale",
            "runtime_options": {"upscale": upscale},
            "capabilities": ["image.upscale"], "hardware_backends": ["rocm"],
            "state": "experimental", "policy_rank": {"auto": 1}, "measurements": None,
            "required_files": [], "weights": [
                {"path": "model.safetensors", "size_bytes": 4, "sha256": "c" * 64},
            ],
        }],
    }), encoding="utf-8")
    return manifest


@pytest.mark.parametrize("targets", [
    [3],        # 4 を割り切らない。画素の格子が合わない。
    [8],        # 重みの倍率より大きい。網はそれ以上を出せない。
    [1, 1],     # 同じものが 2 度。選択肢が重なって出る。
    [],         # 空。何も選べない組を宣言している。
    [0],        # 0 倍。寸法が消える。
])
def test_the_registry_refuses_scales_the_weights_cannot_produce(tmp_path: Path, targets) -> None:
    """宣言できる倍率を、読み込みの時点で縛る。

    実行時に気づくと、モデルを足した人ではなく、押した利用者が失敗を受け取る。
    """
    from mediaforge.models.registry import ModelRegistry, ModelRegistryError

    with pytest.raises(ModelRegistryError, match="upscale options"):
        ModelRegistry.load(_manifest(tmp_path, {"scale": 4, "target_scales": targets}))


def test_the_registry_refuses_a_bound_no_scale_can_produce(tmp_path: Path) -> None:
    """いちばん小さい倍率でも出力の上限を超えるなら、作れない値しか並ばない。"""
    from mediaforge.models.registry import ModelRegistry, ModelRegistryError

    with pytest.raises(ModelRegistryError, match="upscale options"):
        ModelRegistry.load(_manifest(tmp_path, {
            "scale": 4, "target_scales": [2, 4], "max_source_pixels": 24_000_000,
        }))
