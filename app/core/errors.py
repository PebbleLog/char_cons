"""统一错误模型与异常处理。

错误响应形状（技术方案 7.1）::

    {"error": {"code", "message", "retryable", "action", "requestId"}}

错误码见技术方案 14.2；本模块只定义携带错误码的异常，业务层按需抛出。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .context import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    """可预期的业务错误。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        action: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.action = action
        self.details = details


def error_payload(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    action: str | None = None,
    details: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable,
        "action": action,
        "requestId": request_id_var.get(),
    }
    if details is not None:
        payload["details"] = details
    return {"error": payload}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                exc.code,
                exc.message,
                retryable=exc.retryable,
                action=exc.action,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(err.get("loc", ())), "msg": err.get("msg", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "invalid_request",
                "请求参数不合法，请检查后重试。",
                details=details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = str(exc.detail) if exc.detail else "请求无法完成。"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, message),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        # 只记录类型与消息，不记录请求体/图片/密钥
        logger.exception("未处理异常：%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "internal_error",
                "本地服务发生未预期错误，请稍后重试。",
                retryable=True,
            ),
        )
