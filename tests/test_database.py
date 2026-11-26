from __future__ import annotations

import asyncio
import sqlite3

from app.core.config import PROJECT_ROOT
from app.core.timeutil import now_iso
from app.repositories.database import Database

MIGRATIONS = PROJECT_ROOT / "app" / "migrations"

EXPECTED_TABLES = {
    "tasks",
    "shots",
    "shot_versions",
    "observations",
    "judgements",
    "issues",
    "unknown_items",
    "waivers",
    "suspected_issues",
    "suggestions",
    "generation_records",
    "generation_candidates",
    "adoptions",
    "settings",
    "events",
    "usage_records",
    "schema_migrations",
}


def _run(coro):
    return asyncio.run(coro)


def test_pragmas_and_migration(tmp_path):
    async def scenario():
        db = Database(tmp_path / "test.db", busy_timeout_ms=5000)
        await db.connect()
        try:
            journal = await db.fetchone("PRAGMA journal_mode")
            assert journal[0].lower() == "wal"
            fk = await db.fetchone("PRAGMA foreign_keys")
            assert fk[0] == 1

            applied = await db.migrate(MIGRATIONS)
            assert applied == [1, 2, 3, 4]

            rows = await db.fetchall(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            tables = {row["name"] for row in rows}
            assert EXPECTED_TABLES <= tables

            versions = await db.applied_migrations()
            assert [row["version"] for row in versions] == [1, 2, 3, 4]

            # 迁移幂等
            assert await db.migrate(MIGRATIONS) == []
        finally:
            await db.close()

    _run(scenario())


def test_transaction_rollback(tmp_path):
    async def scenario():
        db = Database(tmp_path / "rollback.db")
        await db.connect()
        await db.migrate(MIGRATIONS)
        try:
            with_sql = (
                "INSERT INTO tasks (id, name, mode, status, created_at, updated_at) "
                "VALUES (?, ?, 'live', 'idle', ?, ?)"
            )
            try:
                async with db.transaction() as conn:
                    await conn.execute(with_sql, ("t1", "回滚任务", now_iso(), now_iso()))
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
            row = await db.fetchone("SELECT id FROM tasks WHERE id = 't1'")
            assert row is None

            async with db.transaction() as conn:
                await conn.execute(with_sql, ("t2", "提交任务", now_iso(), now_iso()))
            row = await db.fetchone("SELECT id, name FROM tasks WHERE id = 't2'")
            assert row is not None and row["name"] == "提交任务"
        finally:
            await db.close()

    _run(scenario())


def test_foreign_keys_enforced(tmp_path):
    async def scenario():
        db = Database(tmp_path / "fk.db")
        await db.connect()
        await db.migrate(MIGRATIONS)
        try:
            try:
                await db.execute(
                    "INSERT INTO shots (id, task_id, seq, shot_code, original_path, created_at, updated_at) "
                    "VALUES ('s1', 'missing-task', 1, 'S1', 'a.jpg', ?, ?)",
                    (now_iso(), now_iso()),
                )
            except sqlite3.IntegrityError:
                pass
            else:  # pragma: no cover
                raise AssertionError("外键约束应拒绝不存在的 task_id")
        finally:
            await db.close()

    _run(scenario())


def test_health_and_schema_after_startup(client, settings):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"

    with sqlite3.connect(settings.db_path) as conn:
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert EXPECTED_TABLES <= names
