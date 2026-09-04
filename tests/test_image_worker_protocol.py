from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from worker_packs.image.adapters import ImageGenerationResult
from worker_packs.image import worker as image_worker


def payload(model_path: Path, output_dir: Path) -> dict:
    return {
        "model": {
            "id": "owner/model",
            "path": str(model_path),
            "version": "1",
            "weights_hash": "sha256:" + "a" * 64,
            "license": "Apache-2.0",
            "runtime_adapter": "diffusers.flux2-klein",
        },
        "request": {
            "operation": "image.generate",
            "intent": "a blue robot",
            "constraints": {"width": 256, "height": 256, "steps": 4, "seed": 7},
            "output": {"format": "png", "count": 1},
        },
        "worker_output_dir": str(output_dir),
    }


def test_image_worker_rejects_model_and_output_path_escape(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model_root.mkdir()
    work_root.mkdir()
    model = model_root / "model"
    model.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    with pytest.raises(ValueError, match="model path"):
        worker.handle(payload(outside, work_root / "job" / "outputs"))
    with pytest.raises(ValueError, match="output directory"):
        worker.handle(payload(model, outside / "outputs"))


def test_image_worker_returns_bounded_model_metadata_and_per_output_seed(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    output_dir = work_root / "job" / "outputs"
    model.mkdir(parents=True)
    output_dir.parent.mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))

    class Adapter:
        def __init__(self, _path, *, device_mode, disable_mmap):
            assert device_mode == "cpu_offload"
            assert disable_mmap is True
            self.load_sec = 1.25
            self.last_generation_sec = None
            self.placement = {
                "component_devices": {"transformer": "cuda:0"},
                "device_maps": {"pipeline": {"": "cuda"}},
                "offload_hooks": [],
                "non_gpu_devices": {},
                "non_gpu_map_targets": [],
            }

        def generate(self, request):
            request.output_path.write_bytes(b"png")
            self.last_generation_sec = 0.5
            return ImageGenerationResult(request.output_path, request.seed)

    monkeypatch.setattr(image_worker, "DiffusersFlux2KleinAdapter", Adapter)
    monkeypatch.setattr(image_worker.importlib.metadata, "version", lambda _name: "test-runtime")
    request = payload(model, output_dir)
    request["model"]["runtime_options"] = {"device_mode": "cpu_offload", "disable_mmap": True}
    request["request"]["output"]["count"] = 2
    result = image_worker.ImageWorker().handle(request)

    assert [item["seed"] for item in result["outputs"]] == [7, 8]
    assert result["model"]["id"] == "owner/model"
    assert "path" not in result["model"]
    assert result["runtime_metrics"] == {
        "load_sec": 1.25,
        "generation_sec": 1.0,
        "device_mode": "cpu_offload",
        "disable_mmap": True,
        "placement": {
            "component_devices": {"transformer": "cuda:0"},
            "device_maps": {"pipeline": {"": "cuda"}},
            "offload_hooks": [],
            "non_gpu_devices": {},
            "non_gpu_map_targets": [],
        },
    }


def test_image_worker_has_no_process_override_and_rejects_unknown_mode(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model_root.mkdir()
    work_root.mkdir()
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))

    worker = image_worker.ImageWorker()
    assert worker.device_mode_override is None
    assert worker.disable_mmap_override is None
    monkeypatch.setenv("MEDIA_FORGE_IMAGE_DEVICE_MODE", "dynamic")
    with pytest.raises(ValueError, match="must be one of cpu, cpu_offload, direct_device_map, full_device"):
        image_worker.ImageWorker()
    monkeypatch.setenv("MEDIA_FORGE_IMAGE_DEVICE_MODE", "full_device")
    monkeypatch.setenv("MEDIA_FORGE_IMAGE_DISABLE_MMAP", "yes")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        image_worker.ImageWorker()


def test_image_worker_rejects_fractional_and_boolean_numeric_constraints(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root.mkdir()
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    fractional = payload(model, work_root / "fractional")
    fractional["request"]["constraints"]["width"] = 256.5
    with pytest.raises(ValueError, match="width must be an integer"):
        worker.handle(fractional)
    boolean = payload(model, work_root / "boolean")
    boolean["request"]["constraints"]["seed"] = True
    with pytest.raises(ValueError, match="seed must be an integer"):
        worker.handle(boolean)


def test_image_worker_rejects_edit_source_and_mask_path_escape(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root.mkdir()
    outside = tmp_path / "outside.png"
    Image.new("RGBA", (256, 256), "white").save(outside, format="PNG")
    inside = work_root / "inside.png"
    Image.new("RGBA", (256, 256), "black").save(inside, format="PNG")
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    source_escape = payload(model, work_root / "source-escape")
    source_escape["request"]["operation"] = "image.edit"
    source_escape["request"]["constraints"]["strict_edit"] = True
    source_escape["worker_inputs"] = {"source_path": str(outside), "mask_path": str(inside)}
    with pytest.raises(ValueError, match="source image is outside"):
        worker.handle(source_escape)

    mask_escape = payload(model, work_root / "mask-escape")
    mask_escape["request"]["operation"] = "image.edit"
    mask_escape["request"]["constraints"]["strict_edit"] = True
    mask_escape["worker_inputs"] = {"source_path": str(inside), "mask_path": str(outside)}
    with pytest.raises(ValueError, match="edit mask is outside"):
        worker.handle(mask_escape)

    reference_escape = payload(model, work_root / "reference-escape")
    reference_escape["request"]["operation"] = "image.edit"
    reference_escape["request"]["constraints"].update({
        "strict_edit": False,
        "edit_mode": "multi_reference",
    })
    reference_escape["worker_inputs"] = {
        "source_path": str(inside),
        "reference_paths": [str(outside)],
    }
    with pytest.raises(ValueError, match="reference image is outside"):
        worker.handle(reference_escape)


def test_every_routable_model_has_an_adapter_the_worker_implements():
    """カタログが名乗る runtime_adapter と、worker が実装している名前が
    食い違っていた。"diffusers.stable-diffusion" という誰も宣言しない名前で
    実装され、カタログの "diffusers.sdxl" は実装が無いまま並んでいた。

    experimental は測っていないという表明なので、まだ実装が無くてよい。
    available は「これで作れる」という表明なので、無いと嘘になる。
    """
    import json

    root = Path(__file__).parents[1]
    manifest = json.loads(
        (root / "worker_packs/image/models.json").read_text(encoding="utf-8")
    )
    # available は「これで作れる」という表明である。作るのが画像 worker とは
    # 限らないので、実装している側を全部足して見る。
    from worker_packs.video import worker as video_worker

    implemented = set(image_worker.ADAPTERS) | set(video_worker.ADAPTERS)
    routable = {
        model["model_id"]: model["runtime_adapter"]
        for model in manifest["models"]
        if model.get("state") == "available"
    }
    assert routable, "available なモデルが 1 件も無い"
    missing = {
        model_id: adapter
        for model_id, adapter in routable.items()
        if adapter not in implemented
    }
    assert not missing, f"実装の無い adapter を available として出している: {missing}"


def test_the_worker_refuses_an_adapter_it_does_not_implement(tmp_path: Path, monkeypatch):
    """実装の無い adapter は、静かに何かで代用せず、その場で落ちる。"""
    model_root = tmp_path / "models"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root = tmp_path / "work"
    (work_root / "job" / "outputs").mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    body = payload(model, work_root / "job" / "outputs")
    body["model"]["runtime_adapter"] = "diffusers.qwen-image"
    assert "diffusers.qwen-image" not in image_worker.ADAPTERS
    with pytest.raises(ValueError, match="unsupported"):
        image_worker.ImageWorker().handle(body)


def test_a_single_file_checkpoint_needs_its_family_declared(tmp_path: Path):
    """1 つの safetensors は自分がどの系統か名乗らない。当てて読むと、落ちるか、
    もっと悪いことに静かに違う絵が出る。"""
    from worker_packs.image.adapters.diffusers_single_file import DiffusersSingleFileAdapter

    checkpoint = tmp_path / "model.safetensors"
    checkpoint.write_bytes(b"weights")

    with pytest.raises(ValueError, match="base model"):
        DiffusersSingleFileAdapter(checkpoint)._pipeline_class()
    assert DiffusersSingleFileAdapter(
        checkpoint, base_model="SDXL 1.0"
    )._pipeline_class() == "StableDiffusionXLPipeline"


def test_the_declared_family_survives_the_ways_a_site_writes_it():
    """Civitai は同じ系統を "SD 1.5" とも "SD 1.5 Hyper" とも書く。"""
    from worker_packs.image.adapters.diffusers_single_file import normalize_base_model

    assert normalize_base_model("SD 1.5") == normalize_base_model("SD 1.5 Hyper") == "sd15"
    assert normalize_base_model("SDXL 1.0") == "sdxl"
    # 知らない系統を既定に丸めない。丸めると違う pipeline で読むことになる。
    assert normalize_base_model("Flux.1 D") == ""


def test_a_directory_with_two_checkpoints_is_refused(tmp_path: Path):
    """どれが本体か分からないものを当てて読むと、VAE や refiner を本体として
    読み込むことになる。"""
    from worker_packs.image.adapters.diffusers_single_file import DiffusersSingleFileAdapter

    (tmp_path / "a.safetensors").write_bytes(b"a")
    (tmp_path / "b.safetensors").write_bytes(b"b")

    with pytest.raises(ValueError, match="identifiable"):
        DiffusersSingleFileAdapter(tmp_path, base_model="SDXL 1.0")._checkpoint()


def test_the_sd_adapter_asks_for_the_variant_that_is_on_disk(tmp_path: Path):
    """実機で判明: カタログは fp16 の variant だけを落とす。variant を渡さないと
    diffusers は model.safetensors を探し、落としていないファイルが無いと言って
    落ちる。variant を持たない普通の repository は従来どおり動く必要がある。"""
    from worker_packs.image.adapters.diffusers_sd import DiffusersStableDiffusionAdapter

    plain = tmp_path / "plain"
    (plain / "unet").mkdir(parents=True)
    (plain / "unet" / "diffusion_pytorch_model.safetensors").write_bytes(b"x")
    assert DiffusersStableDiffusionAdapter(plain)._detect_variant() is None

    fp16 = tmp_path / "fp16"
    (fp16 / "unet").mkdir(parents=True)
    (fp16 / "unet" / "diffusion_pytorch_model.fp16.safetensors").write_bytes(b"x")
    assert DiffusersStableDiffusionAdapter(fp16)._detect_variant() == "fp16"


def test_core_and_the_workers_agree_on_what_can_run():
    """core は worker の実装を import しない。だから 2 か所に同じ知識が置かれる。

    ずれると、実行環境の無いモデルを「使える」と言うか、動くモデルを
    一覧から落とすかのどちらかになる。実機では MiniMax が前者だった
    （評価に 161 秒使えるのに、作るときには選べない。2026-08-30）。
    """
    from worker_packs.image import worker as image_side
    from worker_packs.video import worker as video_side

    from mediaforge.models.adapters import IMAGE_ADAPTERS, RUNNABLE_ADAPTERS, VIDEO_ADAPTERS

    assert set(IMAGE_ADAPTERS) == set(image_side.ADAPTERS)
    assert set(VIDEO_ADAPTERS) == set(video_side.ADAPTERS)
    assert RUNNABLE_ADAPTERS == IMAGE_ADAPTERS | VIDEO_ADAPTERS


def test_a_model_without_a_runtime_is_not_called_usable():
    """測れることと使えることは別。

    出荷カタログには実行環境の無い候補が並ぶ。それ自体は正しい（調べる対象
    である）。誤っていたのは、その差を画面へ出していなかったことである。
    """
    import json
    from pathlib import Path

    from mediaforge.models.adapters import is_runnable

    root = Path(__file__).parents[1]
    manifest = json.loads((root / "worker_packs/image/models.json").read_text(encoding="utf-8"))
    by_id = {model["model_id"]: model["runtime_adapter"] for model in manifest["models"]}

    assert is_runnable(by_id["Wan-AI/Wan2.1-T2V-1.3B-Diffusers"])
    # MiniMax H3 は pinned build の sd-cli で動く。駆動系がある側である。
    assert is_runnable(by_id["unsloth/MiniMax-H3-GGUF"])
    # Wan 2.2 も上流の package を組み込んで動かせるようにした。
    assert is_runnable(by_id["Wan-AI/Wan2.2-TI2V-5B"])
    # 実行系を持たない候補はまだある。ここが全部 True になると意味を失う。
    assert not is_runnable(by_id["Lightricks/LTX-2.3"])
    # available なものは必ず走らせられる。ここが崩れると「使える」が嘘になる。
    for model in manifest["models"]:
        if model.get("state") == "available":
            assert is_runnable(model["runtime_adapter"]), model["model_id"]


def test_a_photo_sized_canvas_is_accepted_for_a_masked_edit(monkeypatch, tmp_path):
    """写真を原寸のまま直せるようにする。

    strict edit で渡る width/height は画布（元画像）の寸法である。生成されるのは
    塗った範囲＋64px の切り抜きだけで、この値はモデルに渡らない。2048 で切ると、
    透かしを消すために写真全体の解像度を捨てることになる。実機で 4032x3024 の
    写真を通し、生成 1.69 秒・出力 4032x3024・保護画素の差 0 を確認した。

    上限は core の取り込み（24,000,000 画素）に合わせる。境界の都合で core を
    import できないので、食い違ったら気づけるよう両方から確かめる。
    """
    from mediaforge.asset_import import MAX_IMPORT_PIXELS

    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root.mkdir()
    source = work_root / "source.png"
    mask = work_root / "mask.png"
    Image.new("RGBA", (64, 64), "black").save(source, format="PNG")
    Image.new("RGBA", (64, 64), "white").save(mask, format="PNG")
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    def masked(width: int, height: int) -> dict:
        value = payload(model, work_root / "outputs")
        value["request"]["operation"] = "image.edit"
        value["request"]["constraints"].update({
            "strict_edit": True, "edit_mode": "inpaint",
            "width": width, "height": height,
        })
        value["worker_inputs"] = {"source_path": str(source), "mask_path": str(mask)}
        return value

    # 携帯の標準（12.2MP）と一眼の標準（24MP）は寸法で断らない。ここでは
    # torch を持たないので adapter の手前までしか進めないが、寸法の検査を
    # 抜けたことは、返る失敗が寸法のものでないことで分かる。
    for width, height in ((4032, 3024), (6000, 4000)):
        assert width * height <= MAX_IMPORT_PIXELS
        with pytest.raises(Exception) as raised:
            worker.handle(masked(width, height))
        assert "pixel bound" not in str(raised.value)
        assert "range 1..8192" not in str(raised.value)

    # 1 ジョブが 1.6GB を抱える 48MP は取らない。core の取り込みと同じ線で切る。
    assert 8000 * 6000 > MAX_IMPORT_PIXELS
    with pytest.raises(ValueError, match="24,000,000 pixel bound"):
        worker.handle(masked(8000, 6000))
    with pytest.raises(ValueError, match="range 1..8192"):
        worker.handle(masked(9000, 100))


def test_an_upscale_takes_no_steps_and_produces_exactly_one_image(monkeypatch, tmp_path):
    """拡大は標本化しない。歩数も seed も持たない。

    歩数を要求すると、持っていない値を核が埋めることになり、「4 歩で回した絵」と
    同じ種類の間違いを作る。乱数が無いので、何枚頼まれても同じ絵にしかならない。

    出力寸法は元画像と倍率で決まる。16 の倍数は求めない（4 倍にすると、元の
    寸法が 4 の倍数であることを強いることになる）。
    """
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root.mkdir()
    source = work_root / "source.png"
    Image.new("RGBA", (64, 64), "black").save(source, format="PNG")
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    def upscaling(
        width: int, height: int, count: int = 1, steps: object = None,
        scale: object = None,
    ) -> dict:
        value = payload(model, work_root / "outputs")
        value["model"]["runtime_adapter"] = "spandrel.upscale"
        value["request"]["operation"] = "image.edit"
        value["request"]["constraints"] = {
            "edit_mode": "upscale", "width": width, "height": height,
            **({"steps": steps} if steps is not None else {}),
            **({"upscale_scale": scale} if scale is not None else {}),
        }
        value["request"]["output"] = {"format": "png", "count": count}
        value["worker_inputs"] = {"source_path": str(source)}
        return value

    # 歩数が無くても断らない。adapter の手前まで進む。
    with pytest.raises(Exception) as raised:
        worker.handle(upscaling(4096, 3072))
    assert "steps were not resolved" not in str(raised.value)

    # 出力は取り込みの上限で切る。作れないものを選ばせない。
    with pytest.raises(ValueError, match="24,000,000 pixel bound"):
        worker.handle(upscaling(6000, 4500))
    with pytest.raises(ValueError, match="range 1..8192"):
        worker.handle(upscaling(9000, 100))
    # 乱数が無いので複数枚は同じ絵にしかならない。
    with pytest.raises(ValueError, match="exactly one image"):
        worker.handle(upscaling(4096, 3072, count=4))
    # 出す倍率は核が決めて渡す。worker は範囲だけ見て、既定は置かない。置くと
    # 核が決めた寸法と worker が使う倍率が食い違い、寸法の検査を通ってから
    # 別の大きさが出る。
    for bad in (0, 9, "2", 2.0, True):
        with pytest.raises(ValueError, match="upscale scale"):
            worker.handle(upscaling(2048, 1536, scale=bad))


def test_a_cached_adapter_is_not_reused_for_a_different_placement(monkeypatch, tmp_path):
    """VRAM に載せた adapter を host 配置の要求へ渡さない。

    ImageWorker は model_id で adapter を持ち続ける。置き場所は要求ごとに
    変わる（broker が gpu0 と host のどちらを割り当てたか）ので、model_id
    だけを鍵にすると、VRAM を確保しない約束の要求が VRAM の pipeline を使う。
    """
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    output_dir = work_root / "job" / "outputs"
    model.mkdir(parents=True)
    output_dir.parent.mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    built: list[str] = []

    class Adapter:
        def __init__(self, _path, *, device_mode, disable_mmap):
            built.append(device_mode)
            self.load_sec = 0.1
            self.last_generation_sec = None
            self.placement = {}

        def load(self):
            return None

        def generate(self, request):
            request.output_path.write_bytes(b"png")
            self.last_generation_sec = 0.1
            return ImageGenerationResult(request.output_path, request.seed)

    monkeypatch.setattr(image_worker, "DiffusersFlux2KleinAdapter", Adapter)
    monkeypatch.setattr(image_worker.importlib.metadata, "version", lambda _name: "test-runtime")
    worker = image_worker.ImageWorker()

    for device_mode in ("direct_device_map", "direct_device_map", "cpu"):
        request = payload(model, output_dir)
        request["model"]["runtime_options"] = {"device_mode": device_mode, "disable_mmap": True}
        worker.handle(request)

    assert built == ["direct_device_map", "cpu"]
