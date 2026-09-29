from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pde_operator.config import Settings
from pde_operator.db.models.run import TERMINAL_STATUSES, Run
from pde_operator.db.models.scheduled_run import FireStatus, OverlapPolicy, ScheduledRun, schedule_trigger_ref
from pde_operator.services.schedule_service import ScheduleService
from pde_operator.utils.cron_utils import CronUtils

logger = logging.getLogger(__name__)


class ScheduleDispatcher:
    """Fires due schedules.

    Due rows are claimed and re-anchored in one short transaction holding a row lock; the runs
    themselves are created afterwards, outside the lock, so Job creation never blocks other
    replicas. `next_fire_at` is always advanced from `now`, which is what makes downtime skip
    missed fires instead of replaying them.
    """

    def __init__(self, settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._settings = settings
        self._session_factory = session_factory

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "Schedule dispatcher started (poll=%ss, grace=%ss, batch=%s)",
            self._settings.schedules_poll_seconds,
            self._settings.schedules_missed_grace_seconds,
            self._settings.schedules_batch_size,
        )
        while not stop_event.is_set():
            try:
                fired = await self.fire_due_once()
                if fired:
                    logger.debug("Schedule dispatcher fired %s schedule(s)", fired)
            except Exception:
                logger.exception("Schedule dispatcher tick failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._settings.schedules_poll_seconds)
            except TimeoutError:
                continue
        logger.info("Schedule dispatcher stopped")

    async def fire_due_once(self, *, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        due_ids = await self._claim_due(now)
        fired = 0
        for schedule_id in due_ids:
            if await self._fire(schedule_id, now):
                fired += 1
        return fired

    async def _claim_due(self, now: datetime) -> list[UUID]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ScheduledRun)
                .where(
                    ScheduledRun.enabled.is_(True),
                    or_(
                        ScheduledRun.next_fire_at <= now,
                        ScheduledRun.next_fire_at.is_(None),  # heal rows that lost their anchor
                    ),
                )
                .order_by(ScheduledRun.next_fire_at.asc().nullsfirst(), ScheduledRun.id.asc())
                .limit(self._settings.schedules_batch_size)
                .with_for_update(skip_locked=True)
            )
            due = list(result.scalars().all())
            active_refs = await self._active_run_refs(session, [schedule.id for schedule in due])

            to_fire: list[UUID] = []
            for schedule in due:
                planned = schedule.next_fire_at
                try:
                    schedule.next_fire_at = CronUtils.next_fire_time(schedule.cron_expression, schedule.timezone, base=now)
                except ValueError as exc:
                    logger.error("Schedule %s: cron %r is invalid (%s); disabling", schedule.id, schedule.cron_expression, exc)
                    schedule.enabled = False
                    schedule.next_fire_at = None
                    ScheduleService.apply_fire_result(schedule, now=now, status=FireStatus.FAILED, error=f"invalid cron expression: {exc}")
                    continue

                if planned is None:
                    continue
                if (now - planned).total_seconds() > self._settings.schedules_missed_grace_seconds:
                    logger.info("Schedule %s: missed fire at %s; skipping to %s", schedule.id, planned.isoformat(), schedule.next_fire_at.isoformat())
                    ScheduleService.apply_fire_result(schedule, now=now, status=FireStatus.SKIPPED_MISSED, error=f"missed fire at {planned.isoformat()}")
                    continue
                if schedule.overlap_policy == OverlapPolicy.SKIP and schedule_trigger_ref(schedule.id) in active_refs:
                    logger.info("Schedule %s: previous run still active; skipping this firing", schedule.id)
                    ScheduleService.apply_fire_result(schedule, now=now, status=FireStatus.SKIPPED_OVERLAP)
                    continue
                to_fire.append(schedule.id)

            await session.commit()
            return to_fire

    async def _fire(self, schedule_id: UUID, now: datetime) -> bool:
        async with self._session_factory() as session:
            service = ScheduleService(session, self._settings)
            schedule = await service.get_schedule(schedule_id)
            if schedule is None:
                return False
            try:
                run = await service.fire(schedule)
            except Exception as exc:
                logger.exception("Schedule %s: fire failed", schedule_id)
                await service.record_fire(schedule, now=now, status=FireStatus.FAILED, error=str(exc)[:500])
                return False
            await service.record_fire(schedule, now=now, status=FireStatus.SUCCESS, run_id=run.id)
            logger.info("Schedule %s: fired run %s", schedule_id, run.id)
            return True

    @staticmethod
    async def _active_run_refs(session: AsyncSession, schedule_ids: list[UUID]) -> set[str]:
        """triggered_by values of schedules that still have a run in flight (one query per tick)."""
        if not schedule_ids:
            return set()
        result = await session.execute(
            select(Run.triggered_by)
            .where(
                Run.triggered_by.in_([schedule_trigger_ref(schedule_id) for schedule_id in schedule_ids]),
                Run.status.not_in(TERMINAL_STATUSES),
            )
            .distinct()
        )
        return {ref for ref in result.scalars().all() if ref is not None}
