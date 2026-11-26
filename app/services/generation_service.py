"""候选图生成、自动预检、采用与单镜头复检（F-09 / F-10）。

关键约束：
- Seedream 5.5 单次只生成 1 张；默认 4 张候选由 4 次并行调用实现；
- 单候选失败隔离，允许部分成功；整批等待上限到期保留已返回候选；
- 预检批量失败时降级逐张；预检失败仍可人工采用；
- 采用只影响当前镜头：新建 current 版本、原版本保留；复检只重跑该镜头；
- 复检失败不得伪造关闭问题：回滚当前版本到上一版本，问题保持开启，可重试复检。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
from typing import Any, Sequence

import aiosqlite

from ..core.config import Settings
from ..core.concurrency import TaskRegistry
from ..core.errors import AppError
from ..core.ids import new_id
from ..core.timeutil import now_iso
from ..providers.base import GenerationProvider, VisionProvider
from ..providers.errors import ProviderError
from ..providers.schemas import (
    CharacterProfile,
    PrecheckOutput,
    ScriptContext,
    ShotObservation,
    SuggestionOutput,
)
from ..repositories import (
    adoption_repo,
    event_repo,
    generation_repo,
    judgement_repo,
    observation_repo,
    shot_repo,
    suggestion_repo,
    task_repo,
    usage_repo,
)
from ..repositories.database import Database
from . import file_service, generation_image, suggestion_service
from .judgment_engine import ObservationView, ShotView, judge

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"pending", "generating", "prechecking"}


def _load_json(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _provider_error(exc: ProviderError) -> AppError:
    status = 400 if exc.code in {"auth_failed", "invalid_request"} else 502
    return AppError(
        exc.code,
        exc.message,
        status_code=status,
        retryable=exc.retryable,
        action="settings" if exc.code in {"auth_failed", "quota_exceeded"} else None,
    )


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


async def _generation_or_404(
    db: Database, task_id: str, generation_id: str
) -> aiosqlite.Row:
    row = await generation_repo.get(db, task_id, generation_id)
    if row is None:
        raise AppError("not_found", "生成记录不存在。", status_code=404)
    return row


# ---- 序列化 --------------------------------------------------
def _candidate_state(row: aiosqlite.Row) -> str | None:
    return row["state"]


def _recommended_candidate_id(rows: Sequence[aiosqlite.Row]) -> str | None:
    for row in rows:
        if row["state"] == "pass":
            return row["id"]
    return None


def _precheck_payload(row: aiosqlite.Row) -> dict[str, Any] | None:
    payload = _load_json(row["precheck_json"])
    if not isinstance(payload, dict):
        return None
    error = _load_json(row["error_json"])
    if error:
        payload["error"] = error
    return payload


def serialize_candidate(
    task_id: str, generation_id: str, row: aiosqlite.Row, recommended_id: str | None
) -> dict[str, Any]:
    base = (
        f"/api/tasks/{task_id}/generations/{generation_id}/candidates/"
        f"{row['id']}/image"
    )
    return {
        "id": row["id"],
        "candidateId": row["id"],
        "candidateCode": row["candidate_code"],
        "candidateIndex": row["candidate_index"],
        "state": row["state"] or "unknown",
        "precheck": _precheck_payload(row),
        "summary": (_precheck_payload(row) or {}).get("summary", ""),
        "recommended": row["id"] == recommended_id,
        "adopted": bool(row["adopted"]),
        "adoptedAt": row["adopted_at"],
        "seed": row["seed"],
        "imageUrl": f"{base}?variant=full",
        "thumbUrl": f"{base}?variant=thumb",
    }


async def serialize_generation(
    db: Database, task_id: str, row: aiosqlite.Row
) -> dict[str, Any]:
    candidates = await generation_repo.list_candidates(db, row["id"])
    recommended_id = _recommended_candidate_id(candidates)
    states = [candidate["state"] for candidate in candidates]
    if row["precheck_status"] == "failed":
        overall = "unknown"
    elif "pass" in states:
        overall = "pass"
    elif "partial" in states:
        overall = "partial"
    elif "fail" in states:
        overall = "fail"
    else:
        overall = "unknown"
    return {
        "id": row["id"],
        "taskId": row["task_id"],
        "shotId": row["shot_id"],
        "issueIds": _load_json(row["issue_ids_json"]) or [],
        "provider": row["provider"],
        "model": row["model"],
        "prompt": row["prompt"],
        "negativePrompt": row["negative_prompt"],
        "negativePromptMode": row["negative_prompt_mode"],
        "referenceShotIds": _load_json(row["reference_shot_ids_json"]) or [],
        "requestedCount": row["requested_count"],
        "supportedParams": _load_json(row["supported_params_json"]) or {},
        "status": row["status"],
        "precheckStatus": row["precheck_status"],
        "precheckMode": row["precheck_mode"],
        "requestCount": row["request_count"],
        "succeededCount": row["succeeded_count"],
        "failedCount": row["failed_count"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
        "errorCode": row["error_code"],
        "errorMessage": row["error_message"],
        "costEstimate": row["cost_estimate"],
        "currency": row["currency"],
        "overall": overall,
        "recommendedCandidateId": recommended_id,
        "candidates": [
            serialize_candidate(task_id, row["id"], candidate, recommended_id)
            for candidate in candidates
        ],
    }


def serialize_adoption(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "taskId": row["task_id"],
        "shotId": row["shot_id"],
        "generationId": row["generation_id"],
        "candidateId": row["candidate_id"],
        "adoptedAt": row["adopted_at"],
        "precheckOverall": row["precheck_overall"],
        "overriddenPrecheck": bool(row["overridden_precheck"]),
        "originalVersionId": row["original_version_id"],
        "newVersionId": row["new_version_id"],
        "recheckStatus": row["recheck_status"],
        "recheckAt": row["recheck_at"],
        "recheckResult": _load_json(row["recheck_result_json"]),
        "adopted": True,
    }


async def _shot_adoptions(db: Database, task: aiosqlite.Row) -> dict[str, Any]:
    """只返回「最新一批生成」的采用状态；重新生成即清空该镜头的采用显示。"""
    shots = await shot_repo.get_shots(db, task["id"])
    latest_adoption = await adoption_repo.latest_by_shot(db, task["id"])
    result: dict[str, Any] = {}
    for shot in shots:
        adoption = latest_adoption.get(shot["id"])
        if adoption is None:
            continue
        latest_generation = await generation_repo.latest_for_shot(
            db, task["id"], shot["id"]
        )
        if latest_generation is None or latest_generation["id"] != adoption["generation_id"]:
            continue
        result[shot["shot_code"]] = serialize_adoption(adoption)
    return result


async def _issue_tabs(db: Database, task_id: str, task: aiosqlite.Row) -> list[dict[str, Any]]:
    issues = await judgement_repo.list_issues(db, task_id)
    shots = await shot_repo.get_shots(db, task_id)
    codes = {shot["id"]: shot["shot_code"] for shot in shots}
    grouped: dict[str, dict[str, Any]] = {}
    for issue in issues:
        shot_id = issue["shot_id"]
        entry = grouped.setdefault(
            shot_id,
            {
                "shotId": shot_id,
                "shotCode": codes.get(shot_id, ""),
                "issues": [],
            },
        )
        entry["issues"].append(
            {
                "id": issue["id"],
                "attributeId": issue["attribute_id"],
                "attributeName": issue["attribute_name"],
            }
        )
    # 已采用的问题已关闭，不在开放问题列表中；优化页仍需保留其镜头标签。
    adoptions = await adoption_repo.latest_by_shot(db, task_id)
    for shot in shots:
        if shot["id"] in grouped or shot["id"] not in adoptions:
            continue
        latest_issue = await db.fetchone(
            "SELECT id, attribute_id, attribute_name FROM issues "
            "WHERE task_id = ? AND shot_id = ? ORDER BY rowid DESC LIMIT 1",
            (task_id, shot["id"]),
        )
        if latest_issue is None:
            continue
        grouped[shot["id"]] = {
            "shotId": shot["id"],
            "shotCode": shot["shot_code"],
            "issues": [
                {
                    "id": latest_issue["id"],
                    "attributeId": latest_issue["attribute_id"],
                    "attributeName": latest_issue["attribute_name"],
                }
            ],
            "adopted": True,
        }
    for entry in grouped.values():
        entry["label"] = f"{entry['shotCode']} · {len(entry['issues'])} 个问题"
    return list(grouped.values())


async def get_optimizer_state(
    db: Database,
    settings: Settings,
    task_id: str,
    issue_id: str,
    vision_provider: VisionProvider,
    *,
    ensure_suggestion: bool = True,
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    issue = await _issue_or_404(db, task_id, issue_id)
    shot = await shot_repo.get_shot(db, task_id, issue["shot_id"])
    if shot is None:
        raise AppError("not_found", "问题关联的镜头不存在。", status_code=404)

    suggestion = None
    if ensure_suggestion and issue["status"] == "open":
        try:
            suggestion = await suggestion_service.ensure_suggestion(
                db, settings, task_id, issue_id, vision_provider
            )
        except AppError:
            suggestion = None

    latest = await generation_repo.latest_for_shot(db, task_id, issue["shot_id"])
    generation = await serialize_generation(db, task_id, latest) if latest else None
    adoption = await adoption_repo.latest_for_shot(db, task_id, issue["shot_id"])
    adoption_state = None
    if adoption and latest and adoption["generation_id"] == latest["id"]:
        adoption_state = serialize_adoption(adoption)

    shot_adoptions = await _shot_adoptions(db, task)
    tabs = await _issue_tabs(db, task_id, task)
    issues_for_shot = [
        {
            "id": row["id"],
            "attributeId": row["attribute_id"],
            "attributeName": row["attribute_name"],
        }
        for row in await judgement_repo.list_issues(db, task_id)
        if row["shot_id"] == issue["shot_id"]
    ]

    return {
        "taskId": task_id,
        "taskName": task["name"],
        "taskStatus": task["status"],
        "issue": suggestion_service.issue_context(issue, shot["shot_code"]),
        "suggestion": suggestion,
        "generation": generation,
        "adoption": adoption_state,
        "shotAdoptions": shot_adoptions,
        "tabs": tabs,
        "issuesForShot": issues_for_shot,
        "options": {
            "batchSize": int(task["default_batch_size"] or settings.default_batch_size),
            "maxBatchSize": 4,
            "generationProvider": settings.generation_provider,
            "generationModel": settings.generation_model,
            "generationConfigured": _generation_configured(settings),
            "negativePromptMode": "merged",
            "supportedParams": ["referenceImage", "seed", "size"],
        },
        "shot": {
            "shotId": shot["id"],
            "shotCode": shot["shot_code"],
            "originalUrl": (
                f"/api/tasks/{task_id}/shots/{shot['id']}/image?variant=original"
            ),
            "currentUrl": (
                f"/api/tasks/{task_id}/shots/{shot['id']}/image?variant=current"
            ),
        },
        "reportAvailable": task["status"] in ("completed", "partial"),
    }


async def get_shot_optimizer_state(
    db: Database,
    settings: Settings,
    task_id: str,
    shot_id: str,
    vision_provider: VisionProvider,
    *,
    ensure_suggestion: bool = True,
) -> dict[str, Any]:
    """镜头级优化状态：一个镜头一个批次，合并该镜头全部开放问题。"""
    task = await _task_or_404(db, task_id)
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)

    open_issues = [
        row
        for row in await judgement_repo.list_issues(db, task_id)
        if row["shot_id"] == shot_id
    ]
    latest_issue = None
    if not open_issues:
        latest_issue = await db.fetchone(
            "SELECT * FROM issues WHERE task_id = ? AND shot_id = ? "
            "ORDER BY rowid DESC LIMIT 1",
            (task_id, shot_id),
        )
        if latest_issue is None:
            raise AppError("conflict", "该镜头没有待优化问题。", status_code=409)

    issues = open_issues or ([latest_issue] if latest_issue else [])
    contexts = [
        suggestion_service.issue_context(issue, shot["shot_code"]) for issue in issues
    ]
    issue_ids = [issue["id"] for issue in open_issues]
    suggestion = None
    if ensure_suggestion and open_issues:
        try:
            suggestion = await suggestion_service.ensure_shot_suggestion(
                db, settings, task_id, shot_id, vision_provider
            )
        except AppError:
            suggestion = None

    latest = await generation_repo.latest_for_shot(db, task_id, shot_id)
    generation = await serialize_generation(db, task_id, latest) if latest else None
    adoption = await adoption_repo.latest_for_shot(db, task_id, shot_id)
    adoption_state = None
    if adoption and latest and adoption["generation_id"] == latest["id"]:
        adoption_state = serialize_adoption(adoption)

    shot_adoptions = await _shot_adoptions(db, task)
    tabs = await _issue_tabs(db, task_id, task)
    expected_text = "；".join(
        f"{item['attributeName']}：{item.get('expected') or '与参考镜头一致'}"
        for item in contexts
    )
    observed_text = "；".join(
        f"{item['attributeName']}：{item.get('observed') or '—'}"
        for item in contexts
    )
    batch_issue = {
        "id": issues[0]["id"],
        "shotId": shot_id,
        "shotCode": shot["shot_code"],
        "attributeId": "shot_batch",
        "attributeName": f"本镜头 {len(issues)} 个问题",
        "type": "shot_batch",
        "expected": expected_text,
        "observed": observed_text,
        "evidence": "；".join(
            item.get("evidence") or item.get("reason") or "—" for item in contexts
        ),
        "confidence": "medium",
        "severity": "medium",
        "status": "open" if open_issues else "closed",
        "issueIds": issue_ids,
        "issues": contexts,
    }

    return {
        "taskId": task_id,
        "taskName": task["name"],
        "taskStatus": task["status"],
        "issue": batch_issue,
        "suggestion": suggestion,
        "generation": generation,
        "adoption": adoption_state,
        "shotAdoptions": shot_adoptions,
        "tabs": tabs,
        "issuesForShot": contexts,
        "options": {
            "batchSize": int(task["default_batch_size"] or settings.default_batch_size),
            "maxBatchSize": 4,
            "generationProvider": settings.generation_provider,
            "generationModel": settings.generation_model,
            "generationConfigured": _generation_configured(settings),
            "negativePromptMode": "merged",
            "supportedParams": ["referenceImage", "seed", "size"],
        },
        "shot": {
            "shotId": shot["id"],
            "shotCode": shot["shot_code"],
            "originalUrl": (
                f"/api/tasks/{task_id}/shots/{shot['id']}/image?variant=original"
            ),
            "currentUrl": (
                f"/api/tasks/{task_id}/shots/{shot['id']}/image?variant=current"
            ),
        },
        "reportAvailable": task["status"] in ("completed", "partial"),
    }


def _generation_configured(settings: Settings) -> bool:
    if (settings.generation_provider or "").lower() == "mock":
        return True
    return bool(settings.generation_model.strip())


async def get_candidate_file(
    db: Database,
    settings: Settings,
    task_id: str,
    generation_id: str,
    candidate_id: str,
    variant: str,
) -> tuple[Any, str]:
    await _generation_or_404(db, task_id, generation_id)
    candidate = await generation_repo.get_candidate(db, generation_id, candidate_id)
    if candidate is None:
        raise AppError("not_found", "候选图不存在。", status_code=404)
    relative = candidate["local_path"] if variant == "full" else candidate["thumb_path"]
    if not relative:
        raise AppError("file_unavailable", "候选图文件不可用。", status_code=404)
    try:
        path = file_service.resolve_data_path(settings, relative)
    except AppError:
        raise AppError("file_unavailable", "候选图文件不可用。", status_code=404) from None
    if not path.is_file():
        raise AppError("file_unavailable", "候选图文件不可用。", status_code=404)
    media_type = mimetypes.guess_type(path.name)[0] or (
        "image/jpeg" if variant == "thumb" else "image/png"
    )
    return path, media_type


async def get_generation_state(
    db: Database, task_id: str, generation_id: str
) -> dict[str, Any]:
    row = await _generation_or_404(db, task_id, generation_id)
    generation = await serialize_generation(db, task_id, row)
    adoption = await adoption_repo.latest_for_shot(db, task_id, row["shot_id"])
    adoption_state = (
        serialize_adoption(adoption)
        if adoption and adoption["generation_id"] == generation_id
        else None
    )
    return {
        "generation": generation,
        "adoption": adoption_state,
    }


# ---- 启动生成 ------------------------------------------------
async def start_generation(
    db: Database,
    settings: Settings,
    task_id: str,
    issue_id: str,
    generation_provider: GenerationProvider,
    vision_provider: VisionProvider,
    registry: TaskRegistry,
    *,
    candidate_count: int | None = None,
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    if task["status"] not in ("completed", "partial"):
        raise AppError(
            "conflict", "请先完成分析并生成报告，再优化问题镜头。", status_code=409
        )
    issue = await _issue_or_404(db, task_id, issue_id)
    # 已采用并关闭的问题仍允许「重抽下一批」：该操作会清空本镜头的采用显示，
    # 但不影响其他镜头；若新候选复检仍不一致，问题会重新开启。
    shot = await shot_repo.get_shot(db, task_id, issue["shot_id"])
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)

    count = int(candidate_count or task["default_batch_size"] or settings.default_batch_size)
    if not (1 <= count <= 4):
        raise AppError("invalid_request", "候选张数必须在 1～4 之间。", status_code=400)

    try:
        generation_provider.ensure_configured()
    except ProviderError as exc:
        raise _provider_error(exc) from exc

    suggestion = await suggestion_service.ensure_suggestion(
        db, settings, task_id, issue_id, vision_provider
    )
    plan = suggestion.get("cardDrawPlan") or {}
    supported = generation_provider.capabilities
    reference_images = await _load_references(
        db, settings, task_id, shot["id"], suggestion
    )

    negative = (suggestion.get("negativePrompt") or "").strip()
    # Seedream 无独立负向参数：如实合并进正向提示词；构图基准说明一并写入记录。
    prompt = _compose_generation_prompt(
        suggestion["revisedPrompt"].strip(), negative, reference_images
    )
    reference_shot_ids = [item["shotId"] for item in reference_images]
    supported_params = {
        "referenceImage": bool(supported.get("supports_reference_image")),
        "seed": bool(supported.get("supports_seed")),
        "size": bool(supported.get("supports_size")),
        "nativeBatch": bool(supported.get("native_batch", False)),
        "negativePrompt": bool(supported.get("supports_negative_prompt", False)),
        "negativePromptMode": "merged",
        "batchSize": 1,
        "requestedCount": count,
    }

    handle = registry.get_or_create(f"gen:{task_id}:{shot['id']}")
    async with handle.lock:
        if handle.active:
            raise AppError("conflict", "该镜头正在生成中，请稍候。", status_code=409)
        async with db.transaction() as conn:
            generation_id = await generation_repo.next_generation_id(conn, task_id)
            await generation_repo.create_record(
                conn,
                generation_id=generation_id,
                task_id=task_id,
                shot_id=shot["id"],
                issue_ids=[issue_id],
                provider=getattr(generation_provider, "name", "unknown"),
                model=getattr(generation_provider, "model_name", "unknown"),
                prompt=prompt,
                negative_prompt=negative or None,
                reference_shot_ids=reference_shot_ids,
                requested_count=count,
                supported_params=supported_params,
            )
        handle.cancel_event.clear()
        handle.stage = "生成中"
        handle.runner = asyncio.create_task(
            _run_generation(
                db,
                settings,
                task,
                shot,
                generation_id,
                issue,
                suggestion,
                generation_provider,
                vision_provider,
                handle,
                count,
                reference_images,
                plan,
                prompt,
            ),
            name=f"generation-{generation_id}",
        )
    await event_repo.insert_event(
        db,
        "generation.started",
        {
            "generationId": generation_id,
            "shotCode": shot["shot_code"],
            "requested": count,
            "model": getattr(generation_provider, "model_name", None),
        },
        task_id=task_id,
    )
    row = await _generation_or_404(db, task_id, generation_id)
    return await serialize_generation(db, task_id, row)


async def start_shot_generation(
    db: Database,
    settings: Settings,
    task_id: str,
    shot_id: str,
    generation_provider: GenerationProvider,
    vision_provider: VisionProvider,
    registry: TaskRegistry,
    *,
    candidate_count: int | None = None,
) -> dict[str, Any]:
    """一个镜头一次生成：合并该镜头全部开放问题，采用后复检全部问题。"""
    task = await _task_or_404(db, task_id)
    if task["status"] not in ("completed", "partial"):
        raise AppError(
            "conflict", "请先完成分析并生成报告，再优化问题镜头。", status_code=409
        )
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

    count = int(
        candidate_count or task["default_batch_size"] or settings.default_batch_size
    )
    if not (1 <= count <= 4):
        raise AppError("invalid_request", "候选张数必须在 1～4 之间。", status_code=400)

    try:
        generation_provider.ensure_configured()
    except ProviderError as exc:
        raise _provider_error(exc) from exc

    suggestion = await suggestion_service.ensure_shot_suggestion(
        db, settings, task_id, shot_id, vision_provider
    )
    plan = suggestion.get("cardDrawPlan") or {}
    supported = generation_provider.capabilities
    reference_images = await _load_references(
        db, settings, task_id, shot["id"], suggestion
    )

    negative = (suggestion.get("negativePrompt") or "").strip()
    prompt = _compose_generation_prompt(
        (suggestion.get("revisedPrompt") or "").strip(), negative, reference_images
    )
    reference_shot_ids = [item["shotId"] for item in reference_images]
    supported_params = {
        "referenceImage": bool(supported.get("supports_reference_image")),
        "seed": bool(supported.get("supports_seed")),
        "size": bool(supported.get("supports_size")),
        "nativeBatch": bool(supported.get("native_batch", False)),
        "negativePrompt": bool(supported.get("supports_negative_prompt", False)),
        "negativePromptMode": "merged",
        "batchSize": 1,
        "requestedCount": count,
    }
    issue_ids = [issue["id"] for issue in issues]
    precheck_issue = {
        "id": issue_ids[0],
        "shotId": shot_id,
        "shotCode": shot["shot_code"],
        "attribute_name": f"本镜头 {len(issues)} 个问题",
        "expected": "；".join(
            f"{issue['attribute_name']}：{issue['expected'] or '与参考镜头一致'}"
            for issue in issues
        ),
        "observed": "；".join(
            f"{issue['attribute_name']}：{issue['observed'] or '—'}"
            for issue in issues
        ),
        "issues": suggestion.get("issues") or [],
    }

    handle = registry.get_or_create(f"gen:{task_id}:{shot['id']}")
    async with handle.lock:
        if handle.active:
            raise AppError("conflict", "该镜头正在生成中，请稍候。", status_code=409)
        async with db.transaction() as conn:
            generation_id = await generation_repo.next_generation_id(conn, task_id)
            await generation_repo.create_record(
                conn,
                generation_id=generation_id,
                task_id=task_id,
                shot_id=shot["id"],
                issue_ids=issue_ids,
                provider=getattr(generation_provider, "name", "unknown"),
                model=getattr(generation_provider, "model_name", "unknown"),
                prompt=prompt,
                negative_prompt=negative or None,
                reference_shot_ids=reference_shot_ids,
                requested_count=count,
                supported_params=supported_params,
            )
        handle.cancel_event.clear()
        handle.stage = "生成中"
        handle.runner = asyncio.create_task(
            _run_generation(
                db,
                settings,
                task,
                shot,
                generation_id,
                precheck_issue,
                suggestion,
                generation_provider,
                vision_provider,
                handle,
                count,
                reference_images,
                plan,
                prompt,
            ),
            name=f"generation-{generation_id}",
        )
    await event_repo.insert_event(
        db,
        "generation.started",
        {
            "generationId": generation_id,
            "shotCode": shot["shot_code"],
            "issueIds": issue_ids,
            "requested": count,
            "model": getattr(generation_provider, "model_name", None),
        },
        task_id=task_id,
    )
    row = await _generation_or_404(db, task_id, generation_id)
    return await serialize_generation(db, task_id, row)


async def _load_references(
    db: Database,
    settings: Settings,
    task_id: str,
    target_shot_id: str,
    suggestion: dict[str, Any],
) -> list[dict[str, Any]]:
    shots = await shot_repo.get_shots(db, task_id)
    by_code = {shot["shot_code"]: shot for shot in shots}
    by_id = {shot["id"]: shot for shot in shots}
    codes = suggestion.get("referenceShots") or []
    selected = [by_code[code] for code in codes if code in by_code]
    if not selected:
        chosen = await suggestion_service.choose_references(
            db, task_id, target_shot_id
        )
        selected = [
            by_code[item["shotCode"]]
            for item in chosen
            if item["shotCode"] in by_code
        ]

    result: list[dict[str, Any]] = []
    # 第 1 张固定为问题镜头自身的原画面，作为构图基准；只改问题要素，
    # 避免生成图整体复刻参考镜头（例如 S2/S3 都变成 S1 的构图）。
    target = by_id.get(target_shot_id)
    if target is not None:
        relative = target["analysis_path"] or target["original_path"]
        try:
            path = file_service.resolve_data_path(settings, relative)
            if path.is_file():
                data = await asyncio.to_thread(path.read_bytes)
                result.append(
                    {
                        "shotId": target["id"],
                        "shotCode": target["shot_code"],
                        "data": data,
                        "mime": (
                            "image/jpeg"
                            if target["analysis_path"]
                            else (target["mime_type"] or "image/jpeg")
                        ),
                        "reason": "问题镜头原画面（构图基准）",
                        "isTarget": True,
                    }
                )
        except (OSError, AppError):
            pass

    for shot in selected[:2]:
        if shot["id"] == target_shot_id or len(result) >= 2:
            continue
        relative = shot["analysis_path"] or shot["original_path"]
        try:
            path = file_service.resolve_data_path(settings, relative)
            if not path.is_file():
                continue
            data = await asyncio.to_thread(path.read_bytes)
        except (OSError, AppError):
            continue
        result.append(
            {
                "shotId": shot["id"],
                "shotCode": shot["shot_code"],
                "data": data,
                "mime": "image/jpeg" if shot["analysis_path"] else (shot["mime_type"] or "image/jpeg"),
                "reason": "同角色无确定问题镜头",
                "isTarget": False,
            }
        )
    return result


async def _load_precheck_references(
    db: Database,
    settings: Settings,
    task_id: str,
    suggestion: dict[str, Any],
) -> list[tuple[str, bytes, str]]:
    """预检携带的参考镜头图：只取建议里写明的参考镜头，最多 2 张。"""

    plan = suggestion.get("cardDrawPlan") or {}
    codes = list(plan.get("referenceShots") or suggestion.get("referenceShots") or [])
    if not codes:
        return []
    shots = await shot_repo.get_shots(db, task_id)
    by_code = {shot["shot_code"]: shot for shot in shots}
    result: list[tuple[str, bytes, str]] = []
    for code in codes[:2]:
        shot = by_code.get(code)
        if shot is None or shot["analysis_status"] != "ok":
            continue
        relative = shot["analysis_path"] or shot["original_path"]
        try:
            path = file_service.resolve_data_path(settings, relative)
            if not path.is_file():
                continue
            data = await asyncio.to_thread(path.read_bytes)
            processed = await asyncio.to_thread(
                generation_image.process_generated, data, path.name
            )
        except (OSError, AppError, ProviderError):
            continue
        result.append((code, processed.analysis_jpeg, "image/jpeg"))
    return result


def _compose_generation_prompt(
    prompt: str, negative: str, references: list[dict[str, Any]]
) -> str:
    """把 AI 修正提示词包装成“以原画面为构图基准”的最小改动指令。"""
    parts: list[str] = []
    if references and references[0].get("isTarget"):
        code = references[0].get("shotCode") or "当前镜头"
        directive = (
            f"以第 1 张参考图（{code} 原画面）为构图基准：保持构图、机位、人物姿态、"
            "背景、光线与镜头语言不变，只修正下述要素，不得整体重绘角色，"
            "也不得套用其他镜头的构图。"
        )
        if len(references) > 1:
            directive += "角色身份特征可参考第 2 张图，但不得改变构图与场景。"
        parts.append(directive)
    parts.append(prompt.strip())
    if negative:
        parts.append(f"避免出现：{negative}。")
    return "\n\n".join(part for part in parts if part)


def _seed_for(generation_id: str, index: int) -> int:
    digest = hashlib.sha256(f"{generation_id}:{index}".encode("ascii")).hexdigest()
    return int(digest[:8], 16) % 2_147_483_647 or 1


async def _run_generation(
    db: Database,
    settings: Settings,
    task: aiosqlite.Row,
    shot: aiosqlite.Row,
    generation_id: str,
    issue: aiosqlite.Row,
    suggestion: dict[str, Any],
    provider: GenerationProvider,
    vision_provider: VisionProvider,
    handle,
    count: int,
    references: list[dict[str, Any]],
    plan: dict[str, Any],
    prompt: str,
) -> None:
    task_id = task["id"]
    started = now_iso()
    success = 0
    failed = 0
    stop: dict[str, str | None] = {"code": None}
    semaphore = asyncio.Semaphore(4)

    async def one(index: int) -> bool:
        nonlocal success, failed
        async with semaphore:
            if handle.canceled:
                raise asyncio.CancelledError
            if stop["code"]:
                failed += 1
                return False
            seed = _seed_for(generation_id, index) if provider.capabilities.get("supports_seed") else None
            try:
                generated = await provider.generate(
                    prompt=prompt,
                    references=[(item["data"], item["mime"]) for item in references],
                    size=settings.generation_size or None,
                    seed=seed,
                )
                processed = await asyncio.to_thread(
                    generation_image.process_generated,
                    generated.image_bytes,
                    f"candidate-{index}.png",
                )
                paths = await asyncio.to_thread(
                    file_service.save_generated_candidate,
                    settings,
                    task_id,
                    generation_id,
                    index,
                    processed,
                )
                candidate_id = new_id("cand")
                async with db.transaction() as conn:
                    await generation_repo.insert_candidate(
                        conn,
                        candidate_id=candidate_id,
                        generation_id=generation_id,
                        candidate_index=index,
                        candidate_code=f"C-{index:03d}",
                        provider_request_id=generated.request_id,
                        remote_url=generated.remote_url,
                        local_path=paths["full"],
                        thumb_path=paths["thumb"],
                        width=processed.width,
                        height=processed.height,
                        seed=seed,
                        elapsed_ms=generated.elapsed_ms,
                    )
                await usage_repo.record_usage(
                    db,
                    task_id=task_id,
                    kind="generation",
                    provider=getattr(provider, "name", None),
                    model=generated.model,
                    request_id=generated.request_id,
                    image_count=1,
                )
                success += 1
                return True
            except ProviderError as exc:
                failed += 1
                if exc.code in {"auth_failed", "quota_exceeded", "content_filtered"}:
                    stop["code"] = exc.code
                await event_repo.insert_event(
                    db,
                    "generation.candidate_failed",
                    {"generationId": generation_id, "index": index, "code": exc.code},
                    task_id=task_id,
                )
                return False
            except asyncio.CancelledError:
                raise
            except Exception:
                failed += 1
                logger.exception("候选 %s 生成异常", index)
                await event_repo.insert_event(
                    db,
                    "generation.candidate_failed",
                    {"generationId": generation_id, "index": index, "code": "internal_error"},
                    task_id=task_id,
                )
                return False

    tasks = [asyncio.create_task(one(index)) for index in range(1, count + 1)]
    pending = set(tasks)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.generation_batch_wait_seconds
    try:
        while pending and loop.time() < deadline:
            if handle.canceled:
                break
            remaining = max(0.05, min(1.0, deadline - loop.time()))
            done, pending = await asyncio.wait(
                pending, timeout=remaining, return_when=asyncio.FIRST_COMPLETED
            )
            if done:
                for finished in done:
                    try:
                        await finished
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        logger.exception("生成任务异常结束")
                await generation_repo.update_record(
                    db,
                    generation_id,
                    succeeded_count=success,
                    failed_count=failed,
                    request_count=success + failed,
                )
        if pending:
            for item in pending:
                item.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            timed_out = len(pending)
            failed += timed_out
            await event_repo.insert_event(
                db,
                "generation.batch_timeout",
                {"generationId": generation_id, "pending": timed_out},
                task_id=task_id,
            )
    except asyncio.CancelledError:
        for item in tasks:
            if not item.done():
                item.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        now = now_iso()
        await generation_repo.update_record(
            db,
            generation_id,
            status="failed",
            precheck_status="failed" if row and row["precheck_status"] == "running" else "pending",
            succeeded_count=success,
            failed_count=max(failed, count - success),
            request_count=count,
            finished_at=now,
            error_code="canceled_by_user",
            error_message="生成已取消，已返回的候选图已保留。",
        )
        await event_repo.insert_event(
            db, "generation.canceled", {"generationId": generation_id}, task_id=task_id
        )
        return

    now = now_iso()
    if handle.canceled:
        await generation_repo.update_record(
            db,
            generation_id,
            status="failed",
            succeeded_count=success,
            failed_count=count - success,
            request_count=count,
            finished_at=now,
            error_code="canceled_by_user",
            error_message="生成已取消，已返回的候选图已保留。",
        )
        return

    if success == 0:
        code = stop["code"] or "no_candidates"
        await generation_repo.update_record(
            db,
            generation_id,
            status="failed",
            precheck_status="failed",
            succeeded_count=0,
            failed_count=count,
            request_count=count,
            finished_at=now,
            error_code=code,
            error_message="本批次未返回可用候选图，请检查服务配置或重抽。",
        )
        await event_repo.insert_event(
            db,
            "generation.failed",
            {"generationId": generation_id, "code": code},
            task_id=task_id,
        )
        return

    generation_status = "succeeded" if success == count else "partial"
    await generation_repo.update_record(
        db,
        generation_id,
        status="prechecking",
        precheck_status="running",
        succeeded_count=success,
        failed_count=count - success,
        request_count=success + failed,
        finished_at=now,
    )
    await event_repo.insert_event(
        db,
        "generation.precheck_started",
        {"generationId": generation_id, "candidates": success},
        task_id=task_id,
    )

    try:
        precheck_ok = await _run_precheck(
            db,
            task_id,
            generation_id,
            shot["shot_code"],
            issue,
            suggestion,
            vision_provider,
            settings,
            handle,
        )
        precheck_status = "completed" if precheck_ok else "failed"
    except asyncio.CancelledError:
        await generation_repo.update_record(
            db,
            generation_id,
            status="failed",
            precheck_status="failed",
            error_code="canceled_by_user",
            error_message="生成已取消，候选图已保留。",
        )
        return
    except Exception:
        logger.exception("自动预检整体失败")
        precheck_status = "failed"
        await _mark_precheck_failed(
            db, task_id, generation_id, "预检未完成，候选图仍可人工查看和采用。"
        )

    await generation_repo.update_record(
        db,
        generation_id,
        status=generation_status,
        precheck_status=precheck_status,
        finished_at=now_iso(),
    )
    await event_repo.insert_event(
        db,
        "generation.completed",
        {
            "generationId": generation_id,
            "status": generation_status,
            "precheckStatus": precheck_status,
        },
        task_id=task_id,
    )


async def _run_precheck(
    db: Database,
    task_id: str,
    generation_id: str,
    shot_code: str,
    issue: aiosqlite.Row,
    suggestion: dict[str, Any],
    provider: VisionProvider,
    settings: Settings,
    handle,
) -> bool:
    rows = await generation_repo.list_candidates(db, generation_id)
    if not rows:
        raise RuntimeError("没有可预检的候选图")
    plan = suggestion.get("cardDrawPlan") or {}
    criteria = [
        str(item).strip()
        for item in (plan.get("selectionCriteria") or [])
        if str(item).strip()
    ][:6]
    if not criteria:
        criteria = [
            f"{issue['attribute_name']}与设定一致",
            "角色特征与参考镜头一致",
            "构图与相邻镜头连贯",
        ]

    issue_context = {
        "shotCode": shot_code,
        "attributeName": issue["attribute_name"],
        "expected": issue["expected"],
        "observed": issue["observed"],
    }
    candidates: list[tuple[str, bytes, str]] = []
    for row in rows:
        try:
            path = file_service.resolve_data_path(settings, row["local_path"])
            if not path.is_file():
                raise OSError("文件缺失")
            data = await asyncio.to_thread(path.read_bytes)
            processed = await asyncio.to_thread(
                generation_image.process_generated, data, path.name
            )
            # 预检使用 ≤1568px 的分析副本，避免 4 张 2K 原图造成请求体过大
            candidates.append(
                (row["candidate_code"], processed.analysis_jpeg, "image/jpeg")
            )
        except (OSError, AppError, ProviderError):
            logger.warning("候选图缺失，跳过预检：%s", row["candidate_code"])

    if not candidates:
        await _mark_precheck_failed(
            db, task_id, generation_id, "候选图文件不可用，预检未完成。"
        )
        return False

    references = await _load_precheck_references(db, settings, task_id, suggestion)
    batch_output: PrecheckOutput | None = None
    batch_error: ProviderError | None = None
    mode = "batch"
    try:
        result = await provider.precheck_candidates(
            criteria=criteria,
            candidates=candidates,
            issue=issue_context,
            references=references,
        )
        batch_output = result.value
        expected = {code for code, _data, _mime in candidates}
        actual = {item.candidate_code for item in batch_output.candidates}
        if expected != actual or len(batch_output.candidates) != len(candidates):
            raise ProviderError(
                "invalid_response",
                "批量预检返回的候选映射不完整，降级为逐张预检。",
            )
        await usage_repo.record_usage(
            db,
            task_id=task_id,
            kind="precheck",
            provider=getattr(provider, "name", None),
            model=result.model,
            request_id=result.request_id,
            input_images=result.usage.input_images,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )
    except ProviderError as exc:
        batch_error = exc
        batch_output = None
        mode = "per_candidate"
        await event_repo.insert_event(
            db,
            "precheck.fallback_per_candidate",
            {"generationId": generation_id, "code": exc.code},
            task_id=task_id,
        )

    outputs: dict[str, Any] = {}
    per_candidate_ok = 0
    per_candidate_error: str | None = None
    used_mode = mode
    if batch_output is not None:
        outputs = {item.candidate_code: item for item in batch_output.candidates}
    else:
        for code, data, mime in candidates:
            if handle.canceled:
                raise asyncio.CancelledError
            try:
                single = await provider.precheck_candidates(
                    criteria=criteria,
                    candidates=[(code, data, mime)],
                    issue=issue_context,
                    references=references,
                )
                item = next(
                    (
                        candidate
                        for candidate in single.value.candidates
                        if candidate.candidate_code == code
                    ),
                    None,
                )
                if item is None:
                    raise ProviderError("invalid_response", "逐张预检未返回对应候选。")
                outputs[code] = item
                per_candidate_ok += 1
                await usage_repo.record_usage(
                    db,
                    task_id=task_id,
                    kind="precheck",
                    provider=getattr(provider, "name", None),
                    model=single.model,
                    request_id=single.request_id,
                    input_images=single.usage.input_images,
                    input_tokens=single.usage.input_tokens,
                    output_tokens=single.usage.output_tokens,
                )
            except ProviderError as exc:
                per_candidate_error = exc.message
            except Exception as exc:
                per_candidate_error = "逐张预检发生未预期错误。"
                logger.exception("逐张预检异常：%s", type(exc).__name__)

    async with db.transaction() as conn:
        for row in rows:
            item = outputs.get(row["candidate_code"])
            if item is None:
                payload = {
                    "overall": "unknown",
                    "criteria": [
                        {"key": f"criterion-{index}", "name": name, "passed": None,
                         "evidence": "预检未返回该项。"}
                        for index, name in enumerate(criteria, start=1)
                    ],
                    "summary": "预检未完成，请人工核对。",
                    "mode": used_mode,
                }
                await generation_repo.update_candidate(
                    conn,
                    row["id"],
                    state="unknown",
                    precheck_json=json.dumps(payload, ensure_ascii=False),
                    error_json=json.dumps(
                        {
                            "code": (batch_error.code if batch_error else "precheck_failed"),
                            "message": per_candidate_error or "预检未完成。",
                        },
                        ensure_ascii=False,
                    ),
                )
                continue
            normalized = []
            for index, name in enumerate(criteria, start=1):
                source = item.criteria[index - 1] if index - 1 < len(item.criteria) else None
                normalized.append(
                    {
                        "key": source.key if source else f"criterion-{index}",
                        "name": name,
                        "passed": source.passed if source else None,
                        "evidence": source.evidence if source else "预检未返回该项。",
                    }
                )
            payload = {
                "overall": item.overall,
                "criteria": normalized,
                "summary": item.summary,
                "mode": used_mode,
            }
            await generation_repo.update_candidate(
                conn,
                row["id"],
                state=item.overall,
                precheck_json=json.dumps(payload, ensure_ascii=False),
            )
        succeeded_any = batch_output is not None or per_candidate_ok > 0
        await conn.execute(
            "UPDATE generation_records SET precheck_mode = ?, precheck_status = ? "
            "WHERE id = ?",
            (
                used_mode,
                "completed" if succeeded_any else "failed",
                generation_id,
            ),
        )
    succeeded_any = batch_output is not None or per_candidate_ok > 0
    await event_repo.insert_event(
        db,
        "precheck.completed",
        {
            "generationId": generation_id,
            "mode": used_mode,
            "succeeded": succeeded_any,
        },
        task_id=task_id,
    )
    return succeeded_any


async def _mark_precheck_failed(
    db: Database, task_id: str, generation_id: str, message: str
) -> None:
    rows = await generation_repo.list_candidates(db, generation_id)
    async with db.transaction() as conn:
        for row in rows:
            if row["state"] is None:
                await generation_repo.update_candidate(
                    conn,
                    row["id"],
                    state="unknown",
                    precheck_json=json.dumps(
                        {
                            "overall": "unknown",
                            "criteria": [],
                            "summary": message,
                            "mode": "batch",
                        },
                        ensure_ascii=False,
                    ),
                    error_json=json.dumps(
                        {"code": "precheck_failed", "message": message},
                        ensure_ascii=False,
                    ),
                )
        await conn.execute(
            "UPDATE generation_records SET precheck_status = 'failed' WHERE id = ?",
            (generation_id,),
        )


# ---- 取消 ----------------------------------------------------
async def cancel_generation(
    db: Database, task_id: str, generation_id: str, registry: TaskRegistry
) -> dict[str, Any]:
    row = await _generation_or_404(db, task_id, generation_id)
    if row["status"] not in ACTIVE_STATUSES and row["precheck_status"] != "running":
        return await get_generation_state(db, task_id, generation_id)
    handle = registry.get(f"gen:{task_id}:{row['shot_id']}")
    if handle:
        handle.request_cancel()
        if handle.runner and not handle.runner.done():
            handle.runner.cancel()
            await asyncio.gather(handle.runner, return_exceptions=True)
    await generation_repo.update_record(
        db,
        generation_id,
        status="failed",
        precheck_status=(
            "failed" if row["precheck_status"] in ("pending", "running") else row["precheck_status"]
        ),
        error_code="canceled_by_user",
        error_message="生成已取消，已返回的候选图已保留。",
        finished_at=now_iso(),
    )
    await event_repo.insert_event(
        db, "generation.canceled", {"generationId": generation_id}, task_id=task_id
    )
    return await get_generation_state(db, task_id, generation_id)


# ---- 采用与复检 ----------------------------------------------
async def adopt_candidate(
    db: Database,
    settings: Settings,
    task_id: str,
    generation_id: str,
    candidate_id: str,
    vision_provider: VisionProvider,
) -> dict[str, Any]:
    generation = await _generation_or_404(db, task_id, generation_id)
    if generation["status"] in ACTIVE_STATUSES:
        raise AppError("conflict", "候选图仍在生成/预检中，请稍后再采用。", status_code=409)
    candidate = await generation_repo.get_candidate(db, generation_id, candidate_id)
    if candidate is None:
        raise AppError("not_found", "候选图不存在。", status_code=404)
    if not candidate["local_path"]:
        raise AppError("file_unavailable", "候选图文件不可用。", status_code=404)
    shot = await shot_repo.get_shot(db, task_id, generation["shot_id"])
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)

    latest = await adoption_repo.latest_for_shot(db, task_id, shot["id"])
    if latest and latest["generation_id"] == generation_id:
        if latest["candidate_id"] == candidate_id and latest["recheck_status"] != "failed":
            return await _adoption_response(db, task_id, generation_id)
        raise AppError("conflict", "该镜头已采用候选图，如需更换请重新生成。", status_code=409)

    precheck = _precheck_payload(candidate) or {}
    precheck_overall = precheck.get("overall")
    overridden = precheck_overall in {None, "fail", "unknown"}
    original_version_id = shot["current_version_id"]
    version_id = new_id("ver")
    adoption_id = new_id("adopt")

    async with db.transaction() as conn:
        await shot_repo.insert_adopted_version(
            conn,
            version_id=version_id,
            shot_id=shot["id"],
            image_path=candidate["local_path"],
            width=candidate["width"],
            height=candidate["height"],
            file_size=None,
            source_generation_id=generation_id,
            source_candidate_id=candidate_id,
            recheck_status="running",
        )
        await adoption_repo.insert(
            conn,
            adoption_id=adoption_id,
            task_id=task_id,
            shot_id=shot["id"],
            generation_id=generation_id,
            candidate_id=candidate_id,
            precheck_overall=precheck_overall,
            overridden_precheck=overridden,
            original_version_id=original_version_id,
            new_version_id=version_id,
            recheck_status="running",
        )
        await generation_repo.mark_adopted(conn, candidate_id, now_iso())

    await event_repo.insert_event(
        db,
        "adoption.started",
        {
            "adoptionId": adoption_id,
            "generationId": generation_id,
            "candidateId": candidate_id,
            "shotCode": shot["shot_code"],
            "overriddenPrecheck": overridden,
        },
        task_id=task_id,
    )

    await _recheck_shot(
        db,
        settings,
        task_id,
        shot["id"],
        version_id,
        adoption_id,
        original_version_id,
        vision_provider,
        issue_ids=_load_json(generation["issue_ids_json"]) or [],
    )
    return await _adoption_response(db, task_id, generation_id)


async def _adoption_response(
    db: Database, task_id: str, generation_id: str
) -> dict[str, Any]:
    state = await get_generation_state(db, task_id, generation_id)
    row = await _generation_or_404(db, task_id, generation_id)
    shot = await shot_repo.get_shot(db, task_id, row["shot_id"])
    if shot:
        state["shotCode"] = shot["shot_code"]
    return state


async def _recheck_shot(
    db: Database,
    settings: Settings,
    task_id: str,
    shot_id: str,
    version_id: str,
    adoption_id: str,
    fallback_version_id: str | None,
    provider: VisionProvider,
    *,
    issue_ids: Sequence[str] | None = None,
) -> None:
    """观察新版本并增量判定；失败回滚当前版本，绝不伪造问题关闭。"""
    task = await _task_or_404(db, task_id)
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    version = await shot_repo.get_version(db, version_id)
    if shot is None or version is None:
        await _fail_recheck(
            db, task_id, shot_id, version_id, adoption_id, fallback_version_id,
            "recheck_invalid", "复检所需镜头版本不存在。",
        )
        return
    if not task["profile_json"] or not task["script_context_json"]:
        await _fail_recheck(
            db, task_id, shot_id, version_id, adoption_id, fallback_version_id,
            "recheck_failed", "缺少角色设定或剧本上下文，无法复检。",
        )
        return
    profile = CharacterProfile.model_validate_json(task["profile_json"])
    script = ScriptContext.model_validate_json(task["script_context_json"])
    try:
        path = file_service.resolve_data_path(settings, version["image_path"])
        raw = await asyncio.to_thread(path.read_bytes)
        processed = await asyncio.to_thread(
            generation_image.process_generated, raw, path.name
        )
        image = processed.analysis_jpeg
    except (OSError, AppError, ProviderError):
        await _fail_recheck(
            db, task_id, shot_id, version_id, adoption_id, fallback_version_id,
            "file_unavailable", "候选图文件不可用，复检失败。",
        )
        return

    try:
        result = await provider.observe_shot(
            image,
            mime_type="image/jpeg",
            shot_code=shot["shot_code"],
            note=shot["note"] or "",
            profile=profile,
            script=script,
        )
        await usage_repo.record_usage(
            db,
            task_id=task_id,
            kind="observe",
            provider=getattr(provider, "name", None),
            model=result.model,
            request_id=result.request_id,
            input_images=1,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )
    except ProviderError as exc:
        await _fail_recheck(
            db, task_id, shot_id, version_id, adoption_id, fallback_version_id,
            exc.code, exc.message,
        )
        return
    except Exception:
        logger.exception("复检观察异常")
        await _fail_recheck(
            db, task_id, shot_id, version_id, adoption_id, fallback_version_id,
            "internal_error", "复检观察发生未预期错误。",
        )
        return

    observation: ShotObservation = result.value
    rows = [
        {
            "id": new_id("obs"),
            "task_id": task_id,
            "shot_id": shot_id,
            "version_id": version_id,
            "attribute_id": item.attribute_id,
            "observed_value": item.observed_value,
            "visibility": item.visibility,
            "visibility_reason": item.visibility_reason,
            "evidence": item.evidence,
            "confidence": item.confidence,
            "subject_json": observation.subject.model_dump_json(by_alias=True),
            "raw_json": item.model_dump_json(by_alias=True),
        }
        for item in observation.observations
    ]
    try:
        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM observations WHERE version_id = ?", (version_id,)
            )
            await observation_repo.insert_many(conn, rows)
            await conn.execute(
                "UPDATE shots SET analysis_status = 'ok', analysis_error_code = NULL, "
                "analysis_error_message = NULL, updated_at = ? WHERE id = ?",
                (now_iso(), shot_id),
            )

        # 目标要素以本次生成关联的问题为准（问题可能已关闭，仍需检查该要素）。
        target_attrs: set[str] = set()
        if issue_ids:
            placeholders = ",".join("?" for _ in issue_ids)
            linked = await db.fetchall(
                f"SELECT attribute_id FROM issues WHERE task_id = ? AND id IN ({placeholders})",
                (task_id, *issue_ids),
            )
            target_attrs.update(row["attribute_id"] for row in linked)
        if not target_attrs:
            # 新版本已成为 current，report 查询会过滤旧版本；直接取该镜头开放问题。
            old_issue_rows = await db.fetchall(
                "SELECT * FROM issues WHERE task_id = ? AND shot_id = ? AND status = 'open'",
                (task_id, shot_id),
            )
            target_attrs.update(row["attribute_id"] for row in old_issue_rows)
        shots = await shot_repo.get_shots(db, task_id)
        observation_rows = await observation_repo.list_for_task_current(db, task_id)
        by_shot: dict[str, dict[str, ObservationView]] = {}
        for row in observation_rows:
            by_shot.setdefault(row["shot_id"], {})[row["attribute_id"]] = ObservationView(
                attribute_id=row["attribute_id"],
                observed_value=row["observed_value"],
                visibility=row["visibility"],
                visibility_reason=row["visibility_reason"],
                evidence=row["evidence"],
                confidence=row["confidence"],
            )
        shot_views = [
            ShotView(
                shot_id=item["id"],
                shot_code=item["shot_code"],
                seq=item["seq"],
                version_id=item["current_version_id"] or "",
                analysis_status=item["analysis_status"],
                observations=by_shot.get(item["id"], {}),
                error_code=item["analysis_error_code"],
                error_message=item["analysis_error_message"],
            )
            for item in shots
        ]
        judged = judge(profile, script, shot_views, character_name=task["character_name"] or "")
        target_units = [unit for unit in judged.units if unit.shot_id == shot_id]
        relevant = [unit for unit in target_units if unit.attribute_id in target_attrs]
        if any(unit.verdict == "inconsistent" for unit in relevant):
            recheck_status = "inconsistent"
        elif any(unit.verdict == "unknown" for unit in relevant):
            recheck_status = "unknown"
        elif relevant and all(unit.verdict == "consistent" for unit in relevant):
            recheck_status = "consistent"
        else:
            recheck_status = "unknown"

        async with db.transaction() as conn:
            await judgement_repo.persist_shot_recheck(
                conn, task_id, judged, shot_id
            )
        current_issues = [
            row
            for row in await db.fetchall(
                "SELECT id, attribute_id, status FROM issues WHERE task_id = ? "
                "AND shot_id = ? AND version_id = ?",
                (task_id, shot_id, version_id),
            )
            if row["status"] == "open"
        ]
        recheck_result = {
            "recheckStatus": recheck_status,
            "issueAttributes": sorted(target_attrs),
            "remainingIssueIds": [row["id"] for row in current_issues],
            "verdicts": {
                unit.attribute_id: unit.verdict for unit in relevant
            },
        }
        await shot_repo.update_version_recheck(
            db, version_id, recheck_status, adoption_id=adoption_id
        )
        await adoption_repo.update_recheck(
            db, adoption_id, status=recheck_status, result=recheck_result
        )
        await db.execute(
            "UPDATE tasks SET updated_at = ? WHERE id = ?", (now_iso(), task_id)
        )
        await event_repo.insert_event(
            db,
            "recheck.completed",
            {
                "adoptionId": adoption_id,
                "shotCode": shot["shot_code"],
                "status": recheck_status,
            },
            task_id=task_id,
        )
        # 复检后仍开启的问题需要新的建议；失败只影响建议，不影响判定。
        for issue_row in current_issues:
            try:
                await suggestion_service.ensure_suggestion(
                    db, settings, task_id, issue_row["id"], provider, force=True
                )
            except Exception:
                logger.warning("复检后建议重生成失败：%s", issue_row["id"])
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("复检判定/持久化失败")
        await _fail_recheck(
            db, task_id, shot_id, version_id, adoption_id, fallback_version_id,
            "recheck_failed", "复检完成观察但判定写入失败，可重试复检。",
        )


async def _fail_recheck(
    db: Database,
    task_id: str,
    shot_id: str,
    version_id: str,
    adoption_id: str,
    fallback_version_id: str | None,
    code: str,
    message: str,
) -> None:
    """复检失败：回滚当前版本到采用前版本，问题保持开启，采用记录保留。"""
    now = now_iso()
    async with db.transaction() as conn:
        await conn.execute(
            "UPDATE shot_versions SET is_current = 0, recheck_status = 'failed', "
            "recheck_at = ? WHERE id = ?",
            (now, version_id),
        )
        if fallback_version_id:
            await conn.execute(
                "UPDATE shot_versions SET is_current = 1 WHERE id = ?",
                (fallback_version_id,),
            )
            await conn.execute(
                "UPDATE shots SET current_version_id = ?, updated_at = ? WHERE id = ?",
                (fallback_version_id, now, shot_id),
            )
        else:
            # 极端情况下没有采用前版本：仍保留候选为当前版本，避免镜头失去图片。
            await conn.execute(
                "UPDATE shot_versions SET is_current = 1 WHERE id = ?", (version_id,)
            )
        await conn.execute(
            "UPDATE adoptions SET recheck_status = 'failed', recheck_at = ?, "
            "recheck_result_json = ? WHERE id = ?",
            (
                now,
                json.dumps({"errorCode": code, "message": message}, ensure_ascii=False),
                adoption_id,
            ),
        )
    await event_repo.insert_event(
        db,
        "recheck.failed",
        {"adoptionId": adoption_id, "code": code},
        task_id=task_id,
    )


async def retry_recheck(
    db: Database,
    settings: Settings,
    task_id: str,
    shot_id: str,
    vision_provider: VisionProvider,
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)
    adoption = await adoption_repo.latest_for_shot(db, task_id, shot_id)
    if adoption is None or adoption["recheck_status"] != "failed":
        raise AppError("conflict", "该镜头没有可重试的复检。", status_code=409)
    version = await shot_repo.get_version(db, adoption["new_version_id"])
    if version is None:
        raise AppError("not_found", "采用版本不存在。", status_code=404)
    async with db.transaction() as conn:
        await conn.execute(
            "UPDATE shot_versions SET is_current = 0 WHERE shot_id = ?", (shot_id,)
        )
        await conn.execute(
            "UPDATE shot_versions SET is_current = 1, recheck_status = 'running', "
            "recheck_at = NULL WHERE id = ?",
            (version["id"],),
        )
        await conn.execute(
            "UPDATE shots SET current_version_id = ?, updated_at = ? WHERE id = ?",
            (version["id"], now_iso(), shot_id),
        )
        await conn.execute(
            "UPDATE adoptions SET recheck_status = 'running', recheck_at = NULL "
            "WHERE id = ?",
            (adoption["id"],),
        )
    generation_row = await generation_repo.get(db, task_id, adoption["generation_id"])
    await _recheck_shot(
        db,
        settings,
        task_id,
        shot_id,
        version["id"],
        adoption["id"],
        adoption["original_version_id"],
        vision_provider,
        issue_ids=(
            _load_json(generation_row["issue_ids_json"]) if generation_row else []
        ) or [],
    )
    state = await get_shot_optimizer_state(
        db,
        settings,
        task_id,
        shot_id,
        vision_provider,
        ensure_suggestion=False,
    )
    state["taskStatus"] = task["status"]
    return state


# ---- 报告接入 ------------------------------------------------
async def list_for_report(db: Database, task_id: str) -> dict[str, Any]:
    shots = await shot_repo.get_shots(db, task_id)
    shot_code = {shot["id"]: shot["shot_code"] for shot in shots}
    records = []
    for row in await generation_repo.list_for_task(db, task_id):
        records.append(await serialize_generation(db, task_id, row))
    adoptions = []
    candidate_code: dict[str, str] = {}
    for row in records:
        for candidate in row["candidates"]:
            candidate_code[candidate["id"]] = candidate["candidateCode"]
    for row in await adoption_repo.list_for_task(db, task_id):
        item = serialize_adoption(row)
        item["shotCode"] = shot_code.get(row["shot_id"], "")
        item["candidateCode"] = candidate_code.get(row["candidate_id"], "")
        adoptions.append(item)
    return {"generations": records, "adoptions": adoptions}
