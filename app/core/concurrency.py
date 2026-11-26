"""任务级并发控制（技术方案 5.5）。

- 每个任务一把锁，防止重复分析、重复生成、重复采用（E-19）；
- 内存注册表只保存运行期句柄；进程重启后由数据库恢复为 paused；
- 本模块不做业务状态机，只提供锁、取消标志与句柄登记。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class TaskHandle:
    task_id: str
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    stage: str | None = None
    runner: asyncio.Task | None = None

    def request_cancel(self) -> None:
        self.cancel_event.set()

    @property
    def canceled(self) -> bool:
        return self.cancel_event.is_set()

    @property
    def active(self) -> bool:
        return self.runner is not None and not self.runner.done()


class TaskRegistry:
    """进程内任务注册表。线程/协程安全由单事件循环保证。"""

    def __init__(self) -> None:
        self._handles: dict[str, TaskHandle] = {}

    def get(self, task_id: str) -> TaskHandle | None:
        return self._handles.get(task_id)

    def get_or_create(self, task_id: str) -> TaskHandle:
        handle = self._handles.get(task_id)
        if handle is None:
            handle = TaskHandle(task_id=task_id)
            self._handles[task_id] = handle
        return handle

    def remove(self, task_id: str) -> None:
        self._handles.pop(task_id, None)

    def clear(self) -> None:
        self._handles.clear()

    def active_task_ids(self) -> list[str]:
        return list(self._handles)

    def all_handles(self) -> list[TaskHandle]:
        return list(self._handles.values())
