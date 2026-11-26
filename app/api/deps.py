"""路由依赖。"""

from __future__ import annotations

from fastapi import Request

from ..core.config import Settings
from ..repositories.database import Database


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
