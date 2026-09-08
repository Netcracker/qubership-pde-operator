from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.db.models.run_template import RunTemplate
from pde_operator.declarative_templates.contract.parser import DeclarativeTemplateParser


class DeclarativeTemplateStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_from_yaml(self, *, yaml_text: str, now: datetime | None = None) -> RunTemplate:
        contract = DeclarativeTemplateParser.parse_yaml(yaml_text)
        updated_at = now or datetime.now(UTC)

        template = RunTemplate(
            id=uuid4(),
            name=contract.name,
            pipeline_data="",
        )
        template.description = None
        template.tags = []
        template.template_kind = "declarative"
        template.updated_at = updated_at
        template.declarative_spec = contract.model_dump(mode="json")

        self._session.add(template)
        await self._session.commit()
        await self._session.refresh(template)
        return template
