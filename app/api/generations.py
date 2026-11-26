"""提示词优化、候选生成、预检、采用与单镜头复检接口（F-08～F-10）。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..providers.base import GenerationProvider, VisionProvider
from ..services import generation_service
from .deps import get_db, get_settings

router = APIRouter(prefix="/api/tasks", tags=["generation"])


class GenerateRequest(BaseModel):
    candidateCount: int = Field(default=4, ge=1, le=4)


class AdoptRequest(BaseModel):
    candidateId: str = Field(min_length=1, max_length=80)


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


@router.get("/{task_id}/issues/{issue_id}/optimizer")
async def get_optimizer(request: Request, task_id: str, issue_id: str) -> dict:
    return await generation_service.get_optimizer_state(
        get_db(request),
        get_settings(request),
        task_id,
        issue_id,
        _vision(request),
    )


@router.post("/{task_id}/issues/{issue_id}/generate", status_code=202)
async def start_generation(
    request: Request, task_id: str, issue_id: str, body: GenerateRequest | None = None
) -> dict:
    return await generation_service.start_generation(
        get_db(request),
        get_settings(request),
        task_id,
        issue_id,
        _generation(request),
        _vision(request),
        request.app.state.task_registry,
        candidate_count=body.candidateCount if body else None,
    )


@router.get("/{task_id}/generations/{generation_id}")
async def get_generation(request: Request, task_id: str, generation_id: str) -> dict:
    return await generation_service.get_generation_state(
        get_db(request), task_id, generation_id
    )


@router.post("/{task_id}/generations/{generation_id}/cancel")
async def cancel_generation(request: Request, task_id: str, generation_id: str) -> dict:
    return await generation_service.cancel_generation(
        get_db(request), task_id, generation_id, request.app.state.task_registry
    )


@router.post("/{task_id}/generations/{generation_id}/adopt")
async def adopt_candidate(
    request: Request, task_id: str, generation_id: str, body: AdoptRequest
) -> dict:
    return await generation_service.adopt_candidate(
        get_db(request),
        get_settings(request),
        task_id,
        generation_id,
        body.candidateId,
        _vision(request),
    )


@router.get(
    "/{task_id}/generations/{generation_id}/candidates/{candidate_id}/image"
)
async def get_candidate_image(
    request: Request,
    task_id: str,
    generation_id: str,
    candidate_id: str,
    variant: Literal["full", "thumb"] = "full",
):
    path, media_type = await generation_service.get_candidate_file(
        get_db(request),
        get_settings(request),
        task_id,
        generation_id,
        candidate_id,
        variant,
    )
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/{task_id}/shots/{shot_id}/optimizer")
async def get_shot_optimizer(request: Request, task_id: str, shot_id: str) -> dict:
    return await generation_service.get_shot_optimizer_state(
        get_db(request),
        get_settings(request),
        task_id,
        shot_id,
        _vision(request),
    )


@router.post("/{task_id}/shots/{shot_id}/generate", status_code=202)
async def start_shot_generation(
    request: Request, task_id: str, shot_id: str, body: GenerateRequest | None = None
) -> dict:
    return await generation_service.start_shot_generation(
        get_db(request),
        get_settings(request),
        task_id,
        shot_id,
        _generation(request),
        _vision(request),
        request.app.state.task_registry,
        candidate_count=body.candidateCount if body else None,
    )


@router.post("/{task_id}/shots/{shot_id}/recheck")
async def retry_recheck(request: Request, task_id: str, shot_id: str) -> dict:
    return await generation_service.retry_recheck(
        get_db(request),
        get_settings(request),
        task_id,
        shot_id,
        _vision(request),
    )
