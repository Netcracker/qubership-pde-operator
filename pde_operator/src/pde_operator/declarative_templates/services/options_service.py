from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.db.models.run_template import RunTemplate
from pde_operator.declarative_templates.contract.models import KNOWN_INTERFACES, EnumOption, FieldSpec
from pde_operator.declarative_templates.providers.cluster_namespaces_provider import ClusterNamespacesProvider
from pde_operator.declarative_templates.providers.git_provider import GitFilesProvider
from pde_operator.declarative_templates.providers.profiles_provider import ProfilesProvider
from pde_operator.declarative_templates.services.run_adapter import DeclarativeRunAdapter
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateNotFoundError


class DeclarativeOptionsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_enum_options(
            self,
            *,
            template_id: UUID,
            field_id: str,
            context: dict[str, Any] | None = None,
    ) -> list[EnumOption]:
        template = await self._load_template_or_raise(template_id)
        if template.declarative_spec is None:
            return []

        contract = DeclarativeRunAdapter.load_contract(template)
        field = next((f for f in contract.fields if f.name == field_id), None)
        if field is None or field.interface is None:
            return []
        if field.interface not in KNOWN_INTERFACES:
            return []
        return await self._list_options(field, context or {})

    async def _list_options(self, field: FieldSpec, context: dict[str, Any]) -> list[EnumOption]:
        if field.interface == ClusterNamespacesProvider.INTERFACE_NAME:
            return ClusterNamespacesProvider.list_options(field, context)
        if field.interface == GitFilesProvider.INTERFACE_NAME:
            return GitFilesProvider.list_options(field, context)
        if field.interface == ProfilesProvider.INTERFACE_NAME:
            return await ProfilesProvider.list_options(self._session, field, context)
        return []

    async def _load_template_or_raise(self, template_id: UUID) -> RunTemplate:
        template = await self._session.get(RunTemplate, template_id)
        if template is None:
            raise RunTemplateNotFoundError(template_id)
        if template.template_kind != "declarative":
            raise RunTemplateKindError(template_id, expected="declarative", actual=template.template_kind)
        return template
