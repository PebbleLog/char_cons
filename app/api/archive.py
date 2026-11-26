"""历史存档概况。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..services import task_service
from .deps import get_db, get_settings

router = APIRouter(prefix="/api/archive", tags=["archive"])


@router.get("/summary")
async def archive_summary(request: Request) -> dict:
    return await task_service.archive_summary(
        get_db(request), get_settings(request)
    )
