"""提示词修正建议与抽卡方案（F-08 / F-09）。

- 优先调用视觉/语言模型生成；失败或使用 Mock 时回退确定性本地模板，
  并在 suggestions.source 中如实标注 ai / local，不冒充模型结果；
- 单条失败隔离，不影响报告其他部分；
- 参考镜头只选本任务中无确定问题且观察成功的镜头，最多 2 张。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from ..core.config import Settings
from ..core.errors import AppError
from ..core.timeutil import now_iso
from ..providers.base import VisionProvider
from ..providers.errors import ProviderError, is_fatal
from ..providers.prompt_loader import prompt_version
from ..providers.schemas import (
    CharacterProfile,
    ScriptContext,
    SuggestionOutput,
)
from ..providers.suggestion_templates import build_local_suggestion
from ..repositories import (
    event_repo,
    judgement_repo,
    shot_repo,
    suggestion_repo,
    task_repo,
    usage_repo,
)
from ..repositories.database import Database

logger = logging.getLogger(__name__)


def _load_json(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def _task_or_404(db: Database, task_id: str) -> aiosqlite.Row:
    task = await task_repo.get_task(db, task_id)
    if task is None:
        raise AppError("not_found", "任务不存在或已被删除。", status_code=404)
    return task


async def _issue_or_404(
    db: Database, task_id: str, issue_id: str
) -> aiosqlite.Row:
    row = await db.fetchone(
        "SELECT * FROM issues WHERE task_id = ? AND id = ?", (task_id, issue_id)
    )
    if row is None:
        raise AppError("not_found", "问题不存在或已关闭。", status_code=404)
    return row


def issue_context(
    issue: aiosqlite.Row, shot_code: str
) -> dict[str, Any]:
    return {
        "id": issue["id"],
        "shotId": issue["shot_id"],
        "shotCode": shot_code,
        "attributeId": issue["attribute_id"],
        "attributeName": issue["attribute_name"],
        "type": issue["type"],
        "expected": issue["expected"],
        "observed": issue["observed"],
        "evidence": issue["evidence"],
        "confidence": issue["confidence"],
        "severity": issue["severity"],
        "status": issue["status"],
    }


async def choose_references(
    db: Database, task_id: str, target_shot_id: str, limit: int = 2
) -> list[dict[str, Any]]:
    shots = await shot_repo.get_shots(db, task_id)
    open_issue_shots = {
        row["shot_id"]
        for row in await judgement_repo.list_issues(db, task_id)
        if row["status"] == "open"
    }
    candidates = [
        shot
        for shot in shots
        if shot["id"] != target_shot_id
        and shot["analysis_status"] == "ok"
        and shot["id"] not in open_issue_shots
    ]
    return [
        {
            "shotId": shot["id"],
            "shotCode": shot["shot_code"],
            "reason": "同角色无确定问题镜头",
        }
        for shot in candidates[:limit]
    ]


def _source_for(provider: VisionProvider, result_model: str) -> str:
    if getattr(provider, "name", "") == "mock" or result_model.startswith("local"):
        return "local"
    return "ai"


async def ensure_suggestion(
    db: Database,
    settings: Settings,
    task_id: str,
    issue_id: str,
    provider: VisionProvider,
    *,
    force: bool = False,
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    issue = await _issue_or_404(db, task_id, issue_id)
    shot = await shot_repo.get_shot(db, task_id, issue["shot_id"])
    if shot is None:
        raise AppError("not_found", "问题关联的镜头不存在。", status_code=404)

    if not force:
        existing = await suggestion_repo.get_for_issue(db, task_id, issue_id)
        if existing is not None and existing["status"] == "ready":
            return serialize_suggestion(existing, shot["shot_code"])

    if not task["profile_json"] or not task["script_context_json"]:
        raise AppError(
            "report_unavailable", "任务尚未完成设定与剧本解析。", status_code=409
        )
    profile = CharacterProfile.model_validate_json(task["profile_json"])
    script = ScriptContext.model_validate_json(task["script_context_json"])
    context = issue_context(issue, shot["shot_code"])
    references = await choose_references(db, task_id, issue["shot_id"])
    batch_size = int(task["default_batch_size"] or settings.default_batch_size)

    source = "local"
    suggestion: SuggestionOutput | None = None
    error_message: str | None = None
    try:
        result = await provider.generate_suggestion(
            issue=context,
            profile=profile,
            script=script,
            references=references,
            batch_size=batch_size,
        )
        suggestion = result.value
        source = _source_for(provider, result.model)
        if source == "ai":
            await usage_repo.record_usage(
                db,
                task_id=task_id,
                kind="suggestion",
                provider=getattr(provider, "name", None),
                model=result.model,
                request_id=result.request_id,
                input_images=result.usage.input_images,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            )
    except ProviderError as exc:
        error_message = exc.message
        await event_repo.insert_event(
            db,
            "suggestion.fallback_local",
            {
                "issueId": issue_id,
                "code": exc.code,
                "fatal": is_fatal(exc.code),
            },
            task_id=task_id,
            request_id=exc.request_id,
        )
        if exc.code != "mock_no_ai":
            logger.warning("建议生成失败，使用本地模板：%s", exc.code)
    except Exception as exc:  # 模型返回结构异常等不应中断分析
        error_message = "模型建议结构异常，已使用本地模板。"
        logger.exception("建议生成未预期异常：%s", type(exc).__name__)
        await event_repo.insert_event(
            db,
            "suggestion.fallback_local",
            {"issueId": issue_id, "code": "invalid_response"},
            task_id=task_id,
        )

    if suggestion is None:
        try:
            payload = build_local_suggestion(
                issue=context,
                profile=profile,
                script=script,
                references=references,
                batch_size=batch_size,
            )
            suggestion = SuggestionOutput.model_validate(payload)
            source = "local"
        except Exception as exc:
            logger.exception("本地建议模板失败：%s", type(exc).__name__)
            async with db.transaction() as conn:
                suggestion_id = await suggestion_repo.upsert(
                    conn,
                    task_id=task_id,
                    issue_id=issue_id,
                    shot_id=issue["shot_id"],
                    revised_prompt="",
                    negative_prompt=None,
                    key_points=[],
                    reference_shots=[],
                    rationale="",
                    card_draw_plan={},
                    status="failed",
                    prompt_version=prompt_version(),
                    error_message=error_message or "建议生成失败，请重试。",
                    source="local",
                )
            raise AppError(
                "suggestion_failed", "修正建议生成失败，可单独重试。", status_code=502
            ) from exc

    async with db.transaction() as conn:
        suggestion_id = await suggestion_repo.upsert(
            conn,
            task_id=task_id,
            issue_id=issue_id,
            shot_id=issue["shot_id"],
            revised_prompt=suggestion.revised_prompt,
            negative_prompt=suggestion.negative_prompt or None,
            key_points=suggestion.key_points,
            reference_shots=suggestion.reference_shots,
            rationale=suggestion.rationale,
            card_draw_plan=suggestion.card_draw_plan.model_dump(by_alias=True),
            status="ready",
            prompt_version=prompt_version(),
            error_message=error_message,
            source=source,
        )
    row = await suggestion_repo.get_for_issue(db, task_id, issue_id)
    assert row is not None
    await event_repo.insert_event(
        db,
        "suggestion.ready",
        {"issueId": issue_id, "suggestionId": suggestion_id, "source": source},
        task_id=task_id,
    )
    return serialize_suggestion(row, shot["shot_code"])


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = (value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


async def ensure_shot_suggestion(
    db: Database,
    settings: Settings,
    task_id: str,
    shot_id: str,
    provider: VisionProvider,
) -> dict[str, Any]:
    """把一个镜头的所有开放问题合并成一份修正建议。

    逐问题建议仍保留在问题卡中；优化页和生成批次使用这份镜头级合并建议，
    保证一次生成覆盖该镜头的全部问题。
    """
    task = await _task_or_404(db, task_id)
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)
    issues = [
        row
        for row in await judgement_repo.list_issues(db, task_id)
        if row["shot_id"] == shot_id
    ]
    if not issues:
        raise AppError("conflict", "该镜头没有待优化问题。", status_code=409)

    contexts = [issue_context(row, shot["shot_code"]) for row in issues]
    ready: list[dict[str, Any]] = []
    errors: list[str] = []
    for issue in issues:
        try:
            ready.append(
                await ensure_suggestion(
                    db, settings, task_id, issue["id"], provider
                )
            )
        except (AppError, ProviderError) as exc:
            errors.append(f"{issue['attribute_name']}：{exc.message}")
        except Exception:
            errors.append(f"{issue['attribute_name']}：建议生成异常")

    if not ready:
        raise AppError(
            "suggestion_failed",
            "本镜头所有问题的修正建议均生成失败，请稍后重试。",
            status_code=502,
        )

    base_prompt = ready[0].get("revisedPrompt") or ""
    if len(contexts) > 1:
        lines = [
            f"- {item['attributeName']}：{item.get('expected') or '与参考镜头一致'}"
            for item in contexts
        ]
        base_prompt = (
            f"{base_prompt.rstrip()}\n\n本镜头同时修正：\n" + "\n".join(lines)
        ).strip()

    negative = "，".join(
        _unique([item.get("negativePrompt") or "" for item in ready])
    )
    key_points = _unique(
        [point for item in ready for point in (item.get("keyPoints") or [])]
    )
    reference_shots = _unique(
        [code for item in ready for code in (item.get("referenceShots") or [])]
    )
    criteria = _unique(
        [
            criterion
            for item in ready
            for criterion in ((item.get("cardDrawPlan") or {}).get("selectionCriteria") or [])
        ]
        + [f"{item['attributeName']}与设定一致" for item in contexts]
    )[:6]
    batch_size = int(task["default_batch_size"] or settings.default_batch_size)
    source = "ai" if any(item.get("source") == "ai" for item in ready) else "local"
    rationale = "本镜头合并修正：" + "；".join(
        f"{item['attributeName']} → {item.get('expected') or '与参考镜头一致'}"
        for item in contexts
    )

    return {
        "id": f"shot-{shot_id}",
        "taskId": task_id,
        "issueId": issues[0]["id"],
        "issueIds": [issue["id"] for issue in issues],
        "shotId": shot_id,
        "shotCode": shot["shot_code"],
        "revisedPrompt": base_prompt,
        "negativePrompt": negative or None,
        "negativePromptMode": "merged",
        "keyPoints": key_points,
        "referenceShots": reference_shots,
        "rationale": rationale,
        "cardDrawPlan": {
            "shotIndex": shot["seq"],
            "issueIds": [issue["id"] for issue in issues],
            "batchSize": batch_size,
            "referenceShots": reference_shots,
            "selectionCriteria": criteria,
            "escalation": "如仍有问题，按本镜头问题清单逐项强化描述后重抽。",
        },
        "status": "ready",
        "source": source,
        "errorMessage": "；".join(errors) if errors else None,
        "issues": contexts,
    }


async def generate_for_task(
    db: Database, settings: Settings, task_id: str, provider: VisionProvider
) -> dict[str, int]:
    """分析阶段 6：为每个开放问题生成建议；单条失败隔离。"""
    issues = await judgement_repo.list_issues(db, task_id)
    ready = failed = 0
    for issue in issues:
        try:
            await ensure_suggestion(
                db, settings, task_id, issue["id"], provider
            )
            ready += 1
        except (AppError, ProviderError) as exc:
            failed += 1
            logger.warning("问题 %s 建议生成失败：%s", issue["id"], type(exc).__name__)
        except Exception:
            failed += 1
            logger.exception("问题 %s 建议生成未预期失败", issue["id"])
    await event_repo.insert_event(
        db,
        "suggestion.batch_completed",
        {"ready": ready, "failed": failed, "total": len(issues)},
        task_id=task_id,
    )
    return {"ready": ready, "failed": failed, "total": len(issues)}


def serialize_suggestion(row: aiosqlite.Row, shot_code: str) -> dict[str, Any]:
    return {
        "id": row["id"],
        "taskId": row["task_id"],
        "issueId": row["issue_id"],
        "shotId": row["shot_id"],
        "shotCode": shot_code,
        "revisedPrompt": row["revised_prompt"],
        "negativePrompt": row["negative_prompt"],
        "negativePromptMode": row["negative_prompt_mode"],
        "keyPoints": _load_json(row["key_points_json"]) or [],
        "referenceShots": _load_json(row["reference_shots_json"]) or [],
        "rationale": row["rationale"],
        "cardDrawPlan": _load_json(row["card_draw_plan_json"]) or {},
        "status": row["status"],
        "source": row["source"] or "ai",
        "errorMessage": row["error_message"],
        "promptVersion": row["prompt_version"],
        "updatedAt": row["updated_at"],
    }


async def list_for_report(db: Database, task_id: str) -> list[dict[str, Any]]:
    issues = await judgement_repo.list_issues(db, task_id)
    shots = await shot_repo.get_shots(db, task_id)
    shot_code = {shot["id"]: shot["shot_code"] for shot in shots}
    rows = await suggestion_repo.list_for_task(db, task_id)
    open_ids = {row["id"] for row in issues}
    result = []
    for row in rows:
        if row["issue_id"] not in open_ids:
            continue
        result.append(serialize_suggestion(row, shot_code.get(row["shot_id"], "")))
    return result
