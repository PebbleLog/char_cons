"""任务事件写入（技术方案 6.3.15）。

事件只存脱敏数据：禁止写入 API Key、图片内容、完整提示词中的敏感信息。
"""

from __future__ import annotations

import json
from typing import Any

from ..core.timeutil import now_iso
from .database import Database


async def insert_event(
    db: Database,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    task_id: str | None = None,
    request_id: str | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO events (task_id, type, payload_json, request_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            task_id,
            event_type,
            json.dumps(payload, ensure_ascii=False) if payload is not None else None,
            request_id,
            now_iso(),
        ),
    )
