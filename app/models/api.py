"""API 请求模型。响应以显式字典序列化，字段名与前端保持 camelCase。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Stripped(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TaskCreate(_Stripped):
    name: str | None = Field(default=None, max_length=100)
    character_name: str | None = Field(default=None, alias="characterName", max_length=50)
    profile_raw: str = Field(alias="profileRaw", max_length=500)
    script_raw: str = Field(alias="scriptRaw", max_length=1000)
    default_batch_size: int = Field(default=4, alias="defaultBatchSize", ge=1, le=4)

    @field_validator("profile_raw", "script_raw")
    @classmethod
    def _required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("不能为空")
        return stripped

    @field_validator("name", "character_name")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskUpdate(_Stripped):
    name: str | None = Field(default=None, max_length=100)
    character_name: str | None = Field(default=None, alias="characterName", max_length=50)
    profile_raw: str | None = Field(default=None, alias="profileRaw", max_length=500)
    script_raw: str | None = Field(default=None, alias="scriptRaw", max_length=1000)
    default_batch_size: int | None = Field(
        default=None, alias="defaultBatchSize", ge=1, le=4
    )

    @field_validator("profile_raw", "script_raw")
    @classmethod
    def _required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("不能为空")
        return stripped

    @field_validator("name", "character_name")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ShotReorder(_Stripped):
    shot_ids: list[str] = Field(alias="shotIds")

    @field_validator("shot_ids")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("镜头编号不能重复")
        return value


class ShotNoteUpdate(_Stripped):
    note: str = Field(max_length=500)

    @field_validator("note")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class SettingsUpdate(_Stripped):
    default_batch_size: int | None = Field(
        default=None, alias="defaultBatchSize", ge=1, le=4
    )
    upload_max_mb: int | None = Field(default=None, alias="uploadMaxMb", ge=1, le=100)
    generation_size: str | None = Field(
        default=None, alias="generationSize", max_length=20
    )
    connect_timeout_seconds: int | None = Field(
        default=None, alias="connectTimeoutSeconds", ge=5, le=60
    )
    vision_timeout_seconds: int | None = Field(
        default=None, alias="visionTimeoutSeconds", ge=60, le=600
    )
    precheck_timeout_seconds: int | None = Field(
        default=None, alias="precheckTimeoutSeconds", ge=60, le=600
    )
    seedream_timeout_seconds: int | None = Field(
        default=None, alias="seedreamTimeoutSeconds", ge=120, le=900
    )
    generation_batch_wait_seconds: int | None = Field(
        default=None, alias="generationBatchWaitSeconds", ge=300, le=1800
    )
    retry_max_attempts: int | None = Field(
        default=None, alias="retryMaxAttempts", ge=0, le=5
    )
    privacy_acknowledged: bool | None = Field(default=None, alias="privacyAcknowledged")


class ServiceUpdate(_Stripped):
    provider: Literal["doubao", "mock"] | None = None
    model: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, alias="baseUrl", max_length=300)
    api_key: str | None = Field(default=None, alias="apiKey", max_length=500)
    size: str | None = Field(default=None, max_length=20)

    @field_validator("model", "base_url")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("size")
    @classmethod
    def _size(cls, value: str | None) -> str:
        return (value or "").strip()

    @field_validator("api_key")
    @classmethod
    def _key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ServiceTest(_Stripped):
    service: Literal["analysis", "generation"]


class ClearDataRequest(_Stripped):
    confirm: bool = False
