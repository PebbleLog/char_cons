"""镜头与镜头版本持久化。"""

from __future__ import annotations

from typing import Any, Sequence

import aiosqlite

from ..core.timeutil import now_iso
from .database import Database


async def get_shots(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM shots WHERE task_id = ? ORDER BY seq", (task_id,)
    )


async def get_shot(db: Database, task_id: str, shot_id: str) -> aiosqlite.Row | None:
    return await db.fetchone(
        "SELECT * FROM shots WHERE task_id = ? AND id = ?", (task_id, shot_id)
    )


async def count_shots(db: Database, task_id: str) -> int:
    row = await db.fetchone(
        "SELECT COUNT(*) AS total FROM shots WHERE task_id = ?", (task_id,)
    )
    return int(row["total"]) if row else 0


async def insert_shot(
    conn: aiosqlite.Connection,
    *,
    shot_id: str,
    task_id: str,
    seq: int,
    shot_code: str,
    original_filename: str,
    original_path: str,
    analysis_path: str,
    thumb_path: str,
    width: int,
    height: int,
    file_size: int,
    mime_type: str,
    note: str,
    quality_status: str,
    quality_warnings_json: str | None,
) -> None:
    now = now_iso()
    await conn.execute(
        """
        INSERT INTO shots (
            id, task_id, seq, shot_code, original_filename, original_path,
            analysis_path, thumb_path, width, height, file_size, mime_type,
            note, quality_status, quality_warnings_json,
            analysis_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  'pending', ?, ?)
        """,
        (
            shot_id,
            task_id,
            seq,
            shot_code,
            original_filename,
            original_path,
            analysis_path,
            thumb_path,
            width,
            height,
            file_size,
            mime_type,
            note,
            quality_status,
            quality_warnings_json,
            now,
            now,
        ),
    )


async def insert_original_version(
    conn: aiosqlite.Connection,
    *,
    version_id: str,
    shot_id: str,
    image_path: str,
    width: int,
    height: int,
    file_size: int,
) -> None:
    await conn.execute(
        """
        INSERT INTO shot_versions (
            id, shot_id, kind, image_path, width, height, file_size,
            is_current, created_at
        ) VALUES (?, ?, 'original', ?, ?, ?, ?, 1, ?)
        """,
        (version_id, shot_id, image_path, width, height, file_size, now_iso()),
    )
    await conn.execute(
        "UPDATE shots SET current_version_id = ?, updated_at = ? WHERE id = ?",
        (version_id, now_iso(), shot_id),
    )


async def next_seq(conn: aiosqlite.Connection, task_id: str) -> int:
    cursor = await conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 AS next FROM shots WHERE task_id = ?",
        (task_id,),
    )
    row = await cursor.fetchone()
    return int(row["next"])


async def reorder_shots(conn: aiosqlite.Connection, task_id: str, ordered_ids: Sequence[str]) -> None:
    # 先改为负序号 + 临时编号，避免 UNIQUE(task_id, seq/shot_code) 在交换过程中冲突
    await conn.execute(
        "UPDATE shots SET seq = -seq, shot_code = id WHERE task_id = ?", (task_id,)
    )
    now = now_iso()
    for index, shot_id in enumerate(ordered_ids, start=1):
        await conn.execute(
            "UPDATE shots SET seq = ?, shot_code = ?, updated_at = ? "
            "WHERE task_id = ? AND id = ?",
            (index, f"S{index}", now, task_id, shot_id),
        )


async def delete_shot(conn: aiosqlite.Connection, task_id: str, shot_id: str) -> None:
    await conn.execute(
        "DELETE FROM shots WHERE task_id = ? AND id = ?", (task_id, shot_id)
    )


async def update_shot_files(
    conn: aiosqlite.Connection,
    *,
    shot_id: str,
    original_filename: str,
    original_path: str,
    analysis_path: str,
    thumb_path: str,
    width: int,
    height: int,
    file_size: int,
    mime_type: str,
    quality_status: str,
    quality_warnings_json: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE shots SET
            original_filename = ?, original_path = ?, analysis_path = ?,
            thumb_path = ?, width = ?, height = ?, file_size = ?, mime_type = ?,
            quality_status = ?, quality_warnings_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            original_filename,
            original_path,
            analysis_path,
            thumb_path,
            width,
            height,
            file_size,
            mime_type,
            quality_status,
            quality_warnings_json,
            now_iso(),
            shot_id,
        ),
    )


async def clear_current_versions(conn: aiosqlite.Connection, shot_id: str) -> None:
    await conn.execute(
        "UPDATE shot_versions SET is_current = 0 WHERE shot_id = ?", (shot_id,)
    )


async def set_shot_current_version(
    conn: aiosqlite.Connection, shot_id: str, version_id: str
) -> None:
    await conn.execute(
        "UPDATE shots SET current_version_id = ?, updated_at = ? WHERE id = ?",
        (version_id, now_iso(), shot_id),
    )


async def insert_adopted_version(
    conn: aiosqlite.Connection,
    *,
    version_id: str,
    shot_id: str,
    image_path: str,
    width: int | None,
    height: int | None,
    file_size: int | None,
    source_generation_id: str,
    source_candidate_id: str,
    recheck_status: str = "running",
) -> None:
    now = now_iso()
    await conn.execute(
        "UPDATE shot_versions SET is_current = 0 WHERE shot_id = ?", (shot_id,)
    )
    await conn.execute(
        """
        INSERT INTO shot_versions (
            id, shot_id, kind, image_path, width, height, file_size,
            source_generation_id, source_candidate_id, is_current,
            recheck_status, created_at
        ) VALUES (?, ?, 'adopted', ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            version_id, shot_id, image_path, width, height, file_size,
            source_generation_id, source_candidate_id, recheck_status, now,
        ),
    )
    await conn.execute(
        "UPDATE shots SET current_version_id = ?, updated_at = ? WHERE id = ?",
        (version_id, now, shot_id),
    )


async def update_version_recheck(
    db: Database,
    version_id: str,
    status: str,
    *,
    adoption_id: str | None = None,
) -> None:
    fields = ["recheck_status = ?", "recheck_at = ?"]
    params: list[Any] = [status, now_iso()]
    if adoption_id:
        fields.append("adoption_id = ?")
        params.append(adoption_id)
    params.append(version_id)
    await db.execute(
        f"UPDATE shot_versions SET {', '.join(fields)} WHERE id = ?", params
    )


async def get_version(db: Database, version_id: str) -> aiosqlite.Row | None:
    return await db.fetchone("SELECT * FROM shot_versions WHERE id = ?", (version_id,))


async def list_versions(db: Database, shot_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM shot_versions WHERE shot_id = ? ORDER BY rowid", (shot_id,)
    )


async def get_current_version(db: Database, shot_id: str) -> aiosqlite.Row | None:
    return await db.fetchone(
        """
        SELECT v.* FROM shot_versions v
        JOIN shots s ON s.current_version_id = v.id
        WHERE s.id = ?
        """,
        (shot_id,),
    )


async def list_original_hashes(db: Database, task_id: str) -> list[tuple[str, str]]:
    rows = await db.fetchall(
        "SELECT shot_code, original_path FROM shots WHERE task_id = ? ORDER BY seq",
        (task_id,),
    )
    return [(row["shot_code"], row["original_path"]) for row in rows]


async def update_note(db: Database, task_id: str, shot_id: str, note: str) -> None:
    await db.execute(
        "UPDATE shots SET note = ?, updated_at = ? WHERE task_id = ? AND id = ?",
        (note, now_iso(), task_id, shot_id),
    )
