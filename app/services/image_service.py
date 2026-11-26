"""图片校验、预处理与轻量质量检查。

边界（需求 F-02 / 技术方案 9.3）：
- 只接受 JPG / PNG / WebP，按真实格式（Pillow 解码结果）判断，不信任扩展名；
- 原图字节不修改；另存分析副本（RGB、去 alpha、长边 ≤1568、JPEG）与缩略图（长边 480）；
- 超过单张上限直接拒绝（文件名与上限随错误返回），不做有损“原图压缩”；
- 质量检查是确定性启发式（亮度/边缘方差/分辨率），不冒充 AI 人物检测。
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Final

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

logger = logging.getLogger(__name__)

# 像素总量上限，防止压缩炸弹；超过时 Pillow 抛 DecompressionBombError
Image.MAX_IMAGE_PIXELS = 60_000_000

ANALYSIS_MAX_EDGE: Final = 1568
THUMB_MAX_EDGE: Final = 480
ANALYSIS_MAX_BYTES: Final = 10 * 1024 * 1024
MIN_LONG_EDGE_WARN: Final = 512

_ALLOWED_FORMATS: Final[dict[str, tuple[str, str]]] = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


class ImageValidationError(Exception):
    """单张图片不可用。``code`` 与技术方案 14.2 错误码兼容。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class ProcessedImage:
    original_bytes: bytes
    extension: str
    mime_type: str
    width: int
    height: int
    analysis_jpeg: bytes
    thumb_jpeg: bytes
    warnings: list[str]
    sha256: str


def _to_rgb(image: Image.Image) -> Image.Image:
    """去 alpha：透明区域铺白底，避免转灰度后出现黑边。"""
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        merged = Image.alpha_composite(background, rgba)
        return merged.convert("RGB")
    return image.convert("RGB")


def _resize_long_edge(image: Image.Image, max_edge: int) -> Image.Image:
    width, height = image.size
    long_edge = max(width, height)
    if long_edge <= max_edge:
        return image.copy()
    scale = max_edge / long_edge
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _encode_jpeg(image: Image.Image, quality: int, max_bytes: int | None = None) -> bytes:
    quality_now = quality
    scale = 1.0
    for _ in range(6):
        current = image
        if scale < 1.0:
            size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            current = image.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        current.save(buffer, format="JPEG", quality=quality_now, optimize=True)
        data = buffer.getvalue()
        if max_bytes is None or len(data) <= max_bytes:
            return data
        if quality_now > 60:
            quality_now -= 10
        else:
            scale *= 0.8
    return data


def _quality_warnings(image: Image.Image, width: int, height: int) -> list[str]:
    warnings: list[str] = []
    if max(width, height) < MIN_LONG_EDGE_WARN:
        warnings.append("分辨率偏低（长边 < 512px），部分细节可能无法判断。")

    gray = image.convert("L")
    brightness = ImageStat.Stat(gray).mean[0]
    if brightness < 45:
        warnings.append("画面偏暗，颜色与配饰细节可能难以辨认。")
    elif brightness > 230:
        warnings.append("画面过亮，浅色衣物细节可能过曝。")

    probe = _resize_long_edge(gray, 512)
    edges = probe.filter(ImageFilter.FIND_EDGES)
    edge_std = ImageStat.Stat(edges).stddev[0]
    if edge_std < 8:
        warnings.append("画面边缘细节较少，可能模糊或主体过小。")
    return warnings


def process_upload(data: bytes, filename: str, max_mb: int) -> ProcessedImage:
    """校验并生成分析副本/缩略图；失败抛 ``ImageValidationError``。"""
    max_bytes = max_mb * 1024 * 1024
    if not data:
        raise ImageValidationError("unsupported_file", "文件为空。")
    if len(data) > max_bytes:
        raise ImageValidationError(
            "unsupported_file",
            f"文件超过单张 {max_mb} MB 上限，请压缩后重新上传。",
        )

    try:
        with Image.open(io.BytesIO(data)) as probe:
            actual_format = (probe.format or "").upper()
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        logger.info("图片无法解码：%s (%s)", filename, type(exc).__name__)
        raise ImageValidationError(
            "unsupported_file", "文件无法读取，请重新导出为 JPG / PNG / WebP。"
        ) from exc
    except Image.DecompressionBombError as exc:
        raise ImageValidationError("unsupported_file", "图片像素过大，已被拒绝。") from exc

    if actual_format not in _ALLOWED_FORMATS:
        raise ImageValidationError(
            "unsupported_file", "仅支持 JPG / PNG / WebP 图片。"
        )
    extension, mime_type = _ALLOWED_FORMATS[actual_format]

    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()
            # 按 EXIF 方向摆正后再计算尺寸与副本；原图字节保持不变
            upright = ImageOps.exif_transpose(opened)
            width, height = upright.size
            rgb = _to_rgb(upright)
            analysis_image = _resize_long_edge(rgb, ANALYSIS_MAX_EDGE)
            thumb_image = _resize_long_edge(rgb, THUMB_MAX_EDGE)
            warnings = _quality_warnings(analysis_image, width, height)
            analysis_jpeg = _encode_jpeg(analysis_image, 90, ANALYSIS_MAX_BYTES)
            thumb_jpeg = _encode_jpeg(thumb_image, 82)
    except Image.DecompressionBombError as exc:
        raise ImageValidationError("unsupported_file", "图片像素过大，已被拒绝。") from exc
    except (OSError, ValueError) as exc:
        logger.info("图片处理失败：%s (%s)", filename, type(exc).__name__)
        raise ImageValidationError(
            "unsupported_file", "文件无法读取，请重新导出。"
        ) from exc

    return ProcessedImage(
        original_bytes=data,
        extension=extension,
        mime_type=mime_type,
        width=width,
        height=height,
        analysis_jpeg=analysis_jpeg,
        thumb_jpeg=thumb_jpeg,
        warnings=warnings,
        sha256=hashlib.sha256(data).hexdigest(),
    )
