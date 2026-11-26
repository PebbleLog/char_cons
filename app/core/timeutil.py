"""时间工具：统一 ISO 8601（含本地时区），便于导出与跨平台比较。"""

from __future__ import annotations

from datetime import datetime


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
