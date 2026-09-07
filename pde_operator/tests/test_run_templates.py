from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import Run
from pde_operator.db.models.run_template import RunTemplate
from pde_operator.schemas.run_templates import CreateRunFromTemplateRequest, CreateSimpleRunTemplateRequest
from pde_operator.services.profile_service import ProfileNotFoundError
from pde_operator.services.run_service import RunService
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateService


def _settings() -> Settings:
    return Settings(
        k8s_job_creation_enabled=False,
        ui_enabled=False,
        retention_enabled=False,
        api_admin_token="admin",
        job_token_signing_key="test-job-token-signing-key-32b!!",
        input_encryption_key="test-input-encryption-key",
    )


def _template(**overrides) -> RunTemplate:
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "name": "Deploy prod",
        "description": "Nightly deploy",
        "tags": ["deploy", "nightly"],
        "template_kind": "simple",
        "profile_id": "default",
        "pipeline_data": "https://example.com/pipeline.yaml",
        "pipeline_vars": "FOO=1",
        "pipeline_vars_secure": "SECRET=x",
        "is_dry_run": False,
        "log_level": "INFO",
        "env_vars": {"A": "1"},
        "pde_image": None,
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return RunTemplate(**data)


def _profile(**overrides) -> Profile:
    data = {
        "id": "default",
        "pde_image": "pde:dev",
        "env_vars": {},
        "resources": {},
    }
    data.update(overrides)
    return Profile(**data)


@pytest.mark.asyncio
async def test_create_template_assigns_uuid() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = RunTemplateService(session)
    template = await service.create_template(
        CreateSimpleRunTemplateRequest(
            name="Deploy prod",
            pipeline_data="https://example.com/p.yaml",
        )
    )
    assert template.id is not None
    assert template.name == "Deploy prod"
    assert template.template_kind == "simple"
    session.add.assert_called_once()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_run_from_simple_template_sets_audit_and_values() -> None:
    template = _template()
    profile = _profile()
    created: list[Run] = []

    session = AsyncMock()

    async def _get(model, key):
        if model is RunTemplate and key == template.id:
            return template
        if model is Profile and key == "default":
            return profile
        return None

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock(side_effect=lambda obj: created.append(obj) if isinstance(obj, Run) else None)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service = RunService(session, _settings(), artifacts_service=MagicMock())

    run = await service.create_run_from_simple_template(template.id)
    assert run is created[0]
    assert run.id is not None
    assert run.execution_url is not None
    assert run.created_from_template_id == template.id
    assert run.pipeline_data == template.pipeline_data
    assert run.pipeline_vars == "FOO=1"
    assert run.pipeline_vars_secure == "SECRET=[MASKED]"
    assert run.profile_id == "default"
    assert run.env_vars == {"A": "1"}


@pytest.mark.asyncio
async def test_create_run_from_simple_template_rejects_declarative_kind() -> None:
    template = _template(template_kind="declarative")
    session = AsyncMock()
    session.get = AsyncMock(return_value=template)
    service = RunService(session, _settings())
    with pytest.raises(RunTemplateKindError):
        await service.create_run_from_simple_template(template.id)


@pytest.mark.asyncio
async def test_create_run_from_simple_template_remaps_missing_profile() -> None:
    template = _template(profile_id="gone")
    profile = _profile()

    session = AsyncMock()

    async def _get(model, key):
        if model is RunTemplate and key == template.id:
            return template
        if model is Profile and key == "gone":
            return None
        if model is Profile and key == "default":
            return profile
        return None

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service = RunService(session, _settings(), artifacts_service=MagicMock())

    run = await service.create_run_from_simple_template(template.id)
    assert run.profile_id == "default"
    assert run.created_from_template_id == template.id
    assert run.id is not None
    assert run.execution_url is not None


@pytest.mark.asyncio
async def test_create_run_from_simple_template_override_and_missing_default_profile() -> None:
    template = _template(profile_id="gone")
    session = AsyncMock()
    session.get = AsyncMock(side_effect=lambda model, key: template if model is RunTemplate else None)
    service = RunService(session, _settings())
    with pytest.raises(ProfileNotFoundError):
        await service.create_run_from_simple_template(
            template.id,
            CreateRunFromTemplateRequest(pipeline_vars="BAR=2"),
        )


@pytest.mark.asyncio
async def test_update_simple_template_rejects_declarative_kind() -> None:
    template = _template(template_kind="declarative")
    session = AsyncMock()
    session.get = AsyncMock(return_value=template)
    service = RunTemplateService(session)
    with pytest.raises(RunTemplateKindError):
        await service.update_template(
            template.id,
            CreateSimpleRunTemplateRequest(name="x", pipeline_data="https://example.com/p.yaml"),
        )


@pytest.mark.asyncio
async def test_get_run_includes_template_name_when_template_exists() -> None:
    template = _template(name="Deploy")
    run_id = uuid4()
    run = Run(
        id=run_id,
        profile_id="default",
        status="SUCCESS",
        pde_image="pde:dev",
        pipeline_data="https://example.com/pipeline.yaml",
        is_dry_run=False,
        log_level="INFO",
        created_from_template_id=template.id,
        execution_url=f"http://operator/api/v1/runs/{run_id}",
        created_at=datetime.now(UTC),
    )
    session = AsyncMock()

    async def _get(model, key):
        if model is Run and key == run_id:
            return run
        if model is RunTemplate and key == template.id:
            return template
        return None

    session.get = AsyncMock(side_effect=_get)
    service = RunService(session, _settings())

    detail = await service.get_run(run_id)
    assert detail is not None
    assert detail.created_from_template_id == template.id
    assert detail.created_from_template_name == "Deploy"


@pytest.mark.asyncio
async def test_get_run_omits_template_name_when_template_deleted() -> None:
    template_id = uuid4()
    run_id = uuid4()
    run = Run(
        id=run_id,
        profile_id="default",
        status="SUCCESS",
        pde_image="pde:dev",
        pipeline_data="https://example.com/pipeline.yaml",
        is_dry_run=False,
        log_level="INFO",
        created_from_template_id=template_id,
        execution_url=f"http://operator/api/v1/runs/{run_id}",
        created_at=datetime.now(UTC),
    )
    session = AsyncMock()

    async def _get(model, key):
        if model is Run and key == run_id:
            return run
        return None

    session.get = AsyncMock(side_effect=_get)
    service = RunService(session, _settings())

    detail = await service.get_run(run_id)
    assert detail is not None
    assert detail.created_from_template_id == template_id
    assert detail.created_from_template_name is None
