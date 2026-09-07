from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import Run, RunStatus
from pde_operator.services.run_service import (
    RunNotFoundError,
    RunNotRetriableError,
    RunService,
    RunStateNotAvailableError,
)
from pde_operator.utils.artifact_utils import ArtifactNotFoundError
from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.schemas.runs import RetryRunRequest
from pde_operator.utils.input_crypto_utils import InputCryptoUtils, MASKED_VALUE


def _encrypted_parent_input(settings: Settings, parent: Run) -> bytes:
    payload = RunInputPayload(
        pipeline_data=parent.pipeline_data,
        pipeline_vars=parent.pipeline_vars,
        pipeline_vars_secure="SECRET=real",
        is_dry_run=parent.is_dry_run,
        log_level=parent.log_level,
    )
    return InputCryptoUtils.encrypt(settings.input_encryption_key, payload.model_dump_json().encode("utf-8"))


def _settings(**overrides) -> Settings:
    data = {
        "k8s_job_creation_enabled": False,
        "operator_base_url": "http://host.minikube.internal:8000",
        "api_prefix": "/api/v1",
        "input_encryption_key": Fernet.generate_key().decode("ascii"),
    }
    data.update(overrides)
    return Settings(**data)


def _profile() -> Profile:
    return Profile(
        id="default",
        pde_image="ghcr.io/netcracker/qubership-pipelines-declarative-executor:v2.2.1",
        env_vars={},
    )


def _parent_run(**overrides) -> Run:
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "profile_id": "default",
        "status": RunStatus.FAILED,
        "created_from_template_id": uuid4(),
        "pde_image": "ghcr.io/netcracker/qubership-pipelines-declarative-executor:v2.2.1",
        "pipeline_data": "https://example.com/pipeline.yaml",
        "pipeline_vars": "ENV=test",
        "is_dry_run": False,
        "log_level": "INFO",
        "state_location": "parent-id/pipeline_dir.zip",
        "created_at": now,
        "started_at": now,
        "finished_at": now,
    }
    data.update(overrides)
    return Run(**data)


@pytest.mark.asyncio
async def test_retry_run_creates_child_with_parent_state() -> None:
    settings = _settings()
    parent = _parent_run()
    profile = _profile()
    session = AsyncMock()

    async def get_model(model, key):
        if model is Run and key == parent.id:
            return parent
        if model is Profile and key == parent.profile_id:
            return profile
        return None

    session.get = AsyncMock(side_effect=get_model)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    artifacts = MagicMock()
    artifacts.get_artifact = MagicMock()
    artifacts.get_run_input_bytes = MagicMock(return_value=_encrypted_parent_input(settings, parent))
    artifacts.put_run_input = MagicMock()
    job_service = MagicMock()
    service = RunService(session, settings, job_service=job_service, artifacts_service=artifacts)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "pde_operator.services.run_service.asyncio.to_thread",
            AsyncMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)),
        )
        result = await service.retry_run(parent.id)

    assert result.id is not None
    assert result.execution_url is not None
    assert result.retry_of_run_id == parent.id
    assert result.profile_id == parent.profile_id
    assert result.created_from_template_id == parent.created_from_template_id
    assert result.pipeline_data == parent.pipeline_data
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_retry_run_not_found() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    service = RunService(session, _settings(), artifacts_service=MagicMock())

    with pytest.raises(RunNotFoundError):
        await service.retry_run(uuid4())


@pytest.mark.asyncio
async def test_retry_run_not_retriable_status() -> None:
    parent = _parent_run(status=RunStatus.SUCCESS)
    session = AsyncMock()
    session.get = AsyncMock(return_value=parent)
    service = RunService(session, _settings(), artifacts_service=MagicMock())

    with pytest.raises(RunNotRetriableError):
        await service.retry_run(parent.id)


@pytest.mark.asyncio
async def test_retry_run_missing_state_location() -> None:
    parent = _parent_run(state_location=None)
    session = AsyncMock()
    session.get = AsyncMock(return_value=parent)
    service = RunService(session, _settings(), artifacts_service=MagicMock())

    with pytest.raises(RunStateNotAvailableError, match="no uploaded state"):
        await service.retry_run(parent.id)


@pytest.mark.asyncio
async def test_retry_run_missing_state_in_storage() -> None:
    parent = _parent_run()
    session = AsyncMock()
    session.get = AsyncMock(return_value=parent)
    artifacts = MagicMock()
    service = RunService(session, _settings(), artifacts_service=artifacts)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "pde_operator.services.run_service.asyncio.to_thread",
            AsyncMock(side_effect=ArtifactNotFoundError("missing")),
        )
        with pytest.raises(RunStateNotAvailableError, match="not found in storage"):
            await service.retry_run(parent.id)


@pytest.mark.asyncio
async def test_retry_run_inherits_env_vars_and_retry_vars() -> None:
    settings = _settings()
    parent = _parent_run(env_vars={"MANUAL": "keep"}, retry_vars="RETRY=1")
    profile = _profile()
    session = AsyncMock()

    async def get_model(model, key):
        if model is Run and key == parent.id:
            return parent
        if model is Profile and key == parent.profile_id:
            return profile
        return None

    session.get = AsyncMock(side_effect=get_model)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    artifacts = MagicMock()
    artifacts.get_artifact = MagicMock()
    artifacts.get_run_input_bytes = MagicMock(return_value=_encrypted_parent_input(settings, parent))
    artifacts.put_run_input = MagicMock()
    service = RunService(session, settings, job_service=MagicMock(), artifacts_service=artifacts)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "pde_operator.services.run_service.asyncio.to_thread",
            AsyncMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)),
        )
        result = await service.retry_run(parent.id)

    assert result.env_vars == {"MANUAL": "keep"}
    assert result.retry_vars == "RETRY=1"


@pytest.mark.asyncio
async def test_retry_run_overrides_env_vars_and_retry_vars() -> None:
    settings = _settings()
    parent = _parent_run(env_vars={"MANUAL": "old"}, retry_vars="OLD=1")
    profile = _profile()
    session = AsyncMock()

    async def get_model(model, key):
        if model is Run and key == parent.id:
            return parent
        if model is Profile and key == parent.profile_id:
            return profile
        return None

    session.get = AsyncMock(side_effect=get_model)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    artifacts = MagicMock()
    artifacts.get_artifact = MagicMock()
    artifacts.get_run_input_bytes = MagicMock(return_value=_encrypted_parent_input(settings, parent))
    artifacts.put_run_input = MagicMock()
    service = RunService(session, settings, job_service=MagicMock(), artifacts_service=artifacts)
    request = RetryRunRequest(env_vars={"MANUAL": "new"}, retry_vars="NEW=2")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "pde_operator.services.run_service.asyncio.to_thread",
            AsyncMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)),
        )
        result = await service.retry_run(parent.id, request)

    assert result.env_vars == {"MANUAL": "new"}
    assert result.retry_vars == "NEW=2"
    stored = InputCryptoUtils.decrypt(settings.input_encryption_key, artifacts.put_run_input.call_args.args[1])
    stored_payload = RunInputPayload.model_validate_json(stored)
    assert stored_payload.retry_vars == "NEW=2"


def test_mask_secure_vars_for_retry_display() -> None:
    masked = InputCryptoUtils.mask_secure_vars("FOO=bar")
    assert masked == f"FOO={MASKED_VALUE}"
