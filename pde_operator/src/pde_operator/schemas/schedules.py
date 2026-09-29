from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pde_operator.db.models.scheduled_run import OverlapPolicy


def normalize_overlap_policy(value: str) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned not in {policy.value for policy in OverlapPolicy}:
        allowed = ", ".join(policy.value for policy in OverlapPolicy)
        raise ValueError(f"overlap_policy must be one of: {allowed}")
    return cleaned


class ScheduledRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    cron_expression: str
    timezone: str
    enabled: bool
    overlap_policy: str
    profile_id: str
    created_from_template_id: UUID | None = None
    next_fire_at: datetime | None = None
    last_fire_at: datetime | None = None
    last_fire_status: str | None = None
    last_fire_error: str | None = None
    last_run_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ScheduledRunDetail(ScheduledRunSummary):
    pipeline_data: str
    pipeline_vars: str | None = None
    pipeline_vars_secure: str | None = None
    is_dry_run: bool
    log_level: str
    env_vars: dict[str, Any] | None = None
    pde_image: str | None = None


class ScheduledRunListResponse(BaseModel):
    items: list[ScheduledRunSummary]
    total: int
    offset: int = 0
    limit: int = 20


class _ScheduledRunBase(BaseModel):
    name: str
    description: str | None = None
    cron_expression: str
    timezone: str = "UTC"
    enabled: bool = True
    overlap_policy: str = OverlapPolicy.ALLOW
    profile_id: str = "default"
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

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, value: str) -> str:
        cron = value.strip()
        if not cron:
            raise ValueError("cron_expression must not be empty")
        return cron

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        timezone = value.strip()
        if not timezone:
            raise ValueError("timezone must not be empty")
        return timezone

    @field_validator("overlap_policy")
    @classmethod
    def validate_overlap_policy(cls, value: str) -> str:
        return normalize_overlap_policy(value)


class CreateScheduledRunRequest(_ScheduledRunBase):
    pipeline_data: str | None = None
    created_from_template_id: UUID | None = None
    declarative_values: dict[str, Any] | None = None


class UpdateScheduledRunRequest(_ScheduledRunBase):
    pipeline_data: str

    @field_validator("pipeline_data")
    @classmethod
    def validate_pipeline_data(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("pipeline_data must not be empty")
        return value


class ImportScheduledRunRequest(UpdateScheduledRunRequest):
    id: UUID | None = None


class SchedulePreviewRequest(BaseModel):
    cron_expression: str
    timezone: str = "UTC"
    count: int = Field(default=3, ge=1, le=10)


class SchedulePreviewResponse(BaseModel):
    next_fire_times: list[datetime]


class TimezonesResponse(BaseModel):
    timezones: list[str]
