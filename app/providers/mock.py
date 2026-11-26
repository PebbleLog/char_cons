"""Mock 视觉 Provider：仅用于测试/演示，不调用网络。

输出是固定的结构化数据，明确标记 provider=mock、model=mock-vision；
不得伪装成真实模型结果；生产默认使用豆包 Provider。
"""

from __future__ import annotations

from typing import Any

from ..core.constants import ATTRIBUTE_IDS
from .base import ProviderResult, UsageInfo
from .schemas import (
    CandidatePrecheck,
    CharacterProfile,
    ObservationItem,
    PrecheckCriterion,
    PrecheckOutput,
    ScriptContext,
    ShotObservation,
    SubjectInfo,
    SuggestionOutput,
)
from .suggestion_templates import build_local_suggestion


class MockVisionProvider:
    name = "mock"
    model_name = "mock-vision"
    capabilities = {
        "structured_output": True,
        "max_image_mb": 10,
        "max_images_per_request": 6,
        "supports_multi_image": True,
        "supports_json_schema": False,
        "native_batch": False,
    }

    def ensure_configured(self) -> None:  # Mock 无需配置
        return None

    async def test_connection(self) -> dict[str, Any]:
        return {"model": "mock-vision", "requestId": "mock-connection", "mock": True}

    async def parse_profile(self, text: str) -> ProviderResult:
        # Mock 不实现语义抽取：返回全 undefined，让分析管线走本地规则回退。
        # 这样既不会伪造 AI 解析结果，也能让测试覆盖回退路径。
        profile = CharacterProfile(rawText=text, attributes=[])
        return ProviderResult(
            value=profile,
            request_id="mock-profile",
            model="mock-vision",
            usage=UsageInfo(),
            raw_text=profile.model_dump_json(by_alias=True),
        )

    async def observe_shot(
        self,
        image: bytes,
        *,
        mime_type: str,
        shot_code: str,
        note: str,
        profile: CharacterProfile,
        script: ScriptContext,
    ) -> ProviderResult:
        observations = []
        for attribute in profile.attributes:
            if attribute.attribute_id not in ATTRIBUTE_IDS:
                continue
            if attribute.source == "explicit" and attribute.value:
                observations.append(
                    ObservationItem(
                        attributeId=attribute.attribute_id,
                        observedValue=attribute.value,
                        visibility="visible",
                        evidence=f"Mock 观察：{attribute.name}「{attribute.value}」在图中可见。",
                        confidence="high",
                    )
                )
            else:
                observations.append(
                    ObservationItem(
                        attributeId=attribute.attribute_id,
                        observedValue=None,
                        visibility="not_visible",
                        visibilityReason="Mock：该要素在本测试图中没有可判定信息。",
                        confidence="medium",
                    )
                )
        observation = ShotObservation(
            subject=SubjectInfo(personCount=1, mainSubject=True, confidence=0.96),
            observations=observations,
        )
        return ProviderResult(
            value=observation,
            request_id=f"mock-observe-{shot_code}",
            model="mock-vision",
            usage=UsageInfo(input_images=1),
            raw_text=observation.model_dump_json(by_alias=True),
        )

    async def generate_suggestion(
        self,
        *,
        issue: dict[str, Any],
        profile: CharacterProfile,
        script: ScriptContext,
        references: list[dict[str, Any]],
        batch_size: int,
        existing_prompt: str | None = None,
    ) -> ProviderResult:
        # 明确使用确定性本地模板，不冒充模型生成；source 由服务层记录为 local。
        payload = build_local_suggestion(
            issue=issue,
            profile=profile,
            script=script,
            references=references,
            batch_size=batch_size,
            existing_prompt=existing_prompt,
        )
        suggestion = SuggestionOutput.model_validate(payload)
        return ProviderResult(
            value=suggestion,
            request_id=None,
            model="local-rule",
            usage=UsageInfo(),
            raw_text=suggestion.model_dump_json(by_alias=True),
        )

    async def precheck_candidates(
        self,
        *,
        criteria: list[str],
        candidates: list[tuple[str, bytes, str]],
        issue: dict[str, Any] | None = None,
        references: list[tuple[str, bytes, str]] | None = None,
    ) -> ProviderResult:
        results = []
        for code, _data, _mime in candidates:
            results.append(
                CandidatePrecheck(
                    candidateCode=code,
                    overall="pass",
                    summary="Mock 预检：候选图满足标准（测试数据，不代表真实模型结论）。",
                    criteria=[
                        PrecheckCriterion(
                            key=f"criterion-{index}",
                            name=text,
                            passed=True,
                            evidence="Mock 预检：按测试策略视为通过。",
                        )
                        for index, text in enumerate(criteria, start=1)
                    ],
                )
            )
        output = PrecheckOutput(
            mode="batch" if len(candidates) > 1 else "per_candidate",
            candidates=results,
        )
        return ProviderResult(
            value=output,
            request_id=f"mock-precheck-{len(candidates)}",
            model="mock-vision",
            usage=UsageInfo(input_images=len(candidates) + len(references or [])),
            raw_text=output.model_dump_json(by_alias=True),
        )
