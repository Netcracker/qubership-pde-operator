from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from pde_operator.config import Settings
from pde_operator.db.models.run import Run, RunStatus
from pde_operator.services.job_service import JobService
from pde_operator.services.run_service import RunNotCancellableError, RunNotFoundError, RunService


def _settings() -> Settings:
    return Settings(k8s_job_creation_enabled=False, cancel_grace_seconds=30)


def _in_progress_run(**overrides) -> Run:
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "profile_id": "default",
        "status": RunStatus.IN_PROGRESS,
        "pde_image": "ghcr.io/example/pde:1",
        "pipeline_data": "https://example.com/pipeline.yaml",
        "created_at": now,
        "started_at": now,
        "k8s_job_name": "pde-run-x",
    }
    data.update(overrides)
    return Run(**data)


@pytest.mark.asyncio
async def test_cancel_run_sets_cancel_requested_and_signals() -> None:
    run = _in_progress_run()
    session = AsyncMock()
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    job_service = MagicMock()
    job_service.signal_run_job_sigint.return_value = "pod-1"
    service = RunService(session, _settings(), job_service=job_service)

    with patch("pde_operator.services.run_service.asyncio.to_thread", new_callable=AsyncMock) as to_thread:
        to_thread.return_value = "pod-1"
        result = await service.cancel_run(run.id)

    assert result.cancel_requested_at is not None
    session.commit.assert_awaited()
    to_thread.assert_awaited_once_with(job_service.signal_run_job_sigint, "pde-run-x")


@pytest.mark.asyncio
async def test_cancel_run_not_found() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    service = RunService(session, _settings())

    with pytest.raises(RunNotFoundError):
        await service.cancel_run(uuid4())


@pytest.mark.asyncio
async def test_cancel_run_already_terminal() -> None:
    run = _in_progress_run(status=RunStatus.SUCCESS)
    session = AsyncMock()
    session.get = AsyncMock(return_value=run)
    service = RunService(session, _settings())

    with pytest.raises(RunNotCancellableError, match="already SUCCESS"):
        await service.cancel_run(run.id)


@pytest.mark.asyncio
async def test_cancel_run_already_requested() -> None:
    run = _in_progress_run(cancel_requested_at=datetime.now(UTC))
    session = AsyncMock()
    session.get = AsyncMock(return_value=run)
    service = RunService(session, _settings())

    with pytest.raises(RunNotCancellableError, match="already requested"):
        await service.cancel_run(run.id)


@pytest.mark.asyncio
async def test_cancel_queued_run_marks_cancelled() -> None:
    run = _in_progress_run(status=RunStatus.QUEUED, k8s_job_name=None)
    session = AsyncMock()
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    job_service = MagicMock()
    service = RunService(session, _settings(), job_service=job_service)

    result = await service.cancel_run(run.id)

    assert result.status == RunStatus.CANCELLED
    assert result.finished_at is not None
    job_service.signal_run_job_sigint.assert_not_called()


def test_find_job_pod_returns_running() -> None:
    core_api = MagicMock()
    pod = MagicMock()
    pod.metadata.name = "pde-run-abc-pod"
    pod.status.phase = "Running"
    core_api.list_namespaced_pod.return_value = MagicMock(items=[pod])
    service = JobService(_settings(), core_api=core_api)

    assert service.find_job_pod("pde-run-abc") == "pde-run-abc-pod"
