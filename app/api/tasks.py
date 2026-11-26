"""任务与镜头接口（技术方案 7.2 的子集，阶段二范围）。"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, File, Query, Request, Response, UploadFile

from ..core.constants import TASK_STATUSES
from ..core.errors import AppError
from ..models.api import ShotNoteUpdate, ShotReorder, TaskCreate, TaskUpdate
from ..services import task_service
from .deps import get_db, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", status_code=201)
async def create_task(request: Request, payload: TaskCreate) -> dict:
    db = get_db(request)
    return await task_service.create_task(
        db,
        name=payload.name,
        character_name=payload.character_name,
        profile_raw=payload.profile_raw,
        script_raw=payload.script_raw,
        default_batch_size=payload.default_batch_size,
    )


@router.get("")
async def list_tasks(
    request: Request,
    mode: Literal["live", "demo"] = "live",
    status: str | None = Query(default=None, max_length=32),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    statuses = None
    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        invalid = [item for item in statuses if item not in TASK_STATUSES]
        if invalid or not statuses:
            raise AppError(
                "invalid_request",
                f"不支持的任务状态：{', '.join(invalid) or status}",
                status_code=400,
            )
    return await task_service.list_tasks(
        get_db(request),
        mode=mode,
        statuses=statuses,
        query=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}")
async def get_task(request: Request, task_id: str) -> dict:
    return await task_service.get_task_detail(get_db(request), task_id)


@router.patch("/{task_id}")
async def update_task(request: Request, task_id: str, payload: TaskUpdate) -> dict:
    return await task_service.update_task(
        get_db(request),
        task_id,
        name=payload.name,
        character_name=payload.character_name,
        profile_raw=payload.profile_raw,
        script_raw=payload.script_raw,
        default_batch_size=payload.default_batch_size,
    )


@router.delete("/{task_id}", status_code=204)
async def delete_task(request: Request, task_id: str) -> Response:
    await task_service.delete_task(get_db(request), get_settings(request), task_id)
    return Response(status_code=204)


@router.post("/{task_id}/validate")
async def validate_task(request: Request, task_id: str) -> dict:
    return await task_service.validate_task(get_db(request), task_id)


@router.post("/{task_id}/shots")
async def upload_shots(
    request: Request,
    task_id: str,
    files: list[UploadFile] = File(...),
) -> dict:
    if not files:
        raise AppError("invalid_request", "请至少选择 1 张镜头图片。", status_code=400)
    max_bytes = get_settings(request).upload_max_mb * 1024 * 1024

    uploads: list[tuple[str, bytes]] = []
    errors: list[dict[str, str]] = []
    for upload in files:
        filename = (upload.filename or "未命名").strip() or "未命名"
        size = getattr(upload, "size", None)
        if size is not None and size > max_bytes:
            errors.append(
                {
                    "filename": filename,
                    "code": "unsupported_file",
                    "message": f"文件超过单张 {get_settings(request).upload_max_mb} MB 上限。",
                }
            )
            await upload.close()
            continue
        try:
            data = await upload.read()
        finally:
            await upload.close()
        uploads.append((filename, data))

    result = await task_service.add_shots(
        get_db(request), get_settings(request), task_id, uploads
    )
    result["errors"] = errors + result["errors"]
    return result


@router.post("/{task_id}/shots/reorder")
async def reorder_shots(request: Request, task_id: str, payload: ShotReorder) -> dict:
    return await task_service.reorder_shots(
        get_db(request), task_id, payload.shot_ids
    )


@router.patch("/{task_id}/shots/{shot_id}")
async def update_shot_note(
    request: Request, task_id: str, shot_id: str, payload: ShotNoteUpdate
) -> dict:
    return await task_service.update_shot_note(
        get_db(request), task_id, shot_id, payload.note
    )


@router.post("/{task_id}/shots/{shot_id}/replace")
async def replace_shot(
    request: Request,
    task_id: str,
    shot_id: str,
    file: UploadFile = File(...),
) -> dict:
    filename = (file.filename or "未命名").strip() or "未命名"
    try:
        data = await file.read()
    finally:
        await file.close()
    return await task_service.replace_shot(
        get_db(request),
        get_settings(request),
        task_id,
        shot_id,
        filename,
        data,
    )


@router.delete("/{task_id}/shots/{shot_id}")
async def delete_shot(request: Request, task_id: str, shot_id: str) -> dict:
    return await task_service.delete_shot(
        get_db(request), get_settings(request), task_id, shot_id
    )


@router.get("/{task_id}/shots/{shot_id}/image")
async def get_shot_image(
    request: Request,
    task_id: str,
    shot_id: str,
    variant: Literal["original", "analysis", "thumb", "current"] = "original",
):
    return await task_service.get_shot_image(
        get_db(request), get_settings(request), task_id, shot_id, variant
    )
