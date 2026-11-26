"""候选采用记录持久化（技术方案 6.3.13）。"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from ..core.timeutil import now_iso
from .database import Database


async def insert(
    conn: aiosqlite.Connection,
    *,
    adoption_id: str,
    task_id: str,
    shot_id: str,
    generation_id: str,
    candidate_id: str,
    precheck_overall: str | None,
    overridden_precheck: bool,
    original_version_id: str | None,
    new_version_id: str,
    recheck_status: str,
) -> None:
    now = now_iso()
    await conn.execute(
        """
        INSERT INTO adoptions (
            id, task_id, shot_id, generation_id, candidate_id, adopted_at,
            adopted_by, precheck_overall, overridden_precheck,
            original_version_id, new_version_id, recheck_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'local-user', ?, ?, ?, ?, ?, ?)
        """,
        (
            adoption_id, task_id, shot_id, generation_id, candidate_id, now,
            precheck_overall, 1 if overridden_precheck else 0,
            original_version_id, new_version_id, recheck_status, now,
        ),
    )


async def update_recheck(
    db: Database,
    adoption_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        """
        UPDATE adoptions SET recheck_status = ?, recheck_at = ?,
            recheck_result_json = ?
        WHERE id = ?
        """,
        (
            status,
            now_iso(),
            json.dumps(result, ensure_ascii=False) if result is not None else None,
            adoption_id,
        ),
    )


async def latest_for_shot(db: Database, task_id: str, shot_id: str) -> aiosqlite.Row | None:
    return await db.fetchone(
        "SELECT * FROM adoptions WHERE task_id = ? AND shot_id = ? "
        "ORDER BY rowid DESC LIMIT 1",
        (task_id, shot_id),
    )


async def list_for_task(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM adoptions WHERE task_id = ? ORDER BY rowid", (task_id,)
    )


async def latest_by_shot(db: Database, task_id: str) -> dict[str, aiosqlite.Row]:
    rows = await list_for_task(db, task_id)
    result: dict[str, aiosqlite.Row] = {}
    for row in rows:
        result[row["shot_id"]] = row
    return result
