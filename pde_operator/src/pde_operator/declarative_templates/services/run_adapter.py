from __future__ import annotations

from typing import Any
from uuid import UUID

from pde_operator.db.models.run_template import RunTemplate
from pde_operator.declarative_templates.contract.errors import DeclarativeContractError
from pde_operator.declarative_templates.contract.models import DeclarativeRunTemplate
from pde_operator.declarative_templates.engine import AssembledRunPayload, DeclarativeEngine
from pde_operator.schemas.runs import CreateRunRequest


class DeclarativeRunAdapter:

    @staticmethod
    def load_contract(template: RunTemplate) -> DeclarativeRunTemplate:
        if template.declarative_spec is None:
            raise DeclarativeContractError(f"Declarative template '{template.id}' missing contract JSON")
        return DeclarativeRunTemplate.model_validate(template.declarative_spec)

    @staticmethod
    def to_create_run_request_from_template(template: RunTemplate, values: dict[str, Any]) -> CreateRunRequest:
        payload = DeclarativeEngine.build_run_payload(DeclarativeRunAdapter.load_contract(template), values)
        return DeclarativeRunAdapter._to_create_run_request(payload, template_id=template.id)

    @staticmethod
    def _to_create_run_request(payload: AssembledRunPayload, *, template_id: UUID) -> CreateRunRequest:
        return CreateRunRequest(
            profile_id=payload.profile_id,
            pipeline_data=payload.pipeline_data,
            pipeline_vars=payload.pipeline_vars,
            pipeline_vars_secure=payload.pipeline_vars_secure,
            is_dry_run=payload.is_dry_run,
            log_level=payload.log_level,
            env_vars=payload.env_vars,
            pde_image=payload.pde_image,
            created_from_template_id=template_id,
        )
