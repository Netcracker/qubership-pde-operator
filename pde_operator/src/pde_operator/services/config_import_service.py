from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import yaml
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run_template import RunTemplate
from pde_operator.declarative_templates.contract.models import DeclarativeRunTemplate
from pde_operator.declarative_templates.contract.parser import DeclarativeTemplateParser, GitLabCiLoader
from pde_operator.schemas.profiles import CreateProfileRequest
from pde_operator.schemas.run_templates import CreateSimpleRunTemplateRequest, normalize_tags
from pde_operator.services.profile_service import DEFAULT_PROFILE_ID, ProfileService

logger = logging.getLogger(__name__)

KNOWN_KINDS = frozenset({"Profile", "SimpleRunTemplate", "DeclarativeRunTemplate"})


class ConfigImportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_config_from_yaml(self, *, yaml_text: str, mode: Literal["merge", "replace"]) -> None:
        try:
            docs = list(yaml.load_all(yaml_text, Loader=GitLabCiLoader))
        except yaml.YAMLError:
            docs = list(yaml.safe_load_all(yaml_text))

        profiles: list[CreateProfileRequest] = []
        simple_templates: list[CreateSimpleRunTemplateRequest] = []
        declarative_templates: list[DeclarativeRunTemplate] = []

        for index, doc in enumerate(docs):
            if doc is None:
                continue
            if not isinstance(doc, dict):
                logger.warning("Config import: skipping document %s (not a mapping)", index)
                continue

            if isinstance(doc.get(".ui-variables"), dict):
                declarative_templates.append(DeclarativeTemplateParser.from_document(doc))
                continue

            kind = doc.get("kind")
            if not isinstance(kind, str) or not kind.strip():
                logger.warning("Config import: skipping document %s (missing kind / .ui-variables)", index)
                continue
            kind = kind.strip()

            if kind not in KNOWN_KINDS:
                logger.warning("Config import: skipping document %s (unknown kind %r)", index, kind)
                continue

            payload = {k: v for k, v in doc.items() if k not in {"apiVersion", "kind"}}
            if kind == "Profile":
                profiles.append(CreateProfileRequest.model_validate(payload))
            elif kind == "SimpleRunTemplate":
                simple_templates.append(CreateSimpleRunTemplateRequest.model_validate(payload))
            else:
                logger.warning("Config import: skipping document %s (kind DeclarativeRunTemplate without .ui-variables)", index)

        if mode == "replace":
            await self._session.execute(delete(Profile).where(Profile.id != DEFAULT_PROFILE_ID))
            await self._session.execute(delete(RunTemplate))

        for request in profiles:
            ProfileService.validate_profile_id(request.id)
            await self._upsert_profile(request)

        for request in simple_templates:
            self._session.add(self._build_simple_template(request))

        now = datetime.now(UTC)
        for contract in declarative_templates:
            self._session.add(self._build_declarative_template(contract, now=now))

        await self._session.commit()

    async def _upsert_profile(self, request: CreateProfileRequest) -> None:
        if existing := await self._session.get(Profile, request.id):
            existing.pde_image = request.pde_image
            existing.env_vars = request.env_vars
            existing.resources = request.resources
            existing.updated_at = datetime.now(UTC)
        else:
            self._session.add(Profile(id=request.id, pde_image=request.pde_image, env_vars=request.env_vars, resources=request.resources))

    @staticmethod
    def _build_simple_template(request: CreateSimpleRunTemplateRequest) -> RunTemplate:
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

    @staticmethod
    def _build_declarative_template(contract: DeclarativeRunTemplate, *, now: datetime) -> RunTemplate:
        return RunTemplate(
            id=uuid4(),
            name=contract.name,
            description=None,
            tags=[],
            template_kind="declarative",
            declarative_spec=contract.model_dump(mode="json"),
            pipeline_data="",
            updated_at=now,
        )
