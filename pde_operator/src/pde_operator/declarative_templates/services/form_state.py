from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pde_operator.declarative_templates.contract.models import DeclarativeRunTemplate, FieldSpec
from pde_operator.declarative_templates.services.rsql import RsqlUtils


@dataclass(frozen=True)
class EffectiveFormState:
    fields: dict[str, FieldSpec]
    visible: dict[str, bool]
    required: dict[str, bool]
    resolved_values: dict[str, Any]


class DeclarativeFormStateUtils:
    """Resolve defaults and evaluate hide/required RSQL conditions."""

    @staticmethod
    def evaluate(contract: DeclarativeRunTemplate, user_values: dict[str, Any]) -> EffectiveFormState:
        fields = {f.name: f for f in contract.fields}
        resolved: dict[str, Any] = {}
        for name, field in fields.items():
            if name in user_values:
                resolved[name] = user_values[name]
            else:
                resolved[name] = field.value

        visible: dict[str, bool] = {}
        required: dict[str, bool] = {}
        for name, field in fields.items():
            is_hidden = field.hidden or RsqlUtils.evaluate(field.hide_condition, resolved)
            visible[name] = not is_hidden
            if not visible[name]:
                required[name] = False
            else:
                required[name] = bool(field.required) or RsqlUtils.evaluate(field.required_condition, resolved)

        return EffectiveFormState(fields=fields, visible=visible, required=required, resolved_values=resolved)
