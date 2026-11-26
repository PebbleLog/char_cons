"""单镜头观察持久化。"""

from __future__ import annotations

from typing import Any, Sequence

import aiosqlite

from ..core.timeutil import now_iso
from .database import Database


async def delete_for_task(db: Database, task_id: str) -> None:
    await db.execute("DELETE FROM observations WHERE task_id = ?", (task_id,))


async def delete_for_version(db: Database, version_id: str) -> None:
    await db.execute("DELETE FROM observations WHERE version_id = ?", (version_id,))


async def insert_many(conn: aiosqlite.Connection, rows: Sequence[dict[str, Any]]) -> None:
    now = now_iso()
    await conn.executemany(
        """
        INSERT INTO observations (
            id, task_id, shot_id, version_id, attribute_id, observed_value,
            visibility, visibility_reason, evidence, confidence,
            subject_json, raw_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["id"],
                row["task_id"],
                row["shot_id"],
                row["version_id"],
                row["attribute_id"],
                row["observed_value"],
                row["visibility"],
                row["visibility_reason"],
                row["evidence"],
                row["confidence"],
                row["subject_json"],
                row["raw_json"],
                now,
            )
            for row in rows
        ],
    )


async def list_for_shot_version(
    db: Database, shot_id: str, version_id: str
) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM observations WHERE shot_id = ? AND version_id = ? "
        "ORDER BY rowid",
        (shot_id, version_id),
    )


async def list_for_task_current(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """
        SELECT o.*, s.shot_code, s.seq
        FROM observations o
        JOIN shots s ON s.id = o.shot_id
        WHERE o.task_id = ? AND o.version_id = s.current_version_id
        ORDER BY s.seq
        """,
        (task_id,),
    )
