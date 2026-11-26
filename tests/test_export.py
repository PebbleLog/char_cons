from __future__ import annotations

import json

import pytest

from app.providers.mock import MockVisionProvider
from tests.test_generation_loop import _start_generation
from tests.test_report import FixedProvider, _analyze_and_wait, _create_task


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


def _prepared(client, csrf, app):
    task = _create_task(client, csrf)
    app.state.vision_provider_factory = lambda _settings: FixedProvider()
    assert _analyze_and_wait(client, csrf, task["id"])["status"] == "completed"
    return task


def test_json_export_matches_report_and_contains_traceability(client, csrf, app, settings):
    task = _prepared(client, csrf, app)
    report = client.get(f"/api/tasks/{task['id']}/report").json()
    response = client.get(f"/api/tasks/{task['id']}/export?format=json")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    data = json.loads(response.content.decode("utf-8"))

    assert data["stats"] == report["stats"]
    assert [item["id"] for item in data["issues"]] == ["ISS-001", "ISS-002"]
    assert len(data["unknownItems"]) == 14
    assert len(data["suggestions"]) == 2
    assert len(data["shots"]) == 3
    assert all(len(shot["observations"]) == 11 for shot in data["shots"])
    assert all(len(shot["judgements"]) == 11 for shot in data["shots"])
    assert len(data["judgements"]) == 33
    assert data["schemaVersion"] == report["schemaVersion"]
    assert data["exportedAt"]

    serialized = json.dumps(data, ensure_ascii=False)
    assert str(settings.home_dir) not in serialized
    assert "sk-" not in serialized
    assert '"imageUrl"' not in serialized
    assert '"thumbUrl"' not in serialized
    assert "generationRecords" in data and data["generationRecords"] == []
    assert "adoptions" in data and data["adoptions"] == []


def test_markdown_export_contains_sections_and_no_paths(client, csrf, app, settings):
    task = _prepared(client, csrf, app)
    response = client.get(f"/api/tasks/{task['id']}/export?format=md")
    assert response.status_code == 200, response.text
    text = response.content.decode("utf-8")
    for heading in (
        "# 角色形象一致性检查报告",
        "## 结论摘要",
        "## 统计",
        "## 镜头总览",
        "## 确定问题",
        "## 无法判断",
        "## 修正建议与抽卡",
        "## 生成记录",
        "## 采用记录",
    ):
        assert heading in text
    assert "ISS-001" in text
    assert "ISS-002" in text
    assert "蓝紫四瓣" in text
    assert "本地规则建议" in text
    assert str(settings.home_dir) not in text
    assert "sk-" not in text
    assert "不包含 API Key、绝对路径或远程图片地址" in text


def test_export_includes_generation_precheck_and_adoption(client, csrf, app):
    task = _prepared(client, csrf, app)
    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation = state["generation"]
    candidate = generation["candidates"][0]
    app.state.vision_provider_factory = lambda _settings: MockVisionProvider()
    adopted = client.post(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/adopt",
        json={"candidateId": candidate["id"]},
        headers=csrf,
    )
    assert adopted.status_code == 200, adopted.text

    data = client.get(f"/api/tasks/{task['id']}/export?format=json").json()
    assert len(data["generationRecords"]) == 1
    record = data["generationRecords"][0]
    assert record["precheckMode"] == "batch"
    assert len(record["candidates"]) == 4
    assert record["candidates"][0]["precheck"]["overall"] == "pass"
    assert '"imageUrl"' not in json.dumps(record, ensure_ascii=False)
    assert len(data["adoptions"]) == 1
    assert data["adoptions"][0]["recheckStatus"] == "consistent"

    text = client.get(f"/api/tasks/{task['id']}/export?format=md").content.decode("utf-8")
    assert "GEN-001" in text
    assert "C-001" in text
    assert "复检 一致（问题关闭）" in text


def test_export_before_report_returns_409(client, csrf):
    task = client.post(
        "/api/tasks",
        json={
            "name": "无报告任务",
            "profileRaw": "阿岚，浅米色外套。",
            "scriptRaw": "无换装。",
        },
        headers=csrf,
    ).json()
    response = client.get(f"/api/tasks/{task['id']}/export?format=md")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "report_unavailable"


def test_export_rejects_unknown_format(client, csrf):
    # 格式由 Literal 校验，未知值返回 422
    response = client.get("/api/tasks/not-a-task/export?format=pdf")
    assert response.status_code == 422
