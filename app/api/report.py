"""结构化检测报告接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response

from ..services import export_service, report_service
from .deps import get_db

router = APIRouter(prefix="/api/tasks", tags=["report"])


@router.get("/{task_id}/report")
async def get_report(request: Request, task_id: str) -> dict:
    return await report_service.build_report(get_db(request), task_id)


@router.get("/{task_id}/export")
async def export_report(
    request: Request,
    task_id: str,
    format: Literal["md", "json"] = "md",
) -> Response:
    content, media_type, filename = await export_service.build_export(
        get_db(request), task_id, format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": export_service.content_disposition(filename),
            "Cache-Control": "no-store",
        },
    )
