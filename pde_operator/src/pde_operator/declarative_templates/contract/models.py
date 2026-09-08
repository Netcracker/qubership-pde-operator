from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

FieldType = Literal["string", "checkbox", "select"]
SelectType = Literal["single", "multi"]
BindTo = Literal["pipeline_var", "env_var", "pipeline_data", "is_dry_run", "log_level", "profile"]

KNOWN_INTERFACES = frozenset({"Profiles", "ClusterNamespaces", "GitFiles"})


class EnumOption(BaseModel):
    value: str
    label: str
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _default_label(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("label") is None and "value" in data:
            data = {**data, "label": data["value"]}
        return data


class ValidatorPattern(BaseModel):
    type: Literal["pattern"] = "pattern"
    value: str
    message: str


class FieldSpec(BaseModel):
    name: str
    value: Any = None
    description: str | None = None
    options: list[str] | None = None
    field_type: FieldType = "string"
    select_type: SelectType = "single"
    required: bool = False
    required_condition: str | None = None
    hide_condition: str | None = None
    hidden: bool = False
    readonly: bool = False
    secure: bool = False
    placeholder: str | None = None
    label: str
    bind_to: BindTo = "pipeline_var"
    validators: list[ValidatorPattern] = Field(default_factory=list)
    interface: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _default_label(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("label") is None and "name" in data:
            data = {**data, "label": data["name"]}
        return data


class DeclarativeRunTemplate(BaseModel):
    name: str
    fields: list[FieldSpec] = Field(default_factory=list)
