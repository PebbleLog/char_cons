"""请求/任务上下文变量。

日志过滤器从这里读取 request_id，避免把请求标识塞进每个函数签名。
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
task_id_var: ContextVar[str] = ContextVar("task_id", default="-")
