"""日志配置。

要求（NFR-08 / 技术方案 9.1）：
- 控制台 + 轮转文件；
- 每条日志带 request_id，便于串联；
- 严禁记录 API Key、图片内容；调用方负责不把敏感数据传入日志。
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from .context import request_id_var, task_id_var

_ROOT_NAME = "char_cons"
_FORMAT = "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured_marker = "_char_cons_configured"


class ContextFilter(logging.Filter):
    """把上下文变量注入日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = request_id_var.get()
        record.task_id = task_id_var.get()
        return True


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    """幂等配置日志；重复调用不会叠加 handler。"""
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_ROOT_NAME)
    if getattr(logger, _configured_marker, False):
        return

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)
    context_filter = ContextFilter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(context_filter)
    logger.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)
    logger.addHandler(file_handler)

    setattr(logger, _configured_marker, True)
