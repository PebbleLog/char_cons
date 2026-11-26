"""非敏感配置键值存储。API Key 不放这里（走 keyring）。"""

from __future__ import annotations

import json
from typing import Any

from ..core.timeutil import now_iso
from .database import Database


async def get_setting(db: Database, key: str, default: Any = None) -> Any:
    row = await db.fetchone("SELECT value_json FROM settings WHERE key = ?", (key,))
    if row is None:
        return default
    try:
        return json.loads(row["value_json"])
    except json.JSONDecodeError:
        return default


async def set_setting(db: Database, key: str, value: Any) -> None:
    await db.execute(
        """
        INSERT INTO settings (key, value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json,
                                       updated_at = excluded.updated_at
        """,
        (key, json.dumps(value, ensure_ascii=False), now_iso()),
    )


async def delete_setting(db: Database, key: str) -> None:
    await db.execute("DELETE FROM settings WHERE key = ?", (key,))


async def all_settings(db: Database) -> dict[str, Any]:
    rows = await db.fetchall("SELECT key, value_json FROM settings")
    result: dict[str, Any] = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value_json"])
        except json.JSONDecodeError:
            continue
    return result
