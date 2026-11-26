"""本地文件存储（技术方案 2.6）。

- 路径全部使用 UUID，数据库保存“相对于 data_dir”的 POSIX 路径；
- 原图、分析副本、缩略图分文件保存，原图永不覆盖；
- 读取时通过 ``safe_join`` 防路径穿越。
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from ..core.config import Settings
from ..core.security import safe_join
from .image_service import ProcessedImage

logger = logging.getLogger(__name__)


def _relative_to_data(settings: Settings, path: Path) -> str:
    return path.relative_to(settings.data_dir).as_posix()


def shot_directory(settings: Settings, task_id: str, shot_id: str) -> Path:
    # task_id/shot_id 来自服务端生成的 UUID，不接受用户输入
    return settings.uploads_dir / task_id / shot_id


def save_shot_images(
    settings: Settings,
    task_id: str,
    shot_id: str,
    processed: ProcessedImage,
    *,
    token: str | None = None,
) -> dict[str, str]:
    """落盘原图/分析副本/缩略图，返回相对路径。

    文件名带随机 token，替换镜头内容时不会覆盖旧版本文件（原图永不覆盖）。
    """
    directory = shot_directory(settings, task_id, shot_id)
    directory.mkdir(parents=True, exist_ok=True)
    token = token or uuid.uuid4().hex[:12]

    original_path = directory / f"{token}_original.{processed.extension}"
    analysis_path = directory / f"{token}_analysis.jpg"
    thumb_path = directory / f"{token}_thumb.jpg"

    _atomic_write(original_path, processed.original_bytes)
    _atomic_write(analysis_path, processed.analysis_jpeg)
    _atomic_write(thumb_path, processed.thumb_jpeg)

    return {
        "original": _relative_to_data(settings, original_path),
        "analysis": _relative_to_data(settings, analysis_path),
        "thumb": _relative_to_data(settings, thumb_path),
    }


def replace_shot_images(
    settings: Settings, task_id: str, shot_id: str, processed: ProcessedImage
) -> dict[str, str]:
    """替换镜头内容：新文件使用新名字，旧文件保留可追溯。"""
    return save_shot_images(settings, task_id, shot_id, processed)


def generation_directory(settings: Settings, task_id: str, generation_id: str) -> Path:
    return settings.generated_dir / task_id / generation_id


def save_generated_candidate(
    settings: Settings,
    task_id: str,
    generation_id: str,
    candidate_index: int,
    processed: ProcessedImage,
) -> dict[str, str]:
    """候选图落盘：完整图 + 缩略图；失败时抛 OSError 由调用方隔离。"""
    directory = generation_directory(settings, task_id, generation_id)
    directory.mkdir(parents=True, exist_ok=True)
    full_path = directory / f"candidate-{candidate_index}_full.{processed.extension}"
    thumb_path = directory / f"candidate-{candidate_index}_thumb.jpg"
    _atomic_write(full_path, processed.original_bytes)
    _atomic_write(thumb_path, processed.thumb_jpeg)
    return {
        "full": _relative_to_data(settings, full_path),
        "thumb": _relative_to_data(settings, thumb_path),
    }


def _atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".part")
    temp.write_bytes(data)
    temp.replace(path)


def resolve_data_path(settings: Settings, relative_path: str) -> Path:
    return safe_join(settings.data_dir, relative_path)


def read_shot_original_bytes(settings: Settings, relative_path: str) -> bytes | None:
    try:
        path = resolve_data_path(settings, relative_path)
        return path.read_bytes() if path.is_file() else None
    except Exception:
        return None


def remove_task_files(settings: Settings, task_id: str) -> None:
    """尽力删除任务相关文件；失败只记录，不阻断数据库删除。"""
    targets = [
        settings.uploads_dir / task_id,
        settings.generated_dir / task_id,
        settings.exports_dir / task_id,
    ]
    for target in targets:
        if target.is_dir():
            try:
                shutil.rmtree(target)
            except OSError as exc:  # 文件占用等
                logger.warning("删除任务文件失败：%s (%s)", target, exc)


def remove_shot_files(settings: Settings, task_id: str, shot_id: str) -> None:
    target = shot_directory(settings, task_id, shot_id)
    if target.is_dir():
        try:
            shutil.rmtree(target)
        except OSError as exc:
            logger.warning("删除镜头文件失败：%s (%s)", target, exc)
