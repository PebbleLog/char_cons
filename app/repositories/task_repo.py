"""任务持久化查询。业务规则在 services/task_service。"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import aiosqlite

from ..core.timeutil import now_iso
from .database import Database
from .event_repo import insert_event

logger = logging.getLogger(__name__)


async def recover_interrupted_tasks(db: Database) -> int:
    """进程启动时把 running/retrying 任务标记为 paused（技术方案 5.5）。"""
    rows = await db.fetchall(
        "SELECT id FROM tasks WHERE status IN ('running', 'retrying')"
    )
    if not rows:
        return 0
    task_ids = [row["id"] for row in rows]
    async with db.transaction() as conn:
        await conn.execute(
            "UPDATE tasks SET status = 'paused', updated_at = ? "
            "WHERE status IN ('running', 'retrying')",
            (now_iso(),),
        )
    for task_id in task_ids:
        await insert_event(
            db,
            "analysis.interrupted_on_restart",
            {"from": "running/retrying", "to": "paused"},
            task_id=task_id,
        )
    logger.warning("启动恢复：%d 个任务已标记为 paused，需用户手动重试", len(task_ids))
    return len(task_ids)


async def get_task(db: Database, task_id: str) -> aiosqlite.Row | None:
    return await db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))


async def list_tasks(
    db: Database,
    *,
    mode: str = "live",
    statuses: Sequence[str] | None = None,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[aiosqlite.Row], int]:
    where = ["t.mode = ?"]
    params: list[Any] = [mode]
    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        where.append(f"t.status IN ({placeholders})")
        params.extend(statuses)
    if query:
        where.append("(t.name LIKE ? OR COALESCE(t.character_name, '') LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])
    where_sql = " AND ".join(where)

    total_row = await db.fetchone(
        f"SELECT COUNT(*) AS total FROM tasks t WHERE {where_sql}", params
    )
    rows = await db.fetchall(
        f"""
        SELECT t.*,
               (SELECT COUNT(*) FROM shots s WHERE s.task_id = t.id) AS shots_count,
               (SELECT COUNT(*) FROM issues i
                 WHERE i.task_id = t.id AND i.status = 'open') AS issue_count,
               (SELECT COUNT(*) FROM unknown_items u
                 WHERE u.task_id = t.id) AS unknown_count,
               (SELECT COUNT(*) FROM suggestions g
                 WHERE g.task_id = t.id) AS suggestion_count
        FROM tasks t
        WHERE {where_sql}
        ORDER BY t.updated_at DESC, t.created_at DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    )
    return rows, int(total_row["total"]) if total_row else 0


async def first_thumbnails(db: Database, task_ids: Sequence[str]) -> dict[str, dict[str, str]]:
    """返回每个任务第一个镜头的缩略图地址所需信息。"""
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = await db.fetchall(
        f"""
        SELECT s.task_id, s.id AS shot_id, s.thumb_path, s.current_version_id
        FROM shots s
        WHERE s.task_id IN ({placeholders})
        ORDER BY s.task_id, s.seq
        """,
        list(task_ids),
    )
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        if row["task_id"] not in result:
            result[row["task_id"]] = {
                "shotId": row["shot_id"],
                "hasThumb": "1" if row["thumb_path"] else "0",
                "versionId": row["current_version_id"],
            }
    return result


async def update_task(db: Database, task_id: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": now_iso()}
    assignments = ", ".join(f"{key} = ?" for key in fields)
    await db.execute(
        f"UPDATE tasks SET {assignments} WHERE id = ?",
        [*fields.values(), task_id],
    )


async def delete_task(db: Database, task_id: str) -> None:
    await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


async def archive_counts(db: Database) -> dict[str, Any]:
    rows = await db.fetchall(
        """
        SELECT
            (SELECT COUNT(*) FROM tasks WHERE mode = 'live') AS live_tasks,
            (SELECT COUNT(*) FROM tasks WHERE mode = 'demo') AS demo_tasks,
            (SELECT COUNT(*) FROM tasks WHERE mode = 'live'
                AND status IN ('completed', 'partial')) AS reports,
            (SELECT COUNT(*) FROM generation_records g
                JOIN tasks t ON t.id = g.task_id WHERE t.mode = 'live') AS generations,
            (SELECT COUNT(*) FROM generation_candidates c
                JOIN generation_records g ON g.id = c.generation_id
                JOIN tasks t ON t.id = g.task_id WHERE t.mode = 'live') AS candidates,
            (SELECT MIN(created_at) FROM tasks WHERE mode = 'live') AS earliest
        """
    )
    row = rows[0] if rows else None
    if row is None:  # pragma: no cover - 聚合查询总会返回一行
        return {}
    return {key: row[key] for key in row.keys()}
