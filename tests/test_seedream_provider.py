from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.doubao_seedream import DoubaoSeedreamProvider
from app.providers.errors import ProviderError
from tests.helpers import make_image


async def _no_sleep(_: float) -> None:
    return None


def _provider(tmp_path, handler, monkeypatch) -> DoubaoSeedreamProvider:
    monkeypatch.setenv("CHAR_CONS_GENERATION_API_KEY", "sk-generation-test")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    settings = Settings(home_dir=tmp_path / "seedream-home")
    settings.generation_model = "seedream-test"
    settings.generation_base_url = "https://ark.example/api/v3"
    settings.generation_size = "2K"
    settings.retry_max_attempts = 3
    return DoubaoSeedreamProvider(
        settings,
        transport=httpx.MockTransport(handler),
        retry_backoff=(0, 0, 0),
        sleep=_no_sleep,
    )


async def test_seedream_single_image_payload_and_download(tmp_path, monkeypatch):
    image_bytes = make_image()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, content=image_bytes, headers={"content-type": "image/png"}
            )
        captured["auth"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "seedream-request-1",
                "model": "seedream-test",
                "data": [{"url": "https://cdn.example/candidate.png"}],
            },
            headers={"x-request-id": "req-seedream-1"},
        )

    provider = _provider(tmp_path, handler, monkeypatch)
    generated = await provider.generate(
        prompt="阿岚，圆形吊坠项链（蓝紫四瓣花）。",
        references=[(image_bytes, "image/png")],
        size="2K",
        seed=42,
    )

    assert generated.image_bytes == image_bytes
    assert generated.remote_url == "https://cdn.example/candidate.png"
    assert generated.request_id == "seedream-request-1"
    assert captured["url"].endswith("/images/generations")
    assert captured["auth"] == "Bearer sk-generation-test"
    body = captured["body"]
    assert body["model"] == "seedream-test"
    assert body["seed"] == 42
    assert body["size"] == "2K"
    assert body["response_format"] == "url"
    assert isinstance(body["image"], list) and body["image"][0].startswith("data:image/png;base64,")
    # 服务不支持批量 n 与独立负向参数，不得发送
    assert "n" not in body
    assert "negative_prompt" not in body


async def test_seedream_b64_response(tmp_path, monkeypatch):
    image_bytes = make_image()
    encoded = base64.b64encode(image_bytes).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={"id": "gen-b64", "data": [{"b64_json": encoded}]},
        )

    provider = _provider(tmp_path, handler, monkeypatch)
    generated = await provider.generate(
        prompt="test", references=[], size=None, seed=None
    )
    assert generated.image_bytes == image_bytes
    assert generated.remote_url is None


async def test_seedream_auth_failure_not_retried(tmp_path, monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(
            401, json={"error": {"code": "AuthenticationError", "message": "invalid key"}}
        )

    provider = _provider(tmp_path, handler, monkeypatch)
    with pytest.raises(ProviderError) as raised:
        await provider.generate(prompt="test", references=[], size=None, seed=None)
    assert raised.value.code == "auth_failed"
    assert calls["count"] == 1


async def test_seedream_rate_limit_retries(tmp_path, monkeypatch):
    image_bytes = make_image()
    calls = {"post": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, content=image_bytes, headers={"content-type": "image/png"}
            )
        calls["post"] += 1
        if calls["post"] == 1:
            return httpx.Response(429, json={"error": {"message": "rate limit"}})
        return httpx.Response(
            200, json={"id": "gen-retry", "data": [{"url": "https://cdn.example/x.png"}]}
        )

    provider = _provider(tmp_path, handler, monkeypatch)
    generated = await provider.generate(prompt="test", references=[], size=None, seed=None)
    assert calls["post"] == 2
    assert generated.request_id == "gen-retry"


async def test_seedream_content_filter_maps_error(tmp_path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"code": "SensitiveContent", "message": "content risk"}}
        )

    provider = _provider(tmp_path, handler, monkeypatch)
    with pytest.raises(ProviderError) as raised:
        await provider.generate(prompt="test", references=[], size=None, seed=None)
    assert raised.value.code == "content_filtered"
    assert raised.value.retryable is False


async def test_seedream_requires_model_and_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CHAR_CONS_GENERATION_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    settings = Settings(home_dir=tmp_path / "no-config")
    settings.generation_model = ""
    provider = DoubaoSeedreamProvider(settings)
    with pytest.raises(ProviderError) as raised:
        provider.ensure_configured()
    assert raised.value.code == "auth_failed"
