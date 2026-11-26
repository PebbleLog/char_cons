"""本地设置、连通性测试、密钥状态与本地数据管理（F-12 / F-13）。

安全边界：
- 任何响应只返回 hasKey/source，不返回 Key、末位字符或绝对路径；
- Key 仅保存在 Windows 凭据管理器或环境变量；
- 测试结果与隐私确认是普通配置，可持久化，但不含密钥。
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
from typing import Any

from ..core.config import Settings
from ..core.errors import AppError
from ..core.keyring_store import (
    delete_api_key,
    key_status,
    set_api_key,
)
from ..core.timeutil import now_iso
from ..providers.base import GenerationProvider, VisionProvider
from ..providers.errors import ProviderError
from ..repositories import settings_repo
from ..repositories.database import Database
from . import task_service

logger = logging.getLogger(__name__)

SERVICES = ("analysis", "generation")
SERVICE_LABELS = {"analysis": "分析服务", "generation": "图像生成服务"}
_SECRET_PATTERN = re.compile(r"(?i)(sk-[a-z0-9_-]{6,}|bearer\s+[a-z0-9._-]{8,})")


def _safe_message(message: str) -> str:
    return _SECRET_PATTERN.sub("***", message or "")


def _fingerprint(settings: Settings, service: str) -> dict[str, Any]:
    if service == "analysis":
        return {
            "provider": settings.analysis_provider,
            "model": settings.analysis_model,
            "baseUrl": settings.analysis_base_url,
        }
    return {
        "provider": settings.generation_provider,
        "model": settings.generation_model,
        "baseUrl": settings.generation_base_url,
        "size": settings.generation_size,
    }


def _configured(settings: Settings, service: str, has_key: bool) -> bool:
    if service == "analysis":
        provider = (settings.analysis_provider or "").lower()
        return provider == "mock" or (bool(settings.analysis_model.strip()) and has_key)
    provider = (settings.generation_provider or "").lower()
    return provider == "mock" or (bool(settings.generation_model.strip()) and has_key)


def _service_capabilities(settings: Settings, service: str) -> dict[str, Any]:
    if service == "analysis":
        return {
            "structuredOutput": True,
            "precheckBatch": True,
            "precheckFallbackPerCandidate": True,
            "maxImagesPerRequest": 4,
            "note": "4 图批量预检映射稳定性【待实测】",
        }
    return {
        "singleImagePerRequest": True,
        "nativeBatch": False,
        "negativePrompt": False,
        "negativePromptMode": "merged",
        "maxReferenceImages": 10,
        "supportsSeed": True,
        "supportsSize": True,
        "note": "模型 ID、尺寸档位、角色一致性与费用【待实测】",
    }


async def _service_view(db: Database, settings: Settings, service: str) -> dict[str, Any]:
    status = key_status(service)
    has_key = bool(status["hasKey"])
    provider = (
        settings.analysis_provider if service == "analysis" else settings.generation_provider
    )
    configured = _configured(settings, service, has_key)
    record = await settings_repo.get_setting(db, f"service_test_{service}")
    fingerprint = _fingerprint(settings, service)
    last_test = None
    state = "unconfigured"
    if record and record.get("fingerprint") == fingerprint:
        last_test = {key: value for key, value in record.items() if key != "fingerprint"}
        state = "connected" if record.get("ok") else "failed"
    elif configured:
        state = "ready"
    labels = {
        "connected": "已连接",
        "ready": "已配置",
        "failed": "连接失败",
        "unconfigured": "未配置",
    }
    model = (
        settings.analysis_model if service == "analysis" else settings.generation_model
    )
    base_url = (
        settings.analysis_base_url if service == "analysis" else settings.generation_base_url
    )
    return {
        "service": service,
        "label": SERVICE_LABELS[service],
        "provider": provider,
        "providerLabel": "Mock（本地测试，不联网）" if provider == "mock" else "火山方舟",
        "model": model,
        "baseUrl": base_url,
        "size": settings.generation_size if service == "generation" else None,
        "hasKey": has_key,
        "keySource": status["source"],
        "keyMasked": "••••••••••••••••" if has_key else "未配置",
        "configured": configured,
        "state": state,
        "statusLabel": labels[state],
        "lastTest": last_test,
        "capabilities": _service_capabilities(settings, service),
    }


async def get_settings_view(db: Database, settings: Settings) -> dict[str, Any]:
    return {
        "mode": "live",
        "services": {
            "analysis": await _service_view(db, settings, "analysis"),
            "generation": await _service_view(db, settings, "generation"),
        },
        "limits": {
            "defaultBatchSize": settings.default_batch_size,
            "uploadMaxMb": settings.upload_max_mb,
            "generationSize": settings.generation_size,
        },
        "timeouts": {
            "connectTimeoutSeconds": settings.connect_timeout_seconds,
            "visionTimeoutSeconds": settings.vision_timeout_seconds,
            "precheckTimeoutSeconds": settings.precheck_timeout_seconds,
            "seedreamTimeoutSeconds": settings.seedream_timeout_seconds,
            "generationBatchWaitSeconds": settings.generation_batch_wait_seconds,
            "retryMaxAttempts": settings.retry_max_attempts,
        },
        "privacyAcknowledged": bool(
            await settings_repo.get_setting(db, "privacy_acknowledged", False)
        ),
        "security": {
            "apiKeyStorage": "windows-credential-manager",
            "keyInBrowserStorage": False,
            "keyInLogs": False,
            "keyInExports": False,
            "faceRecognition": False,
            "imageStorage": "local-only",
            "storageLocation": "local",
        },
    }


async def update_general(
    db: Database, settings: Settings, payload: dict[str, Any]
) -> dict[str, Any]:
    updates = {
        "default_batch_size": payload.get("defaultBatchSize"),
        "upload_max_mb": payload.get("uploadMaxMb"),
        "generation_size": payload.get("generationSize"),
        "connect_timeout_seconds": payload.get("connectTimeoutSeconds"),
        "vision_timeout_seconds": payload.get("visionTimeoutSeconds"),
        "precheck_timeout_seconds": payload.get("precheckTimeoutSeconds"),
        "seedream_timeout_seconds": payload.get("seedreamTimeoutSeconds"),
        "generation_batch_wait_seconds": payload.get("generationBatchWaitSeconds"),
        "retry_max_attempts": payload.get("retryMaxAttempts"),
    }
    for key, value in updates.items():
        if value is not None:
            setattr(settings, key, value)
    settings.validate()
    settings.save_file_config()
    if payload.get("privacyAcknowledged") is not None:
        await settings_repo.set_setting(
            db, "privacy_acknowledged", bool(payload["privacyAcknowledged"])
        )
    return await get_settings_view(db, settings)


async def update_service(
    db: Database, settings: Settings, service: str, payload: dict[str, Any]
) -> dict[str, Any]:
    if service not in SERVICES:
        raise AppError("invalid_request", "不支持的服务类型。", status_code=400)
    provider = payload.get("provider")
    model = payload.get("model")
    base_url = payload.get("baseUrl")
    size = payload.get("size")
    api_key = payload.get("apiKey")

    if provider is not None:
        if service == "analysis":
            settings.analysis_provider = provider
        else:
            settings.generation_provider = provider
    if model is not None:
        if service == "analysis":
            settings.analysis_model = model
        else:
            settings.generation_model = model
    if base_url is not None:
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise AppError("invalid_request", "服务地址必须是 http(s) 地址。", status_code=400)
        if parsed.username or parsed.password:
            raise AppError(
                "invalid_request", "服务地址不能包含用户名或密码。", status_code=400
            )
        if service == "analysis":
            settings.analysis_base_url = base_url.rstrip("/")
        else:
            settings.generation_base_url = base_url.rstrip("/")
    if service == "generation" and "size" in payload:
        settings.generation_size = size or ""

    current_provider = (
        settings.analysis_provider if service == "analysis" else settings.generation_provider
    )
    if current_provider == "mock":
        if service == "analysis" and not settings.analysis_model.strip():
            settings.analysis_model = "mock-vision"
        if service == "generation" and not settings.generation_model.strip():
            settings.generation_model = "mock-seedream"

    if api_key:
        try:
            set_api_key(service, api_key)
        except Exception as exc:
            logger.warning("保存 Key 失败（%s）：%s", service, type(exc).__name__)
            raise AppError(
                "keyring_unavailable",
                "无法写入系统凭据管理器，请检查系统凭据服务后重试。",
                status_code=500,
            ) from exc

    settings.validate()
    settings.save_file_config()
    await settings_repo.delete_setting(db, f"service_test_{service}")
    return await get_settings_view(db, settings)


async def remove_key(
    db: Database, settings: Settings, service: str
) -> dict[str, Any]:
    if service not in SERVICES:
        raise AppError("invalid_request", "不支持的服务类型。", status_code=400)
    delete_api_key(service)
    await settings_repo.delete_setting(db, f"service_test_{service}")
    return await get_settings_view(db, settings)


async def test_service(
    db: Database,
    settings: Settings,
    service: str,
    vision_provider: VisionProvider,
    generation_provider: GenerationProvider,
) -> dict[str, Any]:
    if service not in SERVICES:
        raise AppError("invalid_request", "不支持的服务类型。", status_code=400)
    provider = vision_provider if service == "analysis" else generation_provider
    started = time.perf_counter()
    try:
        provider.ensure_configured()
        detail = await provider.test_connection()
        latency = round((time.perf_counter() - started) * 1000)
        result = {
            "ok": True,
            "code": None,
            "message": (
                "连接成功（Mock Provider：本地测试，不联网）"
                if getattr(provider, "name", "") == "mock"
                else "连接成功 · 鉴权通过 · 网络可达"
            ),
            "latencyMs": latency,
            "model": detail.get("model"),
            "mock": bool(detail.get("mock")),
        }
    except ProviderError as exc:
        latency = round((time.perf_counter() - started) * 1000)
        result = {
            "ok": False,
            "code": exc.code,
            "message": _safe_message(exc.message),
            "latencyMs": latency,
            "retryable": exc.retryable,
        }
    except Exception:
        logger.exception("连接测试未预期失败：%s", service)
        result = {
            "ok": False,
            "code": "internal_error",
            "message": "连接测试发生未预期错误，请稍后重试。",
            "latencyMs": round((time.perf_counter() - started) * 1000),
        }
    record = {
        **result,
        "checkedAt": now_iso(),
        "fingerprint": _fingerprint(settings, service),
    }
    await settings_repo.set_setting(db, f"service_test_{service}", record)
    view = await get_settings_view(db, settings)
    return {"result": result, "settings": view}


async def storage_summary(db: Database, settings: Settings) -> dict[str, Any]:
    summary = await task_service.archive_summary(db, settings)
    rows = await db.fetchall(
        """
        SELECT
            (SELECT COUNT(*) FROM generation_candidates c
                JOIN generation_records g ON g.id = c.generation_id
                JOIN tasks t ON t.id = g.task_id WHERE t.mode = 'live') AS candidates,
            (SELECT COUNT(*) FROM generation_candidates c
                JOIN generation_records g ON g.id = c.generation_id
                JOIN tasks t ON t.id = g.task_id
                WHERE t.mode = 'live' AND c.adopted = 1) AS adopted,
            (SELECT COUNT(*) FROM suggestions s
                JOIN tasks t ON t.id = s.task_id WHERE t.mode = 'live') AS suggestions
        """
    )
    extra = dict(rows[0]) if rows else {}
    try:
        db_bytes = settings.db_path.stat().st_size if settings.db_path.exists() else 0
    except OSError:
        db_bytes = 0
    return {
        **summary,
        "databaseBytes": db_bytes,
        "candidates": int(extra.get("candidates") or 0),
        "adoptedCandidates": int(extra.get("adopted") or 0),
        "suggestions": int(extra.get("suggestions") or 0),
    }


async def clear_data(db: Database, settings: Settings, *, confirm: bool) -> dict[str, Any]:
    if not confirm:
        raise AppError(
            "invalid_request", "清除本地数据需要确认。", status_code=400
        )
    active = await db.fetchone(
        "SELECT COUNT(*) AS total FROM tasks WHERE status IN ('running', 'retrying')"
    )
    active_generation = await db.fetchone(
        "SELECT COUNT(*) AS total FROM generation_records "
        "WHERE status IN ('pending', 'generating', 'prechecking') "
        "OR precheck_status = 'running'"
    )
    if int(active["total"] if active else 0) or int(
        active_generation["total"] if active_generation else 0
    ):
        raise AppError(
            "conflict", "仍有分析或生成任务在运行，请先取消后再清除数据。", status_code=409
        )

    async with db.transaction() as conn:
        await conn.execute("DELETE FROM events")
        await conn.execute("DELETE FROM usage_records")
        await conn.execute("DELETE FROM tasks")
    await asyncio.to_thread(_reset_data_dirs, settings)
    try:
        await db.execute("VACUUM")
    except Exception as exc:  # 回收失败不影响数据已清除的事实
        logger.warning("VACUUM 失败：%s", type(exc).__name__)
    logger.info("本地任务数据已清除")
    return await storage_summary(db, settings)


def _reset_data_dirs(settings: Settings) -> None:
    for directory in (
        settings.uploads_dir,
        settings.generated_dir,
        settings.exports_dir,
    ):
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
