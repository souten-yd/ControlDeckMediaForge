"""動画 worker の境界。GPU を必要としない部分だけを見る。

生成そのものは実機で測ってある（512x320 33 frames 30 steps で 144.6 秒）。
ここで守るのは、外から渡される値を信じないことと、公開する形が 1 つに
揃っていることである。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def worker(tmp_path: Path, monkeypatch) -> object:
    from worker_packs.video import worker as module

    models = tmp_path / "models"
    work = tmp_path / "work"
    (models / "wan").mkdir(parents=True)
    (work / "job").mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(models))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work))
    return module.VideoWorker()


def request_for(tmp_path: Path, **constraints) -> dict:
    base = {"width": 512, "height": 320, "frames": 33, "steps": 30, "fps": 16}
    base.update(constraints)
    return {
        "model": {
            "id": "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
            "path": str(tmp_path / "models" / "wan"),
            "version": "1",
            "weights_hash": "sha256:" + "0" * 64,
            "license": "apache-2.0",
            "runtime_adapter": "diffusers.wan-t2v",
        },
        "request": {"intent": "a small robot waves", "constraints": base},
        "worker_output_dir": str(tmp_path / "work" / "job"),
    }


def test_a_model_outside_the_boundary_is_refused(tmp_path: Path, monkeypatch):
    """path は外から来る。境界の外を指されたら読みに行かない。"""
    subject = worker(tmp_path, monkeypatch)
    payload = request_for(tmp_path)
    payload["model"]["path"] = "/etc"
    with pytest.raises(ValueError, match="model path"):
        subject.handle(payload)


def test_an_unknown_adapter_is_refused_before_anything_loads(tmp_path: Path, monkeypatch):
    subject = worker(tmp_path, monkeypatch)
    payload = request_for(tmp_path)
    payload["model"]["runtime_adapter"] = "diffusers.sdxl"
    with pytest.raises(ValueError, match="adapter"):
        subject.handle(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("width", 513),      # 奇数は正規化が拒む。ここで断る
        ("width", 4096),     # 上限の外
        ("frames", 1),       # 下限の外
        ("frames", 100000),  # 尺の上限を越える
        ("steps", 0),
        ("fps", 240),
    ],
)
def test_out_of_bound_geometry_is_refused(tmp_path: Path, monkeypatch, field, value):
    """要求どおりに走らせてから失敗させると、GPU の時間だけが消える。"""
    subject = worker(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        subject.handle(request_for(tmp_path, **{field: value}))


def test_an_empty_intent_is_refused(tmp_path: Path, monkeypatch):
    subject = worker(tmp_path, monkeypatch)
    payload = request_for(tmp_path)
    payload["request"]["intent"] = "   "
    with pytest.raises(ValueError, match="intent"):
        subject.handle(payload)


def test_the_worker_speaks_the_same_protocol_as_the_image_worker():
    """core は 1 つの規約しか知らない。行ごとの JSON で ok と error を返す。"""
    source = (Path(__file__).parents[1] / "worker_packs/video/worker.py").read_text(encoding="utf-8")
    image = (Path(__file__).parents[1] / "worker_packs/image/worker.py").read_text(encoding="utf-8")
    for token in ('"ok": True', '"ok": False', '"code": "resource_oom"', "MAX_MESSAGE_BYTES"):
        assert token in source and token in image
    # 読み込みは process が生きている間 1 度きり。コールドで 162.8 秒かかる。
    assert "self._pipeline is not None and self._pipeline_path == model_path" in source
    # 公開する形は正規化を通したものだけ。生成器の書き出しをそのまま出さない。
    assert "normalize(NormalizeRequest(" in source
    assert "probe(output)" in source
