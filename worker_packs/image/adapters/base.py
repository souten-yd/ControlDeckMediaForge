from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    width: int
    height: int
    steps: int
    seed: int
    output_path: Path


@dataclass(frozen=True)
class ImageGenerationResult:
    output_path: Path
    seed: int


class ImageAdapter(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...
