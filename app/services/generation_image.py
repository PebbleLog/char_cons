"""生成图片校验/预处理：复用上传图片管线，但使用独立的 30MB 上限。"""

from __future__ import annotations

import logging

from ..providers.errors import ProviderError
from .image_service import ImageValidationError, ProcessedImage, process_upload

logger = logging.getLogger(__name__)

GENERATED_MAX_MB = 30


def process_generated(data: bytes, filename: str) -> ProcessedImage:
    try:
        return process_upload(data, filename, GENERATED_MAX_MB)
    except ImageValidationError as exc:
        logger.info("生成图无法使用：%s (%s)", exc.code, exc.message)
        raise ProviderError(exc.code, f"生成图不可用：{exc.message}") from exc
