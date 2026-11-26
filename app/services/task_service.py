"""任务与镜头业务服务。

阶段二范围：
- 创建/更新/删除任务草稿；
- 批量上传镜头（校验、落盘、入库、编号与质量警告）；
- 列表、详情、状态、排序、删除、替换、受控图片读取；
- 存档概况。

分析、判定、生成与报告在后续阶段接入；本模块不伪造任何分析结论。
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import aiosqlite
from fastapi.responses import FileResponse

from ..core.config import Settings
from ..core.constants import SCHEMA_VERSION
from ..core.errors import AppError
from ..core.ids import new_id
from ..core.timeutil import now_iso
from ..repositories import generation_repo, shot_repo, task_repo
from ..repositories.database import Database
from . import file_service, image_service

logger = logging.getLogger(__name__)

EDITABLE_STATUSES = {"idle"}
EDITABLE_HINT = "任务处于分析中或已完成，不能修改素材。"
_MISSING_TASK = "任务不存在或已被删除。"


# ---- 序列化 --------------------------------------------------
def _guess_character_name(text: str) -> str:
    first = re.split(r"[，,。；;\s·]", text.strip(), maxsplit=1)[0]
    return first[:20] or "未命名"


def _task_base(task: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": task["id"],
        "name": task["name"],
        "characterName": task["character_name"],
        "mode": task["mode"],
        "status": task["status"],
        "profileRaw": task["profile_raw"],
        "scriptRaw": task["script_raw"],
        "defaultBatchSize": task["default_batch_size"],
        "schemaVersion": task["schema_version"],
        "createdAt": task["created_at"],
        "updatedAt": task["updated_at"],
        "startedAt": task["started_at"],
        "completedAt": task["completed_at"],
        "errorCode": task["error_code"],
        "errorMessage": task["error_message"],
    }


def _load_json(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _shot_urls(
    task_id: str, shot_id: str, version_id: str | None = None
) -> dict[str, str]:
    base = f"/api/tasks/{task_id}/shots/{shot_id}/image"
    # thumb/current 指向“当前版本”，带版本参数避免采用后命中旧缓存。
    version = f"&v={version_id}" if version_id else ""
    return {
        "imageUrl": f"{base}?variant=original",
        "analysisUrl": f"{base}?variant=analysis",
        "thumbUrl": f"{base}?variant=thumb{version}",
        "currentUrl": f"{base}?variant=current{version}",
    }


def _shot_dict(task: aiosqlite.Row) -> dict[str, Any]:
    try:
        warnings = json.loads(task["quality_warnings_json"] or "[]")
    except json.JSONDecodeError:
        warnings = []
    return {
        "id": task["id"],
        "seq": task["seq"],
        "shotCode": task["shot_code"],
        "originalFilename": task["original_filename"],
        "width": task["width"],
        "height": task["height"],
        "fileSize": task["file_size"],
        "mimeType": task["mime_type"],
        "note": task["note"],
        "qualityStatus": task["quality_status"],
        "qualityWarnings": warnings,
        "analysisStatus": task["analysis_status"],
        "conclusionStatus": task["conclusion_status"],
        **_shot_urls(task["task_id"], task["id"], task["current_version_id"]),
    }


async def _task_or_404(db: Database, task_id: str) -> aiosqlite.Row:
    task = await task_repo.get_task(db, task_id)
    if task is None:
        raise AppError("not_found", _MISSING_TASK, status_code=404)
    return task


def _ensure_editable(task: aiosqlite.Row) -> None:
    if task["status"] not in EDITABLE_STATUSES:
        raise AppError("conflict", EDITABLE_HINT, status_code=409)


async def _task_stats(db: Database, task_id: str) -> dict[str, int]:
    rows = await db.fetchall(
        """
        SELECT
            (SELECT COUNT(*) FROM shots WHERE task_id = ?) AS shots,
            (SELECT COUNT(*) FROM issues WHERE task_id = ? AND status = 'open') AS issues,
            (SELECT COUNT(*) FROM unknown_items WHERE task_id = ?) AS unknown_items,
            (SELECT COUNT(*) FROM judgements j
                WHERE j.task_id = ? AND j.verdict = 'consistent') AS consistent,
            (SELECT COUNT(*) FROM waivers WHERE task_id = ?) AS waivers
        """,
        (task_id, task_id, task_id, task_id, task_id),
    )
    row = rows[0] if rows else None
    if row is None:  # pragma: no cover
        return {"shots": 0, "issues": 0, "unknownItems": 0, "consistent": 0, "waivers": 0}
    return {
        "shots": int(row["shots"]),
        "issues": int(row["issues"]),
        "unknownItems": int(row["unknown_items"]),
        "consistent": int(row["consistent"]),
        "waivers": int(row["waivers"]),
    }


# ---- 任务 ----------------------------------------------------
async def create_task(
    db: Database,
    *,
    name: str | None,
    character_name: str | None,
    profile_raw: str,
    script_raw: str,
    default_batch_size: int = 4,
    mode: str = "live",
) -> dict[str, Any]:
    profile_raw = profile_raw.strip()
    script_raw = script_raw.strip()
    character = (character_name or _guess_character_name(profile_raw)).strip()[:50]
    task_name = (name or f"{character} · 新检测").strip()[:100]
    task_id = new_id("task")
    now = now_iso()

    await db.execute(
        """
        INSERT INTO tasks (
            id, name, character_name, mode, status, profile_raw, script_raw,
            schema_version, default_batch_size, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'idle', ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            task_name,
            character,
            mode,
            profile_raw,
            script_raw,
            SCHEMA_VERSION,
            default_batch_size,
            now,
            now,
        ),
    )
    logger.info("已创建任务 %s（%s）", task_id, task_name)
    return await get_task_detail(db, task_id)


async def get_task_detail(db: Database, task_id: str) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    shots = await shot_repo.get_shots(db, task_id)
    stats = await _task_stats(db, task_id)
    missing = []
    if not task["profile_raw"].strip():
        missing.append("角色设定")
    if not task["script_raw"].strip():
        missing.append("剧本说明")
    if not shots:
        missing.append("镜头")
    return {
        **_task_base(task),
        "profile": _load_json(task["profile_json"]),
        "scriptContext": _load_json(task["script_context_json"]),
        "shots": [_shot_dict(shot) for shot in shots],
        "stats": stats,
        "validation": {"ready": not missing, "missing": missing},
    }


async def list_tasks(
    db: Database,
    *,
    mode: str = "live",
    statuses: Sequence[str] | None = None,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    rows, total = await task_repo.list_tasks(
        db,
        mode=mode,
        statuses=statuses,
        query=(query or "").strip() or None,
        limit=limit,
        offset=offset,
    )
    thumbs = await task_repo.first_thumbnails(db, [row["id"] for row in rows])
    items = []
    for row in rows:
        thumb = thumbs.get(row["id"])
        thumbnail_url = None
        if thumb and thumb["hasThumb"] == "1":
            version = f"&v={thumb['versionId']}" if thumb.get("versionId") else ""
            thumbnail_url = (
                f"/api/tasks/{row['id']}/shots/{thumb['shotId']}/image?variant=thumb{version}"
            )
        items.append(
            {
                "id": row["id"],
                "name": row["name"],
                "characterName": row["character_name"],
                "mode": row["mode"],
                "status": row["status"],
                "shotsCount": int(row["shots_count"]),
                "issueCount": int(row["issue_count"]),
                "unknownCount": int(row["unknown_count"]),
                "suggestionCount": int(row["suggestion_count"]),
                "thumbnailUrl": thumbnail_url,
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "completedAt": row["completed_at"],
            }
        )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def update_task(
    db: Database,
    task_id: str,
    *,
    name: str | None = None,
    character_name: str | None = None,
    profile_raw: str | None = None,
    script_raw: str | None = None,
    default_batch_size: int | None = None,
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    _ensure_editable(task)

    fields: dict[str, Any] = {}
    if name is not None:
        fields["name"] = name.strip()[:100] or task["name"]
    if character_name is not None:
        fields["character_name"] = character_name.strip()[:50]
    if profile_raw is not None:
        fields["profile_raw"] = profile_raw.strip()
        # 设定变化后旧的权威解析结果失效，待后续阶段重新解析
        fields["profile_json"] = None
    if script_raw is not None:
        fields["script_raw"] = script_raw.strip()
        fields["script_context_json"] = None
    if default_batch_size is not None:
        fields["default_batch_size"] = default_batch_size
    if fields:
        await task_repo.update_task(db, task_id, fields)
    return await get_task_detail(db, task_id)


async def delete_task(db: Database, settings: Settings, task_id: str) -> None:
    task = await _task_or_404(db, task_id)
    if task["status"] in ("running", "retrying"):
        raise AppError("conflict", "任务正在分析，请先取消后再删除。", status_code=409)
    await task_repo.delete_task(db, task_id)
    await asyncio.to_thread(file_service.remove_task_files, settings, task_id)
    logger.info("已删除任务 %s", task_id)


async def validate_task(db: Database, task_id: str) -> dict[str, Any]:
    detail = await get_task_detail(db, task_id)
    return {
        "ready": detail["validation"]["ready"],
        "missing": detail["validation"]["missing"],
        "shots": len(detail["shots"]),
        "totalBytes": sum(shot["fileSize"] or 0 for shot in detail["shots"]),
    }


# ---- 镜头 ----------------------------------------------------
@dataclass(slots=True)
class _PreparedShot:
    shot_id: str
    filename: str
    processed: image_service.ProcessedImage
    paths: dict[str, str]
    duplicate_of: str | None = None


def _existing_hashes(settings: Settings, pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    import hashlib

    result: dict[str, str] = {}
    for shot_code, relative_path in pairs:
        try:
            path = file_service.resolve_data_path(settings, relative_path)
            if path.is_file():
                result[hashlib.sha256(path.read_bytes()).hexdigest()] = shot_code
        except Exception:  # 文件缺失/不可读时不做重复判断
            continue
    return result


async def add_shots(
    db: Database,
    settings: Settings,
    task_id: str,
    uploads: Sequence[tuple[str, bytes]],
) -> dict[str, Any]:
    """批量上传；单张失败隔离，成功项照常入库。"""
    task = await _task_or_404(db, task_id)
    _ensure_editable(task)

    existing_pairs = await shot_repo.list_original_hashes(db, task_id)
    known_hashes = await asyncio.to_thread(_existing_hashes, settings, existing_pairs)
    prepared: list[_PreparedShot] = []
    errors: list[dict[str, str]] = []
    duplicates: list[dict[str, str]] = []

    for filename, data in uploads:
        try:
            processed = image_service.process_upload(data, filename, settings.upload_max_mb)
        except image_service.ImageValidationError as exc:
            errors.append({"filename": filename, "code": exc.code, "message": exc.message})
            continue

        duplicate_of = known_hashes.get(processed.sha256)
        shot_id = new_id("shot")
        try:
            paths = await asyncio.to_thread(
                file_service.save_shot_images, settings, task_id, shot_id, processed
            )
        except OSError as exc:
            logger.error("保存镜头文件失败：%s", type(exc).__name__)
            errors.append(
                {
                    "filename": filename,
                    "code": "storage_error",
                    "message": "文件写入失败，请检查磁盘空间后重试。",
                }
            )
            continue

        known_hashes[processed.sha256] = duplicate_of or filename
        if duplicate_of:
            duplicates.append({"filename": filename, "duplicateOf": duplicate_of})
        prepared.append(
            _PreparedShot(
                shot_id=shot_id,
                filename=filename,
                processed=processed,
                paths=paths,
                duplicate_of=duplicate_of,
            )
        )

    if not prepared:
        return {"shots": [], "errors": errors, "duplicates": duplicates}

    try:
        async with db.transaction() as conn:
            status_row = await (
                await conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
            ).fetchone()
            if status_row is None:
                raise AppError("not_found", _MISSING_TASK, status_code=404)
            if status_row["status"] not in EDITABLE_STATUSES:
                raise AppError("conflict", EDITABLE_HINT, status_code=409)

            seq = await shot_repo.next_seq(conn, task_id)
            for item in prepared:
                code = f"S{seq}"
                quality = "warn" if item.processed.warnings else "ok"
                await shot_repo.insert_shot(
                    conn,
                    shot_id=item.shot_id,
                    task_id=task_id,
                    seq=seq,
                    shot_code=code,
                    original_filename=item.filename,
                    original_path=item.paths["original"],
                    analysis_path=item.paths["analysis"],
                    thumb_path=item.paths["thumb"],
                    width=item.processed.width,
                    height=item.processed.height,
                    file_size=len(item.processed.original_bytes),
                    mime_type=item.processed.mime_type,
                    note="",
                    quality_status=quality,
                    quality_warnings_json=(
                        json.dumps(item.processed.warnings, ensure_ascii=False)
                        if item.processed.warnings
                        else None
                    ),
                )
                await shot_repo.insert_original_version(
                    conn,
                    version_id=new_id("ver"),
                    shot_id=item.shot_id,
                    image_path=item.paths["original"],
                    width=item.processed.width,
                    height=item.processed.height,
                    file_size=len(item.processed.original_bytes),
                )
                seq += 1
            await conn.execute(
                "UPDATE tasks SET updated_at = ? WHERE id = ?", (now_iso(), task_id)
            )
    except Exception:
        # 数据库失败时清理已写文件，避免孤儿目录
        for item in prepared:
            await asyncio.to_thread(
                file_service.remove_shot_files, settings, task_id, item.shot_id
            )
        raise

    shots = await shot_repo.get_shots(db, task_id)
    accepted_ids = {item.shot_id for item in prepared}
    return {
        "shots": [_shot_dict(shot) for shot in shots if shot["id"] in accepted_ids],
        "errors": errors,
        "duplicates": duplicates,
    }


async def update_shot_note(
    db: Database, task_id: str, shot_id: str, note: str
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    _ensure_editable(task)
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)
    await shot_repo.update_note(db, task_id, shot_id, note)
    detail = await get_task_detail(db, task_id)
    updated = next((item for item in detail["shots"] if item["id"] == shot_id), None)
    return {"shot": updated}


async def reorder_shots(
    db: Database, task_id: str, ordered_ids: Sequence[str]
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    _ensure_editable(task)
    shots = await shot_repo.get_shots(db, task_id)
    current_ids = [shot["id"] for shot in shots]
    if len(ordered_ids) != len(current_ids) or set(ordered_ids) != set(current_ids):
        raise AppError(
            "invalid_request", "排序列表必须包含全部镜头且不能重复。", status_code=400
        )
    async with db.transaction() as conn:
        await shot_repo.reorder_shots(conn, task_id, ordered_ids)
        await conn.execute(
            "UPDATE tasks SET updated_at = ? WHERE id = ?", (now_iso(), task_id)
        )
    return await get_task_detail(db, task_id)


async def delete_shot(
    db: Database, settings: Settings, task_id: str, shot_id: str
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    _ensure_editable(task)
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)

    async with db.transaction() as conn:
        await shot_repo.delete_shot(conn, task_id, shot_id)
        remaining = await (
            await conn.execute(
                "SELECT id FROM shots WHERE task_id = ? ORDER BY seq", (task_id,)
            )
        ).fetchall()
        await shot_repo.reorder_shots(
            conn, task_id, [row["id"] for row in remaining]
        )
        await conn.execute(
            "UPDATE tasks SET updated_at = ? WHERE id = ?", (now_iso(), task_id)
        )
    await asyncio.to_thread(file_service.remove_shot_files, settings, task_id, shot_id)
    return await get_task_detail(db, task_id)


async def replace_shot(
    db: Database,
    settings: Settings,
    task_id: str,
    shot_id: str,
    filename: str,
    data: bytes,
) -> dict[str, Any]:
    task = await _task_or_404(db, task_id)
    _ensure_editable(task)
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)

    try:
        processed = image_service.process_upload(data, filename, settings.upload_max_mb)
    except image_service.ImageValidationError as exc:
        raise AppError(exc.code, exc.message, status_code=400) from exc

    paths = await asyncio.to_thread(
        file_service.replace_shot_images, settings, task_id, shot_id, processed
    )
    version_id = new_id("ver")
    quality = "warn" if processed.warnings else "ok"
    async with db.transaction() as conn:
        await shot_repo.clear_current_versions(conn, shot_id)
        await shot_repo.update_shot_files(
            conn,
            shot_id=shot_id,
            original_filename=filename,
            original_path=paths["original"],
            analysis_path=paths["analysis"],
            thumb_path=paths["thumb"],
            width=processed.width,
            height=processed.height,
            file_size=len(processed.original_bytes),
            mime_type=processed.mime_type,
            quality_status=quality,
            quality_warnings_json=(
                json.dumps(processed.warnings, ensure_ascii=False)
                if processed.warnings
                else None
            ),
        )
        await shot_repo.insert_original_version(
            conn,
            version_id=version_id,
            shot_id=shot_id,
            image_path=paths["original"],
            width=processed.width,
            height=processed.height,
            file_size=len(processed.original_bytes),
        )
        await conn.execute(
            "UPDATE tasks SET updated_at = ? WHERE id = ?", (now_iso(), task_id)
        )
    detail = await get_task_detail(db, task_id)
    replaced = next((item for item in detail["shots"] if item["id"] == shot_id), None)
    return {"shot": replaced}


async def get_shot_image(
    db: Database, settings: Settings, task_id: str, shot_id: str, variant: str
) -> FileResponse:
    shot = await shot_repo.get_shot(db, task_id, shot_id)
    if shot is None:
        raise AppError("not_found", "镜头不存在。", status_code=404)

    if variant == "original":
        relative = shot["original_path"]
    elif variant == "analysis":
        relative = shot["analysis_path"]
    elif variant == "thumb":
        # 缩略图始终代表镜头当前展示版本：未采用时是原图，采用后是采用图缩略图。
        version = await shot_repo.get_current_version(db, shot_id)
        if version and version["kind"] == "adopted":
            candidate = None
            if version["source_generation_id"] and version["source_candidate_id"]:
                candidate = await generation_repo.get_candidate(
                    db, version["source_generation_id"], version["source_candidate_id"]
                )
            relative = (
                (candidate["thumb_path"] if candidate else None)
                or version["image_path"]
                or shot["thumb_path"]
            )
        else:
            relative = shot["thumb_path"]
    elif variant == "current":
        version = await shot_repo.get_current_version(db, shot_id)
        relative = version["image_path"] if version else shot["original_path"]
    else:
        raise AppError("invalid_request", "不支持的文件类型。", status_code=400)

    if not relative:
        raise AppError("file_unavailable", "该镜头文件不可用。", status_code=404)
    try:
        path = file_service.resolve_data_path(settings, relative)
    except AppError:
        raise AppError("file_unavailable", "该镜头文件不可用。", status_code=404) from None
    if not path.is_file():
        raise AppError("file_unavailable", "该镜头文件不可用。", status_code=404)

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


# ---- 存档概况 ------------------------------------------------
def _directory_size(root: Path) -> int:
    total = 0
    for base, _dirs, files in os.walk(root):
        for name in files:
            try:
                total += (Path(base) / name).stat().st_size
            except OSError:
                continue
    return total


async def archive_summary(db: Database, settings: Settings) -> dict[str, Any]:
    counts = await task_repo.archive_counts(db)
    data_bytes = await asyncio.to_thread(_directory_size, settings.data_dir)
    try:
        db_bytes = settings.db_path.stat().st_size if settings.db_path.exists() else 0
    except OSError:
        db_bytes = 0
    return {
        "liveTasks": int(counts.get("live_tasks") or 0),
        "demoTasks": int(counts.get("demo_tasks") or 0),
        "reports": int(counts.get("reports") or 0),
        "generations": int(counts.get("generations") or 0),
        "candidates": int(counts.get("candidates") or 0),
        "storageBytes": data_bytes + db_bytes,
        "storageLocation": "local",
        "earliest": counts.get("earliest"),
    }
