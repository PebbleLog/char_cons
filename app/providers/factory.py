"""Provider 工厂：业务层只依赖接口，不直接依赖厂商实现。"""

from __future__ import annotations

from ..core.config import Settings
from .base import GenerationProvider, VisionProvider
from .doubao_seedream import DoubaoSeedreamProvider
from .doubao_vision import DoubaoVisionProvider
from .mock import MockVisionProvider
from .mock_generation import MockGenerationProvider


def make_vision_provider(settings: Settings) -> VisionProvider:
    provider = (settings.analysis_provider or "doubao").lower()
    if provider == "mock":
        return MockVisionProvider()
    if provider == "doubao":
        return DoubaoVisionProvider(settings)
    raise ValueError(f"不支持的分析服务：{settings.analysis_provider}")


def make_generation_provider(settings: Settings) -> GenerationProvider:
    provider = (settings.generation_provider or "doubao").lower()
    if provider == "mock":
        return MockGenerationProvider()
    if provider == "doubao":
        return DoubaoSeedreamProvider(settings)
    raise ValueError(f"不支持的生成服务：{settings.generation_provider}")
