from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pde_operator.declarative_templates.contract.errors import DeclarativeContractError
from pde_operator.declarative_templates.contract.models import DeclarativeRunTemplate
from pde_operator.declarative_templates.services.form_state import DeclarativeFormStateUtils, EffectiveFormState
from pde_operator.declarative_templates.validators.field import FieldValidator


@dataclass(frozen=True)
class AssembledRunPayload:
    profile_id: str
    pipeline_data: str
    pipeline_vars: str | None
    pipeline_vars_secure: str | None
    is_dry_run: bool
    log_level: str
    env_vars: dict[str, Any] | None
    pde_image: str | None


class DeclarativeEngine:
    """Validate values and assemble an operator create-run payload."""

    @staticmethod
    def build_run_payload(contract: DeclarativeRunTemplate, values: dict[str, Any]) -> AssembledRunPayload:
        effective = DeclarativeFormStateUtils.evaluate(contract, values)
        resolved = DeclarativeEngine._collect_submitted(effective)
        return DeclarativeEngine._assemble(effective, resolved)

    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

    @staticmethod
    def _collect_submitted(effective: EffectiveFormState) -> dict[str, Any]:
        submitted: dict[str, Any] = {}
        for name, field in effective.fields.items():
            value = effective.resolved_values.get(name)
            if DeclarativeEngine._is_empty(value):
                if effective.visible.get(name, True) and effective.required.get(name, False):
                    raise DeclarativeContractError(f"Missing required declarative field '{name}'")
                continue
            if effective.visible.get(name, True):
                FieldValidator.validate(field, value)
            submitted[name] = value
        return submitted

    @staticmethod
    def _assemble(effective: EffectiveFormState, submitted: dict[str, Any]) -> AssembledRunPayload:
        profile_id = DeclarativeEngine._get_singleton(effective, submitted, "profile", default="default")
        pipeline_data = DeclarativeEngine._get_singleton(effective, submitted, "pipeline_data", required=True)
        log_level = DeclarativeEngine._get_singleton(effective, submitted, "log_level", default="INFO")
        is_dry_run = DeclarativeEngine._get_singleton(effective, submitted, "is_dry_run", default=False)

        pipeline_vars: dict[str, str] = {}
        pipeline_vars_secure: dict[str, str] = {}
        env_vars: dict[str, Any] = {}
        for name, value in submitted.items():
            field = effective.fields[name]
            if field.bind_to == "pipeline_var":
                text = DeclarativeEngine._as_pipeline_text(value)
                if field.secure:
                    pipeline_vars_secure[name] = text
                else:
                    pipeline_vars[name] = text
            elif field.bind_to == "env_var":
                env_vars[name] = value

        pipeline_vars_text = "\n".join(f"{k}={pipeline_vars[k]}" for k in sorted(pipeline_vars)) if pipeline_vars else None
        pipeline_vars_secure_text = "\n".join(f"{k}={pipeline_vars_secure[k]}" for k in sorted(pipeline_vars_secure)) if pipeline_vars_secure else None

        return AssembledRunPayload(
            profile_id=str(profile_id),
            pipeline_data=str(pipeline_data),
            pipeline_vars=pipeline_vars_text,
            pipeline_vars_secure=pipeline_vars_secure_text,
            is_dry_run=DeclarativeEngine._as_bool(is_dry_run),
            log_level=str(log_level),
            env_vars=env_vars or None,
            pde_image=None,
        )

    @staticmethod
    def _get_singleton(
            effective: EffectiveFormState,
            submitted: dict[str, Any],
            bind_to: str,
            *,
            default: Any = None,
            required: bool = False,
    ) -> Any:
        for field in effective.fields.values():
            if field.bind_to != bind_to:
                continue
            if field.name in submitted:
                return submitted[field.name]
            if not DeclarativeEngine._is_empty(field.value):
                return field.value
        if default is not None or not required:
            return default
        raise DeclarativeContractError(f"Missing required bind_to '{bind_to}'")

    @staticmethod
    def _as_pipeline_text(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)
