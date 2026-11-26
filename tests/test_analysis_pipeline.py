from __future__ import annotations

import asyncio
import sqlite3
import threading
import time

import pytest

from app.providers.errors import ProviderError
from app.providers.mock import MockVisionProvider
from tests.helpers import make_image, task_payload
from tests.test_report import FixedProvider


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


def _create_with_shots(client, csrf, count=3):
    task = client.post("/api/tasks", json=task_payload(), headers=csrf).json()
    files = [
        ("files", (f"shot{i}.png", make_image(base=(200 - i * 20, 190, 170 - i * 10)), "image/png"))
        for i in range(1, count + 1)
    ]
    response = client.post(f"/api/tasks/{task['id']}/shots", files=files, headers=csrf)
    assert response.status_code == 200, response.text
    return task, response.json()["shots"]


def _wait_terminal(client, task_id, timeout=8.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/tasks/{task_id}/analysis").json()
        if last["status"] in {"completed", "partial", "paused", "failed", "idle"}:
            return last
        time.sleep(0.02)
    raise AssertionError(f"分析未在超时内结束，最后状态：{last}")


class SelectiveFailProvider(MockVisionProvider):
    async def observe_shot(self, image, *, shot_code, **kwargs):
        if shot_code == "S2":
            raise ProviderError("provider_timeout", "S2 观察超时", retryable=True)
        return await super().observe_shot(image, shot_code=shot_code, **kwargs)


class AllFailProvider(MockVisionProvider):
    async def observe_shot(self, image, *, shot_code, **kwargs):
        raise ProviderError("auth_failed", "鉴权失败")


class SlowProvider(MockVisionProvider):
    async def observe_shot(self, image, *, shot_code, **kwargs):
        await asyncio.sleep(5)
        return await super().observe_shot(image, shot_code=shot_code, **kwargs)


class BlockingSuggestionProvider(FixedProvider):
    """判定写入后挂起建议生成，用于确认问题不必等建议阶段结束才可见。"""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    async def generate_suggestion(self, **kwargs):
        self.entered.set()
        await asyncio.to_thread(self.release.wait, 8)
        return await super().generate_suggestion(**kwargs)


class UnconfiguredProvider(MockVisionProvider):
    def ensure_configured(self) -> None:
        raise ProviderError("auth_failed", "分析服务未配置 API Key。")


def test_analysis_completes_with_structured_data(client, csrf, app, settings):
    task, shots = _create_with_shots(client, csrf, 3)

    started = client.post(f"/api/tasks/{task['id']}/analyze", headers=csrf)
    assert started.status_code == 202, started.text
    assert started.json()["status"] in {"running", "completed"}

    status = _wait_terminal(client, task["id"])
    assert status["status"] == "completed"
    assert status["progress"] == 100
    assert status["stage"]["completed"] is True
    assert [shot["analysisStatus"] for shot in status["shots"]] == ["ok", "ok", "ok"]
    assert all(shot["evidenceReady"] for shot in status["shots"])
    assert all(shot["judged"] for shot in status["shots"])
    assert all(len(shot["verdicts"]) == 11 for shot in status["shots"])

    detail = client.get(f"/api/tasks/{task['id']}").json()
    profile = detail["profile"]
    assert profile is not None
    values = {item["id"]: item for item in profile["attributes"]}
    assert len(values) == 11
    assert values["hair_color"]["value"] == "深棕"
    assert values["top_color"]["value"] == "浅米色"
    assert values["bottom_style"]["source"] == "undefined"
    assert detail["scriptContext"]["ruleBadge"] == "严格比对 · 无豁免"

    observations = client.get(
        f"/api/tasks/{task['id']}/shots/{shots[0]['id']}/observations"
    )
    assert observations.status_code == 200
    body = observations.json()
    assert len(body["observations"]) == 11
    assert body["subject"]["confidence"] == 0.96
    visible = [item for item in body["observations"] if item["visibility"] == "visible"]
    hidden = [item for item in body["observations"] if item["visibility"] == "not_visible"]
    assert visible and hidden
    assert all(item["evidence"] for item in visible)
    assert all(item["visibilityReason"] for item in hidden)

    with sqlite3.connect(settings.db_path) as conn:
        usage = dict(
            conn.execute(
                "SELECT kind, COUNT(*) FROM usage_records WHERE task_id = ? GROUP BY kind",
                (task["id"],),
            ).fetchall()
        )
        providers = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT provider FROM usage_records WHERE task_id = ?",
                (task["id"],),
            )
        }
        observations_count = conn.execute(
            "SELECT COUNT(*) FROM observations WHERE task_id = ?", (task["id"],)
        ).fetchone()[0]
    assert usage == {"profile": 1, "observe": 3}
    assert providers == {"mock"}
    assert observations_count == 33


def test_judgement_is_visible_before_suggestions_finish(client, csrf, app):
    task, _shots = _create_with_shots(client, csrf, 3)
    provider = BlockingSuggestionProvider()
    app.state.vision_provider_factory = lambda _settings: provider

    response = client.post(f"/api/tasks/{task['id']}/analyze", headers=csrf)
    assert response.status_code == 202
    try:
        assert provider.entered.wait(8), "未进入建议生成阶段"
        status = client.get(f"/api/tasks/{task['id']}/analysis").json()
        assert status["status"] == "running"
        assert status["stage"]["index"] == 6
        assert all(shot["judged"] for shot in status["shots"])
        assert all(len(shot["verdicts"]) == 11 for shot in status["shots"])
        assert sum(shot["inconsistent"] for shot in status["shots"]) == 2
        assert sum(shot["unknown"] for shot in status["shots"]) > 0
        # 判定完成后进度不再回退，生成建议阶段有真实建议子进度。
        assert 95 <= status["progress"] < 100
        assert status["suggestions"] == {"ready": 0, "total": 2}
        assert [item["name"] for item in status["stages"]] == [
            "素材校验",
            "设定解析",
            "剧本解析",
            "逐镜头观察",
            "一致性判定",
            "生成建议",
        ]
    finally:
        provider.release.set()
    final = _wait_terminal(client, task["id"])
    assert final["status"] == "completed"
    assert final["progress"] == 100
    assert final["suggestions"] == {"ready": 2, "total": 2}


def test_single_shot_failure_is_isolated(client, csrf, app, settings):
    task, shots = _create_with_shots(client, csrf, 3)
    app.state.vision_provider_factory = lambda _settings: SelectiveFailProvider()

    response = client.post(f"/api/tasks/{task['id']}/analyze", headers=csrf)
    assert response.status_code == 202

    status = _wait_terminal(client, task["id"])
    assert status["status"] == "partial"
    assert status["progress"] == 100
    assert [shot["analysisStatus"] for shot in status["shots"]] == ["ok", "failed", "ok"]
    assert status["shots"][1]["errorCode"] == "provider_timeout"

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["status"] == "partial"
    assert "1 个镜头观察失败" in detail["errorMessage"]

    with sqlite3.connect(settings.db_path) as conn:
        counts = dict(
            conn.execute(
                "SELECT shot_id, COUNT(*) FROM observations WHERE task_id = ? GROUP BY shot_id",
                (task["id"],),
            ).fetchall()
        )
    assert counts[shots[0]["id"]] == 11
    assert counts[shots[2]["id"]] == 11
    assert shots[1]["id"] not in counts


def test_all_shots_failure_marks_task_failed(client, csrf, app):
    task, _shots = _create_with_shots(client, csrf, 3)
    app.state.vision_provider_factory = lambda _settings: AllFailProvider()

    response = client.post(f"/api/tasks/{task['id']}/analyze", headers=csrf)
    assert response.status_code == 202

    status = _wait_terminal(client, task["id"])
    assert status["status"] == "failed"
    assert status["error"]["code"] == "auth_failed"
    assert all(shot["analysisStatus"] == "failed" for shot in status["shots"])
    # 全失败不应假装走完判定/建议并显示 100%。
    assert status["stage"]["index"] == 4
    assert status["progress"] == 90


def test_analysis_requires_configuration(client, csrf, app):
    task, _shots = _create_with_shots(client, csrf, 1)
    app.state.vision_provider_factory = lambda _settings: UnconfiguredProvider()

    response = client.post(f"/api/tasks/{task['id']}/analyze", headers=csrf)
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "auth_failed"
    assert body["action"] == "settings"

    # 任务保持草稿，不应被标记为运行中
    assert client.get(f"/api/tasks/{task['id']}").json()["status"] == "idle"


def test_analysis_without_shots_rejected(client, csrf):
    task = client.post("/api/tasks", json=task_payload(), headers=csrf).json()
    response = client.post(f"/api/tasks/{task['id']}/analyze", headers=csrf)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_cancel_analysis_returns_to_idle(client, csrf, app):
    task, _shots = _create_with_shots(client, csrf, 2)
    app.state.vision_provider_factory = lambda _settings: SlowProvider()

    response = client.post(f"/api/tasks/{task['id']}/analyze", headers=csrf)
    assert response.status_code == 202

    cancelled = client.post(f"/api/tasks/{task['id']}/cancel", headers=csrf)
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "idle"
    assert body["progress"] == 0
    assert all(shot["analysisStatus"] == "pending" for shot in body["shots"])

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["profile"] is None
    assert detail["scriptContext"] is None
