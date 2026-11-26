"""健康检查与会话信息。

健康检查只读探测数据库，并在数据目录做一次小文件写入自检；
不返回任何路径、密钥或环境细节之外的信息。
"""

from __future__ import annotations

import logging
import tempfile
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..core.config import Settings
from ..core.constants import APP_TITLE, APP_VERSION, PROMPT_VERSION, SCHEMA_VERSION
from ..core.timeutil import now_iso
from ..repositories.database import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system"])


async def _check_storage(settings: Settings) -> bool:
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=settings.data_dir, prefix=".health_", delete=True
        ) as handle:
            handle.write(b"ok")
            handle.flush()
        return True
    except OSError as exc:
        logger.error("数据目录不可写：%s", exc)
        return False


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    db: Database = request.app.state.db
    settings: Settings = request.app.state.settings

    db_ok = False
    try:
        db_ok = await db.ping()
    except Exception as exc:  # 健康检查必须始终可返回
        logger.error("数据库健康检查失败：%s", type(exc).__name__)
    storage_ok = await _check_storage(settings)

    started = getattr(request.app.state, "started_at_monotonic", None)
    uptime = round(time.monotonic() - started, 1) if started else 0

    payload = {
        "status": "ok" if (db_ok and storage_ok) else "degraded",
        "service": APP_TITLE,
        "version": APP_VERSION,
        "schemaVersion": SCHEMA_VERSION,
        "promptVersion": PROMPT_VERSION,
        "time": now_iso(),
        "uptimeSeconds": uptime,
        "checks": {
            "database": "ok" if db_ok else "error",
            "storage": "ok" if storage_ok else "error",
        },
    }
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/session")
async def session(request: Request) -> dict:
    settings: Settings = request.app.state.settings
    return {
        "csrfToken": request.app.state.csrf_token,
        "version": APP_VERSION,
        "schemaVersion": SCHEMA_VERSION,
        "promptVersion": PROMPT_VERSION,
        "mode": "live",
        "demoAvailable": True,
        "maxUploadMb": settings.upload_max_mb,
        "defaultBatchSize": settings.default_batch_size,
        "serverTime": now_iso(),
    }
