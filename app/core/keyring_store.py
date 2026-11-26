"""API Key 安全存取（技术方案 9.1）。

- 生产默认：Windows 凭据管理器（keyring），服务名 ``char_cons``；
- 读取顺序：环境变量（开发/CI）→ keyring；
- 分析与生成 Key 分开保存，不自动复用；
- 本模块不提供“读取全部 Key”的接口，也不会把 Key 写入日志。
"""

from __future__ import annotations

import logging
import os

import keyring

logger = logging.getLogger(__name__)

SERVICE_NAME = "char_cons"
_USERNAMES = {
    "analysis": "ark-analysis",
    "generation": "ark-generation",
}
# 分析与生成分别读取各自的 Key，不通过通用 ARK_API_KEY 自动复用
_ENV_KEYS = {
    "analysis": ("CHAR_CONS_ANALYSIS_API_KEY",),
    "generation": ("CHAR_CONS_GENERATION_API_KEY",),
}


def _normalize(service: str) -> str:
    if service not in _USERNAMES:
        raise ValueError(f"未知服务：{service}")
    return service


def get_api_key(service: str) -> str | None:
    service = _normalize(service)
    for env_name in _ENV_KEYS[service]:
        value = os.environ.get(env_name)
        if value and value.strip():
            return value.strip()
    try:
        value = keyring.get_password(SERVICE_NAME, _USERNAMES[service])
    except Exception as exc:  # 凭据后端不可用时不应导致服务崩溃
        logger.warning("读取 keyring 失败（%s）：%s", service, type(exc).__name__)
        return None
    return value.strip() if value else None


def set_api_key(service: str, key: str) -> None:
    service = _normalize(service)
    key = (key or "").strip()
    if not key:
        raise ValueError("API Key 不能为空")
    keyring.set_password(SERVICE_NAME, _USERNAMES[service], key)


def delete_api_key(service: str) -> None:
    service = _normalize(service)
    try:
        keyring.delete_password(SERVICE_NAME, _USERNAMES[service])
    except keyring.errors.PasswordDeleteError:
        return
    except Exception as exc:
        logger.warning("删除 keyring 失败（%s）：%s", service, type(exc).__name__)


def has_api_key(service: str) -> bool:
    return bool(get_api_key(service))


def key_status(service: str) -> dict[str, str | bool]:
    """返回可安全展示的 Key 状态；绝不返回 Key 内容或末位字符。"""
    service = _normalize(service)
    for env_name in _ENV_KEYS[service]:
        value = os.environ.get(env_name)
        if value and value.strip():
            return {"hasKey": True, "source": "env"}
    try:
        value = keyring.get_password(SERVICE_NAME, _USERNAMES[service])
    except Exception as exc:
        logger.warning("读取 keyring 失败（%s）：%s", service, type(exc).__name__)
        return {"hasKey": False, "source": "unavailable"}
    return {"hasKey": bool(value), "source": "keyring" if value else "none"}
