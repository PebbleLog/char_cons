"""SQLite 访问层。

设计（技术方案 2.4）：
- 标准库 sqlite3 的异步封装 aiosqlite；不使用 ORM；
- WAL、外键、busy_timeout、NORMAL 同步；
- 写操作通过单个 ``asyncio.Lock`` 串行化；读操作共用连接并发排队；
- 迁移按文件名序号顺序执行，``schema_migrations`` 记录已应用版本；
- 关键事务使用 ``BEGIN IMMEDIATE``，避免先读后写时的锁升级冲突。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Sequence

import aiosqlite

from ..core.timeutil import now_iso

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: Path, busy_timeout_ms: int = 15000) -> None:
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    # ---- 生命周期 ---------------------------------------------
    async def connect(self) -> None:
        if self._conn is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None：完全手动控制事务，避免隐式 BEGIN 干扰
        self._conn = await aiosqlite.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)}")
        logger.info("SQLite 已连接：%s", self.path)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("数据库尚未连接")
        return self._conn

    # ---- 迁移 --------------------------------------------------
    async def migrate(self, migrations_dir: Path) -> list[int]:
        """应用尚未执行的迁移，返回本次应用的版本号列表。"""
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        rows = await self.fetchall("SELECT version FROM schema_migrations")
        applied = {int(row["version"]) for row in rows}

        files = sorted(
            (p for p in Path(migrations_dir).glob("*.sql") if p.is_file()),
            key=lambda p: p.name,
        )
        newly_applied: list[int] = []
        for path in files:
            try:
                version = int(path.name.split("_", 1)[0])
            except ValueError:
                logger.warning("忽略无法识别序号的迁移文件：%s", path.name)
                continue
            if version in applied:
                continue

            script = path.read_text(encoding="utf-8")
            async with self._write_lock:
                try:
                    # executescript 会先提交挂起事务；用显式事务保证整份迁移原子
                    await self.conn.executescript(
                        "BEGIN IMMEDIATE;\n" + script + "\nCOMMIT;"
                    )
                except Exception:
                    try:
                        await self.conn.execute("ROLLBACK")
                    except Exception:  # pragma: no cover - 回滚失败时保留原始异常
                        logger.warning("迁移回滚失败：%s", path.name)
                    raise
                await self.conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, path.name, now_iso()),
                )
            applied.add(version)
            newly_applied.append(version)
            logger.info("已应用数据库迁移：%s", path.name)
        return newly_applied

    # ---- 基础读写 ----------------------------------------------
    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        async with self._write_lock:
            await self.conn.execute(sql, params)

    async def executemany(self, sql: str, params: Iterable[Sequence[Any]]) -> None:
        async with self._write_lock:
            await self.conn.executemany(sql, list(params))

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cursor:
            return list(await cursor.fetchall())

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """写事务；调用方不得嵌套使用。"""
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                await self.conn.execute("ROLLBACK")
                raise
            else:
                await self.conn.execute("COMMIT")

    # ---- 健康检查 ----------------------------------------------
    async def ping(self) -> bool:
        row = await self.fetchone("SELECT 1 AS ok")
        return bool(row and row["ok"] == 1)

    async def applied_migrations(self) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        )
