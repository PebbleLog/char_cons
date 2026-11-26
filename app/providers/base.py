"""Provider 接口与通用结果对象（技术方案 3.10）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .schemas import CharacterProfile, ScriptContext, ShotObservation


@dataclass(slots=True)
class UsageInfo:
    input_images: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class ProviderResult:
    value: Any
    request_id: str | None
    model: str
    usage: UsageInfo = field(default_factory=UsageInfo)
    raw_text: str = ""


class VisionProvider(Protocol):
    name: str
    capabilities: dict[str, Any]

    def ensure_configured(self) -> None: ...

    async def test_connection(self) -> dict[str, Any]: ...

    async def parse_profile(self, text: str) -> ProviderResult: ...

    async def observe_shot(
        self,
        image: bytes,
        *,
        mime_type: str,
        shot_code: str,
        note: str,
        profile: CharacterProfile,
        script: ScriptContext,
    ) -> ProviderResult: ...

    async def generate_suggestion(
        self,
        *,
        issue: dict[str, Any],
        profile: CharacterProfile,
        script: ScriptContext,
        references: list[dict[str, Any]],
        batch_size: int,
        existing_prompt: str | None = None,
    ) -> ProviderResult: ...

    async def precheck_candidates(
        self,
        *,
        criteria: list[str],
        candidates: list[tuple[str, bytes, str]],
        issue: dict[str, Any] | None = None,
        references: list[tuple[str, bytes, str]] | None = None,
    ) -> ProviderResult: ...


@dataclass(slots=True)
class GeneratedImage:
    image_bytes: bytes
    mime_type: str
    remote_url: str | None
    request_id: str | None
    model: str
    usage: UsageInfo = field(default_factory=UsageInfo)
    elapsed_ms: int | None = None


class GenerationProvider(Protocol):
    """单次只生成 1 张；4 张候选由服务层并行调用 4 次。"""

    name: str
    model_name: str
    capabilities: dict[str, Any]

    def ensure_configured(self) -> None: ...

    async def test_connection(self) -> dict[str, Any]: ...

    async def generate(
        self,
        *,
        prompt: str,
        references: list[tuple[bytes, str]],
        size: str | None,
        seed: int | None,
    ) -> GeneratedImage: ...


__all__ = [
    "CharacterProfile",
    "ScriptContext",
    "ShotObservation",
    "UsageInfo",
    "ProviderResult",
    "VisionProvider",
    "GeneratedImage",
    "GenerationProvider",
]
