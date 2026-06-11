from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ImageRequest:
    prompt: str
    reference_images: list[Path]
    style_tags: list[str]
    size: str = "2K"
    node_id: str = ""


@dataclass(slots=True)
class ImageResult:
    node_id: str
    image_url: str | None = None
    image_path: Path | None = None
    prompt_used: str = ""
    status: str = "pending"


class ImageGenerator(ABC):
    @abstractmethod
    def generate(self, request: ImageRequest) -> ImageResult:
        ...


class PlaceholderGenerator(ImageGenerator):
    def generate(self, request: ImageRequest) -> ImageResult:
        return ImageResult(node_id=request.node_id, prompt_used=request.prompt, status="skipped")


class SeedreamGenerator(ImageGenerator):
    def __init__(self, api_key: str, model: str = "doubao-seedream-4-5-251128"):
        self.api_key = api_key
        self.model = model

    def generate(self, request: ImageRequest) -> ImageResult:
        raise NotImplementedError("Seedream image generation is reserved but not enabled yet.")

