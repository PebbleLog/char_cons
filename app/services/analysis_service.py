"""异步分析编排（阶段三：素材校验 → 设定解析 → 剧本解析 → 逐镜头观察）。

设计要点：
- 分析在 asyncio 后台任务中执行，进度写入 SQLite，页面通过 /analysis 轮询；
- 单镜头失败隔离，不丢弃已成功镜头；全部失败才判任务失败；
- 鉴权/额度/内容安全错误停止后续调用；
- 业务判定（R1～R10）不在本阶段，观察结果先持久化，报告在阶段四生成。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Sequence

import aiosqlite

from ..core.config import Settings
from ..core.constants import ATTRIBUTE_NAMES
from ..core.concurrency import TaskHandle, TaskRegistry
from ..core.errors import AppError
from ..core.ids import new_id
from ..core.timeutil import now_iso
from ..providers.base import ProviderResult, VisionProvider
from ..providers.errors import ProviderError, is_fatal
from ..providers.prompt_loader import prompt_version
from ..providers.schemas import CharacterProfile, ScriptContext
from ..repositories import (
    event_repo,
    judgement_repo,
    observation_repo,
    shot_repo,
    suggestion_repo,
    task_repo,
    usage_repo,
)
from ..repositories.database import Database
from . import file_service, image_service, profile_local, script_parser, suggestion_service
from .judgment_engine import ObservationView, ShotView, judge

logger = logging.getLogger(__name__)

STAGE_NAMES = {
    1: "素材校验",
    2: "设定解析",
    3: "剧本解析",
    4: "逐镜头观察",
    5: "一致性判定",
    6: "生成建议",
}
TERMINAL_STATUSES = {"completed", "partial", "failed"}


# ---- 状态与查询 ----------------------------------------------
def _provider_to_app_error(exc: ProviderError) -> AppError:
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


def _parse_json(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def get_analysis_status(db: Database, task_id: str) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    shots = await shot_repo.get_shots(db, task_id)
    observations = await observation_repo.list_for_task_current(db, task_id)
    verdict_counts = await judgement_repo.counts_by_shot(db, task_id)
    verdict_map = await judgement_repo.verdicts_by_shot(db, task_id)

    by_shot: dict[str, list[aiosqlite.Row]] = {}
    for row in observations:
        by_shot.setdefault(row["shot_id"], []).append(row)
    verdicts_by_shot: dict[str, dict[str, str]] = {}
    for (shot_id, attribute_id), verdict in verdict_map.items():
        verdicts_by_shot.setdefault(shot_id, {})[attribute_id] = verdict

    running = task["status"] in ("running", "retrying")
    stage_index = int(task["analysis_stage"] or (4 if task["status"] in TERMINAL_STATUSES else 1))
    stage_name = task["analysis_stage_name"] or STAGE_NAMES.get(stage_index, "素材校验")

    shot_items = []
    current_shot = None
    for shot in shots:
        rows = by_shot.get(shot["id"], [])
        counts = verdict_counts.get(shot["id"], {})
        verdicts = verdicts_by_shot.get(shot["id"], {})
        item = {
            "shotId": shot["id"],
            "shotCode": shot["shot_code"],
            "analysisStatus": shot["analysis_status"],
            "conclusionStatus": shot["conclusion_status"],
            "inconsistent": int(counts.get("inconsistent", 0)),
            "unknown": int(counts.get("unknown", 0)),
            "judged": bool(verdicts),
            "verdicts": verdicts,
            "evidenceReady": len(rows) >= 11,
            "errorCode": shot["analysis_error_code"],
            "errorMessage": shot["analysis_error_message"],
        }
        shot_items.append(item)
        if current_shot is None and shot["analysis_status"] == "analyzing":
            current_shot = {
                "shotCode": shot["shot_code"],
                "observations": [
                    {
                        "attributeId": row["attribute_id"],
                        "attributeName": ATTRIBUTE_NAMES.get(row["attribute_id"], row["attribute_id"]),
                        "observedValue": row["observed_value"],
                        "visibility": row["visibility"],
                        "evidence": row["evidence"],
                        "visibilityReason": row["visibility_reason"],
                        "verdict": verdicts.get(row["attribute_id"]),
                    }
                    for row in rows
                ],
            }
    if current_shot is None and shot_items:
        last = shot_items[-1]
        rows = by_shot.get(last["shotId"], [])
        last_verdicts = verdicts_by_shot.get(last["shotId"], {})
        current_shot = {
            "shotCode": last["shotCode"],
            "observations": [
                {
                    "attributeId": row["attribute_id"],
                    "attributeName": ATTRIBUTE_NAMES.get(row["attribute_id"], row["attribute_id"]),
                    "observedValue": row["observed_value"],
                    "visibility": row["visibility"],
                    "evidence": row["evidence"],
                    "visibilityReason": row["visibility_reason"],
                    "verdict": last_verdicts.get(row["attribute_id"]),
                }
                for row in rows
            ],
        }

    pending = sum(
        1
        for shot in shots
        if shot["analysis_status"] in ("pending", "analyzing")
    )
    eta = None
    if running:
        eta = await _estimate_eta(db, task_id, pending)

    # 生成建议阶段没有镜头级 ETA；用已落库的建议条数给出真实子进度。
    open_issues = await judgement_repo.list_issues(db, task_id)
    issue_ids = {row["id"] for row in open_issues}
    suggestion_rows = await suggestion_repo.list_for_task(db, task_id)
    suggestions_ready = sum(
        1
        for row in suggestion_rows
        if row["issue_id"] in issue_ids and row["status"] == "ready"
    )
    progress = int(task["analysis_progress"] or 0)
    if running and stage_index == 6 and issue_ids:
        progress = max(
            progress,
            min(98, 95 + round(3 * suggestions_ready / len(issue_ids))),
        )

    return {
        "taskId": task_id,
        "status": task["status"],
        "progress": progress,
        "etaSeconds": eta,
        "stage": {
            "index": stage_index,
            "name": stage_name,
            "completed": task["status"] not in ("running", "retrying"),
        },
        "stages": [
            {"index": index, "name": STAGE_NAMES[index]}
            for index in sorted(STAGE_NAMES)
        ],
        "suggestions": {
            "ready": suggestions_ready,
            "total": len(issue_ids),
        },
        "shots": shot_items,
        "currentShot": current_shot,
        "error": (
            {"code": task["error_code"], "message": task["error_message"]}
            if task["error_code"] or task["error_message"]
            else None
        ),
        "startedAt": task["started_at"],
        "updatedAt": task["updated_at"],
    }


async def _estimate_eta(db: Database, task_id: str, pending: int) -> int | None:
    if pending <= 0:
        return None
    # 简单估算：观察并发为 3，按批 × 20 秒；仅供展示，不作为超时依据
    return ((pending + 2) // 3) * 20


async def get_shot_observations(
    db: Database, task_id: str, shot_id: str
) -> dict[str, Any]:
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)
    version_id = shot["current_version_id"]
    rows = await observation_repo.list_for_shot_version(db, shot_id, version_id) if version_id else []
    subject = _parse_json(rows[0]["subject_json"]) if rows else None
    return {
        "shotId": shot_id,
        "shotCode": shot["shot_code"],
        "analysisStatus": shot["analysis_status"],
        "subject": subject,
        "observations": [
            {
                "attributeId": row["attribute_id"],
                "attributeName": ATTRIBUTE_NAMES.get(row["attribute_id"], row["attribute_id"]),
                "observedValue": row["observed_value"],
                "visibility": row["visibility"],
                "visibilityReason": row["visibility_reason"],
                "evidence": row["evidence"],
                "confidence": row["confidence"],
            }
            for row in rows
        ],
    }


# ---- 启动/取消 ----------------------------------------------
async def start_analysis(
    db: Database,
    settings: Settings,
    task_id: str,
    provider: VisionProvider,
    registry: TaskRegistry,
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    if task["status"] in ("running", "retrying"):
        raise AppError("conflict", "该任务正在分析中。", status_code=409)
    shots = await shot_repo.get_shots(db, task_id)
    if not shots:
        raise AppError("invalid_request", "请先上传至少 1 张镜头。", status_code=400)
    if not task["profile_raw"].strip() or not task["script_raw"].strip():
        raise AppError(
            "invalid_request", "角色设定与剧本说明齐全后才能开始分析。", status_code=400
        )
    try:
        provider.ensure_configured()
    except ProviderError as exc:
        raise _provider_to_app_error(exc) from exc

    handle = registry.get_or_create(task_id)
    async with handle.lock:
        if handle.active:
            raise AppError("conflict", "该任务正在分析中。", status_code=409)
        model_name = getattr(
            provider, "model_name", getattr(provider, "name", "unknown")
        )
        await _reset_for_analysis(
            db, task_id, model_name=model_name
        )
        handle.cancel_event.clear()
        handle.stage = STAGE_NAMES[1]
        handle.runner = asyncio.create_task(
            _run_analysis(db, settings, task_id, provider, handle),
            name=f"analysis-{task_id}",
        )
    await event_repo.insert_event(db, "analysis.started", {"model": model_name}, task_id=task_id)
    return await get_analysis_status(db, task_id)


async def _reset_for_analysis(db: Database, task_id: str, *, model_name: str) -> None:
    now = now_iso()
    async with db.transaction() as conn:
        row = await (
            await conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        ).fetchone()
        if row is None:
            raise AppError("not_found", "任务不存在或已被删除。", status_code=404)
        if row["status"] in ("running", "retrying"):
            raise AppError("conflict", "该任务正在分析中。", status_code=409)
        await conn.execute("DELETE FROM observations WHERE task_id = ?", (task_id,))
        await conn.execute("DELETE FROM issues WHERE task_id = ?", (task_id,))
        await conn.execute("DELETE FROM unknown_items WHERE task_id = ?", (task_id,))
        await conn.execute("DELETE FROM waivers WHERE task_id = ?", (task_id,))
        await conn.execute("DELETE FROM suspected_issues WHERE task_id = ?", (task_id,))
        await conn.execute("DELETE FROM judgements WHERE task_id = ?", (task_id,))
        await conn.execute(
            """
            UPDATE shots SET analysis_status = 'pending', conclusion_status = NULL,
                analysis_error_code = NULL, analysis_error_message = NULL, updated_at = ?
            WHERE task_id = ?
            """,
            (now, task_id),
        )
        await conn.execute(
            """
            UPDATE tasks SET status = 'running', analysis_stage = 1,
                analysis_stage_name = '素材校验', analysis_progress = 2,
                analysis_eta_seconds = NULL, error_code = NULL, error_message = NULL,
                started_at = ?, completed_at = NULL, profile_json = NULL,
                script_context_json = NULL, analysis_model = ?, prompt_version = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, model_name, prompt_version(), now, task_id),
        )


async def cancel_analysis(
    db: Database, task_id: str, registry: TaskRegistry
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    if task["status"] not in ("running", "retrying"):
        return await get_analysis_status(db, task_id)

    handle = registry.get(task_id)
    if handle:
        handle.request_cancel()
        if handle.runner and not handle.runner.done():
            handle.runner.cancel()
            await asyncio.gather(handle.runner, return_exceptions=True)

    now = now_iso()
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM observations WHERE task_id = ?", (task_id,))
        await conn.execute(
            """
            UPDATE shots SET analysis_status = 'pending', conclusion_status = NULL,
                analysis_error_code = NULL, analysis_error_message = NULL, updated_at = ?
            WHERE task_id = ?
            """,
            (now, task_id),
        )
        await conn.execute(
            """
            UPDATE tasks SET status = 'idle', analysis_stage = NULL,
                analysis_stage_name = NULL, analysis_progress = 0,
                analysis_eta_seconds = NULL, error_code = NULL, error_message = NULL,
                completed_at = NULL, profile_json = NULL, script_context_json = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now, task_id),
        )
    await event_repo.insert_event(db, "analysis.canceled", {}, task_id=task_id)
    return await get_analysis_status(db, task_id)


# ---- 管线 ----------------------------------------------------
async def _run_analysis(
    db: Database,
    settings: Settings,
    task_id: str,
    provider: VisionProvider,
    handle: TaskHandle,
) -> None:
    try:
        await _stage_progress(db, handle, task_id, 1, "素材校验", 5)
        shots, invalid = await _validate_materials(db, settings, task_id)
        if not shots:
            raise AppError("file_unavailable", "没有可用的镜头文件。", status_code=400)

        await _stage_progress(db, handle, task_id, 2, "设定解析", 12)
        profile = await _build_profile(db, task_id, provider)

        await _stage_progress(db, handle, task_id, 3, "剧本解析", 22)
        script = await _build_script(db, task_id, [shot["shot_code"] for shot in shots])

        await _stage_progress(db, handle, task_id, 4, "逐镜头观察", 25)
        failures = [
            *invalid,
            *await _observe_all(
                db, settings, task_id, provider, profile, script, shots, handle
            ),
        ]
        total = len(shots) + len(invalid)
        # 全部镜头观察失败时不再假装进入判定/建议阶段。
        if len(failures) >= total:
            await _finalize(db, task_id, failures, total)
            return

        await _stage_progress(db, handle, task_id, 5, "一致性判定", 92)
        await _judge_and_persist(db, task_id)

        await _stage_progress(db, handle, task_id, 6, "生成建议", 95)
        await suggestion_service.generate_for_task(db, settings, task_id, provider)

        await _finalize(db, task_id, failures, total)
    except asyncio.CancelledError:
        logger.info("分析已取消：%s", task_id)
        raise
    except AppError as exc:
        await _mark_task_failed(db, task_id, exc.code, exc.message)
    except ProviderError as exc:
        await _mark_task_failed(db, task_id, exc.code, exc.message)
    except Exception as exc:  # 兜底：不允许后台异常吞掉状态
        logger.exception("分析管线未预期异常：%s", type(exc).__name__)
        await _mark_task_failed(db, task_id, "internal_error", "分析过程中发生未预期错误。")
    finally:
        handle.runner = None
        handle.stage = None


async def _stage_progress(
    db: Database, handle: TaskHandle, task_id: str, index: int, name: str, progress: int
) -> None:
    if handle.canceled:
        raise asyncio.CancelledError
    handle.stage = name
    await db.execute(
        """
        UPDATE tasks SET analysis_stage = ?, analysis_stage_name = ?,
            analysis_progress = ?, updated_at = ?
        WHERE id = ?
        """,
        (index, name, progress, now_iso(), task_id),
    )


async def _validate_materials(
    db: Database, settings: Settings, task_id: str
) -> tuple[list[aiosqlite.Row], list[tuple[str, str]]]:
    shots = await shot_repo.get_shots(db, task_id)
    usable: list[aiosqlite.Row] = []
    invalid: list[tuple[str, str]] = []
    for shot in shots:
        try:
            version = (
                await shot_repo.get_version(db, shot["current_version_id"])
                if shot["current_version_id"]
                else None
            )
            relative = (
                version["image_path"]
                if version and version["kind"] == "adopted"
                else (shot["analysis_path"] or shot["original_path"])
            )
            path = file_service.resolve_data_path(settings, relative)
            exists = path.is_file() and shot["current_version_id"]
        except AppError:
            exists = False
        if exists:
            usable.append(shot)
        else:
            await _mark_shot_failed(
                db, shot["id"], "file_unavailable", "镜头文件不可用，请重新上传。"
            )
            invalid.append(("file_unavailable", "镜头文件不可用"))
    return usable, invalid


async def _shot_image_for_model(
    db: Database, settings: Settings, shot: aiosqlite.Row
) -> tuple[bytes, str]:
    """优先使用当前版本；采用版本没有分析副本时现场生成 ≤1568px JPEG。"""
    version = (
        await shot_repo.get_version(db, shot["current_version_id"])
        if shot["current_version_id"]
        else None
    )
    if version and version["kind"] == "adopted":
        path = file_service.resolve_data_path(settings, version["image_path"])
        raw = await asyncio.to_thread(path.read_bytes)
        processed = await asyncio.to_thread(
            image_service.process_upload, raw, path.name, 30
        )
        return processed.analysis_jpeg, "image/jpeg"
    path = file_service.resolve_data_path(
        settings, shot["analysis_path"] or shot["original_path"]
    )
    data = await asyncio.to_thread(path.read_bytes)
    return data, "image/jpeg" if shot["analysis_path"] else (shot["mime_type"] or "image/jpeg")


async def _build_profile(
    db: Database, task_id: str, provider: VisionProvider
) -> CharacterProfile:
    task = await _task_or_404(db, task_id)
    raw = task["profile_raw"]
    profile: CharacterProfile | None = None
    used_model = task["analysis_model"]

    try:
        result = await provider.parse_profile(raw)
        await _record_usage(db, task_id, "profile", provider, result, input_images=0)
        parsed = result.value
        if isinstance(parsed, CharacterProfile) and parsed.explicit_count > 0:
            profile = parsed
            used_model = result.model
        else:
            await event_repo.insert_event(
                db, "profile.fallback_to_local", {"reason": "empty_model_result"}, task_id=task_id
            )
    except ProviderError as exc:
        await _record_failed_usage(db, task_id, "profile", provider, exc, input_images=0)
        if is_fatal(exc.code):
            raise
        await event_repo.insert_event(
            db,
            "profile.fallback_to_local",
            {"reason": exc.code},
            task_id=task_id,
        )

    if profile is None:
        local = profile_local.parse_profile_local(raw)
        if local.explicit_count == 0:
            raise AppError(
                "profile_empty",
                "未能从角色设定中抽取任何外观要素，请补充明确的外观描述。",
                status_code=400,
            )
        profile = local
        # analysis_model 记录本次观察使用的模型；本地回退单独写入事件，避免误导
        await event_repo.insert_event(
            db, "profile.parsed_local", {"explicit": local.explicit_count}, task_id=task_id
        )
    else:
        await event_repo.insert_event(
            db, "profile.parsed", {"explicit": profile.explicit_count}, task_id=task_id
        )

    await db.execute(
        "UPDATE tasks SET profile_json = ?, analysis_model = ?, updated_at = ? WHERE id = ?",
        (
            profile.model_dump_json(by_alias=True),
            used_model,
            now_iso(),
            task_id,
        ),
    )
    return profile


async def _build_script(
    db: Database, task_id: str, shot_codes: Sequence[str]
) -> ScriptContext:
    task = await _task_or_404(db, task_id)
    script = script_parser.parse_script(task["script_raw"], list(shot_codes))
    await db.execute(
        "UPDATE tasks SET script_context_json = ?, updated_at = ? WHERE id = ?",
        (script.model_dump_json(by_alias=True), now_iso(), task_id),
    )
    await event_repo.insert_event(
        db,
        "script.parsed",
        {"badge": script.rule_badge, "warnings": len(script.warnings)},
        task_id=task_id,
    )
    return script


async def _observe_all(
    db: Database,
    settings: Settings,
    task_id: str,
    provider: VisionProvider,
    profile: CharacterProfile,
    script: ScriptContext,
    shots: Sequence[aiosqlite.Row],
    handle: TaskHandle,
) -> list[tuple[str, str]]:
    semaphore = asyncio.Semaphore(3)
    stop: dict[str, str | None] = {"fatal": None, "message": None}
    failures: list[tuple[str, str]] = []
    total = len(shots)
    done = 0

    async def guarded(shot: aiosqlite.Row) -> bool:
        async with semaphore:
            if handle.canceled:
                raise asyncio.CancelledError
            if stop["fatal"]:
                await _mark_shot_failed(
                    db,
                    shot["id"],
                    stop["fatal"] or "aborted",
                    "前置调用失败（鉴权/额度/内容安全），已停止后续观察。",
                )
                failures.append((stop["fatal"] or "aborted", "已停止后续观察"))
                return False
            return await _observe_one(
                db, settings, task_id, provider, profile, script, shot, stop, failures
            )

    tasks = [asyncio.create_task(guarded(shot)) for shot in shots]
    try:
        for completed in asyncio.as_completed(tasks):
            await completed
            done += 1
            if handle.canceled:
                raise asyncio.CancelledError
            progress = 25 + round(65 * done / total)
            await db.execute(
                "UPDATE tasks SET analysis_progress = ?, updated_at = ? WHERE id = ?",
                (min(progress, 90), now_iso(), task_id),
            )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
    return failures


async def _observe_one(
    db: Database,
    settings: Settings,
    task_id: str,
    provider: VisionProvider,
    profile: CharacterProfile,
    script: ScriptContext,
    shot: aiosqlite.Row,
    stop: dict[str, str | None],
    failures: list[tuple[str, str]],
) -> bool:
    shot_id = shot["id"]
    await db.execute(
        "UPDATE shots SET analysis_status = 'analyzing', updated_at = ? WHERE id = ?",
        (now_iso(), shot_id),
    )
    try:
        image, image_mime = await _shot_image_for_model(db, settings, shot)
    except (OSError, AppError, image_service.ImageValidationError) as exc:
        await _mark_shot_failed(db, shot_id, "file_unavailable", "镜头文件不可用。")
        failures.append(("file_unavailable", "镜头文件不可用"))
        return False

    try:
        result = await provider.observe_shot(
            image,
            mime_type=image_mime,
            shot_code=shot["shot_code"],
            note=shot["note"] or "",
            profile=profile,
            script=script,
        )
    except ProviderError as exc:
        await _record_failed_usage(
            db, task_id, "observe", provider, exc, input_images=1
        )
        await _mark_shot_failed(db, shot_id, exc.code, exc.message)
        failures.append((exc.code, exc.message))
        if is_fatal(exc.code):
            stop["fatal"] = exc.code
            stop["message"] = exc.message
        await event_repo.insert_event(
            db,
            "shot.failed",
            {"shotCode": shot["shot_code"], "code": exc.code},
            task_id=task_id,
        )
        return False
    except Exception as exc:  # Provider 内部未映射异常也隔离到单镜头
        logger.exception("单镜头观察异常：%s", type(exc).__name__)
        await _mark_shot_failed(db, shot_id, "internal_error", "观察过程发生未预期错误。")
        failures.append(("internal_error", "观察过程发生未预期错误"))
        return False

    observation = result.value
    subject_json = observation.subject.model_dump_json(by_alias=True)
    rows = [
        {
            "id": new_id("obs"),
            "task_id": task_id,
            "shot_id": shot_id,
            "version_id": shot["current_version_id"],
            "attribute_id": item.attribute_id,
            "observed_value": item.observed_value,
            "visibility": item.visibility,
            "visibility_reason": item.visibility_reason,
            "evidence": item.evidence,
            "confidence": item.confidence,
            "subject_json": subject_json,
            "raw_json": item.model_dump_json(by_alias=True),
        }
        for item in observation.observations
    ]
    async with db.transaction() as conn:
        await conn.execute(
            "DELETE FROM observations WHERE version_id = ?", (shot["current_version_id"],)
        )
        await observation_repo.insert_many(conn, rows)
        await conn.execute(
            """
            UPDATE shots SET analysis_status = 'ok', conclusion_status = NULL,
                analysis_error_code = NULL, analysis_error_message = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), shot_id),
        )
    await _record_usage(db, task_id, "observe", provider, result, input_images=1)
    await event_repo.insert_event(
        db,
        "shot.observed",
        {"shotCode": shot["shot_code"], "attributes": len(rows)},
        task_id=task_id,
    )
    return True


async def _record_usage(
    db: Database,
    task_id: str,
    kind: str,
    provider: VisionProvider,
    result: ProviderResult,
    *,
    input_images: int,
) -> None:
    await usage_repo.record_usage(
        db,
        task_id=task_id,
        kind=kind,
        provider=getattr(provider, "name", None),
        model=result.model,
        request_id=result.request_id,
        input_images=input_images,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
    )


async def _record_failed_usage(
    db: Database,
    task_id: str,
    kind: str,
    provider: VisionProvider,
    exc: ProviderError,
    *,
    input_images: int,
) -> None:
    await usage_repo.record_usage(
        db,
        task_id=task_id,
        kind=kind,
        provider=getattr(provider, "name", None),
        model=None,
        request_id=exc.request_id,
        input_images=input_images,
    )


async def _mark_shot_failed(
    db: Database, shot_id: str, code: str, message: str
) -> None:
    await db.execute(
        """
        UPDATE shots SET analysis_status = 'failed',
            analysis_error_code = ?, analysis_error_message = ?, updated_at = ?
        WHERE id = ?
        """,
        (code, message, now_iso(), shot_id),
    )


async def _mark_task_failed(db: Database, task_id: str, code: str, message: str) -> None:
    now = now_iso()
    await db.execute(
        """
        UPDATE tasks SET status = 'failed', error_code = ?, error_message = ?,
            analysis_eta_seconds = NULL, completed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (code, message, now, now, task_id),
    )
    # 兜底：不允许残留“观察中”的镜头状态
    await db.execute(
        """
        UPDATE shots SET analysis_status = 'failed',
            analysis_error_code = COALESCE(analysis_error_code, ?),
            analysis_error_message = COALESCE(analysis_error_message, ?),
            updated_at = ?
        WHERE task_id = ? AND analysis_status = 'analyzing'
        """,
        (code, message, now, task_id),
    )
    await event_repo.insert_event(
        db, "analysis.failed", {"code": code}, task_id=task_id
    )


async def _judge_and_persist(db: Database, task_id: str) -> None:
    task = await _task_or_404(db, task_id)
    if not task["profile_json"] or not task["script_context_json"]:
        return
    profile = CharacterProfile.model_validate_json(task["profile_json"])
    script = ScriptContext.model_validate_json(task["script_context_json"])
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
            shot_id=shot["id"],
            shot_code=shot["shot_code"],
            seq=shot["seq"],
            version_id=shot["current_version_id"] or "",
            analysis_status=shot["analysis_status"],
            observations=by_shot.get(shot["id"], {}),
            error_code=shot["analysis_error_code"],
            error_message=shot["analysis_error_message"],
        )
        for shot in shots
    ]
    if not any(view.analysis_status == "ok" for view in shot_views):
        return

    result = judge(
        profile, script, shot_views, character_name=task["character_name"] or ""
    )
    await judgement_repo.clear_for_task(db, task_id)
    async with db.transaction() as conn:
        await judgement_repo.persist_result(conn, task_id, result)
        await conn.execute(
            """
            UPDATE tasks SET analysis_stage = 5, analysis_stage_name = '一致性判定',
                analysis_progress = 94, updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), task_id),
        )
    await event_repo.insert_event(
        db, "judgement.completed", result.stats, task_id=task_id
    )


async def _finalize(
    db: Database, task_id: str, failures: Sequence[tuple[str, str]], total: int
) -> None:
    failed = len(failures)
    now = now_iso()
    if failed == 0:
        status = "completed"
        code = None
        message = None
    elif failed >= total:
        status = "failed"
        code = failures[0][0] if failures else "all_shots_failed"
        message = "全部镜头观察失败，未生成报告。"
    else:
        status = "partial"
        code = "partial_failure"
        message = f"{failed} 个镜头观察失败，报告覆盖其余镜头。"

    stage, stage_name, progress = (
        (4, "逐镜头观察", 90)
        if status == "failed"
        else (6, "生成建议", 100)
    )
    await db.execute(
        """
        UPDATE tasks SET status = ?, analysis_stage = ?,
            analysis_stage_name = ?, analysis_progress = ?,
            analysis_eta_seconds = 0, error_code = ?, error_message = ?,
            completed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, stage, stage_name, progress, code, message, now, now, task_id),
    )
    event_type = {
        "completed": "analysis.completed",
        "partial": "analysis.partial",
        "failed": "analysis.failed",
    }[status]
    await event_repo.insert_event(
        db,
        event_type,
        {"failedShots": failed, "totalShots": total},
        task_id=task_id,
    )
