from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mediaforge.validators import validate_png


def save_image(path: Path, mode: str) -> None:
    Image.new(mode, (11, 7), 0).save(path, format="PNG")


def test_validator_accepts_decodable_rgba_png(tmp_path: Path):
    path = tmp_path / "valid.png"
    save_image(path, "RGBA")

    width, height, results = validate_png(path)

    assert (width, height) == (11, 7)
    assert all(item["status"] == "passed" for item in results)


def test_validator_rejects_non_rgba_png(tmp_path: Path):
    path = tmp_path / "rgb.png"
    save_image(path, "RGB")

    with pytest.raises(ValueError, match="8-bit RGBA"):
        validate_png(path)


def test_validator_rejects_corrupt_png(tmp_path: Path):
    path = tmp_path / "corrupt.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-image")

    with pytest.raises(ValueError, match="decodable PNG"):
        validate_png(path)
