"""
lumina/services/media.py — 图片 OCR / Caption 服务层

第一阶段仅支持：
  - 图片文件上传
  - 图片直链 URL

实现策略：
  - OCR: TrOCR（本地 transformers pipeline）
  - Caption: BLIP image-to-text（本地 transformers pipeline）
"""
from __future__ import annotations

import asyncio
import io
import threading

import httpx


def _load_image(image_bytes: bytes):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow 未安装，无法处理图片") from exc

    image = Image.open(io.BytesIO(image_bytes))
    return image.convert("RGB")


class MediaService:
    def __init__(self, *, ocr_model: str, caption_model: str, max_image_mb: int = 12) -> None:
        self.ocr_model = ocr_model
        self.caption_model = caption_model
        self.max_image_bytes = max(1, int(max_image_mb)) * 1024 * 1024
        self._ocr_pipe = None
        self._caption_pipe = None
        self._lock = threading.Lock()

    async def ocr_bytes(self, image_bytes: bytes) -> dict[str, str]:
        image = await asyncio.to_thread(self._prepare_image, image_bytes)
        text = await asyncio.to_thread(self._run_ocr, image)
        return {"text": text.strip(), "model": self.ocr_model}

    async def caption_bytes(self, image_bytes: bytes) -> dict[str, str]:
        image = await asyncio.to_thread(self._prepare_image, image_bytes)
        text = await asyncio.to_thread(self._run_caption, image)
        return {"text": text.strip(), "model": self.caption_model}

    async def fetch_image_url(self, url: str) -> bytes:
        if not url.strip():
            raise ValueError("url 不能为空")
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url.strip())
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise ValueError("仅支持图片直链 URL")
            image_bytes = response.content
        self._validate_image_bytes(image_bytes)
        return image_bytes

    def _prepare_image(self, image_bytes: bytes):
        self._validate_image_bytes(image_bytes)
        return _load_image(image_bytes)

    def _validate_image_bytes(self, image_bytes: bytes) -> None:
        if not image_bytes:
            raise ValueError("图片内容为空")
        if len(image_bytes) > self.max_image_bytes:
            raise ValueError(f"图片过大，请控制在 {self.max_image_bytes // (1024 * 1024)} MB 以内")

    def _run_ocr(self, image) -> str:
        pipe = self._get_ocr_pipeline()
        result = pipe(image)
        return self._extract_text(result)

    def _run_caption(self, image) -> str:
        pipe = self._get_caption_pipeline()
        result = pipe(image)
        return self._extract_text(result)

    def _get_ocr_pipeline(self):
        if self._ocr_pipe is None:
            with self._lock:
                if self._ocr_pipe is None:
                    self._ocr_pipe = self._build_pipeline(self.ocr_model)
        return self._ocr_pipe

    def _get_caption_pipeline(self):
        if self._caption_pipe is None:
            with self._lock:
                if self._caption_pipe is None:
                    self._caption_pipe = self._build_pipeline(self.caption_model)
        return self._caption_pipe

    @staticmethod
    def _build_pipeline(model_id: str):
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("transformers 未安装，无法加载图片模型") from exc
        return pipeline("image-to-text", model=model_id)

    @staticmethod
    def _extract_text(result) -> str:
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict):
                return str(first.get("generated_text", "")).strip()
        if isinstance(result, dict):
            return str(result.get("generated_text", "")).strip()
        return str(result or "").strip()

