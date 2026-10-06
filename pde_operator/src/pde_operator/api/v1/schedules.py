from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from pde_operator.declarative_templates.contract.errors import DeclarativeContractError
from pde_operator.schemas.runs import CreateRunResponse
from pde_operator.schemas.schedules import (
    CreateScheduledRunRequest,
    ScheduledRunDetail,
    ScheduledRunListResponse,
    ScheduledRunSummary,
    SchedulePreviewRequest,
    SchedulePreviewResponse,
    TimezonesResponse,
    UpdateScheduledRunRequest,
)
from pde_operator.services.profile_service import ProfileNotFoundError
from pde_operator.services.run_input_storage import RunInputNotAvailableError, RunInputStorageError
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateNotFoundError
from pde_operator.services.schedule_service import (
    ScheduleArtifactCleanupError,
    ScheduleFireError,
    ScheduleNotFoundError,
    ScheduleService,
    ScheduleValidationError,
)
from pde_operator.utils.cron_utils import CronUtils
from pde_operator.utils.depend_utils import DependUtils
from pde_operator.utils.input_crypto_utils import InputCryptoError

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("/timezones", response_model=TimezonesResponse)
async def list_timezones() -> TimezonesResponse:
    return TimezonesResponse(timezones=CronUtils.available_timezones())


@router.post("/preview", response_model=SchedulePreviewResponse)
async def preview_schedule(
        body: SchedulePreviewRequest,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> SchedulePreviewResponse:
    try:
        fire_times = service.preview_fire_times(body.cron_expression, body.timezone, body.count)
    except ScheduleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SchedulePreviewResponse(next_fire_times=fire_times)


@router.get("", response_model=ScheduledRunListResponse)
async def list_schedules(
        q: str | None = Query(default=None),
        enabled: bool | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=500),
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> ScheduledRunListResponse:
    schedules, total = await service.list_schedules(q=q, enabled=enabled, offset=offset, limit=limit)
    items = [ScheduledRunSummary.model_validate(schedule) for schedule in schedules]
    return ScheduledRunListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=ScheduledRunDetail, status_code=201)
async def create_schedule(
        body: CreateScheduledRunRequest,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> ScheduledRunDetail:
    try:
        schedule = await service.create_schedule(body)
    except (ProfileNotFoundError, RunTemplateNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ScheduleValidationError, RunTemplateKindError, InputCryptoError, DeclarativeContractError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RunInputStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ScheduledRunDetail.model_validate(schedule)


@router.get("/{schedule_id}", response_model=ScheduledRunDetail)
async def get_schedule(
        schedule_id: UUID,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> ScheduledRunDetail:
    schedule = await service.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return ScheduledRunDetail.model_validate(schedule)


@router.put("/{schedule_id}", response_model=ScheduledRunDetail)
async def update_schedule(
        schedule_id: UUID,
        body: UpdateScheduledRunRequest,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> ScheduledRunDetail:
    try:
        schedule = await service.update_schedule(schedule_id, body)
    except ScheduleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ScheduleValidationError, InputCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RunInputNotAvailableError, RunInputStorageError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ScheduledRunDetail.model_validate(schedule)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
        schedule_id: UUID,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> Response:
    try:
        await service.delete_schedule(schedule_id)
    except ScheduleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleArtifactCleanupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/{schedule_id}/enable", response_model=ScheduledRunDetail)
async def enable_schedule(
        schedule_id: UUID,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> ScheduledRunDetail:
    return await _set_enabled(service, schedule_id, enabled=True)


@router.post("/{schedule_id}/disable", response_model=ScheduledRunDetail)
async def disable_schedule(
        schedule_id: UUID,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> ScheduledRunDetail:
    return await _set_enabled(service, schedule_id, enabled=False)


@router.post("/{schedule_id}/trigger", response_model=CreateRunResponse, status_code=201)
async def trigger_schedule(
        schedule_id: UUID,
        service: ScheduleService = Depends(DependUtils.get_schedule_service),
) -> CreateRunResponse:
    try:
        run = await service.trigger_now(schedule_id)
    except ScheduleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleFireError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CreateRunResponse.model_validate(run)


async def _set_enabled(service: ScheduleService, schedule_id: UUID, *, enabled: bool) -> ScheduledRunDetail:
    try:
        schedule = await service.set_enabled(schedule_id, enabled)
    except ScheduleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduledRunDetail.model_validate(schedule)
