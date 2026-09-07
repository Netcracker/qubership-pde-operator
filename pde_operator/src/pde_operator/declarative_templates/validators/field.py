from __future__ import annotations

from typing import Any

from pde_operator.declarative_templates.contract.errors import DeclarativeContractError
from pde_operator.declarative_templates.contract.models import FieldSpec
from pde_operator.declarative_templates.validators.pattern import PatternValidator


class FieldValidator:
    @staticmethod
    def validate(field: FieldSpec, value: Any) -> None:
        if field.field_type == "string":
            if not isinstance(value, str):
                raise DeclarativeContractError(f"Field '{field.name}' must be a string")
            PatternValidator.validate(field, value)
        elif field.field_type == "checkbox":
            if isinstance(value, bool):
                return
            if isinstance(value, str) and value.lower() in {"true", "false"}:
                return
            raise DeclarativeContractError(f"Field '{field.name}' must be boolean")
        elif field.field_type == "select":
            if not isinstance(value, str):
                raise DeclarativeContractError(f"Field '{field.name}' must be a string")
            PatternValidator.validate(field, value)
            if field.options is None:
                return
            if field.select_type == "multi":
                parts = [part for part in value.split(",") if part != ""]
                allowed = set(field.options)
                for part in parts:
                    if part not in allowed:
                        raise DeclarativeContractError(f"Field '{field.name}' value is not one of the allowed options")
            elif value not in field.options:
                raise DeclarativeContractError(f"Field '{field.name}' value is not one of the allowed options")
