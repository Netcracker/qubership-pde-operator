from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CleanupRequest(BaseModel):
    older_than: datetime = Field(description="Delete runs with created_at strictly before this timestamp")


class CleanupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    older_than: datetime
    deleted: int
    failed: int
