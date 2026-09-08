from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pde_operator.schemas.job_resources import JobResources


class ProfileListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pde_image: str
    created_at: datetime
    updated_at: datetime


class ProfileDetail(ProfileListItem):
    env_vars: dict = Field(default_factory=dict)
    resources: dict = Field(default_factory=dict)


class ProfileListResponse(BaseModel):
    items: list[ProfileListItem]
    total: int
    offset: int = 0
    limit: int = 20


class _ProfileBase(BaseModel):
    pde_image: str
    env_vars: dict = Field(default_factory=dict)
    resources: dict = Field(default_factory=dict)

    @field_validator("resources")
    @classmethod
    def validate_resources(cls, value: dict) -> dict:
        JobResources.model_validate(value)
        return value


class CreateProfileRequest(_ProfileBase):
    id: str


class UpdateProfileRequest(_ProfileBase):
    pass
