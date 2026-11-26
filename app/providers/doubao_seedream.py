"""火山方舟 Seedream 5.5 图像生成 Provider。

能力声明与约束（以官方文档/控制台为准，未验证项标注【待实测】）：
- 单次只生成 1 张，不存在批量 n；4 张候选由服务层并行调用 4 次；
- 无独立 negative_prompt 参数，负向内容由服务层合并进 prompt；
- 支持参考图数组、seed、size；具体字段名与取值范围【待实测】；
- 返回 URL 仅短期有效，必须立刻下载到本地；不在日志中记录图片内容或 Key。
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Awaitable, Callable, Sequence

import httpx

from ..core.config import Settings
from ..core.keyring_store import get_api_key
from .base import GeneratedImage, UsageInfo
from .errors import ProviderError

logger = logging.getLogger(__name__)

MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024


class DoubaoSeedreamProvider:
    name = "volcengine-ark"
    model_name = "doubao-seedream"

    capabilities = {
        "native_batch": False,
        "max_images_per_request": 1,
        "max_reference_images": 10,
        "supports_reference_image": True,
        "supports_seed": True,
        "supports_size": True,
        "supports_negative_prompt": False,
        "negative_prompt_mode": "merged",
        "response_format": "url",
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
        self.model_name = settings.generation_model or "doubao-seedream"
        self._transport = transport
        self._retry_backoff = tuple(retry_backoff)
        self._sleep = sleep or asyncio.sleep

    def ensure_configured(self) -> None:
        if not self.settings.generation_model.strip():
            raise ProviderError(
                "auth_failed",
                "图像生成模型未配置。请填写火山方舟控制台中的 Seedream 模型 ID。",
            )
        if not get_api_key("generation"):
            raise ProviderError(
                "auth_failed",
                "图像生成服务未配置 API Key。请在设置中保存，或使用环境变量。",
            )

    def _headers(self) -> dict[str, str]:
        key = get_api_key("generation")
        if not key:
            raise ProviderError("auth_failed", "图像生成服务未配置 API Key。")
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> dict[str, Any]:
        """发起一次最小生成请求验证鉴权/网络/额度；可能产生一次图片费用。"""
        self.ensure_configured()
        generated = await self.generate(
            prompt="纯色浅灰背景，无人物、无文字，连接测试。",
            references=[],
            size=None,
            seed=1,
        )
        return {
            "model": generated.model,
            "requestId": generated.request_id,
            "imageBytes": len(generated.image_bytes),
        }

    async def generate(
        self,
        *,
        prompt: str,
        references: list[tuple[bytes, str]],
        size: str | None,
        seed: int | None,
    ) -> GeneratedImage:
        self.ensure_configured()
        payload: dict[str, Any] = {
            "model": self.settings.generation_model,
            "prompt": prompt,
            "response_format": "url",
        }
        if references:
            payload["image"] = [
                f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
                for data, mime in references[:10]
            ]
        if size:
            payload["size"] = size
        if seed is not None:
            payload["seed"] = int(seed)

        data = await self._post_with_retries(payload)
        items = data.get("data")
        if not isinstance(items, list) or not items:
            raise ProviderError(
                "no_candidates",
                "生成服务未返回候选图。",
                request_id=data.get("id"),
            )
        item = items[0] if isinstance(items[0], dict) else {}
        remote_url = item.get("url")
        b64 = item.get("b64_json")
        image_bytes: bytes
        mime_type = "image/png"
        if b64:
            try:
                image_bytes = base64.b64decode(b64)
            except (ValueError, TypeError) as exc:
                raise ProviderError(
                    "invalid_response",
                    "生成服务返回的图片数据无法解码。",
                    request_id=data.get("id"),
                ) from exc
        elif remote_url:
            image_bytes, mime_type = await self._download(str(remote_url), data.get("id"))
        else:
            raise ProviderError(
                "invalid_response",
                "生成服务响应缺少图片 URL。",
                request_id=data.get("id"),
            )

        usage_raw = data.get("usage") or {}
        return GeneratedImage(
            image_bytes=image_bytes,
            mime_type=mime_type,
            remote_url=str(remote_url) if remote_url else None,
            request_id=data.get("id"),
            model=data.get("model") or self.settings.generation_model,
            usage=UsageInfo(),
            elapsed_ms=None,
        )

    async def _download(self, url: str, request_id: str | None) -> tuple[bytes, str]:
        timeout = httpx.Timeout(
            self.settings.image_download_timeout_seconds,
            connect=self.settings.connect_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.get(url)
                response.raise_for_status()
                if len(response.content) > MAX_DOWNLOAD_BYTES:
                    raise ProviderError(
                        "unsupported_file", "生成图片超过 30MB 上限。", request_id=request_id
                    )
                content_type = (response.headers.get("content-type") or "image/png").split(";")[0]
                return response.content, content_type or "image/png"
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "provider_timeout", "下载生成图片超时，已保留请求记录。", retryable=True,
                request_id=request_id,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "provider_unavailable", "下载生成图片失败。", retryable=True,
                request_id=request_id,
            ) from exc

    async def _post_with_retries(self, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = max(1, int(self.settings.retry_max_attempts))
        last_error: ProviderError | None = None
        for attempt in range(attempts):
            try:
                return await self._post_once(payload)
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts - 1:
                    raise
                delay = exc.retry_after
                if delay is None:
                    index = min(attempt, len(self._retry_backoff) - 1)
                    delay = self._retry_backoff[index]
                logger.warning(
                    "生成服务请求失败（%s），%.1f 秒后第 %d 次重试",
                    exc.code,
                    delay,
                    attempt + 2,
                )
                await self._sleep(delay)
        assert last_error is not None
        raise last_error

    async def _post_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        base = self.settings.generation_base_url.rstrip("/")
        timeout = httpx.Timeout(
            self.settings.seedream_timeout_seconds,
            connect=self.settings.connect_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{base}/images/generations",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "provider_timeout", "图像生成服务响应超时。", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "provider_unavailable", "无法连接图像生成服务。", retryable=True
            ) from exc

        request_id = response.headers.get("x-request-id")
        if response.status_code >= 400:
            raise self._map_http_error(response, request_id)
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                "invalid_response",
                "图像生成服务返回了无法解析的响应。",
                request_id=request_id,
            ) from exc
        if not isinstance(data, dict):
            raise ProviderError(
                "invalid_response", "图像生成响应结构不正确。", request_id=request_id
            )
        return data

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
            return ProviderError(
                "auth_failed", "图像生成服务鉴权失败，请检查生成服务 API Key。",
                status_code=status, request_id=request_id,
            )
        if status == 429:
            retry_after = None
            raw = response.headers.get("retry-after")
            if raw:
                try:
                    retry_after = max(0.0, float(raw))
                except ValueError:
                    retry_after = None
            return ProviderError(
                "rate_limited", "图像生成服务限流，请稍后重试。", retryable=True,
                status_code=status, request_id=request_id, retry_after=retry_after,
            )
        if status >= 500:
            return ProviderError(
                "provider_unavailable", "图像生成服务暂时不可用。", retryable=True,
                status_code=status, request_id=request_id,
            )
        if any(token in combined for token in ("quota", "insufficient", "balance", "额度")):
            return ProviderError(
                "quota_exceeded", "图像生成服务额度不足。", status_code=status,
                request_id=request_id,
            )
        if any(
            token in combined
            for token in ("sensitive", "content_filter", "contentfilter", "risk", "safety", "安全", "审核")
        ):
            return ProviderError(
                "content_filtered", "素材或提示词未通过内容安全审核。",
                status_code=status, request_id=request_id,
            )
        return ProviderError(
            "invalid_response",
            message or f"图像生成服务返回错误（HTTP {status}）。",
            status_code=status,
            request_id=request_id,
        )
