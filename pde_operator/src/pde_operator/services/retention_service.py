from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pde_operator.config import Settings
from pde_operator.db.models.run import Run
from pde_operator.services.artifacts_service import ArtifactsService
from pde_operator.services.run_service import RunArtifactCleanupError, RunService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CleanupResult:
    older_than: datetime
    deleted: int
    failed: int


class RetentionService:
    def __init__(
            self,
            settings: Settings,
            session_factory: async_sessionmaker[AsyncSession],
            artifacts_service: ArtifactsService | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._artifacts = artifacts_service or ArtifactsService(settings)

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "Retention cleanup started (cron=%r, retention_days=%s)",
            self._settings.retention_cron,
            self._settings.retention_days,
        )
        while not stop_event.is_set():
            delay = self._seconds_until_next_run()
            logger.debug("Retention cleanup next run in %.0fs", delay)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
                break
            except TimeoutError:
                pass
            try:
                cutoff = datetime.now(UTC) - timedelta(days=self._settings.retention_days)
                result = await self.cleanup_older_than(cutoff)
                logger.info(
                    "Retention cleanup finished: deleted=%s failed=%s older_than=%s",
                    result.deleted,
                    result.failed,
                    result.older_than.isoformat(),
                )
            except Exception:
                logger.exception("Retention cleanup tick failed")
        logger.info("Retention cleanup stopped")

    async def cleanup_older_than(self, older_than: datetime) -> CleanupResult:
        if older_than.tzinfo is None:
            older_than = older_than.replace(tzinfo=UTC)
        else:
            older_than = older_than.astimezone(UTC)

        async with self._session_factory() as session:
            result = await session.execute(
                select(Run.id).where(Run.created_at < older_than).order_by(Run.created_at.asc()))
            run_ids = list(result.scalars().all())

        deleted = 0
        failed = 0
        for run_id in run_ids:
            async with self._session_factory() as session:
                service = RunService(session, self._settings, artifacts_service=self._artifacts)
                try:
                    await service.delete_run(run_id)
                    deleted += 1
                except RunArtifactCleanupError:
                    failed += 1
                    logger.exception("Retention: skipped run %s (artifact cleanup failed)", run_id)
                except Exception:
                    failed += 1
                    logger.exception("Retention: skipped run %s", run_id)

        return CleanupResult(older_than=older_than, deleted=deleted, failed=failed)

    def _seconds_until_next_run(self) -> float:
        now = datetime.now(UTC)
        try:
            itr = croniter(self._settings.retention_cron, now)
        except (ValueError, KeyError) as exc:
            logger.error("Invalid retention_cron %r: %s; falling back to daily midnight", self._settings.retention_cron,
                         exc)
            itr = croniter("0 0 * * *", now)
        nxt = itr.get_next(datetime)
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=UTC)
        delay = (nxt - now).total_seconds()
        return max(delay, 1.0)
