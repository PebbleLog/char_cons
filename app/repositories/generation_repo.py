"""生成记录与候选图持久化（技术方案 6.3.11 / 6.3.12）。"""

from __future__ import annotations

import json
from typing import Any, Sequence

import aiosqlite

from ..core.timeutil import now_iso
from .database import Database


async def next_generation_id(conn: aiosqlite.Connection, task_id: str) -> str:
    # GEN-xxx 是全局主键，多个任务不能各自从 001 开始。
    rows = await (
        await conn.execute(
            "SELECT id FROM generation_records WHERE id LIKE 'GEN-%'"
        )
    ).fetchall()
    numbers: list[int] = []
    for row in rows:
        try:
            numbers.append(int(str(row["id"]).split("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return f"GEN-{max(numbers, default=0) + 1:03d}"


async def create_record(
    conn: aiosqlite.Connection,
    *,
    generation_id: str,
    task_id: str,
    shot_id: str,
    issue_ids: Sequence[str],
    provider: str,
    model: str,
    prompt: str,
    negative_prompt: str | None,
    reference_shot_ids: Sequence[str],
    requested_count: int,
    supported_params: dict[str, Any],
) -> None:
    now = now_iso()
    await conn.execute(
        """
        INSERT INTO generation_records (
            id, task_id, shot_id, issue_ids_json, provider, model, prompt,
            negative_prompt, negative_prompt_mode, reference_shot_ids_json,
            requested_count, supported_params_json, status, precheck_status,
            started_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'merged', ?, ?, ?, 'generating',
                  'pending', ?, ?, ?)
        """,
        (
            generation_id,
            task_id,
            shot_id,
            json.dumps(list(issue_ids), ensure_ascii=False),
            provider,
            model,
            prompt,
            negative_prompt,
            json.dumps(list(reference_shot_ids), ensure_ascii=False),
            requested_count,
            json.dumps(supported_params, ensure_ascii=False),
            now,
            now,
            now,
        ),
    )


async def update_record(db: Database, generation_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": now_iso()}
    assignments = ", ".join(f"{key} = ?" for key in fields)
    await db.execute(
        f"UPDATE generation_records SET {assignments} WHERE id = ?",
        [*fields.values(), generation_id],
    )


async def get(db: Database, task_id: str, generation_id: str) -> aiosqlite.Row | None:
    return await db.fetchone(
        "SELECT * FROM generation_records WHERE task_id = ? AND id = ?",
        (task_id, generation_id),
    )


async def latest_for_shot(
    db: Database, task_id: str, shot_id: str
) -> aiosqlite.Row | None:
    return await db.fetchone(
        "SELECT * FROM generation_records WHERE task_id = ? AND shot_id = ? "
        "ORDER BY rowid DESC LIMIT 1",
        (task_id, shot_id),
    )


async def list_for_task(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM generation_records WHERE task_id = ? ORDER BY rowid",
        (task_id,),
    )


async def insert_candidate(
    conn: aiosqlite.Connection,
    *,
    candidate_id: str,
    generation_id: str,
    candidate_index: int,
    candidate_code: str,
    provider_request_id: str | None,
    remote_url: str | None,
    local_path: str,
    thumb_path: str | None,
    width: int | None,
    height: int | None,
    seed: int | None,
    elapsed_ms: int | None,
) -> None:
    await conn.execute(
        """
        INSERT INTO generation_candidates (
            id, generation_id, candidate_index, candidate_code,
            provider_request_id, remote_url, local_path, thumb_path,
            width, height, seed, elapsed_ms, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            generation_id,
            candidate_index,
            candidate_code,
            provider_request_id,
            remote_url,
            local_path,
            thumb_path,
            width,
            height,
            seed,
            elapsed_ms,
            now_iso(),
        ),
    )


async def list_candidates(
    db: Database, generation_id: str
) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM generation_candidates WHERE generation_id = ? "
        "ORDER BY candidate_index",
        (generation_id,),
    )


async def get_candidate(
    db: Database, generation_id: str, candidate_id: str
) -> aiosqlite.Row | None:
    return await db.fetchone(
        "SELECT * FROM generation_candidates WHERE generation_id = ? AND id = ?",
        (generation_id, candidate_id),
    )


async def update_candidate(
    conn: aiosqlite.Connection, candidate_id: str, **fields: Any
) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{key} = ?" for key in fields)
    await conn.execute(
        f"UPDATE generation_candidates SET {assignments} WHERE id = ?",
        [*fields.values(), candidate_id],
    )


async def mark_adopted(conn: aiosqlite.Connection, candidate_id: str, adopted_at: str) -> None:
    await conn.execute(
        "UPDATE generation_candidates SET adopted = 1, adopted_at = ? WHERE id = ?",
        (adopted_at, candidate_id),
    )


async def recover_interrupted(db: Database) -> int:
    """服务重启后把未完成的生成/预检标记为失败，保留已返回候选。"""
    rows = await db.fetchall(
        "SELECT id FROM generation_records WHERE status IN ('pending', 'generating', 'prechecking')"
    )
    if not rows:
        return 0
    now = now_iso()
    await db.execute(
        """
        UPDATE generation_records SET status = 'failed',
            precheck_status = CASE WHEN precheck_status = 'running' THEN 'failed'
                                   ELSE precheck_status END,
            error_code = COALESCE(error_code, 'interrupted_on_restart'),
            error_message = COALESCE(error_message, '服务重启，生成已中断，可重新生成。'),
            finished_at = COALESCE(finished_at, ?), updated_at = ?
        WHERE status IN ('pending', 'generating', 'prechecking')
        """,
        (now, now),
    )
    return len(rows)
