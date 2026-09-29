from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pde_operator.schemas.runs import CreateRunRequest


class RunInputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_data: str
    pipeline_vars: str | None = None
    pipeline_vars_secure: str | None = None
    is_dry_run: bool
    log_level: str
    retry_vars: str | None = None

    @classmethod
    def from_create_request(cls, request: CreateRunRequest) -> RunInputPayload:
        return cls(
            pipeline_data=request.pipeline_data,
            pipeline_vars=request.pipeline_vars,
            pipeline_vars_secure=request.pipeline_vars_secure,
            is_dry_run=request.is_dry_run,
            log_level=request.log_level,
        )
