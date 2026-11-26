"""进程重启后，遗留的 running/retrying 任务应变为 paused，且写入事件。"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from app.core.timeutil import now_iso
from app.main import create_app


def test_interrupted_tasks_marked_paused(settings):
    app1 = create_app(settings, configure_logs=False)
    with TestClient(app1):
        pass  # 仅执行迁移

    now = now_iso()
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO tasks (id, name, mode, status, created_at, updated_at) "
            "VALUES ('task_running', '进行中任务', 'live', 'running', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO tasks (id, name, mode, status, created_at, updated_at) "
            "VALUES ('task_retrying', '重试任务', 'live', 'retrying', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO tasks (id, name, mode, status, created_at, updated_at) "
            "VALUES ('task_done', '已完成任务', 'live', 'completed', ?, ?)",
            (now, now),
        )
        conn.commit()

    app2 = create_app(settings, configure_logs=False)
    with TestClient(app2):
        pass

    with sqlite3.connect(settings.db_path) as conn:
        conn.row_factory = sqlite3.Row
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute(
                "SELECT id, status FROM tasks WHERE id IN "
                "('task_running', 'task_retrying', 'task_done')"
            )
        }
        events = conn.execute(
            "SELECT task_id, type FROM events WHERE type = 'analysis.interrupted_on_restart'"
        ).fetchall()

    assert statuses == {
        "task_running": "paused",
        "task_retrying": "paused",
        "task_done": "completed",
    }
    assert {row["task_id"] for row in events} == {"task_running", "task_retrying"}
