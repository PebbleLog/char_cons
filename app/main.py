"""FastAPI 应用入口。

启动顺序（技术方案 2.3 / 5.6）：
1. 加载配置、创建数据目录、初始化日志；
2. 连接 SQLite 并执行顺序迁移；
3. 把上次进程遗留的 running/retrying 任务标记为 paused；
4. 生成会话 CSRF Token，挂载 API 与定稿前端静态资源。

命令：
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe -m uvicorn app.main:app \
        --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import analysis, archive, generations, health, report, settings as settings_api, tasks
from .core.concurrency import TaskRegistry
from .core.config import Settings
from .core.constants import APP_TITLE, APP_VERSION
from .core.context import request_id_var
from .core.errors import error_payload, install_exception_handlers
from .core.logging import setup_logging
from .core.security import (
    constant_time_compare,
    generate_csrf_token,
    request_source_allowed,
)
from .providers.factory import make_generation_provider, make_vision_provider
from .repositories.database import Database
from .repositories.generation_repo import recover_interrupted as recover_generations
from .repositories.task_repo import recover_interrupted_tasks

logger = logging.getLogger(__name__)

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _clean_request_id(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if 1 <= len(value) <= 64 and all(
        ch.isalnum() or ch in "-._" for ch in value
    ):
        return value
    return None


def create_app(settings: Settings | None = None, *, configure_logs: bool = True) -> FastAPI:
    settings = settings or Settings.load()
    settings.ensure_dirs()
    if configure_logs:
        setup_logging(settings.logs_dir)
    if not settings.frontend_index.is_file():
        raise RuntimeError(
            f"前端定稿文件缺失：{settings.frontend_index}。"
            "请确认 frontend/ 目录已按 UI页面原型 复制。"
        )

    db = Database(settings.db_path, settings.sqlite_busy_timeout_ms)
    registry = TaskRegistry()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db = db
        app.state.task_registry = registry
        app.state.csrf_token = generate_csrf_token()
        app.state.started_at_monotonic = time.monotonic()

        await db.connect()
        try:
            await db.migrate(settings.migrations_dir)
        except Exception:
            await db.close()
            raise
        try:
            await recover_interrupted_tasks(db)
            await recover_generations(db)
        except Exception as exc:  # 恢复失败不阻止启动，但必须可见
            logger.error("启动恢复失败：%s", type(exc).__name__)
        logger.info(
            "服务启动完成：%s v%s · 数据目录 %s · 监听 %s:%s",
            APP_TITLE,
            APP_VERSION,
            settings.home_dir,
            settings.host,
            settings.port,
        )
        try:
            yield
        finally:
            # 取消在途分析，避免关闭数据库后仍有协程写入
            runners: list[asyncio.Task] = []
            for handle in registry.all_handles():
                handle.request_cancel()
                if handle.runner and not handle.runner.done():
                    handle.runner.cancel()
                    runners.append(handle.runner)
            if runners:
                await asyncio.gather(*runners, return_exceptions=True)
            try:
                # 进程退出时未完成的分析标记为 paused，重启后由用户决定是否重试
                await recover_interrupted_tasks(db)
            except Exception as exc:
                logger.error("关闭时恢复任务状态失败：%s", type(exc).__name__)
            registry.clear()
            await db.close()
            logger.info("服务已停止")

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    # 供中间件在生命周期开始前也能读到配置
    app.state.settings = settings
    app.state.db = db
    app.state.task_registry = registry
    app.state.csrf_token = None
    # 测试可替换为自定义 Provider；生产按配置选择豆包/Mock
    app.state.vision_provider_factory = make_vision_provider
    app.state.generation_provider_factory = make_generation_provider

    install_exception_handlers(app)

    # ---- 中间件（后添加者位于外层） ----------------------------
    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        if request.url.path.startswith("/api") and request.method in _UNSAFE_METHODS:
            expected = getattr(request.app.state, "csrf_token", None)
            provided = request.headers.get("x-csrf-token", "")
            if not expected or not provided or not constant_time_compare(provided, expected):
                return JSONResponse(
                    status_code=403,
                    content=error_payload(
                        "csrf_failed", "安全校验失败，请刷新页面后重试。"
                    ),
                )
            # 以本次请求的实际端口为准：命令行或配置改端口后仍能正确校验同源
            request_port = request.url.port or settings.port
            if not request_source_allowed(
                request.headers.get("origin"),
                request.headers.get("referer"),
                request_port,
            ):
                return JSONResponse(
                    status_code=403,
                    content=error_payload(
                        "csrf_failed", "请求来源不是本地页面，已拒绝。"
                    ),
                )
        return await call_next(request)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = _clean_request_id(request.headers.get("x-request-id")) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = request_id
        # 前端模块与样式必须每次重新校验，避免升级后浏览器继续使用旧 ES Module。
        path = request.url.path.lower()
        if path == "/" or path.endswith((".html", ".js", ".css")):
            response.headers["Cache-Control"] = "no-cache"
        elapsed_ms = (time.perf_counter() - started) * 1000
        if request.url.path.startswith("/api"):
            logger.info(
                "%s %s -> %s (%.0f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        return response

    # ---- 路由 --------------------------------------------------
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(analysis.router)
    app.include_router(report.router)
    app.include_router(generations.router)
    app.include_router(settings_api.router)
    app.include_router(archive.router)

    @app.api_route(
        "/api/{rest:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def api_not_found(rest: str) -> JSONResponse:
        return JSONResponse(
            status_code=404, content=error_payload("not_found", "接口不存在。")
        )

    # ---- 定稿前端静态资源 --------------------------------------
    app.mount(
        "/",
        StaticFiles(directory=str(settings.frontend_dir), html=True),
        name="frontend",
    )
    return app


app = create_app()
