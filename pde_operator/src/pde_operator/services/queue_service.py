from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import TERMINAL_STATUSES, Run, RunStatus
from pde_operator.services.job_service import JobCreationError, JobService

logger = logging.getLogger(__name__)


class QueueService:
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
            "Queue worker started (poll=%ss, max_concurrent_runs=%s)",
            self._settings.queue_poll_seconds,
            self._settings.max_concurrent_runs,
        )
        while not stop_event.is_set():
            try:
                started = await self.admit_once()
                if started:
                    logger.debug("Queue worker admitted %s run(s)", started)
            except Exception:
                logger.exception("Queue worker tick failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._settings.queue_poll_seconds)
            except TimeoutError:
                continue
        logger.info("Queue worker stopped")

    async def admit_once(self) -> int:
        if not self._settings.k8s_job_creation_enabled:
            return 0

        async with self._session_factory() as session:
            free = await self._free_slots(session)
            if free == 0:
                return 0

            query = (
                select(Run)
                .where(Run.status == RunStatus.QUEUED, Run.k8s_job_name.is_(None))
                .order_by(Run.created_at.asc(), Run.id.asc())
                .with_for_update(skip_locked=True)
            )
            if free is not None:
                query = query.limit(free)

            result = await session.execute(query)
            queued = list(result.scalars().all())
            if not queued:
                return 0

            started = 0
            now = datetime.now(UTC)
            for run in queued:
                profile = await session.get(Profile, run.profile_id)
                if profile is None:
                    run.status = RunStatus.FAILED
                    run.finished_at = now
                    logger.error("Queue: run %s profile '%s' missing -> FAILED", run.id, run.profile_id)
                    continue
                try:
                    job_name = self._job_service.create_run_job(run, profile)
                except JobCreationError:
                    logger.exception("Queue: failed to create Job for run %s (left QUEUED)", run.id)
                    continue
                run.k8s_job_name = job_name
                run.status = RunStatus.NOT_STARTED
                run.status_updated_at = now
                started += 1

            await session.commit()
            return started

    async def _free_slots(self, session: AsyncSession) -> int | None:
        """Return available slots, or None when unlimited (max_concurrent_runs <= 0)."""
        if self._settings.max_concurrent_runs <= 0:
            return None
        active = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Run)
                    .where(Run.k8s_job_name.is_not(None), Run.status.not_in(TERMINAL_STATUSES))
                )
            ).scalar_one()
        )
        return max(self._settings.max_concurrent_runs - active, 0)
