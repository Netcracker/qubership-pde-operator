from pydantic import BaseModel, ConfigDict


class RunInputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_data: str
    pipeline_vars: str | None = None
    pipeline_vars_secure: str | None = None
    is_dry_run: bool
    log_level: str
    retry_vars: str | None = None
