from typing import Any

from pydantic import BaseModel, Field

from pde_operator.declarative_templates.contract.models import EnumOption


class GetDeclarativeEnumOptionsRequest(BaseModel):
    fieldId: str
    context: dict[str, Any] = Field(default_factory=dict)


class GetDeclarativeEnumOptionsResponse(BaseModel):
    options: list[EnumOption]


class CreateDeclarativeRunFromTemplateRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict, description="Map of declarative field ids to user-provided values")
