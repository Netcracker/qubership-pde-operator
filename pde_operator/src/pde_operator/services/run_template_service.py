from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.db.models.run_template import RunTemplate
from pde_operator.schemas.run_templates import (
    CreateSimpleRunTemplateRequest,
    UpdateSimpleRunTemplateRequest,
    normalize_tags,
)


class RunTemplateService:
    """Catalog + simple run-template CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_templates(
            self,
            *,
            q: str | None = None,
            tag: str | None = None,
            offset: int = 0,
            limit: int = 20,
    ) -> tuple[list[RunTemplate], int]:
        filters = select(RunTemplate)
        query_text = (q or "").strip()
        if query_text:
            like = f"%{query_text}%"
            filters = filters.where(
                or_(
                    cast(RunTemplate.id, String).ilike(like),
                    RunTemplate.name.ilike(like),
                    RunTemplate.description.ilike(like),
                    cast(RunTemplate.tags, String).ilike(like),
                )
            )
        tag_value = (tag or "").strip()
        if tag_value:
            filters = filters.where(RunTemplate.tags.contains([tag_value]))

        count_query = select(func.count()).select_from(filters.subquery())
        total = int((await self._session.execute(count_query)).scalar_one())

        query = filters.order_by(RunTemplate.updated_at.desc(), RunTemplate.id.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def get_template(self, template_id: UUID) -> RunTemplate | None:
        return await self._session.get(RunTemplate, template_id)

    async def create_template(self, request: CreateSimpleRunTemplateRequest) -> RunTemplate:
        template = self._build_template(request)
        self._session.add(template)
        await self._session.commit()
        await self._session.refresh(template)
        return template

    @staticmethod
    def _build_template(request: CreateSimpleRunTemplateRequest) -> RunTemplate:
        return RunTemplate(
            id=uuid4(),
            name=request.name,
            description=request.description,
            tags=normalize_tags(request.tags),
            template_kind="simple",
            declarative_spec=None,
            profile_id=request.profile_id or "default",
            pipeline_data=request.pipeline_data,
            pipeline_vars=request.pipeline_vars,
            pipeline_vars_secure=request.pipeline_vars_secure,
            is_dry_run=request.is_dry_run,
            log_level=request.log_level,
            env_vars=request.env_vars,
            pde_image=(request.pde_image or "").strip() or None,
        )

    async def update_template(self, template_id: UUID, request: UpdateSimpleRunTemplateRequest) -> RunTemplate:
        template = await self._session.get(RunTemplate, template_id)
        if template is None:
            raise RunTemplateNotFoundError(template_id)
        if template.template_kind != "simple":
            raise RunTemplateKindError(template_id, expected="simple", actual=template.template_kind)

        template.name = request.name
        template.description = request.description
        template.tags = normalize_tags(request.tags)
        template.profile_id = request.profile_id or "default"
        template.pipeline_data = request.pipeline_data
        template.pipeline_vars = request.pipeline_vars
        template.pipeline_vars_secure = request.pipeline_vars_secure
        template.is_dry_run = request.is_dry_run
        template.log_level = request.log_level
        template.env_vars = request.env_vars
        template.pde_image = (request.pde_image or "").strip() or None
        template.updated_at = datetime.now(UTC)

        await self._session.commit()
        await self._session.refresh(template)
        return template

    async def delete_template(self, template_id: UUID) -> None:
        template = await self._session.get(RunTemplate, template_id)
        if template is None:
            raise RunTemplateNotFoundError(template_id)
        await self._session.delete(template)
        await self._session.commit()


class RunTemplateNotFoundError(LookupError):
    def __init__(self, template_id: UUID, *, message: str | None = None) -> None:
        self.template_id = template_id
        super().__init__(message or f"Run template '{template_id}' not found")


class RunTemplateKindError(ValueError):
    def __init__(self, template_id: UUID, *, expected: str, actual: str) -> None:
        self.template_id = template_id
        self.expected = expected
        self.actual = actual
        super().__init__(f"Run template '{template_id}' is kind '{actual}', expected '{expected}' for this operation")
