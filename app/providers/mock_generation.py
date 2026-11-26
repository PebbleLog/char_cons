"""Mock 图像生成 Provider：仅用于测试/演示，不联网。

明确标记 provider=mock、model=mock-seedream；输出图片由本地 PIL 合成，
不代表任何真实生成模型的能力或画质。
"""

from __future__ import annotations

import hashlib
import io
from typing import Any

from PIL import Image, ImageDraw

from .base import GeneratedImage, UsageInfo


class MockGenerationProvider:
    name = "mock"
    model_name = "mock-seedream"
    capabilities = {
        "native_batch": False,
        "max_images_per_request": 1,
        "max_reference_images": 10,
        "supports_reference_image": True,
        "supports_seed": True,
        "supports_size": True,
        "supports_negative_prompt": False,
        "negative_prompt_mode": "merged",
        "response_format": "b64",
    }

    def ensure_configured(self) -> None:
        return None

    async def test_connection(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "requestId": "mock-generation-connection",
            "mock": True,
        }

    async def generate(
        self,
        *,
        prompt: str,
        references: list[tuple[bytes, str]],
        size: str | None,
        seed: int | None,
    ) -> GeneratedImage:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        actual_seed = seed if seed is not None else int(digest[:8], 16) % 1_000_000
        image = await self._render(references, actual_seed)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return GeneratedImage(
            image_bytes=buffer.getvalue(),
            mime_type="image/png",
            remote_url=None,
            request_id=f"mock-gen-{actual_seed}",
            model=self.model_name,
            usage=UsageInfo(),
            elapsed_ms=0,
        )

    async def _render(
        self, references: list[tuple[bytes, str]], seed: int
    ) -> Image.Image:
        size = (720, 1080)
        if references:
            try:
                with Image.open(io.BytesIO(references[0][0])) as reference:
                    base = reference.convert("RGB")
                    # 居中裁成竖图并缩放，模拟同角色候选
                    width, height = base.size
                    target_ratio = size[0] / size[1]
                    if width / height > target_ratio:
                        new_width = int(height * target_ratio)
                        left = (width - new_width) // 2
                        base = base.crop((left, 0, left + new_width, height))
                    else:
                        new_height = int(width / target_ratio)
                        top = (height - new_height) // 2
                        base = base.crop((0, top, width, top + new_height))
                    base = base.resize(size, Image.Resampling.LANCZOS)
            except Exception:
                base = self._gradient(size, seed)
        else:
            base = self._gradient(size, seed)

        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        hue = seed % 360
        r, g, b = self._hue_rgb(hue)
        draw.rectangle((0, 0, size[0], 86), fill=(r, g, b, 70))
        draw.rectangle((0, size[1] - 86, size[0], size[1]), fill=(r, g, b, 70))
        merged = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(merged)
        draw.text((24, 30), f"MOCK CANDIDATE · SEED {seed}", fill=(255, 255, 255))
        draw.text((24, size[1] - 58), "本地合成预览 · 非真实模型输出", fill=(255, 255, 255))
        return merged

    @staticmethod
    def _gradient(size: tuple[int, int], seed: int) -> Image.Image:
        r, g, b = MockGenerationProvider._hue_rgb(seed % 360)
        strip = Image.new("RGB", (2, 256))
        pixels = strip.load()
        for y in range(256):
            ratio = y / 255
            pixels[0, y] = (
                int(r * (0.28 + ratio * 0.5)),
                int(g * (0.28 + ratio * 0.5)),
                int(b * (0.28 + ratio * 0.5)),
            )
            pixels[1, y] = pixels[0, y]
        return strip.resize(size, Image.Resampling.BILINEAR)

    @staticmethod
    def _hue_rgb(hue: int) -> tuple[int, int, int]:
        # 简单 HSV→RGB，仅用于生成可区分的 Mock 色块
        import colorsys

        r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 0.55, 0.95)
        return int(r * 255), int(g * 255), int(b * 255)
