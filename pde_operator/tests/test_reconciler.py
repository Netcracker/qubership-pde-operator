import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from kubernetes.client.exceptions import ApiException

from pde_operator.config import Settings
from pde_operator.db.models.run import Run, RunStatus
from pde_operator.services.job_service import JobPhase, JobService
from pde_operator.services.job_reconciler import JobReconciler


def _settings() -> Settings:
    return Settings(
        k8s_namespace="pde-system",
        k8s_job_creation_enabled=False,
        reconciler_stuck_timeout_seconds=60,
    )


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


def test_get_job_phase_succeeded() -> None:
    batch_api = MagicMock()
    batch_api.read_namespaced_job.return_value = MagicMock(
        status=MagicMock(succeeded=1, failed=0)
    )
    service = JobService(_settings(), batch_api=batch_api)
    assert service.get_job_phase("pde-run-x") == JobPhase.SUCCEEDED


def test_get_job_phase_failed() -> None:
    batch_api = MagicMock()
    batch_api.read_namespaced_job.return_value = MagicMock(
        status=MagicMock(succeeded=0, failed=1)
    )
    service = JobService(_settings(), batch_api=batch_api)
    assert service.get_job_phase("pde-run-x") == JobPhase.FAILED


def test_get_job_phase_missing() -> None:
    batch_api = MagicMock()
    batch_api.read_namespaced_job.side_effect = ApiException(status=404)
    service = JobService(_settings(), batch_api=batch_api)
    assert service.get_job_phase("pde-run-x") == JobPhase.MISSING


def test_delete_run_job_ignores_404() -> None:
    batch_api = MagicMock()
    batch_api.delete_namespaced_job.side_effect = ApiException(status=404)
    service = JobService(_settings(), batch_api=batch_api)
    service.delete_run_job("pde-run-x")  # does not raise


def test_is_stuck_uses_status_updated_at() -> None:
    reconciler = JobReconciler(_settings(), session_factory=MagicMock(), job_service=MagicMock())
    now = datetime.now(UTC)
    run = _in_progress_run(
        created_at=now - timedelta(hours=2),
        started_at=now - timedelta(hours=2),
        status_updated_at=now - timedelta(seconds=30),
    )
    assert reconciler._is_stuck(run, now) is False
    run.status_updated_at = now - timedelta(seconds=120)
    assert reconciler._is_stuck(run, now) is True


def test_reconcile_run_marks_succeeded() -> None:
    job_service = MagicMock()
    job_service.get_job_phase.return_value = JobPhase.SUCCEEDED
    reconciler = JobReconciler(_settings(), session_factory=MagicMock(), job_service=job_service)
    run = _in_progress_run()
    now = datetime.now(UTC)

    assert asyncio.run(reconciler._reconcile_run(run, now)) is True
    assert run.status == RunStatus.SUCCESS
    assert run.finished_at == now


def test_reconcile_run_marks_missing_failed() -> None:
    job_service = MagicMock()
    job_service.get_job_phase.return_value = JobPhase.MISSING
    reconciler = JobReconciler(_settings(), session_factory=MagicMock(), job_service=job_service)
    run = _in_progress_run()
    now = datetime.now(UTC)

    assert asyncio.run(reconciler._reconcile_run(run, now)) is True
    assert run.status == RunStatus.FAILED


def test_reconcile_run_failed_with_cancel_becomes_cancelled() -> None:
    job_service = MagicMock()
    job_service.get_job_phase.return_value = JobPhase.FAILED
    reconciler = JobReconciler(_settings(), session_factory=MagicMock(), job_service=job_service)
    run = _in_progress_run(cancel_requested_at=datetime.now(UTC))
    now = datetime.now(UTC)

    assert asyncio.run(reconciler._reconcile_run(run, now)) is True
    assert run.status == RunStatus.CANCELLED


def test_reconcile_run_cancel_grace_hard_stops() -> None:
    job_service = MagicMock()
    job_service.get_job_phase.return_value = JobPhase.ACTIVE
    settings = Settings(k8s_job_creation_enabled=False, cancel_grace_seconds=30)
    reconciler = JobReconciler(settings, session_factory=MagicMock(), job_service=job_service)
    now = datetime.now(UTC)
    run = _in_progress_run(
        cancel_requested_at=now - timedelta(seconds=31),
        k8s_job_name="pde-run-cancel",
    )

    with patch(
        "pde_operator.services.job_reconciler.asyncio.to_thread",
        new_callable=AsyncMock,
    ) as to_thread:
        to_thread.side_effect = [JobPhase.ACTIVE, None, None]
        assert asyncio.run(reconciler._reconcile_run(run, now)) is True

    assert run.status == RunStatus.CANCELLED
    to_thread.assert_any_await(job_service.signal_run_job_sigint, "pde-run-cancel")
    to_thread.assert_any_await(job_service.delete_run_job, "pde-run-cancel")


def test_reconcile_run_cancel_within_grace_waits() -> None:
    job_service = MagicMock()
    job_service.get_job_phase.return_value = JobPhase.ACTIVE
    settings = Settings(k8s_job_creation_enabled=False, cancel_grace_seconds=30)
    reconciler = JobReconciler(settings, session_factory=MagicMock(), job_service=job_service)
    now = datetime.now(UTC)
    run = _in_progress_run(cancel_requested_at=now - timedelta(seconds=5))

    with patch(
        "pde_operator.services.job_reconciler.asyncio.to_thread",
        new_callable=AsyncMock,
    ) as to_thread:
        to_thread.side_effect = [JobPhase.ACTIVE, None]
        assert asyncio.run(reconciler._reconcile_run(run, now)) is False

    to_thread.assert_any_await(job_service.signal_run_job_sigint, "pde-run-x")
    assert run.status == RunStatus.IN_PROGRESS


def test_reconcile_run_deletes_stuck_job() -> None:
    job_service = MagicMock()
    job_service.get_job_phase.return_value = JobPhase.ACTIVE
    job_service.get_pod_diagnostic.return_value = "pde: ImagePullBackOff (Back-off pulling image)"
    reconciler = JobReconciler(_settings(), session_factory=MagicMock(), job_service=job_service)
    now = datetime.now(UTC)
    run = _in_progress_run(
        created_at=now - timedelta(minutes=5),
        started_at=now - timedelta(minutes=5),
        k8s_job_name="pde-run-stuck",
    )

    assert asyncio.run(reconciler._reconcile_run(run, now)) is True
    assert run.status == RunStatus.FAILED
    assert run.finish_code == "PDE-OPERATOR-JOB-STUCK-TIMEOUT"
    assert "progress timeout" in (run.finish_message or "")
    job_service.delete_run_job.assert_called_once_with("pde-run-stuck")


def test_reconcile_once_commits_when_updated() -> None:
    run = _in_progress_run()
    session = AsyncMock()
    session.commit = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [run]
    session.execute = AsyncMock(return_value=result)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    session_factory = MagicMock(return_value=session_cm)

    job_service = MagicMock()
    reconciler = JobReconciler(_settings(), session_factory, job_service=job_service)

    with patch(
        "pde_operator.services.job_reconciler.asyncio.to_thread",
        new_callable=AsyncMock,
        return_value=JobPhase.FAILED,
    ):
        updated = asyncio.run(reconciler.reconcile_once())

    assert updated == 1
    assert run.status == RunStatus.FAILED
    session.commit.assert_awaited_once()
