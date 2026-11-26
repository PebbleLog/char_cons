"""分析任务接口：启动、轮询、取消、单镜头观察结果。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..providers.base import VisionProvider
from ..services import analysis_service
from .deps import get_db, get_settings

router = APIRouter(prefix="/api/tasks", tags=["analysis"])


def _provider(request: Request) -> VisionProvider:
    factory = getattr(request.app.state, "vision_provider_factory", None)
    if factory is None:
        from ..providers.factory import make_vision_provider

        factory = make_vision_provider
    return factory(request.app.state.settings)


@router.post("/{task_id}/analyze", status_code=202)
async def start_analysis(request: Request, task_id: str) -> dict:
    return await analysis_service.start_analysis(
        get_db(request),
        get_settings(request),
        task_id,
        _provider(request),
        request.app.state.task_registry,
    )


@router.get("/{task_id}/analysis")
async def get_analysis(request: Request, task_id: str) -> dict:
    return await analysis_service.get_analysis_status(get_db(request), task_id)


@router.post("/{task_id}/cancel")
async def cancel_analysis(request: Request, task_id: str) -> dict:
    return await analysis_service.cancel_analysis(
        get_db(request), task_id, request.app.state.task_registry
    )


@router.get("/{task_id}/shots/{shot_id}/observations")
async def get_observations(request: Request, task_id: str, shot_id: str) -> dict:
    return await analysis_service.get_shot_observations(
        get_db(request), task_id, shot_id
    )
