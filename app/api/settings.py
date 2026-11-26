"""本地设置、服务配置、连接测试、密钥状态与数据清理接口（F-13）。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from ..models.api import ClearDataRequest, ServiceTest, ServiceUpdate, SettingsUpdate
from ..providers.base import GenerationProvider, VisionProvider
from ..services import settings_service
from .deps import get_db, get_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _vision(request: Request) -> VisionProvider:
    factory = getattr(request.app.state, "vision_provider_factory", None)
    if factory is None:
        from ..providers.factory import make_vision_provider

        factory = make_vision_provider
    return factory(request.app.state.settings)


def _generation(request: Request) -> GenerationProvider:
    factory = getattr(request.app.state, "generation_provider_factory", None)
    if factory is None:
        from ..providers.factory import make_generation_provider

        factory = make_generation_provider
    return factory(request.app.state.settings)


@router.get("")
async def get_settings_view(request: Request) -> dict:
    return await settings_service.get_settings_view(
        get_db(request), get_settings(request)
    )


@router.put("")
async def update_settings(request: Request, payload: SettingsUpdate) -> dict:
    return await settings_service.update_general(
        get_db(request),
        get_settings(request),
        payload.model_dump(by_alias=True, exclude_none=True),
    )


@router.put("/services/{service}")
async def update_service(
    request: Request,
    service: Literal["analysis", "generation"],
    payload: ServiceUpdate,
) -> dict:
    return await settings_service.update_service(
        get_db(request),
        get_settings(request),
        service,
        payload.model_dump(by_alias=True, exclude_none=True),
    )


@router.delete("/keys/{service}")
async def delete_key(
    request: Request, service: Literal["analysis", "generation"]
) -> dict:
    return await settings_service.remove_key(
        get_db(request), get_settings(request), service
    )


@router.post("/test")
async def test_service(request: Request, payload: ServiceTest) -> dict:
    return await settings_service.test_service(
        get_db(request),
        get_settings(request),
        payload.service,
        _vision(request),
        _generation(request),
    )


@router.get("/storage")
async def get_storage(request: Request) -> dict:
    return await settings_service.storage_summary(
        get_db(request), get_settings(request)
    )


@router.post("/clear-data")
async def clear_data(request: Request, payload: ClearDataRequest) -> dict:
    return await settings_service.clear_data(
        get_db(request), get_settings(request), confirm=payload.confirm
    )
