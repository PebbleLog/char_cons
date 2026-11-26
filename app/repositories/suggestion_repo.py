"""修正建议持久化（技术方案 6.3.10）。"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from ..core.timeutil import now_iso
from .database import Database


async def get_for_issue(db: Database, task_id: str, issue_id: str) -> aiosqlite.Row | None:
    return await db.fetchone(
        "SELECT * FROM suggestions WHERE task_id = ? AND issue_id = ? "
        "ORDER BY rowid DESC LIMIT 1",
        (task_id, issue_id),
    )


async def list_for_task(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM suggestions WHERE task_id = ? ORDER BY rowid", (task_id,)
    )


async def delete_for_shot(db: Database, task_id: str, shot_id: str) -> None:
    await db.execute(
        "DELETE FROM suggestions WHERE task_id = ? AND shot_id = ?",
        (task_id, shot_id),
    )


async def upsert(
    conn: aiosqlite.Connection,
    *,
    task_id: str,
    issue_id: str,
    shot_id: str,
    revised_prompt: str,
    negative_prompt: str | None,
    key_points: list[str],
    reference_shots: list[str],
    rationale: str,
    card_draw_plan: dict[str, Any],
    status: str = "ready",
    prompt_version: str | None = None,
    error_message: str | None = None,
    source: str = "ai",
) -> str:
    now = now_iso()
    existing = await (
        await conn.execute(
            "SELECT id FROM suggestions WHERE task_id = ? AND issue_id = ? "
            "ORDER BY rowid DESC LIMIT 1",
            (task_id, issue_id),
        )
    ).fetchone()
    values = (
        revised_prompt,
        negative_prompt,
        "merged",
        json.dumps(key_points, ensure_ascii=False),
        json.dumps(reference_shots, ensure_ascii=False),
        rationale,
        json.dumps(card_draw_plan, ensure_ascii=False),
        status,
        prompt_version,
        error_message,
        source,
        now,
    )
    if existing:
        suggestion_id = existing["id"]
        await conn.execute(
            """
            UPDATE suggestions SET revised_prompt = ?, negative_prompt = ?,
                negative_prompt_mode = ?, key_points_json = ?, reference_shots_json = ?,
                rationale = ?, card_draw_plan_json = ?, status = ?, prompt_version = ?,
                error_message = ?, source = ?, updated_at = ?
            WHERE id = ?
            """,
            (*values, suggestion_id),
        )
        return suggestion_id

    rows = await (
        await conn.execute(
            "SELECT id FROM suggestions WHERE id LIKE 'SUG-%'"
        )
    ).fetchall()
    numbers = []
    for row in rows:
        try:
            numbers.append(int(str(row["id"]).split("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    suggestion_id = f"SUG-{max(numbers, default=0) + 1:03d}"
    await conn.execute(
        """
        INSERT INTO suggestions (
            id, task_id, issue_id, shot_id, revised_prompt, negative_prompt,
            negative_prompt_mode, key_points_json, reference_shots_json, rationale,
            card_draw_plan_json, status, prompt_version, error_message, source,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            suggestion_id, task_id, issue_id, shot_id,
            *values[:-1],
            now,
            now,
        ),
    )
    return suggestion_id
