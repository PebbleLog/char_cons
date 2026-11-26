from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.core.constants import ATTRIBUTE_IDS
from app.providers.doubao_vision import DoubaoVisionProvider
from app.providers.errors import ProviderError
from app.providers.json_utils import extract_json_object
from app.providers.schemas import CharacterProfile


def _profile_payload() -> dict:
    return {
        "rawText": "测试设定",
        "attributes": [
            {
                "id": aid,
                "value": "值" if aid == "top_style" else None,
                "source": "explicit" if aid == "top_style" else "undefined",
                "evidenceText": "证据" if aid == "top_style" else None,
                "confidence": 0.9 if aid == "top_style" else None,
            }
            for aid in ATTRIBUTE_IDS
        ]
    }


def _observation_payload() -> dict:
    return {
        "subject": {"personCount": 1, "mainSubject": True, "confidence": 0.96},
        "observations": [
            {
                "attributeId": aid,
                "observedValue": "值",
                "visibility": "visible",
                "evidence": "画面证据",
                "confidence": "high",
            }
            for aid in ATTRIBUTE_IDS
        ],
    }


def _chat_response(content: str, *, model: str = "test-model") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "model": model,
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        headers={"x-request-id": "req-1"},
    )


async def _no_sleep(_: float) -> None:
    return None


def _provider(tmp_path, handler, monkeypatch) -> DoubaoVisionProvider:
    monkeypatch.setenv("CHAR_CONS_ANALYSIS_API_KEY", "sk-test")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    settings = Settings(home_dir=tmp_path / "provider-home")
    settings.analysis_model = "test-model"
    settings.analysis_base_url = "https://ark.example/api/v3"
    settings.retry_max_attempts = 3
    return DoubaoVisionProvider(
        settings,
        transport=httpx.MockTransport(handler),
        retry_backoff=(0, 0, 0),
        sleep=_no_sleep,
    )


async def test_parse_profile_success_and_usage(tmp_path, monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return _chat_response(json.dumps(_profile_payload(), ensure_ascii=False))

    provider = _provider(tmp_path, handler, monkeypatch)
    result = await provider.parse_profile("阿岚，浅米色亚麻西装外套。")

    assert isinstance(result.value, CharacterProfile)
    assert result.value.explicit_count == 1
    assert result.request_id == "req-1"
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["response_format"] == {"type": "json_object"}


async def test_extract_json_from_code_fence():
    text = '说明文字\n```json\n{"a": 1}\n```\n结尾'
    assert extract_json_object(text) == {"a": 1}

    with pytest.raises(ValueError):
        extract_json_object("没有 JSON")


async def test_invalid_json_repairs_once(tmp_path, monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _chat_response("这不是 JSON")
        body = json.loads(request.content)
        assert "合法 JSON" in body["messages"][-1]["content"]
        return _chat_response(json.dumps(_profile_payload(), ensure_ascii=False))

    provider = _provider(tmp_path, handler, monkeypatch)
    result = await provider.parse_profile("设定")
    assert calls["n"] == 2
    assert result.usage.input_tokens == 20  # 两次调用求和


async def test_json_failure_after_repair_raises(tmp_path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("仍然不是 JSON")

    provider = _provider(tmp_path, handler, monkeypatch)
    with pytest.raises(ProviderError) as exc:
        await provider.parse_profile("设定")
    assert exc.value.code == "invalid_response"


async def test_rate_limit_retries(tmp_path, monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "slow"}})
        return _chat_response(json.dumps(_profile_payload(), ensure_ascii=False))

    provider = _provider(tmp_path, handler, monkeypatch)
    await provider.parse_profile("设定")
    assert calls["n"] == 2


async def test_auth_failure_not_retried(tmp_path, monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    provider = _provider(tmp_path, handler, monkeypatch)
    with pytest.raises(ProviderError) as exc:
        await provider.parse_profile("设定")
    assert exc.value.code == "auth_failed"
    assert calls["n"] == 1


async def test_timeout_retries(tmp_path, monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        return _chat_response(json.dumps(_profile_payload(), ensure_ascii=False))

    provider = _provider(tmp_path, handler, monkeypatch)
    await provider.parse_profile("设定")
    assert calls["n"] == 2


async def test_quota_and_content_errors(tmp_path, monkeypatch):
    def quota_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "QuotaExceeded", "message": "额度不足"}})

    provider = _provider(tmp_path, quota_handler, monkeypatch)
    with pytest.raises(ProviderError) as exc:
        await provider.parse_profile("设定")
    assert exc.value.code == "quota_exceeded"

    def content_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "SensitiveContentDetected", "message": "risk"}})

    provider = _provider(tmp_path, content_handler, monkeypatch)
    with pytest.raises(ProviderError) as exc:
        await provider.parse_profile("设定")
    assert exc.value.code == "content_filtered"


async def test_observe_sends_image_and_parses(tmp_path, monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _chat_response(json.dumps(_observation_payload(), ensure_ascii=False))

    provider = _provider(tmp_path, handler, monkeypatch)
    profile = CharacterProfile(
        rawText="设定",
        attributes=[{"id": "top_style", "value": "外套", "source": "explicit"}],
    )
    from app.services.script_parser import parse_script

    result = await provider.observe_shot(
        b"\xff\xd8\xff\xe0fake",
        mime_type="image/jpeg",
        shot_code="S1",
        note="正面",
        profile=profile,
        script=parse_script("无换装。", ["S1"]),
    )
    assert len(result.value.observations) == 11
    content = captured["body"]["messages"][-1]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert result.usage.input_images == 1


def _suggestion_payload() -> dict:
    return {
        "revisedPrompt": "阿岚，浅米色亚麻西装外套（与 S1 一致）。",
        "negativePrompt": "冷灰外套",
        "negativePromptMode": "merged",
        "keyPoints": ["锁定浅米色外套", "引用 S1 作为参考", "保留原构图"],
        "referenceShots": ["S1"],
        "rationale": "S2 外套偏冷灰，需要锁定浅暖米色。",
        "cardDrawPlan": {
            "batchSize": 4,
            "referenceShots": ["S1"],
            "selectionCriteria": ["外套主色为浅暖米色", "与 S1 一致", "构图连贯"],
            "escalation": "强化要素后重抽。",
            "supportedParams": ["referenceImage", "seed", "size", "unsupportedParam"],
            "negativePromptMode": "merged",
        },
    }


def _precheck_payload(codes: list[str]) -> dict:
    return {
        "mode": "batch" if len(codes) > 1 else "per_candidate",
        "candidates": [
            {
                "candidateCode": code,
                "overall": "pass",
                "summary": "符合标准",
                "criteria": [
                    {"key": f"c{i}", "name": "标准", "passed": True, "evidence": "证据"}
                    for i in range(1, 4)
                ],
            }
            for code in codes
        ],
    }


async def test_generate_suggestion_parses_and_filters_unsupported_params(tmp_path, monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _chat_response(json.dumps(_suggestion_payload(), ensure_ascii=False))

    provider = _provider(tmp_path, handler, monkeypatch)
    from app.services.profile_local import parse_profile_local
    from app.services.script_parser import parse_script

    profile = parse_profile_local("阿岚，浅米色亚麻西装外套。")
    result = await provider.generate_suggestion(
        issue={
            "id": "ISS-001",
            "shotCode": "S2",
            "attributeId": "top_color",
            "attributeName": "上装颜色",
            "expected": "浅米色",
            "observed": "冷灰米色",
            "evidence": "外套偏冷灰",
            "severity": "medium",
            "confidence": "high",
        },
        profile=profile,
        script=parse_script("无换装。", ["S1", "S2"]),
        references=[{"shotCode": "S1", "reason": "无问题参考"}],
        batch_size=4,
    )
    assert result.value.revised_prompt.startswith("阿岚")
    assert result.value.card_draw_plan.batch_size == 4
    assert "unsupportedParam" not in result.value.card_draw_plan.supported_params
    user_text = captured["body"]["messages"][-1]["content"]
    assert "ISS-001" in user_text and "浅米色" in user_text
    assert "单次只生成 1 张" in user_text


async def test_precheck_batch_sends_multiple_images(tmp_path, monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _chat_response(
            json.dumps(_precheck_payload(["C-001", "C-002"]), ensure_ascii=False)
        )

    provider = _provider(tmp_path, handler, monkeypatch)
    result = await provider.precheck_candidates(
        criteria=["标准 1", "标准 2", "标准 3"],
        candidates=[
            ("C-001", b"\x89PNGfake1", "image/png"),
            ("C-002", b"\x89PNGfake2", "image/png"),
        ],
        issue={"shotCode": "S3", "attributeName": "配饰", "expected": "蓝紫四瓣"},
        references=[("S1", b"\x89PNGreference", "image/png")],
    )
    assert len(result.value.candidates) == 2
    assert result.usage.input_images == 3
    content = captured["body"]["messages"][-1]["content"]
    images = [part for part in content if part.get("type") == "image_url"]
    assert len(images) == 3
    texts = " ".join(
        part.get("text", "") for part in content if part.get("type") == "text"
    )
    assert "参考 S1" in texts
    assert "参考镜头：S1" in texts


async def test_profile_raw_text_missing_is_filled_and_visibility_synonyms(tmp_path, monkeypatch):
    payload = _profile_payload()
    payload.pop("rawText", None)

    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(json.dumps(payload, ensure_ascii=False))

    provider = _provider(tmp_path, handler, monkeypatch)
    result = await provider.parse_profile("阿岚，深棕长发低侧发髻。")
    assert result.value.raw_text == "阿岚，深棕长发低侧发髻。"

    observation = _observation_payload()
    observation["observations"][0]["visibility"] = "partially_visible"
    observation["observations"][0]["observedValue"] = "深棕"
    observation["observations"][0]["evidence"] = "可见"

    def observe_handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(json.dumps(observation, ensure_ascii=False))

    provider = _provider(tmp_path, observe_handler, monkeypatch)
    profile = CharacterProfile(
        rawText="设定",
        attributes=[{"id": "hair_color", "value": "深棕", "source": "explicit"}],
    )
    from app.services.script_parser import parse_script

    seen = await provider.observe_shot(
        b"fake-image",
        mime_type="image/png",
        shot_code="S1",
        note="",
        profile=profile,
        script=parse_script("无换装。", ["S1"]),
    )
    assert seen.value.observations[0].visibility == "partial"
