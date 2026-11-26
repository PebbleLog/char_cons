"""本地服务安全工具。

覆盖（技术方案 9.2 / 9.3）：
- CSRF Token 生成与常量时间比较；
- Origin / Referer 同源校验（只允许本机回环地址）;
- 文件相对路径安全解析，拒绝绝对路径、``..`` 与符号链接逃逸。
"""

from __future__ import annotations

import hmac
import secrets
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .errors import AppError

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _url_allowed(url: str, port: int) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.hostname not in _LOCAL_HOSTS:
        return False
    effective_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return effective_port == port


def origin_allowed(origin: str | None, port: int) -> bool:
    """没有 Origin（本地脚本/测试）视为允许；有则必须是本机同端口。"""
    if not origin:
        return True
    return _url_allowed(origin, port)


def referer_allowed(referer: str | None, port: int) -> bool:
    if not referer:
        return True
    return _url_allowed(referer, port)


def request_source_allowed(origin: str | None, referer: str | None, port: int) -> bool:
    """优先校验 Origin；缺失时退化为校验 Referer。"""
    if origin:
        return origin_allowed(origin, port)
    if referer:
        return referer_allowed(referer, port)
    return True


def safe_join(root: Path, relative: str | Path) -> Path:
    """把数据库中的相对路径解析到存储根目录内。

    拒绝：空路径、绝对路径、盘符路径、``..``、NUL、路径组件为符号链接。
    """
    if relative is None:
        raise _bad_path()
    raw = str(relative).strip()
    if not raw or "\x00" in raw:
        raise _bad_path()

    # 统一分隔符后按 POSIX 语义判断，兼容 Windows 输入
    normalized = raw.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or (len(normalized) >= 2 and normalized[1] == ":"):
        raise _bad_path()
    if any(part in ("..", "") for part in pure.parts):
        raise _bad_path()

    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*pure.parts)

    # 逐级检查已存在的组件，拒绝符号链接（Windows 上可能指向根目录外）
    probe = root_resolved
    for part in pure.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise _bad_path()

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:  # 非法字符等
        raise _bad_path() from exc

    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise _bad_path()
    return resolved


def _bad_path() -> AppError:
    return AppError(
        "invalid_request",
        "非法的文件路径。",
        status_code=400,
    )
