import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import RETRYABLE_STATUSES, TERMINAL_STATUSES, Run, RunStatus
from pde_operator.db.models.run_template import RunTemplate
from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.schemas.runs import CreateRunRequest, RetryRunRequest, RunDetail
from pde_operator.schemas.run_templates import CreateRunFromTemplateRequest
from pde_operator.services.artifacts_service import ArtifactsService
from pde_operator.declarative_templates.services.run_adapter import DeclarativeRunAdapter
from pde_operator.services.job_service import JobCreationError, JobService, JobSignalError
from pde_operator.services.profile_service import DEFAULT_PROFILE_ID, ProfileNotFoundError
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateNotFoundError
from pde_operator.utils.artifact_utils import ArtifactKind, ArtifactNotFoundError
from pde_operator.utils.finish_utils import FinishUtils
from pde_operator.utils.input_crypto_utils import InputCryptoError, InputCryptoUtils

logger = logging.getLogger(__name__)


class RunService:
    def __init__(
            self,
            session: AsyncSession,
            settings: Settings,
            job_service: JobService | None = None,
            artifacts_service: ArtifactsService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._job_service = job_service or JobService(settings)
        self._artifacts = artifacts_service or ArtifactsService(settings)

    async def create_run(self, request: CreateRunRequest) -> Run:
        profile = await self._session.get(Profile, request.profile_id)
        if profile is None:
            raise ProfileNotFoundError(request.profile_id)

        run_id = uuid4()
        await self._store_run_input(
            run_id,
            RunInputPayload(
                pipeline_data=request.pipeline_data,
                pipeline_vars=request.pipeline_vars,
                pipeline_vars_secure=request.pipeline_vars_secure,
                is_dry_run=request.is_dry_run,
                log_level=request.log_level,
            ),
        )

        run = Run(
            id=run_id,
            profile_id=request.profile_id,
            status=RunStatus.QUEUED,
            pde_image=(request.pde_image or "").strip() or profile.pde_image,
            pipeline_data=request.pipeline_data,
            pipeline_vars=request.pipeline_vars,
            pipeline_vars_secure=InputCryptoUtils.mask_secure_vars(request.pipeline_vars_secure),
            is_dry_run=request.is_dry_run,
            log_level=request.log_level,
            env_vars=request.env_vars,
            created_from_template_id=request.created_from_template_id,
            execution_url=self._execution_url(run_id),
        )
        self._session.add(run)
        await self._start_run_job_now(run, profile)

        await self._session.commit()
        await self._session.refresh(run)
        logger.info("Run %s: created (profile=%s, status=%s)", run.id, run.profile_id, run.status)
        return run

    async def create_run_from_simple_template(
            self,
            template_id: UUID,
            request: CreateRunFromTemplateRequest | None = None,
    ) -> Run:
        template = await self._session.get(RunTemplate, template_id)
        if template is None:
            raise RunTemplateNotFoundError(template_id)
        if template.template_kind != "simple":
            raise RunTemplateKindError(template_id, expected="simple", actual=template.template_kind)

        overrides = request or CreateRunFromTemplateRequest()
        profile_id = (overrides.profile_id or template.profile_id or DEFAULT_PROFILE_ID).strip()
        profile = await self._session.get(Profile, profile_id)
        if profile is None and profile_id != DEFAULT_PROFILE_ID:
            logger.warning(
                "Run template %s: profile '%s' missing; remapping to '%s'",
                template_id,
                profile_id,
                DEFAULT_PROFILE_ID,
            )
            profile_id = DEFAULT_PROFILE_ID
            profile = await self._session.get(Profile, DEFAULT_PROFILE_ID)
        if profile is None:
            raise ProfileNotFoundError(profile_id)

        def _pick(override, fallback):
            return fallback if override is None else override

        create_req = CreateRunRequest(
            profile_id=profile_id,
            pipeline_data=_pick(overrides.pipeline_data, template.pipeline_data),
            pipeline_vars=_pick(overrides.pipeline_vars, template.pipeline_vars),
            pipeline_vars_secure=_pick(overrides.pipeline_vars_secure, template.pipeline_vars_secure),
            is_dry_run=_pick(overrides.is_dry_run, template.is_dry_run),
            log_level=_pick(overrides.log_level, template.log_level),
            env_vars=_pick(overrides.env_vars, template.env_vars),
            pde_image=_pick(overrides.pde_image, template.pde_image),
            created_from_template_id=template.id,
        )
        return await self.create_run(create_req)

    async def create_run_from_declarative_template(self, template_id: UUID, values: dict[str, Any] | None = None) -> Run:
        template = await self._session.get(RunTemplate, template_id)
        if template is None:
            raise RunTemplateNotFoundError(template_id)
        if template.template_kind != "declarative":
            raise RunTemplateKindError(template_id, expected="declarative", actual=template.template_kind)
        create_req = DeclarativeRunAdapter.to_create_run_request_from_template(template, values or {})
        return await self.create_run(create_req)

    async def list_runs(
            self,
            *,
            q: str | None = None,
            status: str | None = None,
            profile_id: str | None = None,
            created_from_template_id: UUID | None = None,
            created_after: datetime | None = None,
            created_before: datetime | None = None,
            offset: int = 0,
            limit: int = 20,
    ) -> tuple[list[Run], int]:
        filters = self._build_list_query(
            q=q,
            status=status,
            profile_id=profile_id,
            created_from_template_id=created_from_template_id,
            created_after=created_after,
            created_before=created_before,
        )
        count_query = select(func.count()).select_from(filters.subquery())
        total = int((await self._session.execute(count_query)).scalar_one())

        query = filters.order_by(Run.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def get_run(self, run_id: UUID) -> RunDetail | None:
        run = await self._session.get(Run, run_id)
        if run is None:
            return None
        detail = RunDetail.model_validate(run)
        if run.created_from_template_id is None:
            return detail
        template = await self._session.get(RunTemplate, run.created_from_template_id)
        if template is None:
            return detail
        return detail.model_copy(update={"created_from_template_name": template.name})

    async def run_exists(self, run_id: UUID) -> bool:
        return await self._session.get(Run, run_id) is not None

    async def cancel_run(self, run_id: UUID) -> Run:
        run = await self._session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if run.status in TERMINAL_STATUSES:
            raise RunNotCancellableError(f"Run is already {run.status}")
        if run.cancel_requested_at is not None:
            raise RunNotCancellableError("Cancel already requested for this run")

        now = datetime.now(UTC)
        if not run.k8s_job_name:
            run.cancel_requested_at = now
            run.status = RunStatus.CANCELLED
            run.finished_at = now
            await self._session.commit()
            await self._session.refresh(run)
            logger.info("Run %s: cancelled while waiting in queue", run.id)
            return run

        run.cancel_requested_at = now
        await self._session.commit()

        try:
            await asyncio.to_thread(self._job_service.signal_run_job_sigint, run.k8s_job_name)
        except JobSignalError:
            logger.exception("Failed to signal cancel for run %s (Job '%s')", run.id, run.k8s_job_name)

        await self._session.refresh(run)
        logger.info("Run %s: cancel requested (Job '%s')", run.id, run.k8s_job_name)
        return run

    async def retry_run(self, run_id: UUID, request: RetryRunRequest | None = None) -> Run:
        parent = await self._session.get(Run, run_id)
        if parent is None:
            raise RunNotFoundError(run_id)
        if parent.status not in RETRYABLE_STATUSES:
            raise RunNotRetriableError(f"Run status {parent.status} is not retriable")
        if not parent.state_location:
            raise RunStateNotAvailableError("Parent run has no uploaded state")

        try:
            await asyncio.to_thread(self._artifacts.get_artifact, parent.id, ArtifactKind.STATE)
        except ArtifactNotFoundError as exc:
            raise RunStateNotAvailableError("Parent run state artifact not found in storage") from exc

        profile = await self._session.get(Profile, parent.profile_id)
        if profile is None:
            raise ProfileNotFoundError(parent.profile_id, message=f"Profile '{parent.profile_id}' no longer exists; cannot retry this run")

        env_vars = parent.env_vars if request is None or request.env_vars is None else request.env_vars
        retry_vars = parent.retry_vars if request is None or request.retry_vars is None else request.retry_vars
        override = ((request.pde_image if request is not None else None) or "").strip()
        pde_image = override or parent.pde_image or profile.pde_image

        run_id = uuid4()
        parent_input = await asyncio.to_thread(self.get_run_input, parent.id)
        await self._store_run_input(run_id, parent_input.model_copy(update={"retry_vars": retry_vars}))

        run = Run(
            id=run_id,
            profile_id=parent.profile_id,
            status=RunStatus.QUEUED,
            pde_image=pde_image,
            pipeline_data=parent.pipeline_data,
            pipeline_vars=parent.pipeline_vars,
            pipeline_vars_secure=parent.pipeline_vars_secure,
            is_dry_run=parent.is_dry_run,
            log_level=parent.log_level,
            env_vars=env_vars,
            retry_vars=retry_vars,
            retry_of_run_id=parent.id,
            created_from_template_id=parent.created_from_template_id,
            execution_url=self._execution_url(run_id),
        )
        self._session.add(run)
        await self._start_run_job_now(run, profile)

        await self._session.commit()
        await self._session.refresh(run)
        logger.info("Run %s: retry of %s (status=%s)", run.id, parent.id, run.status)
        return run

    async def deliver_status(self, run_id: UUID, status: dict) -> Run:
        run = await self._session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(run_id)

        now = datetime.now(UTC)
        run.status_updated_at = now
        self._apply_status_fields(run, status, now)
        progress = status.get("progress")
        run.progress_json = progress if isinstance(progress, dict) else None

        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def deliver_report(self, run_id: UUID, data: bytes) -> Run:
        run = await self._session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(run_id)

        now = datetime.now(UTC)
        await asyncio.to_thread(self._artifacts.put_artifact, run_id, ArtifactKind.REPORT, data)
        run.report_updated_at = now
        FinishUtils.apply_report_finish_code(run, data)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def deliver_log(self, run_id: UUID, data: bytes) -> Run:
        run = await self._session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(run_id)

        now = datetime.now(UTC)
        await asyncio.to_thread(self._artifacts.put_artifact, run_id, ArtifactKind.LOG, data)
        run.log_updated_at = now
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def upload_artifacts(
            self,
            run_id: UUID,
            *,
            state: bytes | None = None,
            log: bytes | None = None,
            x_debug: bytes | None = None,
            report: bytes | None = None,
    ) -> Run:
        run = await self._session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(run_id)

        uploads = {
            ArtifactKind.STATE: state,
            ArtifactKind.LOG: log,
            ArtifactKind.X_DEBUG: x_debug,
            ArtifactKind.REPORT: report,
        }
        stored: dict[ArtifactKind, str] = {}
        now = datetime.now(UTC)
        for kind, data in uploads.items():
            if data is None:
                continue
            key = await asyncio.to_thread(self._artifacts.put_artifact, run_id, kind, data)
            stored[kind] = key

        if ArtifactKind.STATE in stored:
            run.state_location = stored[ArtifactKind.STATE]
        if ArtifactKind.REPORT in stored:
            run.report_updated_at = now
            if report is not None:
                FinishUtils.apply_report_finish_code(run, report)
        if ArtifactKind.LOG in stored:
            run.log_updated_at = now
        await self._session.commit()
        await self._session.refresh(run)
        logger.debug("Run %s: stored artifacts %s", run_id, sorted(stored))
        return run

    def get_artifact(self, run_id: UUID, kind: str):
        return self._artifacts.get_artifact(run_id, kind)

    def get_run_input(self, run_id: UUID) -> RunInputPayload:
        try:
            ciphertext = self._artifacts.get_run_input_bytes(run_id)
        except ArtifactNotFoundError as exc:
            raise RunInputNotAvailableError("Run input not found in storage") from exc
        try:
            plaintext = InputCryptoUtils.decrypt(self._settings.input_encryption_key, ciphertext)
        except InputCryptoError as exc:
            raise RunInputNotAvailableError(str(exc)) from exc
        return RunInputPayload.model_validate_json(plaintext)

    async def _store_run_input(self, run_id: UUID, payload: RunInputPayload) -> None:
        plaintext = payload.model_dump_json().encode("utf-8")
        try:
            ciphertext = InputCryptoUtils.encrypt(self._settings.input_encryption_key, plaintext)
        except InputCryptoError as exc:
            raise RunInputStorageError(str(exc)) from exc
        try:
            await asyncio.to_thread(self._artifacts.put_run_input, run_id, ciphertext)
        except Exception as exc:
            raise RunInputStorageError(f"Failed to store encrypted run input for '{run_id}': {exc}") from exc

    async def _start_run_job_now(self, run: Run, profile: Profile) -> None:
        if self._settings.queue_enabled or not self._settings.k8s_job_creation_enabled:
            return
        try:
            job_name = self._job_service.create_run_job(run, profile)
        except JobCreationError:
            await self._session.rollback()
            raise
        run.k8s_job_name = job_name
        run.status = RunStatus.NOT_STARTED
        run.status_updated_at = datetime.now(UTC)

    async def delete_run(self, run_id: UUID) -> None:
        run = await self._session.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        try:
            await asyncio.to_thread(self._artifacts.delete_run_artifacts, run_id)
        except Exception as exc:
            raise RunArtifactCleanupError(f"Failed to delete artifacts for run '{run_id}': {exc}") from exc
        await self._session.delete(run)
        await self._session.commit()
        logger.debug("Run %s: deleted (DB + artifacts)", run_id)

    def _execution_url(self, run_id: UUID) -> str:
        base = self._settings.execution_url_base.rstrip("/")
        prefix = self._settings.api_prefix.rstrip("/")
        return f"{base}{prefix}/runs/{run_id}"

    def _apply_status_fields(self, run: Run, status: dict, now: datetime) -> None:
        if run.name is None:
            report_name = status.get("name")
            if isinstance(report_name, str) and report_name.strip():
                run.name = report_name.strip()
        mapped = self._parse_status_value(status.get("status"))
        if mapped is not None:
            run.status = mapped
        if run.started_at is None:
            run.started_at = self._parse_timestamp(status.get("startedAt"))
        if run.status in TERMINAL_STATUSES:
            run.finished_at = self._parse_timestamp(status.get("finishedAt")) or now

    @staticmethod
    def _build_list_query(
            *,
            q: str | None,
            status: str | None,
            profile_id: str | None,
            created_from_template_id: UUID | None,
            created_after: datetime | None,
            created_before: datetime | None,
    ) -> Select[tuple[Run]]:
        query = select(Run)
        if q is not None and q.strip():
            pattern = f"%{q.strip()}%"
            query = query.where(or_(Run.status.ilike(pattern), Run.profile_id.ilike(pattern), Run.name.ilike(pattern)))
        if status is not None:
            query = query.where(Run.status == status)
        if profile_id is not None:
            query = query.where(Run.profile_id == profile_id)
        if created_from_template_id is not None:
            query = query.where(Run.created_from_template_id == created_from_template_id)
        if created_after is not None:
            query = query.where(Run.created_at >= created_after)
        if created_before is not None:
            query = query.where(Run.created_at <= created_before)
        return query

    @staticmethod
    def _parse_status_value(status_value: object) -> RunStatus | None:
        if not isinstance(status_value, str):
            return None
        try:
            return RunStatus(status_value.strip())
        except ValueError:
            return None

    @staticmethod
    def _parse_timestamp(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed


class RunNotFoundError(LookupError):
    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Run '{run_id}' not found")
        self.run_id = run_id


class RunNotCancellableError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class RunNotRetriableError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class RunStateNotAvailableError(LookupError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class RunInputNotAvailableError(LookupError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class RunInputStorageError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class RunArtifactCleanupError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
