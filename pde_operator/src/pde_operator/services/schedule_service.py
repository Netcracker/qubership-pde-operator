from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import Run
from pde_operator.db.models.run_template import RunTemplate
from pde_operator.db.models.scheduled_run import (
    FireStatus,
    ScheduledRun,
    schedule_trigger_ref,
)
from pde_operator.declarative_templates.services.run_adapter import DeclarativeRunAdapter
from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.schemas.runs import CreateRunRequest
from pde_operator.schemas.schedules import CreateScheduledRunRequest, UpdateScheduledRunRequest
from pde_operator.services.artifacts_service import ArtifactsService
from pde_operator.services.profile_service import ProfileNotFoundError
from pde_operator.services.run_input_storage import (
    RunInputNotAvailableError,
    RunInputStorage,
    RunInputStorageError,
)
from pde_operator.services.run_service import RunService
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateNotFoundError
from pde_operator.utils.cron_utils import CronUtils
from pde_operator.utils.input_crypto_utils import InputCryptoError, InputCryptoUtils

logger = logging.getLogger(__name__)


class ScheduleService:
    """CRUD for scheduled runs plus the single-schedule fire path.

    Secrets follow the run pattern: the DB column keeps `[MASKED]` values while the real ones live
    Fernet-encrypted in artifact storage under the schedule id.
    """

    def __init__(
            self,
            session: AsyncSession,
            settings: Settings,
            artifacts_service: ArtifactsService | None = None,
            run_input_storage: RunInputStorage | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._artifacts = artifacts_service or ArtifactsService(settings)
        self._storage = run_input_storage or RunInputStorage(settings, artifacts_service=self._artifacts)

    async def list_schedules(
            self,
            *,
            q: str | None = None,
            enabled: bool | None = None,
            offset: int = 0,
            limit: int = 20,
    ) -> tuple[list[ScheduledRun], int]:
        filters = self._build_list_query(q=q, enabled=enabled)
        count_query = select(func.count()).select_from(filters.subquery())
        total = int((await self._session.execute(count_query)).scalar_one())

        query = filters.order_by(ScheduledRun.created_at.desc(), ScheduledRun.id.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def get_schedule(self, schedule_id: UUID) -> ScheduledRun | None:
        return await self._session.get(ScheduledRun, schedule_id)

    async def create_schedule(
            self,
            request: CreateScheduledRunRequest,
            *,
            schedule_id: UUID | None = None,
    ) -> ScheduledRun:
        self._validate_cron(request.cron_expression, request.timezone)
        run_request = await self._resolve_run_request(request)
        await self._ensure_profile(run_request.profile_id)

        try:
            # Nothing stored yet, so any [MASKED] placeholder is a mistake rather than a kept secret.
            resolved_secure = InputCryptoUtils.merge_masked_secure(run_request.pipeline_vars_secure, None)
        except InputCryptoError as exc:
            raise ScheduleValidationError(str(exc)) from exc
        run_request = run_request.model_copy(update={"pipeline_vars_secure": resolved_secure})

        schedule_id = schedule_id or uuid4()
        await self._storage.store(schedule_id, RunInputPayload.from_create_request(run_request))

        now = datetime.now(UTC)
        schedule = ScheduledRun(
            id=schedule_id,
            enabled=request.enabled,
            created_from_template_id=run_request.created_from_template_id,
            next_fire_at=self._next_fire_at(request.cron_expression, request.timezone) if request.enabled else None,
            created_at=now,
            updated_at=now,
        )
        self._apply_request(schedule, request, run_request)
        self._session.add(schedule)
        await self._session.commit()
        await self._session.refresh(schedule)
        logger.info("Schedule %s: created (cron=%r, tz=%s, enabled=%s)", schedule.id, schedule.cron_expression, schedule.timezone, schedule.enabled)
        return schedule

    async def update_schedule(self, schedule_id: UUID, request: UpdateScheduledRunRequest) -> ScheduledRun:
        schedule = await self._get_or_raise(schedule_id)
        self._validate_cron(request.cron_expression, request.timezone)
        await self._ensure_profile(request.profile_id)

        current = await asyncio.to_thread(self._storage.load, schedule_id)
        try:
            merged_secure = InputCryptoUtils.merge_masked_secure(request.pipeline_vars_secure, current.pipeline_vars_secure)
        except InputCryptoError as exc:
            raise ScheduleValidationError(str(exc)) from exc

        run_request = CreateRunRequest(
            profile_id=request.profile_id,
            pipeline_data=request.pipeline_data,
            pipeline_vars=request.pipeline_vars,
            pipeline_vars_secure=merged_secure,
            is_dry_run=request.is_dry_run,
            log_level=request.log_level,
            env_vars=request.env_vars,
            pde_image=request.pde_image,
        )
        await self._storage.store(schedule_id, RunInputPayload.from_create_request(run_request))

        schedule_changed = (
            schedule.cron_expression != request.cron_expression or schedule.timezone != request.timezone
        )
        self._apply_request(schedule, request, run_request)
        schedule.updated_at = datetime.now(UTC)

        if not request.enabled:
            schedule.enabled = False
            schedule.next_fire_at = None
        else:
            if not schedule.enabled or schedule_changed or schedule.next_fire_at is None:
                schedule.next_fire_at = self._next_fire_at(request.cron_expression, request.timezone)
            schedule.enabled = True

        await self._session.commit()
        await self._session.refresh(schedule)
        logger.info("Schedule %s: updated (cron=%r, enabled=%s)", schedule.id, schedule.cron_expression, schedule.enabled)
        return schedule

    async def set_enabled(self, schedule_id: UUID, enabled: bool) -> ScheduledRun:
        schedule = await self._get_or_raise(schedule_id)
        if schedule.enabled == enabled:
            return schedule

        schedule.enabled = enabled
        schedule.next_fire_at = self._next_fire_at(schedule.cron_expression, schedule.timezone) if enabled else None
        schedule.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(schedule)
        logger.info("Schedule %s: %s", schedule.id, "enabled" if enabled else "disabled")
        return schedule

    async def delete_schedule(self, schedule_id: UUID) -> None:
        schedule = await self._get_or_raise(schedule_id)
        try:
            await self._storage.delete(schedule_id)
        except RunInputStorageError as exc:
            raise ScheduleArtifactCleanupError(f"Failed to delete stored input for schedule '{schedule_id}': {exc}") from exc
        await self._session.delete(schedule)
        await self._session.commit()
        logger.info("Schedule %s: deleted", schedule_id)

    async def fire(self, schedule: ScheduledRun) -> Run:
        """Create a run from the schedule's stored input. Callers own the bookkeeping around it."""
        try:
            payload = await asyncio.to_thread(self._storage.load, schedule.id)
        except RunInputNotAvailableError as exc:
            raise ScheduleFireError(f"Stored run input is unavailable: {exc}") from exc

        run_service = RunService(
            self._session,
            self._settings,
            artifacts_service=self._artifacts,
            run_input_storage=self._storage,
        )
        run = await run_service.create_run(
            CreateRunRequest(
                profile_id=schedule.profile_id,
                pipeline_data=payload.pipeline_data,
                pipeline_vars=payload.pipeline_vars,
                pipeline_vars_secure=payload.pipeline_vars_secure,
                is_dry_run=payload.is_dry_run,
                log_level=payload.log_level,
                env_vars=schedule.env_vars,
                pde_image=schedule.pde_image,
                created_from_template_id=schedule.created_from_template_id,
            ),
            triggered_by=schedule_trigger_ref(schedule.id),
        )
        return run

    async def trigger_now(self, schedule_id: UUID) -> Run:
        """Manual trigger: fires regardless of the overlap policy, but records the same bookkeeping."""
        schedule = await self._get_or_raise(schedule_id)
        now = datetime.now(UTC)
        run = await self.fire(schedule)
        await self.record_fire(schedule, now=now, status=FireStatus.SUCCESS, run_id=run.id)
        return run

    async def record_fire(
            self,
            schedule: ScheduledRun,
            *,
            now: datetime,
            status: FireStatus,
            run_id: UUID | None = None,
            error: str | None = None,
    ) -> None:
        self.apply_fire_result(schedule, now=now, status=status, run_id=run_id, error=error)
        await self._session.commit()
        await self._session.refresh(schedule)

    @staticmethod
    def apply_fire_result(
            schedule: ScheduledRun,
            *,
            now: datetime,
            status: FireStatus,
            run_id: UUID | None = None,
            error: str | None = None,
    ) -> None:
        """Record a fire outcome on the row without committing (callers own the transaction)."""
        schedule.last_fire_at = now
        schedule.last_fire_status = status
        schedule.last_fire_error = error
        if run_id is not None:
            schedule.last_run_id = run_id
        schedule.updated_at = now

    def preview_fire_times(self, cron_expression: str, timezone: str, count: int = 3) -> list[datetime]:
        self._validate_cron(cron_expression, timezone)
        return CronUtils.next_fire_times(cron_expression, timezone, count)

    @staticmethod
    def _apply_request(
            schedule: ScheduledRun,
            request: CreateScheduledRunRequest | UpdateScheduledRunRequest,
            run_request: CreateRunRequest,
    ) -> None:
        schedule.name = request.name
        schedule.description = request.description
        schedule.cron_expression = request.cron_expression
        schedule.timezone = request.timezone
        schedule.overlap_policy = request.overlap_policy
        schedule.profile_id = run_request.profile_id
        schedule.pde_image = (run_request.pde_image or "").strip() or None
        schedule.pipeline_data = run_request.pipeline_data
        schedule.pipeline_vars = run_request.pipeline_vars
        schedule.pipeline_vars_secure = InputCryptoUtils.mask_secure_vars(run_request.pipeline_vars_secure)
        schedule.is_dry_run = run_request.is_dry_run
        schedule.log_level = run_request.log_level
        schedule.env_vars = run_request.env_vars

    def _validate_cron(self, cron_expression: str, timezone: str) -> None:
        try:
            CronUtils.validate_expression(cron_expression, min_interval_seconds=self._settings.schedules_min_interval_seconds)
            CronUtils.resolve_timezone(timezone)
        except ValueError as exc:
            raise ScheduleValidationError(str(exc)) from exc

    def _next_fire_at(self, cron_expression: str, timezone: str) -> datetime:
        try:
            return CronUtils.next_fire_time(cron_expression, timezone)
        except ValueError as exc:
            raise ScheduleValidationError(str(exc)) from exc

    async def _ensure_profile(self, profile_id: str) -> None:
        if await self._session.get(Profile, profile_id) is None:
            raise ProfileNotFoundError(profile_id)

    async def _resolve_run_request(self, request: CreateScheduledRunRequest) -> CreateRunRequest:
        if request.declarative_values is not None and request.created_from_template_id is not None:
            template = await self._session.get(RunTemplate, request.created_from_template_id)
            if template is None:
                raise RunTemplateNotFoundError(request.created_from_template_id)
            if template.template_kind != "declarative":
                raise RunTemplateKindError(request.created_from_template_id, expected="declarative", actual=template.template_kind)
            run_request = DeclarativeRunAdapter.to_create_run_request_from_template(template, request.declarative_values)
        else:
            run_request = CreateRunRequest(
                profile_id=request.profile_id,
                pipeline_data=request.pipeline_data or "",
                pipeline_vars=request.pipeline_vars,
                pipeline_vars_secure=request.pipeline_vars_secure,
                is_dry_run=request.is_dry_run,
                log_level=request.log_level,
                env_vars=request.env_vars,
                pde_image=request.pde_image,
                created_from_template_id=request.created_from_template_id,
            )

        if not (run_request.pipeline_data or "").strip():
            raise ScheduleValidationError("pipeline_data must not be empty")
        return run_request

    async def delete_all_schedules(self) -> int:
        """Delete every schedule plus its stored input (config import replace mode)."""
        schedule_ids = list((await self._session.execute(select(ScheduledRun.id))).scalars().all())
        if not schedule_ids:
            return 0
        await self._session.execute(delete(ScheduledRun))
        await self._session.commit()
        for schedule_id in schedule_ids:
            try:
                await self._storage.delete(schedule_id)
            except RunInputStorageError:
                logger.warning("Schedule %s: stored input not deleted", schedule_id, exc_info=True)
        logger.info("Deleted %s schedule(s)", len(schedule_ids))
        return len(schedule_ids)

    async def _get_or_raise(self, schedule_id: UUID) -> ScheduledRun:
        schedule = await self._session.get(ScheduledRun, schedule_id)
        if schedule is None:
            raise ScheduleNotFoundError(schedule_id)
        return schedule

    @staticmethod
    def _build_list_query(*, q: str | None, enabled: bool | None) -> Select[tuple[ScheduledRun]]:
        query = select(ScheduledRun)
        if q is not None and q.strip():
            pattern = f"%{q.strip()}%"
            query = query.where(or_(ScheduledRun.name.ilike(pattern), ScheduledRun.description.ilike(pattern)))
        if enabled is not None:
            query = query.where(ScheduledRun.enabled.is_(enabled))
        return query


class ScheduleNotFoundError(LookupError):
    def __init__(self, schedule_id: UUID) -> None:
        super().__init__(f"Schedule '{schedule_id}' not found")
        self.schedule_id = schedule_id


class ScheduleValidationError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ScheduleFireError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ScheduleArtifactCleanupError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
