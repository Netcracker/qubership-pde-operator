from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_tags(value: list[str] | None) -> list[str]:
    if not value:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in value:
        tag = (raw or "").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


class RunTemplateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    template_kind: str = Field(default="simple")
    profile_id: str
    is_dry_run: bool
    log_level: str
    created_at: datetime
    updated_at: datetime


class RunTemplateDetail(RunTemplateSummary):
    pipeline_data: str
    pipeline_vars: str | None = None
    pipeline_vars_secure: str | None = None
    env_vars: dict[str, Any] | None = None
    pde_image: str | None = None
    declarative_spec: dict[str, Any] | None = None


class RunTemplateListResponse(BaseModel):
    items: list[RunTemplateSummary]
    total: int
    offset: int = 0
    limit: int = 20


class _RunTemplateBase(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    profile_id: str = "default"
    pipeline_data: str
    pipeline_vars: str | None = None
    pipeline_vars_secure: str | None = None
    is_dry_run: bool = False
    log_level: str = "INFO"
    env_vars: dict[str, Any] | None = None
    pde_image: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name must not be empty")
        return name

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("tags must be a list of strings")
        return normalize_tags([str(item) for item in value])

    @field_validator("pipeline_data")
    @classmethod
    def validate_pipeline_data(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("pipeline_data must not be empty")
        return value


class CreateSimpleRunTemplateRequest(_RunTemplateBase):
    pass


class UpdateSimpleRunTemplateRequest(_RunTemplateBase):
    pass


class CreateRunFromTemplateRequest(BaseModel):
    """Optional overrides when starting a run from a template. Unset fields use the template."""

    profile_id: str | None = None
    pipeline_data: str | None = None
    pipeline_vars: str | None = None
    pipeline_vars_secure: str | None = None
    is_dry_run: bool | None = None
    log_level: str | None = None
    env_vars: dict[str, Any] | None = None
    pde_image: str | None = None
