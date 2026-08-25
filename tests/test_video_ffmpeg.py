from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from worker_packs.video.ffmpeg import NormalizeRequest, VideoToolError, normalize, probe


def test_video_normalization_rejects_unsafe_or_unbounded_requests(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not decoded before request validation")

    with pytest.raises(VideoToolError, match="must differ"):
        normalize(NormalizeRequest(source, source, 64, 64, 12, 1))
    with pytest.raises(VideoToolError, match="even integers"):
        normalize(NormalizeRequest(source, tmp_path / "out.mp4", 63, 64, 12, 1))
    with pytest.raises(VideoToolError, match="at most 300"):
        normalize(NormalizeRequest(source, tmp_path / "out.mp4", 64, 64, 12, 301))
    with pytest.raises(VideoToolError, match="mp4 or webm"):
        normalize(NormalizeRequest(source, tmp_path / "out.mov", 64, 64, 12, 1, format="mov"))


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="system FFmpeg is not installed",
)
def test_real_ffmpeg_normalizes_geometry_rate_duration_and_audio(tmp_path: Path):
    source = tmp_path / "source.mkv"
    subprocess.run([
        str(shutil.which("ffmpeg")), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=96x64:rate=24:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "ffv1", "-c:a", "pcm_s16le", str(source),
    ], check=True, timeout=30)

    raw = probe(source)
    assert (raw.width, raw.height, round(raw.frame_rate), raw.has_audio) == (96, 64, 24, True)

    output = tmp_path / "nested" / "normalized.mp4"
    info = normalize(NormalizeRequest(
        source_path=source,
        output_path=output,
        width=128,
        height=72,
        frame_rate=12,
        duration_sec=1.25,
        include_audio=False,
    ))

    assert output.is_file() and output.stat().st_size > 0
    assert (info.width, info.height) == (128, 72)
    assert info.frame_rate == pytest.approx(12, abs=0.01)
    assert info.frame_count == 15
    assert info.duration_sec == pytest.approx(1.25, abs=0.05)
    assert info.codec == "h264"
    assert info.has_audio is False

    with_audio = tmp_path / "normalized.webm"
    audio_info = normalize(NormalizeRequest(
        source_path=source,
        output_path=with_audio,
        width=96,
        height=64,
        frame_rate=24,
        duration_sec=0.5,
        format="webm",
        include_audio=True,
    ))
    assert audio_info.frame_count == 12
    assert audio_info.duration_sec == pytest.approx(0.5, abs=0.05)
    assert audio_info.codec == "vp9"
    assert audio_info.has_audio is True
