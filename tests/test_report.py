from __future__ import annotations

import json
import time

import pytest

from app.providers.base import ProviderResult, UsageInfo
from app.providers.mock import MockVisionProvider
from app.providers.schemas import (
    CharacterProfile,
    ObservationItem,
    ShotObservation,
    SubjectInfo,
)
from app.services.profile_local import parse_profile_local
from tests.helpers import make_image, task_payload

PROFILE_TEXT = (
    "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，"
    "紫色口袋巾，圆形吊坠项链（蓝紫四瓣花）。"
)


def _item(aid, value, visibility="visible", reason=None, evidence=None, confidence="high"):
    return ObservationItem.model_construct(
        attribute_id=aid,
        observed_value=value,
        visibility=visibility,
        visibility_reason=reason,
        evidence=evidence,
        confidence=confidence,
    )


def _base():
    return [
        _item("hair_style", "低侧发髻", evidence="低侧发髻轮廓清晰。"),
        _item("hair_color", "深棕", evidence="发丝为深棕色。"),
        _item("top_style", "亚麻西装外套", evidence="翻领亚麻西装。"),
        _item("top_color", "浅米色", evidence="外套为浅暖米色。"),
        _item("top_pattern", "纯色", evidence="外套为纯色。"),
        _item("bottom_style", None, "not_visible", "下装未入画。"),
        _item("bottom_color", None, "not_visible", "下装未入画。"),
        _item("bottom_pattern", None, "not_visible", "下装未入画。"),
        _item("accessories", "蓝紫四瓣吊坠", evidence="吊坠完整可见。"),
        _item("shoes", None, "not_visible", "鞋履未入画。"),
        _item("props", "咖啡杯", evidence="画面下方有咖啡杯。"),
    ]


def _fixture_observation(shot_code: str) -> ShotObservation:
    items = _base()
    if shot_code == "S2":
        items[3] = _item("top_color", "冷灰米色", evidence="外套偏冷灰。")
        items[8] = _item("accessories", None, "not_visible", "侧身角度胸前被衣领遮挡。")
        items[10] = _item("props", "未入画", "not_visible", "画面未包含道具。")
    if shot_code == "S3":
        items[8] = _item("accessories", "红橙五瓣吊坠", evidence="吊坠内部为红橙五瓣。")
    subject = SubjectInfo.model_construct(
        person_count=1, main_subject=True, confidence=0.96, note=None
    )
    return ShotObservation.model_construct(subject=subject, observations=items)


class FixedProvider(MockVisionProvider):
    name = "fixture"
    model_name = "fixture-vision"

    async def parse_profile(self, text: str) -> ProviderResult:
        profile = parse_profile_local(text)
        return ProviderResult(
            value=profile,
            request_id="fixture-profile",
            model=self.model_name,
            usage=UsageInfo(),
        )

    async def observe_shot(self, image, *, shot_code, **kwargs) -> ProviderResult:
        return ProviderResult(
            value=_fixture_observation(shot_code),
            request_id=f"fixture-{shot_code}",
            model=self.model_name,
            usage=UsageInfo(input_images=1),
        )


class FixedFailS2(FixedProvider):
    async def observe_shot(self, image, *, shot_code, **kwargs) -> ProviderResult:
        if shot_code == "S2":
            from app.providers.errors import ProviderError

            raise ProviderError("provider_timeout", "S2 超时", retryable=True)
        return await super().observe_shot(image, shot_code=shot_code, **kwargs)


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


def _create_task(client, csrf):
    task = client.post("/api/tasks", json=task_payload(profileRaw=PROFILE_TEXT), headers=csrf).json()
    files = [
        ("files", (f"shot{i}.png", make_image(base=(200 - i * 15, 185, 165)), "image/png"))
        for i in range(1, 4)
    ]
    response = client.post(f"/api/tasks/{task['id']}/shots", files=files, headers=csrf)
    assert response.status_code == 200
    return task


def _analyze_and_wait(client, csrf, task_id):
    assert client.post(f"/api/tasks/{task_id}/analyze", headers=csrf).status_code == 202
    deadline = time.time() + 8
    while time.time() < deadline:
        status = client.get(f"/api/tasks/{task_id}/analysis").json()
        if status["status"] in {"completed", "partial", "failed", "idle"}:
            return status
        time.sleep(0.02)
    raise AssertionError("分析未结束")


def test_fixed_example_report_matches_acceptance(client, csrf, app, settings):
    task = _create_task(client, csrf)
    app.state.vision_provider_factory = lambda _settings: FixedProvider()

    status = _analyze_and_wait(client, csrf, task["id"])
    assert status["status"] == "completed"

    response = client.get(f"/api/tasks/{task['id']}/report")
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["stats"] == {
        "totalShots": 3,
        "totalUnits": 33,
        "failedShots": 0,
        "consistent": 12,
        "inconsistent": 2,
        "confirmedIssues": 2,
        "unknown": 14,
        "waived": 0,
        "observedOnly": 5,
        "suspectedIssues": 0,
    }
    assert [(i["id"], i["shotCode"], i["attributeId"]) for i in report["issues"]] == [
        ("ISS-001", "S2", "top_color"),
        ("ISS-002", "S3", "accessories"),
    ]
    assert report["issues"][0]["expected"] == "浅米色"
    assert report["issues"][0]["observed"] == "冷灰米色"
    assert report["issues"][1]["observed"] == "红橙五瓣吊坠"
    assert len(report["unknownItems"]) == 14
    assert len(report["matrix"]) == 11
    assert all(len(row["cells"]) == 3 for row in report["matrix"])
    assert [g["conclusionStatus"] for g in report["gallery"]] == ["unknown", "issue", "issue"]
    assert [item["issueId"] for item in report["suggestions"]] == ["ISS-001", "ISS-002"]
    assert all(item["status"] == "ready" for item in report["suggestions"])
    assert all(item["source"] == "local" for item in report["suggestions"])
    assert "浅米色" in report["suggestions"][0]["revisedPrompt"]
    assert "蓝紫四瓣" in report["suggestions"][1]["revisedPrompt"]
    # 修正提示词必须是最小改动，保留问题镜头自身构图，不能整体复刻参考镜头。
    assert report["suggestions"][0]["revisedPrompt"].startswith(
        "保持当前镜头原构图、机位、人物姿态、背景与光线不变"
    )
    assert "仅将上装颜色" in report["suggestions"][0]["revisedPrompt"]
    assert "其余外观" not in report["suggestions"][0]["revisedPrompt"]
    assert any(
        "保持当前镜头原构图" in criterion
        for criterion in report["suggestions"][1]["cardDrawPlan"]["selectionCriteria"]
    )
    assert report["suggestions"][1]["cardDrawPlan"]["batchSize"] == 4
    assert len(report["suggestions"][1]["cardDrawPlan"]["selectionCriteria"]) == 3
    assert "2 处确定不一致" in report["summary"]

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["status"] == "completed"
    assert detail["stats"]["consistent"] == 12
    assert detail["stats"]["issues"] == 2
    assert detail["stats"]["unknownItems"] == 14

    serialized = json.dumps(report, ensure_ascii=False)
    assert str(settings.home_dir) not in serialized
    assert "sk-" not in serialized


def test_partial_report_after_single_shot_failure(client, csrf, app):
    task = _create_task(client, csrf)
    app.state.vision_provider_factory = lambda _settings: FixedFailS2()

    status = _analyze_and_wait(client, csrf, task["id"])
    assert status["status"] == "partial"

    report = client.get(f"/api/tasks/{task['id']}/report").json()
    assert report["stats"]["failedShots"] == 1
    assert report["stats"]["totalUnits"] == 22
    assert all(item["shotCode"] != "S2" for item in report["unknownItems"])
    assert "1 个镜头观察失败" in report["summary"]
    assert report["stats"]["confirmedIssues"] == 1  # 仅 S3 配饰


def test_report_not_available_before_analysis(client, csrf):
    task = client.post("/api/tasks", json=task_payload(), headers=csrf).json()
    response = client.get(f"/api/tasks/{task['id']}/report")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "report_unavailable"
