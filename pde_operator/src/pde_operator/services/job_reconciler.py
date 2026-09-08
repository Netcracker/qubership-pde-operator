"""Periodic reconciliation of K8s Job state into run rows."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pde_operator.config import Settings
from pde_operator.db.models.run import TERMINAL_STATUSES, Run, RunStatus
from pde_operator.services.job_service import JobPhase, JobService
from pde_operator.utils.finish_utils import OperatorFinishCodes, FinishUtils

logger = logging.getLogger(__name__)


class JobReconciler:
    def __init__(
            self,
            settings: Settings,
            session_factory: async_sessionmaker[AsyncSession],
            job_service: JobService | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._job_service = job_service or JobService(settings)

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "Job reconciler started (interval=%ss, stuck_timeout=%ss)",
            self._settings.reconciler_interval_seconds,
            self._settings.reconciler_stuck_timeout_seconds,
        )
        while not stop_event.is_set():
            try:
                await self.reconcile_once()
            except Exception:
                logger.exception("Job reconciler tick failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._settings.reconciler_interval_seconds)
            except TimeoutError:
                continue
        logger.info("Job reconciler stopped")

    async def reconcile_once(self) -> int:
        updated = 0
        async with self._session_factory() as session:
            result = await session.execute(
                select(Run).where(
                    Run.k8s_job_name.is_not(None),
                    Run.status.not_in(TERMINAL_STATUSES),
                )
            )
            runs = list(result.scalars().all())
            now = datetime.now(UTC)
            for run in runs:
                if await self._reconcile_run(run, now):
                    updated += 1
            if updated:
                await session.commit()
        return updated

    async def _reconcile_run(self, run: Run, now: datetime) -> bool:
        assert run.k8s_job_name is not None
        phase = await asyncio.to_thread(self._job_service.get_job_phase, run.k8s_job_name)
        cancel_pending = run.cancel_requested_at is not None

        if phase == JobPhase.SUCCEEDED:
            run.finished_at = run.finished_at or now
            if run.status not in TERMINAL_STATUSES:
                run.status = RunStatus.SUCCESS
                logger.info("Run %s: Job succeeded -> SUCCESS", run.id)
            else:
                logger.info("Run %s: Job succeeded; keeping status %s", run.id, run.status)
            return True

        if phase == JobPhase.FAILED:
            run.status = RunStatus.CANCELLED if cancel_pending else RunStatus.FAILED
            run.finished_at = run.finished_at or now
            if run.finish_code is None:
                diagnostic = await asyncio.to_thread(self._job_service.get_pod_diagnostic, run.k8s_job_name)
                run.finish_code = OperatorFinishCodes.RUN_CANCELLED if cancel_pending else OperatorFinishCodes.RUN_JOB_FAILED
                run.finish_message = diagnostic or "Kubernetes Job failed."
            logger.info("Run %s: Job failed -> %s", run.id, run.status)
            return True

        if phase == JobPhase.MISSING:
            run.status = RunStatus.CANCELLED if cancel_pending else RunStatus.FAILED
            run.finished_at = run.finished_at or now
            if run.finish_code is None:
                run.finish_code = OperatorFinishCodes.RUN_CANCELLED if cancel_pending else OperatorFinishCodes.RUN_JOB_MISSING
                run.finish_message = "Kubernetes Job no longer exists."
            logger.warning("Run %s: Job '%s' missing -> %s", run.id, run.k8s_job_name, run.status)
            return True

        # JobPhase.ACTIVE - check stuck timeout
        if cancel_pending:
            requested = run.cancel_requested_at
            assert requested is not None
            if requested.tzinfo is None:
                requested = requested.replace(tzinfo=UTC)
            try:
                await asyncio.to_thread(self._job_service.signal_run_job_sigint, run.k8s_job_name)
            except Exception:
                logger.exception("Run %s: failed to re-signal Job '%s' during cancel grace", run.id, run.k8s_job_name)
            if now - requested >= timedelta(seconds=self._settings.cancel_grace_seconds):
                try:
                    await asyncio.to_thread(self._job_service.delete_run_job, run.k8s_job_name)
                except Exception:
                    logger.exception("Run %s: failed to hard-stop Job '%s' after cancel grace", run.id, run.k8s_job_name)
                run.status = RunStatus.CANCELLED
                run.finished_at = now
                run.finish_code = OperatorFinishCodes.RUN_CANCELLED
                run.finish_message = "Run cancelled; Kubernetes Job removed after grace period."
                logger.warning("Run %s: cancel grace elapsed -> CANCELLED (Job deleted)", run.id)
                return True
            return False

        if self._is_stuck(run, now):
            diagnostic = await asyncio.to_thread(self._job_service.get_pod_diagnostic, run.k8s_job_name)
            try:
                await asyncio.to_thread(self._job_service.delete_run_job, run.k8s_job_name)
            except Exception:
                logger.exception("Run %s: failed to delete stuck Job '%s'", run.id, run.k8s_job_name)
            run.status = RunStatus.FAILED
            run.finished_at = now
            run.finish_code = OperatorFinishCodes.RUN_STUCK_TIMEOUT
            run.finish_message = FinishUtils.stuck_finish_message(diagnostic)
            logger.warning("Run %s: stuck IN_PROGRESS -> FAILED (Job deleted)", run.id)
            return True

        return False

    def _is_stuck(self, run: Run, now: datetime) -> bool:
        timeout = timedelta(seconds=self._settings.reconciler_stuck_timeout_seconds)
        reference = run.status_updated_at or run.started_at or run.created_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return now - reference >= timeout
