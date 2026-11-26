"""多个真实/受控任务并存时，报告类 ID 必须全局唯一。

回归背景：issues/unknown/waiver/suspected/suggestion/generation 的 ID 是全局主键，
早期按任务从 001 编号会在第二个任务写入时触发 UNIQUE constraint failed。
"""

from __future__ import annotations

import pytest

from tests.test_generation_loop import _start_generation
from tests.test_report import FixedProvider, _analyze_and_wait, _create_task


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


def test_second_task_does_not_collide_with_first_task_ids(client, csrf, app):
    task1 = _create_task(client, csrf)
    task2 = _create_task(client, csrf)
    app.state.vision_provider_factory = lambda _settings: FixedProvider()

    assert _analyze_and_wait(client, csrf, task1["id"])["status"] == "completed"
    assert _analyze_and_wait(client, csrf, task2["id"])["status"] == "completed"

    report1 = client.get(f"/api/tasks/{task1['id']}/report").json()
    report2 = client.get(f"/api/tasks/{task2['id']}/report").json()
    assert report1["stats"]["confirmedIssues"] == 2
    assert report2["stats"]["confirmedIssues"] == 2

    issue_ids_1 = {item["id"] for item in report1["issues"]}
    issue_ids_2 = {item["id"] for item in report2["issues"]}
    assert issue_ids_1 == {"ISS-001", "ISS-002"}
    assert issue_ids_2.isdisjoint(issue_ids_1)
    assert len(issue_ids_1 | issue_ids_2) == 4

    unknown_ids_1 = {item["id"] for item in report1["unknownItems"]}
    unknown_ids_2 = {item["id"] for item in report2["unknownItems"]}
    assert unknown_ids_1.isdisjoint(unknown_ids_2)

    suggestion_ids_1 = {item["id"] for item in report1["suggestions"]}
    suggestion_ids_2 = {item["id"] for item in report2["suggestions"]}
    assert suggestion_ids_1.isdisjoint(suggestion_ids_2)
    assert len(suggestion_ids_1) == 2 and len(suggestion_ids_2) == 2

    gen1 = _start_generation(client, csrf, task1["id"], "ISS-001")
    gen2 = _start_generation(client, csrf, task2["id"], next(iter(issue_ids_2)))
    assert gen1["generation"]["id"] == "GEN-001"
    assert gen2["generation"]["id"] == "GEN-002"
