"""豆包 Seed 视觉 Provider（火山方舟 OpenAI 兼容 Chat Completions）。

【待实测】
- 具体模型 ID 由设置/环境变量提供，代码不写死；
- `response_format=json_object` 与该模型的实际支持情况以控制台为准；
- 多图/预检能力在后续阶段接入。

安全：API Key 只在本模块读取，不写日志、不进入返回值。
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Awaitable, Callable, Sequence

import httpx
from pydantic import ValidationError

from ..core.config import Settings
from ..core.keyring_store import get_api_key
from .base import ProviderResult, UsageInfo
from .errors import ProviderError
from .json_utils import extract_json_object, truncate
from .prompt_loader import load_prompt
from .schemas import (
    CharacterProfile,
    PrecheckOutput,
    ScriptContext,
    ShotObservation,
    SuggestionOutput,
)

logger = logging.getLogger(__name__)

_SCHEMA_HINTS = {
    CharacterProfile: (
        '顶层 {"attributes": [...]}；11 个要素全部出现且唯一；'
        "source 只能是 explicit/undefined；explicit 必须有 value。"
    ),
    ShotObservation: (
        '顶层 {"subject": {...}, "observations": [...]}；11 个要素全部出现且唯一；'
        "visible/partial 必须有 observedValue 与 evidence；not_visible 必须有 visibilityReason。"
    ),
    SuggestionOutput: (
        '顶层包含 revisedPrompt / negativePrompt / negativePromptMode=merged / '
        "keyPoints / referenceShots / rationale / cardDrawPlan；"
        "supportedParams 只能是 referenceImage、seed、size。"
    ),
    PrecheckOutput: (
        '顶层 {"mode":"batch|per_candidate","candidates":[...]}；'
        "每张候选包含 candidateCode / overall(pass|partial|fail|unknown) / criteria；"
        "每条标准 passed 只能为 true/false/null 且必须给证据。"
    ),
}


class _SchemaFailure(Exception):
    pass


class DoubaoVisionProvider:
    name = "volcengine-ark"
    model_name = "volcengine-ark"
    capabilities = {
        "structured_output": True,
        "max_image_mb": 10,
        # 观察为单图；预检批量最多 4 张候选 + 2 张参考镜头（多图映射稳定性【待实测】）
        "max_images_per_request": 6,
        "supports_multi_image": True,
        "supports_json_schema": False,  # 【待实测】当前按 json_object + Pydantic 校验
        "native_batch": False,
    }

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_backoff: Sequence[float] = (2.0, 5.0, 10.0),
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings
        self.model_name = settings.analysis_model or "volcengine-ark"
        self._transport = transport
        self._retry_backoff = tuple(retry_backoff)
        self._sleep = sleep or asyncio.sleep

    # ---- 配置 --------------------------------------------------
    def ensure_configured(self) -> None:
        if not self.settings.analysis_model.strip():
            raise ProviderError(
                "auth_failed",
                "分析模型未配置。请填写火山方舟控制台中的视觉模型 ID。",
            )
        if not get_api_key("analysis"):
            raise ProviderError(
                "auth_failed",
                "分析服务未配置 API Key。请在设置中保存，或使用环境变量。",
            )

    def _headers(self) -> dict[str, str]:
        key = get_api_key("analysis")
        if not key:  # 理论上 ensure_configured 已拦截
            raise ProviderError("auth_failed", "分析服务未配置 API Key。")
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    # ---- 对外能力 ----------------------------------------------
    async def parse_profile(self, text: str) -> ProviderResult:
        self.ensure_configured()
        system = load_prompt("profile_parse")
        user = f"角色设定原文：\n{text}\n\n请按要求输出 11 个要素的 JSON。"
        result = await self._chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            schema=CharacterProfile,
            input_images=0,
        )
        if isinstance(result.value, CharacterProfile):
            # 模型不负责回显原文；由后端填入，避免 rawText 缺失导致解析失败。
            result.value.raw_text = text.strip()
        return result

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
        self.ensure_configured()
        system = load_prompt("shot_observe")
        explicit = "\n".join(
            f"- {attribute.name}：{attribute.value}"
            for attribute in profile.attributes
            if attribute.source == "explicit"
        ) or "（无显式要素）"
        allowed = "、".join(sorted(script.allowed_for_shot(shot_code))) or "无"
        user_text = (
            f"镜头编号：{shot_code}\n"
            f"镜头备注：{note or '无'}\n"
            f"角色设定显式要素：\n{explicit}\n"
            f"剧本规则：{script.rule_badge}；本镜头允许变化：{allowed}\n"
            "请只基于本图可见信息，输出 11 个要素的 JSON。"
        )
        data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        content: list[dict[str, Any]] = [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": user_text},
        ]
        return await self._chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            schema=ShotObservation,
            input_images=1,
        )

    async def test_connection(self) -> dict[str, Any]:
        """最小化鉴权/网络检查；不发送图片，不打印 Key。"""
        self.ensure_configured()
        # 复用同一请求管线，但不要求结构化 JSON，避免额外修复请求。
        exchange = await self._post_with_retries(
            [
                {
                    "role": "user",
                    "content": '这是本地服务的连通性测试，请只返回 JSON：{"ok":true}。',
                }
            ],
            timeout_seconds=min(30, self.settings.vision_timeout_seconds),
        )
        return {
            "model": exchange.get("model") or self.settings.analysis_model,
            "requestId": exchange.get("request_id"),
        }

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
        self.ensure_configured()
        system = load_prompt("suggestion")
        explicit = "\n".join(
            f"- {attribute.name}：{attribute.value}"
            for attribute in profile.attributes
            if attribute.source == "explicit"
        ) or "（无显式要素）"
        reference_text = "、".join(
            f"{item['shotCode']}（{item.get('reason') or '同角色参考'}）" for item in references
        ) or "无合格参考镜头，仅使用提示词与多批重抽策略"
        user_text = (
            f"问题编号：{issue.get('id')}\n"
            f"镜头：{issue.get('shotCode')}\n"
            f"要素：{issue.get('attributeName')}（{issue.get('attributeId')}）\n"
            f"设定期望：{issue.get('expected') or '设定未定义（不得臆造具体外观）'}\n"
            f"实际观察：{issue.get('observed') or '—'}\n"
            f"证据：{issue.get('evidence') or issue.get('reason') or '—'}\n"
            f"严重度/置信度：{issue.get('severity') or 'medium'} / {issue.get('confidence') or 'medium'}\n"
            f"本批候选张数：{batch_size}（服务单次只生成 1 张，将并行调用 {batch_size} 次）\n"
            f"参考镜头：{reference_text}\n"
            f"剧本规则：{script.rule_badge}\n"
            f"角色设定显式要素：\n{explicit}\n"
            f"原生成提示词（可能为空）：{existing_prompt or '无'}\n"
            "请输出一份可直接使用的中文修正建议与抽卡方案 JSON。"
        )
        return await self._chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            schema=SuggestionOutput,
            input_images=0,
        )

    async def precheck_candidates(
        self,
        *,
        criteria: list[str],
        candidates: list[tuple[str, bytes, str]],
        issue: dict[str, Any] | None = None,
        references: list[tuple[str, bytes, str]] | None = None,
    ) -> ProviderResult:
        self.ensure_configured()
        system = load_prompt("precheck")
        criterion_text = "\n".join(
            f"{index}. {text}" for index, text in enumerate(criteria, start=1)
        )
        codes = "、".join(code for code, _data, _mime in candidates)
        reference_codes = "、".join(
            code for code, _data, _mime in (references or [])
        ) or "无"
        context = (
            f"问题：{issue.get('shotCode')} · {issue.get('attributeName')}；"
            f"期望：{issue.get('expected') or '设定未定义'}；"
            f"原图问题：{issue.get('observed') or '—'}。"
            if issue
            else ""
        )
        user_text = (
            f"{context}\n"
            f"参考镜头：{reference_codes}\n"
            f"挑选标准：\n{criterion_text}\n"
            f"本次候选编号：{codes}\n"
            f"模式：{'batch' if len(candidates) > 1 else 'per_candidate'}\n"
            "请逐张输出候选预检 JSON。"
        )
        content: list[dict[str, Any]] = []
        if references:
            content.append(
                {
                    "type": "text",
                    "text": "参考镜头图（仅用于核对写明「参考镜头 Sx」的标准）：",
                }
            )
            for code, data, mime in references:
                content.append({"type": "text", "text": f"参考 {code}："})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
                        },
                    }
                )
        content.append({"type": "text", "text": "候选图："})
        for code, data, mime in candidates:
            content.append({"type": "text", "text": f"候选 {code}："})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"},
                }
            )
        content.append({"type": "text", "text": user_text})
        return await self._chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            schema=PrecheckOutput,
            input_images=len(candidates) + len(references or []),
            timeout_seconds=self.settings.precheck_timeout_seconds,
        )

    # ---- 请求/重试 ----------------------------------------------
    async def _chat_json(
        self,
        *,
        messages: list[dict[str, Any]],
        schema: type,
        input_images: int,
        timeout_seconds: int | None = None,
    ) -> ProviderResult:
        exchange = await self._post_with_retries(messages, timeout_seconds=timeout_seconds)
        usage = exchange["usage"]

        try:
            value = self._parse(schema, exchange["text"])
        except _SchemaFailure as exc:
            logger.warning("模型 JSON 校验失败，尝试一次修复：%s", exc)
            repair_messages = [
                {
                    "role": "user",
                    "content": (
                        "下面是一次不合规的模型输出。请只返回符合要求的合法 JSON，"
                        "不要 Markdown、不要解释。\n"
                        f"结构要求：{_SCHEMA_HINTS.get(schema, '严格 JSON 对象')}\n"
                        f"校验错误：{exc}\n"
                        f"原始输出：\n{truncate(exchange['text'])}"
                    ),
                }
            ]
            repaired = await self._post_with_retries(
                repair_messages, timeout_seconds=timeout_seconds
            )
            usage = UsageInfo(
                input_images=input_images,
                input_tokens=usage.input_tokens + repaired["usage"].input_tokens,
                output_tokens=usage.output_tokens + repaired["usage"].output_tokens,
            )
            try:
                value = self._parse(schema, repaired["text"])
            except _SchemaFailure as repair_exc:
                raise ProviderError(
                    "invalid_response",
                    "模型返回结构不符合要求，已尝试修复仍失败。",
                    request_id=repaired.get("request_id"),
                ) from repair_exc
            exchange = repaired
        else:
            usage = UsageInfo(
                input_images=input_images,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

        return ProviderResult(
            value=value,
            request_id=exchange.get("request_id"),
            model=exchange.get("model") or self.settings.analysis_model,
            usage=usage,
            raw_text=exchange["text"],
        )

    @staticmethod
    def _parse(schema: type, text: str) -> Any:
        try:
            payload = extract_json_object(text)
            return schema.model_validate(payload)
        except (ValueError, ValidationError) as exc:
            raise _SchemaFailure(str(exc)) from exc

    async def _post_with_retries(
        self, messages: list[dict[str, Any]], *, timeout_seconds: int | None = None
    ) -> dict[str, Any]:
        attempts = max(1, int(self.settings.retry_max_attempts))
        last_error: ProviderError | None = None
        for attempt in range(attempts):
            try:
                return await self._post_once(messages, timeout_seconds=timeout_seconds)
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts - 1:
                    raise
                delay = exc.retry_after
                if delay is None:
                    index = min(attempt, len(self._retry_backoff) - 1)
                    delay = self._retry_backoff[index]
                logger.warning(
                    "分析服务请求失败（%s），%.1f 秒后第 %d 次重试",
                    exc.code,
                    delay,
                    attempt + 2,
                )
                await self._sleep(delay)
        assert last_error is not None
        raise last_error

    async def _post_once(
        self, messages: list[dict[str, Any]], *, timeout_seconds: int | None = None
    ) -> dict[str, Any]:
        base = self.settings.analysis_base_url.rstrip("/")
        payload = {
            "model": self.settings.analysis_model,
            "temperature": 0.1,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        timeout = httpx.Timeout(
            timeout_seconds or self.settings.vision_timeout_seconds,
            connect=self.settings.connect_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{base}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "provider_timeout", "分析服务响应超时。", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "provider_unavailable", "无法连接分析服务。", retryable=True
            ) from exc

        request_id = response.headers.get("x-request-id")
        if response.status_code >= 400:
            raise self._map_http_error(response, request_id)

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                "invalid_response",
                "分析服务返回了无法解析的响应。",
                request_id=request_id,
            ) from exc

        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "invalid_response",
                "分析服务响应缺少 message.content。",
                request_id=request_id or data.get("id"),
            ) from exc

        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        if not isinstance(content, str) or not content.strip():
            raise ProviderError(
                "invalid_response",
                "分析服务返回为空。",
                request_id=request_id or data.get("id"),
            )

        usage_raw = data.get("usage") or {}
        usage = UsageInfo(
            input_images=0,
            input_tokens=int(usage_raw.get("prompt_tokens") or 0),
            output_tokens=int(usage_raw.get("completion_tokens") or 0),
        )
        return {
            "text": content,
            "usage": usage,
            "request_id": request_id or data.get("id"),
            "model": data.get("model") or self.settings.analysis_model,
        }

    @staticmethod
    def _map_http_error(response: httpx.Response, request_id: str | None) -> ProviderError:
        status = response.status_code
        message = ""
        code = ""
        try:
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                message = str(error.get("message") or "")
                code = str(error.get("code") or "")
        except ValueError:
            message = response.text[:300] if response.text else ""

        combined = f"{code} {message}".lower()
        if status in (401, 403):
            return ProviderError("auth_failed", "鉴权失败，请检查分析服务 API Key。", status_code=status, request_id=request_id)
        if status == 429:
            retry_after = None
            raw = response.headers.get("retry-after")
            if raw:
                try:
                    retry_after = max(0.0, float(raw))
                except ValueError:
                    retry_after = None
            return ProviderError(
                "rate_limited",
                "分析服务限流，请稍后重试。",
                retryable=True,
                status_code=status,
                request_id=request_id,
                retry_after=retry_after,
            )
        if status >= 500:
            return ProviderError(
                "provider_unavailable",
                "分析服务暂时不可用。",
                retryable=True,
                status_code=status,
                request_id=request_id,
            )
        if any(token in combined for token in ("quota", "insufficient", "balance", "额度")):
            return ProviderError(
                "quota_exceeded", "分析服务额度不足。", status_code=status, request_id=request_id
            )
        if any(
            token in combined
            for token in ("sensitive", "content_filter", "contentfilter", "risk", "safety", "安全", "审核")
        ):
            return ProviderError(
                "content_filtered",
                "素材或提示词未通过内容安全审核。",
                status_code=status,
                request_id=request_id,
            )
        return ProviderError(
            "invalid_response",
            message or f"分析服务返回错误（HTTP {status}）。",
            status_code=status,
            request_id=request_id,
        )
