from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateRunRequest(BaseModel):
    profile_id: str = "default"
    pipeline_data: str
    pipeline_vars: str | None = None
    pipeline_vars_secure: str | None = None
    is_dry_run: bool = False
    log_level: str = "INFO"
    env_vars: dict[str, Any] | None = None
    pde_image: str | None = None
    created_from_template_id: UUID | None = None


class RetryRunRequest(BaseModel):
    env_vars: dict[str, Any] | None = None
    retry_vars: str | None = None
    pde_image: str | None = None


class CreateRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    execution_url: str
    created_at: datetime


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: str
    status: str
    pde_image: str
    pipeline_data: str
    is_dry_run: bool
    log_level: str
    name: str | None
    k8s_job_name: str | None
    execution_url: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunDetail(RunSummary):
    pipeline_vars: str | None
    pipeline_vars_secure: str | None
    retry_vars: str | None
    triggered_by: str | None
    progress_json: dict | None
    status_updated_at: datetime | None
    report_updated_at: datetime | None
    log_updated_at: datetime | None
    state_location: str | None
    retry_of_run_id: UUID | None
    cancel_requested_at: datetime | None = None
    finish_code: str | None = None
    finish_message: str | None = None
    created_from_template_id: UUID | None = None
    created_from_template_name: str | None = None


class StatusDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    status_updated_at: datetime


class ReportDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    report_updated_at: datetime


class LogDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    log_updated_at: datetime


class RunListResponse(BaseModel):
    items: list[RunSummary]
    total: int = Field(description="Total runs matching filters (not just this page)")
    offset: int = 0
    limit: int = 20


class ArtifactsUploadResponse(BaseModel):
    id: UUID
    state_location: str | None = None
