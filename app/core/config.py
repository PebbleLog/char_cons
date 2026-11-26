"""应用配置。

约定（技术方案 2.6 / 2.8 / 9.4.1）：
- 非敏感配置写 ``<home>/config.json``；API Key 永远不在这里（走 keyring）。
- 数据目录默认 ``%APPDATA%\\char_cons``，可用环境变量 ``CHAR_CONS_HOME`` 覆盖，
  测试与开发期可指向项目内目录。
- 所有超时/重试默认值集中在此，业务代码禁止散落魔法数字。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .constants import APP_NAME, APP_VERSION, PROMPT_VERSION, SCHEMA_VERSION

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRONTEND_DIR = PROJECT_ROOT / "frontend"
DEFAULT_MIGRATIONS_DIR = PROJECT_ROOT / "app" / "migrations"


def default_home_dir() -> Path:
    """返回本地数据根目录，优先环境变量，其次 Windows APPDATA。"""
    env = os.environ.get("CHAR_CONS_HOME")
    if env:
        return Path(env).expanduser().resolve()
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata).resolve() / APP_NAME
    return Path.home().resolve() / f".{APP_NAME}"


@dataclass(slots=True)
class Settings:
    """一次进程内生效的配置快照。"""

    home_dir: Path
    frontend_dir: Path = DEFAULT_FRONTEND_DIR
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR

    host: str = "127.0.0.1"
    port: int = 8765

    upload_max_mb: int = 20
    default_batch_size: int = 4

    # 分析服务（模型 ID 与 Key 以控制台/实测为准；默认不内置虚构模型）
    analysis_provider: str = "doubao"
    analysis_model: str = ""
    analysis_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # 图像生成服务（Seedream 5.5：单次 1 张、无独立负向参数【待实测】）
    generation_provider: str = "doubao"
    generation_model: str = ""
    generation_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    # 留空表示不发送 size，由服务端默认；可选值以控制台为准【待实测】
    generation_size: str = ""

    # 运行时超时/重试（技术方案 9.4.1，均可配置、默认宽松）
    connect_timeout_seconds: int = 15
    vision_timeout_seconds: int = 180
    precheck_timeout_seconds: int = 180
    seedream_timeout_seconds: int = 300
    generation_batch_wait_seconds: int = 900
    observation_wait_seconds: int = 180
    precheck_batch_wait_seconds: int = 300
    image_download_timeout_seconds: int = 60
    upload_timeout_seconds: int = 120
    export_timeout_seconds: int = 60
    sqlite_busy_timeout_ms: int = 15000
    retry_max_attempts: int = 3
    analysis_task_limit_seconds: int = 1800

    app_version: str = APP_VERSION
    schema_version: str = SCHEMA_VERSION
    prompt_version: str = PROMPT_VERSION

    # ---- 路径 ------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.home_dir / "char_cons.db"

    @property
    def config_path(self) -> Path:
        return self.home_dir / "config.json"

    @property
    def data_dir(self) -> Path:
        return self.home_dir / "data"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def generated_dir(self) -> Path:
        return self.data_dir / "generated"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def frontend_index(self) -> Path:
        return self.frontend_dir / "index.html"

    def ensure_dirs(self) -> None:
        """创建数据库与数据目录；失败时抛出可读异常由启动流程处理。"""
        for path in (
            self.home_dir,
            self.data_dir,
            self.uploads_dir,
            self.generated_dir,
            self.exports_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        if not (1 <= self.default_batch_size <= 4):
            raise ValueError("default_batch_size 必须在 1～4 之间")
        if self.upload_max_mb <= 0:
            raise ValueError("upload_max_mb 必须为正整数")
        if not (0 <= self.retry_max_attempts <= 5):
            raise ValueError("retry_max_attempts 必须在 0～5 之间")
        if not (1024 <= self.port <= 65535):
            raise ValueError("port 超出有效范围")
        if self.analysis_provider not in ("doubao", "mock"):
            raise ValueError("analysis_provider 仅支持 doubao / mock")
        for label, url in (
            ("analysis_base_url", self.analysis_base_url),
            ("generation_base_url", self.generation_base_url),
        ):
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"{label} 必须是 http(s) 地址")
            if parsed.username or parsed.password:
                raise ValueError(f"{label} 不能包含用户名或密码")
        if self.generation_provider not in ("doubao", "mock"):
            raise ValueError("generation_provider 仅支持 doubao / mock")

    # ---- 加载 -------------------------------------------------
    @classmethod
    def load(
        cls,
        home_dir: Path | None = None,
        *,
        frontend_dir: Path | None = None,
        migrations_dir: Path | None = None,
    ) -> "Settings":
        """从默认目录 + ``config.json`` 构建配置。

        ``config.json`` 只覆盖白名单中的非敏感字段；非法值记录警告并使用默认值，
        避免一处手误导致应用无法启动。
        """
        home = Path(home_dir).resolve() if home_dir else default_home_dir()
        settings = cls(
            home_dir=home,
            frontend_dir=Path(frontend_dir).resolve() if frontend_dir else DEFAULT_FRONTEND_DIR,
            migrations_dir=(
                Path(migrations_dir).resolve() if migrations_dir else DEFAULT_MIGRATIONS_DIR
            ),
        )
        settings._apply_file_config()
        settings._apply_env_overrides()
        settings.validate()
        return settings

    def _apply_env_overrides(self) -> None:
        """少量便于脚本/调试的覆盖；API Key 不在此列。"""
        env_port = os.environ.get("CHAR_CONS_PORT")
        if env_port:
            try:
                self.port = int(env_port)
            except ValueError:
                logger.warning("CHAR_CONS_PORT 不是整数，已忽略")
        env_host = os.environ.get("CHAR_CONS_HOST")
        if env_host:
            self.host = env_host
        env_provider = os.environ.get("CHAR_CONS_ANALYSIS_PROVIDER")
        if env_provider:
            self.analysis_provider = env_provider.strip().lower()
        env_model = os.environ.get("CHAR_CONS_ANALYSIS_MODEL")
        if env_model:
            self.analysis_model = env_model.strip()
        env_base = os.environ.get("CHAR_CONS_ANALYSIS_BASE_URL")
        if env_base:
            self.analysis_base_url = env_base.strip()
        env_gen_provider = os.environ.get("CHAR_CONS_GENERATION_PROVIDER")
        if env_gen_provider:
            self.generation_provider = env_gen_provider.strip().lower()
        env_gen_model = os.environ.get("CHAR_CONS_GENERATION_MODEL")
        if env_gen_model:
            self.generation_model = env_gen_model.strip()
        env_gen_base = os.environ.get("CHAR_CONS_GENERATION_BASE_URL")
        if env_gen_base:
            self.generation_base_url = env_gen_base.strip()
        env_gen_size = os.environ.get("CHAR_CONS_GENERATION_SIZE")
        if env_gen_size:
            self.generation_size = env_gen_size.strip()

    def _apply_file_config(self) -> None:
        path = self.config_path
        if not path.is_file():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取 config.json 失败，使用默认配置：%s", exc)
            return
        if not isinstance(raw, dict):
            logger.warning("config.json 顶层必须是对象，已忽略")
            return

        allowed = {
            "host": str,
            "port": int,
            "upload_max_mb": int,
            "default_batch_size": int,
            "analysis_provider": str,
            "analysis_model": str,
            "analysis_base_url": str,
            "generation_provider": str,
            "generation_model": str,
            "generation_base_url": str,
            "generation_size": str,
            "connect_timeout_seconds": int,
            "vision_timeout_seconds": int,
            "precheck_timeout_seconds": int,
            "seedream_timeout_seconds": int,
            "generation_batch_wait_seconds": int,
            "observation_wait_seconds": int,
            "precheck_batch_wait_seconds": int,
            "image_download_timeout_seconds": int,
            "upload_timeout_seconds": int,
            "export_timeout_seconds": int,
            "sqlite_busy_timeout_ms": int,
            "retry_max_attempts": int,
            "analysis_task_limit_seconds": int,
        }
        ranges: dict[str, tuple[int, int]] = {
            "port": (1024, 65535),
            "upload_max_mb": (1, 100),
            "default_batch_size": (1, 4),
            "connect_timeout_seconds": (5, 60),
            "vision_timeout_seconds": (60, 600),
            "precheck_timeout_seconds": (60, 600),
            "seedream_timeout_seconds": (120, 900),
            "generation_batch_wait_seconds": (300, 1800),
            "observation_wait_seconds": (60, 600),
            "precheck_batch_wait_seconds": (60, 900),
            "image_download_timeout_seconds": (30, 180),
            "upload_timeout_seconds": (60, 300),
            "export_timeout_seconds": (30, 180),
            "sqlite_busy_timeout_ms": (5000, 30000),
            "retry_max_attempts": (0, 5),
            "analysis_task_limit_seconds": (600, 7200),
        }
        for key, expected in allowed.items():
            if key not in raw:
                continue
            value = raw[key]
            if not isinstance(value, expected) or isinstance(value, bool):
                logger.warning("config.json 字段 %s 类型不合法，已忽略", key)
                continue
            bounds = ranges.get(key)
            if bounds and not (bounds[0] <= value <= bounds[1]):
                logger.warning(
                    "config.json 字段 %s=%s 超出范围 %s，已使用默认值",
                    key,
                    value,
                    bounds,
                )
                continue
            setattr(self, key, value)

    # ---- 持久化（仅非敏感字段） --------------------------------
    def public_config(self) -> dict[str, Any]:
        """返回可写入 config.json 的字段（不含任何路径或密钥）。"""
        keys = (
            "host",
            "port",
            "upload_max_mb",
            "default_batch_size",
            "analysis_provider",
            "analysis_model",
            "analysis_base_url",
            "generation_provider",
            "generation_model",
            "generation_base_url",
            "generation_size",
            "connect_timeout_seconds",
            "vision_timeout_seconds",
            "precheck_timeout_seconds",
            "seedream_timeout_seconds",
            "generation_batch_wait_seconds",
            "observation_wait_seconds",
            "precheck_batch_wait_seconds",
            "image_download_timeout_seconds",
            "upload_timeout_seconds",
            "export_timeout_seconds",
            "sqlite_busy_timeout_ms",
            "retry_max_attempts",
            "analysis_task_limit_seconds",
        )
        valid = {f.name for f in fields(self)}
        return {k: getattr(self, k) for k in keys if k in valid}

    def save_file_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.public_config(), ensure_ascii=False, indent=2)
        self.config_path.write_text(text + "\n", encoding="utf-8")
