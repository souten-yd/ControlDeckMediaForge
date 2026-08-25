from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class VideoToolError(RuntimeError):
    """A bounded FFmpeg/FFprobe operation failed or returned invalid media."""


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration_sec: float
    frame_rate: float
    frame_count: int
    codec: str
    container: str
    has_audio: bool


@dataclass(frozen=True)
class NormalizeRequest:
    source_path: Path
    output_path: Path
    width: int
    height: int
    frame_rate: int
    duration_sec: float
    format: str = "mp4"
    include_audio: bool = False
    timeout_sec: float = 300.0


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise VideoToolError(f"{name} is not installed")
    return resolved


def _run(arguments: list[str], timeout_sec: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            arguments,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoToolError(f"video tool timed out after {timeout_sec:g} seconds") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "video tool failed").strip()[-1000:]
        raise VideoToolError(detail) from exc


def _positive_float(value: Any, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise VideoToolError(f"{label} is missing or invalid") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise VideoToolError(f"{label} is missing or invalid")
    return parsed


def _frame_rate(value: Any) -> float:
    try:
        parsed = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError) as exc:
        raise VideoToolError("video frame rate is missing or invalid") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise VideoToolError("video frame rate is missing or invalid")
    return parsed


def probe(path: Path, *, timeout_sec: float = 30.0) -> VideoInfo:
    path = path.resolve()
    if not path.is_file():
        raise VideoToolError("video artifact does not exist")
    result = _run([
        _tool("ffprobe"), "-v", "error", "-show_streams", "-show_format",
        "-count_frames", "-of", "json", str(path),
    ], timeout_sec)
    try:
        payload = json.loads(result.stdout)
        streams = payload["streams"]
        video_streams = [item for item in streams if item.get("codec_type") == "video"]
        audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
        if len(video_streams) != 1:
            raise VideoToolError("video artifact must contain exactly one video stream")
        video = video_streams[0]
        duration = video.get("duration") or payload.get("format", {}).get("duration")
        rate = _frame_rate(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        frames = video.get("nb_read_frames") or video.get("nb_frames")
        frame_count = (
            int(frames)
            if frames not in {None, "N/A"}
            else round(_positive_float(duration, "video duration") * rate)
        )
        if frame_count < 1:
            raise VideoToolError("video artifact contains no frames")
        return VideoInfo(
            width=int(video["width"]),
            height=int(video["height"]),
            duration_sec=_positive_float(duration, "video duration"),
            frame_rate=rate,
            frame_count=frame_count,
            codec=str(video.get("codec_name", "")),
            container=str(payload.get("format", {}).get("format_name", "")),
            has_audio=bool(audio_streams),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VideoToolError("ffprobe returned unreadable video metadata") from exc


def normalize(request: NormalizeRequest) -> VideoInfo:
    source = request.source_path.resolve()
    output = request.output_path.resolve()
    if not source.is_file():
        raise VideoToolError("source video does not exist")
    if source == output:
        raise VideoToolError("source and output video paths must differ")
    if request.format not in {"mp4", "webm"}:
        raise VideoToolError("normalized video format must be mp4 or webm")
    if request.width < 16 or request.height < 16 or request.width % 2 or request.height % 2:
        raise VideoToolError("video dimensions must be even integers of at least 16 pixels")
    if not 1 <= request.frame_rate <= 120:
        raise VideoToolError("video frame rate must be between 1 and 120")
    if not math.isfinite(request.duration_sec) or not 0 < request.duration_sec <= 300:
        raise VideoToolError("video duration must be greater than zero and at most 300 seconds")
    if not 1 <= request.timeout_sec <= 3600:
        raise VideoToolError("video tool timeout must be between 1 and 3600 seconds")

    output.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, round(request.duration_sec * request.frame_rate))
    filters = (
        f"scale={request.width}:{request.height}:force_original_aspect_ratio=decrease,"
        f"pad={request.width}:{request.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={request.frame_rate},trim=end_frame={frame_count},setpts=PTS-STARTPTS"
    )
    arguments = [
        _tool("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-map", "0:v:0", "-vf", filters,
        "-frames:v", str(frame_count),
    ]
    if request.include_audio:
        audio_codec = "aac" if request.format == "mp4" else "libopus"
        arguments.extend(["-map", "0:a:0?", "-c:a", audio_codec, "-b:a", "192k"])
    else:
        arguments.append("-an")
    if request.format == "mp4":
        arguments.extend([
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
            "-crf", "18", "-movflags", "+faststart", "-f", "mp4",
        ])
    else:
        arguments.extend([
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", "-crf", "24",
            "-b:v", "0", "-f", "webm",
        ])
    arguments.extend(["-t", f"{request.duration_sec:.6f}", str(output)])
    try:
        _run(arguments, request.timeout_sec)
        info = probe(output, timeout_sec=min(request.timeout_sec, 30.0))
        if (info.width, info.height) != (request.width, request.height):
            raise VideoToolError("normalized video dimensions do not match the request")
        if abs(info.frame_rate - request.frame_rate) > 0.01:
            raise VideoToolError("normalized video frame rate does not match the request")
        if info.frame_count != frame_count:
            raise VideoToolError("normalized video frame count does not match the request")
        expected_codec = "h264" if request.format == "mp4" else "vp9"
        if info.codec != expected_codec:
            raise VideoToolError("normalized video codec does not match the request")
        expected_container = "mp4" if request.format == "mp4" else "webm"
        if expected_container not in info.container.split(","):
            raise VideoToolError("normalized video container does not match the request")
        if not request.include_audio and info.has_audio:
            raise VideoToolError("normalized video unexpectedly contains audio")
        return info
    except Exception:
        output.unlink(missing_ok=True)
        raise
