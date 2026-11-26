from __future__ import annotations

import asyncio
import time

import pytest

from app.providers.errors import ProviderError
from app.providers.mock import MockVisionProvider
from app.providers.mock_generation import MockGenerationProvider
from tests.helpers import make_image, task_payload
from tests.test_report import FixedProvider, _create_task, _analyze_and_wait


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


def _wait_generation(client, task_id, generation_id, timeout=15.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(
            f"/api/tasks/{task_id}/generations/{generation_id}"
        ).json()
        generation = last["generation"]
        if generation["status"] not in {"pending", "generating", "prechecking"}:
            return last
        time.sleep(0.03)
    raise AssertionError(f"生成未结束：{last}")


def _start_generation(client, csrf, task_id, issue_id, count=4):
    response = client.post(
        f"/api/tasks/{task_id}/issues/{issue_id}/generate",
        json={"candidateCount": count},
        headers=csrf,
    )
    assert response.status_code == 202, response.text
    state = response.json()
    return _wait_generation(client, task_id, state["id"])


def _start_shot_generation(client, csrf, task_id, shot_id, count=4):
    response = client.post(
        f"/api/tasks/{task_id}/shots/{shot_id}/generate",
        json={"candidateCount": count},
        headers=csrf,
    )
    assert response.status_code == 202, response.text
    state = response.json()
    return _wait_generation(client, task_id, state["id"])


def _prepared_task(client, csrf, app):
    task = _create_task(client, csrf)
    app.state.vision_provider_factory = lambda _settings: FixedProvider()
    status = _analyze_and_wait(client, csrf, task["id"])
    assert status["status"] == "completed"
    report = client.get(f"/api/tasks/{task['id']}/report").json()
    return task, report


def test_generation_precheck_adopt_and_single_shot_recheck(client, csrf, app, settings):
    task, report = _prepared_task(client, csrf, app)
    assert len(report["suggestions"]) == 2
    gallery_before = report["gallery"][2]
    issue = next(item for item in report["issues"] if item["id"] == "ISS-002")
    shot_id = issue["shotId"]
    original_before = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=original"
    ).content
    current_before = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=current"
    ).content

    optimizer = client.get(
        f"/api/tasks/{task['id']}/issues/ISS-002/optimizer"
    )
    assert optimizer.status_code == 200, optimizer.text
    body = optimizer.json()
    assert body["suggestion"]["issueId"] == "ISS-002"
    assert body["suggestion"]["cardDrawPlan"]["batchSize"] == 4
    assert body["options"]["generationProvider"] == "mock"
    assert body["shot"]["shotCode"] == "S3"

    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation = state["generation"]
    # 第 1 张参考图必须是问题镜头自身原画面，作为构图基准；
    # 提示词必须先锁定原构图，避免生成图整体复刻 S1。
    assert generation["referenceShotIds"][0] == shot_id
    assert generation["prompt"].startswith("以第 1 张参考图")
    assert "保持构图、机位、人物姿态、背景、光线与镜头语言不变" in generation["prompt"]
    assert generation["status"] == "succeeded"
    assert generation["precheckStatus"] == "completed"
    assert generation["succeededCount"] == 4
    assert generation["failedCount"] == 0
    assert len(generation["candidates"]) == 4
    assert generation["candidates"][0]["candidateCode"] == "C-001"
    assert generation["recommendedCandidateId"] == generation["candidates"][0]["id"]
    assert all(item["state"] == "pass" for item in generation["candidates"])
    assert generation["supportedParams"]["negativePrompt"] is False
    assert generation["supportedParams"]["negativePromptMode"] == "merged"

    candidate = generation["candidates"][0]
    full = client.get(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/candidates/"
        f"{candidate['id']}/image?variant=full"
    )
    thumb = client.get(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/candidates/"
        f"{candidate['id']}/image?variant=thumb"
    )
    assert full.status_code == 200 and thumb.status_code == 200
    assert full.headers["content-type"].startswith("image/")

    # 模拟模型看到修正后的候选图；Mock 返回设定中的显式要素（S3 配饰恢复）
    app.state.vision_provider_factory = lambda _settings: MockVisionProvider()
    adopted = client.post(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/adopt",
        json={"candidateId": candidate["id"]},
        headers=csrf,
    )
    assert adopted.status_code == 200, adopted.text
    adoption = adopted.json()["adoption"]
    assert adoption["recheckStatus"] == "consistent"
    assert adoption["candidateId"] == candidate["id"]

    # 原图字节不变；当前版本指向候选图
    original_after = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=original"
    ).content
    current_after = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=current"
    ).content
    assert original_after == original_before
    assert current_after != current_before
    assert current_after == full.content
    # 画廊/历史使用的 thumb 也切换到当前采用版本
    thumb_after = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=thumb"
    )
    assert thumb_after.status_code == 200
    assert thumb_after.content == thumb.content

    report_after = client.get(f"/api/tasks/{task['id']}/report").json()
    assert report_after["stats"]["confirmedIssues"] == 1
    assert [item["id"] for item in report_after["issues"]] == ["ISS-001"]
    # 配饰问题已关闭；下装/鞋履仍不可见，镜头结论保持 unknown，不伪装为一致
    assert report_after["gallery"][2]["issueCount"] == 0
    assert report_after["gallery"][2]["conclusionStatus"] == "unknown"
    assert report_after["gallery"][2]["isAdopted"] is True
    assert report_after["gallery"][2]["adoptedCandidateCode"] == "C-001"
    assert "C-001" in report_after["gallery"][2]["versionLabel"]
    # 采用后 thumb/current 地址必须随版本变化，否则浏览器会继续用旧图缓存。
    adopted_version = report_after["gallery"][2]["currentVersionId"]
    assert report_after["gallery"][2]["currentUrl"] != gallery_before["currentUrl"]
    assert report_after["gallery"][2]["thumbUrl"] != gallery_before["thumbUrl"]
    assert report_after["gallery"][2]["currentUrl"].endswith(f"&v={adopted_version}")
    assert report_after["gallery"][2]["thumbUrl"].endswith(f"&v={adopted_version}")
    assert client.get(report_after["gallery"][2]["currentUrl"]).content == full.content
    assert client.get(report_after["gallery"][2]["thumbUrl"]).content == thumb.content
    assert len(report_after["generationRecords"]) == 1
    assert len(report_after["adoptions"]) == 1
    assert report_after["adoptions"][0]["candidateCode"] == "C-001"
    # 仅 S3 被复检；S2 问题仍在
    assert any(item["shotCode"] == "S2" for item in report_after["issues"])


def test_shot_optimizer_groups_all_shot_issues(client, csrf, app):
    task, report = _prepared_task(client, csrf, app)
    shot = report["gallery"][2]
    shot_issues = [item for item in report["issues"] if item["shotId"] == shot["shotId"]]
    assert shot_issues

    state = client.get(
        f"/api/tasks/{task['id']}/shots/{shot['shotId']}/optimizer"
    )
    assert state.status_code == 200, state.text
    body = state.json()
    assert body["issue"]["shotId"] == shot["shotId"]
    assert {item["id"] for item in body["issuesForShot"]} == {
        item["id"] for item in shot_issues
    }
    assert set(body["suggestion"]["issueIds"]) == {
        item["id"] for item in shot_issues
    }

    generation = _start_shot_generation(
        client, csrf, task["id"], shot["shotId"]
    )["generation"]
    assert set(generation["issueIds"]) == {item["id"] for item in shot_issues}


def test_shot_optimizer_merges_multiple_issues_on_same_shot(client, csrf, app):
    profile = (
        "阿岚，深棕长发低侧发髻，浅米色条纹亚麻西装外套，黑色丝质衬衫，"
        "圆形吊坠项链（蓝紫四瓣花）。"
    )
    task = client.post(
        "/api/tasks", json=task_payload(profileRaw=profile), headers=csrf
    ).json()
    files = [
        ("files", (f"shot{i}.png", make_image(base=(200 - i * 15, 185, 165)), "image/png"))
        for i in range(1, 4)
    ]
    assert (
        client.post(
            f"/api/tasks/{task['id']}/shots", files=files, headers=csrf
        ).status_code
        == 200
    )
    app.state.vision_provider_factory = lambda _settings: FixedProvider()
    assert _analyze_and_wait(client, csrf, task["id"])["status"] == "completed"
    report = client.get(f"/api/tasks/{task['id']}/report").json()
    shot = report["gallery"][1]
    shot_issue_ids = {
        item["id"] for item in report["issues"] if item["shotId"] == shot["shotId"]
    }
    assert len(shot_issue_ids) >= 2

    state = client.get(
        f"/api/tasks/{task['id']}/shots/{shot['shotId']}/optimizer"
    ).json()
    assert set(state["suggestion"]["issueIds"]) == shot_issue_ids
    assert {item["id"] for item in state["issuesForShot"]} == shot_issue_ids
    assert len(state["suggestion"]["cardDrawPlan"]["selectionCriteria"]) >= 2

    generation = _start_shot_generation(
        client, csrf, task["id"], shot["shotId"]
    )["generation"]
    assert set(generation["issueIds"]) == shot_issue_ids


def test_partial_generation_keeps_successful_candidates(client, csrf, app):
    task, _report = _prepared_task(client, csrf, app)

    class FlakyGeneration(MockGenerationProvider):
        def __init__(self):
            self.calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            if self.calls <= 2:
                raise ProviderError("provider_unavailable", "模拟单候选失败", retryable=True)
            return await super().generate(**kwargs)

    provider = FlakyGeneration()
    app.state.generation_provider_factory = lambda _settings: provider
    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation = state["generation"]
    assert generation["status"] == "partial"
    assert generation["succeededCount"] == 2
    assert generation["failedCount"] == 2
    assert len(generation["candidates"]) == 2
    assert generation["precheckStatus"] in {"completed", "failed"}


def test_precheck_batch_mapping_failure_degrades_per_candidate(client, csrf, app):
    task = _create_task(client, csrf)

    class FallbackPrecheck(FixedProvider):
        def __init__(self):
            self.batch_calls = 0
            self.single_calls = 0
            self.references_seen = []

        async def precheck_candidates(
            self, *, criteria, candidates, issue=None, references=None
        ):
            self.references_seen.append([item[0] for item in (references or [])])
            if len(candidates) > 1:
                self.batch_calls += 1
                raise ProviderError("invalid_response", "批量映射不稳定")
            self.single_calls += 1
            return await super().precheck_candidates(
                criteria=criteria,
                candidates=candidates,
                issue=issue,
                references=references,
            )

    provider = FallbackPrecheck()
    app.state.vision_provider_factory = lambda _settings: provider
    assert _analyze_and_wait(client, csrf, task["id"])["status"] == "completed"

    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation = state["generation"]
    assert generation["status"] == "succeeded"
    assert generation["precheckMode"] == "per_candidate"
    assert provider.batch_calls == 1
    assert provider.single_calls == 4
    # 预检请求携带参考镜头图，模型才能核对「与参考镜头 S1 一致」类标准
    assert ["S1"] in provider.references_seen
    assert len(generation["candidates"]) == 4


def test_recheck_failure_keeps_issue_open_and_can_retry(client, csrf, app):
    task, report = _prepared_task(client, csrf, app)
    issue = next(item for item in report["issues"] if item["id"] == "ISS-002")
    shot_id = issue["shotId"]
    original = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=original"
    ).content

    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation = state["generation"]
    candidate = generation["candidates"][0]

    class FailingObserve(FixedProvider):
        async def observe_shot(self, image, **kwargs):
            raise ProviderError("provider_timeout", "复检超时", retryable=True)

    app.state.vision_provider_factory = lambda _settings: FailingObserve()
    adopted = client.post(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/adopt",
        json={"candidateId": candidate["id"]},
        headers=csrf,
    )
    assert adopted.status_code == 200, adopted.text
    adoption = adopted.json()["adoption"]
    assert adoption["recheckStatus"] == "failed"
    assert adoption["recheckResult"]["errorCode"] == "provider_timeout"

    # 复检失败：当前版本回滚，问题保持开启，报告不伪造关闭
    report_after = client.get(f"/api/tasks/{task['id']}/report").json()
    assert report_after["stats"]["confirmedIssues"] == 2
    current = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=current"
    ).content
    assert current == original

    # 切回能正确观察修正图的 Provider 后重试复检成功
    app.state.vision_provider_factory = lambda _settings: MockVisionProvider()
    retry = client.post(
        f"/api/tasks/{task['id']}/shots/{shot_id}/recheck", headers=csrf
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["adoption"]["recheckStatus"] == "consistent"
    report_final = client.get(f"/api/tasks/{task['id']}/report").json()
    assert report_final["stats"]["confirmedIssues"] == 1


def test_recheck_inconsistent_keeps_issue_open_and_candidate_current(client, csrf, app):
    task, report = _prepared_task(client, csrf, app)
    issue = next(item for item in report["issues"] if item["id"] == "ISS-002")
    shot_id = issue["shotId"]
    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation = state["generation"]
    candidate = generation["candidates"][0]

    # FixedProvider 仍返回红橙五瓣：复检结果应为「仍不一致」，不得关闭问题
    adopted = client.post(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/adopt",
        json={"candidateId": candidate["id"]},
        headers=csrf,
    )
    assert adopted.status_code == 200, adopted.text
    adoption = adopted.json()["adoption"]
    assert adoption["recheckStatus"] == "inconsistent"
    report_after = client.get(f"/api/tasks/{task['id']}/report").json()
    assert len(report_after["issues"]) == 2
    assert any(item["id"] == "ISS-002" for item in report_after["issues"])
    # 复检完成（即使不一致）不触发回滚，候选图仍是当前版本
    current = client.get(
        f"/api/tasks/{task['id']}/shots/{shot_id}/image?variant=current"
    ).content
    full = client.get(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/candidates/"
        f"{candidate['id']}/image?variant=full"
    ).content
    assert current == full


def test_redraw_after_adoption_clears_only_current_shot_state(client, csrf, app):
    task, report = _prepared_task(client, csrf, app)
    app.state.vision_provider_factory = lambda _settings: MockVisionProvider()

    # 先采用 S3
    state = _start_generation(client, csrf, task["id"], "ISS-002")
    client.post(
        f"/api/tasks/{task['id']}/generations/{state['generation']['id']}/adopt",
        json={"candidateId": state["generation"]["candidates"][0]["id"]},
        headers=csrf,
    )
    # 再采用 S2
    state2 = _start_generation(client, csrf, task["id"], "ISS-001")
    client.post(
        f"/api/tasks/{task['id']}/generations/{state2['generation']['id']}/adopt",
        json={"candidateId": state2["generation"]["candidates"][0]["id"]},
        headers=csrf,
    )
    optimizer = client.get(
        f"/api/tasks/{task['id']}/issues/ISS-002/optimizer"
    ).json()
    assert set(optimizer["shotAdoptions"]) == {"S2", "S3"}

    # 对已采用的 S3 重抽：允许启动，且只清空 S3 的采用显示
    redraw = client.post(
        f"/api/tasks/{task['id']}/issues/ISS-002/generate",
        json={"candidateCount": 2},
        headers=csrf,
    )
    assert redraw.status_code == 202, redraw.text
    redraw_id = redraw.json()["id"]
    _wait_generation(client, task["id"], redraw_id)
    optimizer_after = client.get(
        f"/api/tasks/{task['id']}/issues/ISS-002/optimizer"
    ).json()
    assert "S2" in optimizer_after["shotAdoptions"]
    assert "S3" not in optimizer_after["shotAdoptions"]
    assert optimizer_after["adoption"] is None
    assert optimizer_after["generation"]["id"] == redraw_id


def test_generation_cancel_marks_failed_and_keeps_terminal_state(client, csrf, app):
    task, _report = _prepared_task(client, csrf, app)
    app.state.vision_provider_factory = lambda _settings: FixedProvider()

    class SlowGeneration(MockGenerationProvider):
        async def generate(self, **kwargs):
            await asyncio.sleep(5)
            return await super().generate(**kwargs)

    app.state.generation_provider_factory = lambda _settings: SlowGeneration()
    response = client.post(
        f"/api/tasks/{task['id']}/issues/ISS-002/generate",
        json={"candidateCount": 4},
        headers=csrf,
    )
    assert response.status_code == 202
    generation_id = response.json()["id"]
    time.sleep(0.2)
    cancelled = client.post(
        f"/api/tasks/{task['id']}/generations/{generation_id}/cancel",
        headers=csrf,
    )
    assert cancelled.status_code == 200
    generation = cancelled.json()["generation"]
    assert generation["status"] == "failed"
    assert generation["errorCode"] == "canceled_by_user"


def test_suggestion_model_failure_falls_back_to_local(client, csrf, app):
    task = _create_task(client, csrf)

    class NoSuggestion(FixedProvider):
        async def generate_suggestion(self, **kwargs):
            raise ProviderError("auth_failed", "模型不可用")

    app.state.vision_provider_factory = lambda _settings: NoSuggestion()
    status = _analyze_and_wait(client, csrf, task["id"])
    assert status["status"] == "completed"
    report = client.get(f"/api/tasks/{task['id']}/report").json()
    assert len(report["suggestions"]) == 2
    assert all(item["source"] == "local" for item in report["suggestions"])
    assert all(item["status"] == "ready" for item in report["suggestions"])


def test_precheck_failure_still_allows_manual_adoption_and_records_override(client, csrf, app):
    task = _create_task(client, csrf)

    class NoPrecheck(FixedProvider):
        async def precheck_candidates(
            self, *, criteria, candidates, issue=None, references=None
        ):
            raise ProviderError("provider_timeout", "预检超时", retryable=True)

    app.state.vision_provider_factory = lambda _settings: NoPrecheck()
    assert _analyze_and_wait(client, csrf, task["id"])["status"] == "completed"
    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation = state["generation"]
    assert generation["status"] == "succeeded"
    assert generation["precheckStatus"] == "failed"
    assert generation["precheckMode"] == "per_candidate"
    assert all(item["state"] == "unknown" for item in generation["candidates"])

    candidate = generation["candidates"][0]
    app.state.vision_provider_factory = lambda _settings: MockVisionProvider()
    adopted = client.post(
        f"/api/tasks/{task['id']}/generations/{generation['id']}/adopt",
        json={"candidateId": candidate["id"]},
        headers=csrf,
    )
    assert adopted.status_code == 200, adopted.text
    adoption = adopted.json()["adoption"]
    assert adoption["precheckOverall"] == "unknown"
    assert adoption["overriddenPrecheck"] is True
    assert adoption["recheckStatus"] in {"consistent", "unknown", "inconsistent"}
