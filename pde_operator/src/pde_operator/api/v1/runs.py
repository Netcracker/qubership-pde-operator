import asyncio
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.schemas.runs import (
    ArtifactsUploadResponse,
    CreateRunRequest,
    CreateRunResponse,
    LogDeliveryResponse,
    ReportDeliveryResponse,
    RetryRunRequest,
    RunDetail,
    RunListResponse,
    RunSummary,
    StatusDeliveryResponse,
)
from pde_operator.services.job_service import JobCreationError
from pde_operator.services.profile_service import ProfileNotFoundError
from pde_operator.services.run_service import (
    RunNotCancellableError,
    RunNotFoundError,
    RunNotRetriableError,
    RunService,
    RunInputNotAvailableError,
    RunInputStorageError,
    RunStateNotAvailableError,
)
from pde_operator.utils.artifact_utils import ArtifactNotFoundError, ArtifactsDisabledError, ArtifactUtils
from pde_operator.utils.depend_utils import DependUtils
from pde_operator.utils.http_utils import HttpUtils

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=CreateRunResponse, status_code=201)
async def create_run(
        body: CreateRunRequest,
        service: RunService = Depends(DependUtils.get_run_service),
) -> CreateRunResponse:
    try:
        run = await service.create_run(body)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (JobCreationError, RunInputStorageError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CreateRunResponse.model_validate(run)


@router.get("", response_model=RunListResponse)
async def list_runs(
        q: str | None = Query(default=None),
        status: str | None = Query(default=None),
        profile_id: str | None = Query(default=None),
        created_from_template_id: UUID | None = Query(default=None),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=500),
        service: RunService = Depends(DependUtils.get_run_service),
) -> RunListResponse:
    runs, total = await service.list_runs(
        q=q,
        status=status,
        profile_id=profile_id,
        created_from_template_id=created_from_template_id,
        created_after=created_after,
        created_before=created_before,
        offset=offset,
        limit=limit,
    )
    items = [RunSummary.model_validate(run) for run in runs]
    return RunListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(
        run_id: UUID,
        service: RunService = Depends(DependUtils.get_run_service),
) -> RunDetail:
    detail = await service.get_run(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return detail


@router.post("/{run_id}/cancel", response_model=RunDetail)
async def cancel_run(
        run_id: UUID,
        service: RunService = Depends(DependUtils.get_run_service),
) -> RunDetail:
    try:
        run = await service.cancel_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunNotCancellableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RunDetail.model_validate(run)


@router.post("/{run_id}/retry", response_model=CreateRunResponse, status_code=201)
async def retry_run(
        run_id: UUID,
        body: RetryRunRequest | None = None,
        service: RunService = Depends(DependUtils.get_run_service),
) -> CreateRunResponse:
    try:
        run = await service.retry_run(run_id, body)
    except (RunNotFoundError, ProfileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RunNotRetriableError, RunStateNotAvailableError, RunInputNotAvailableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (JobCreationError, RunInputStorageError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CreateRunResponse.model_validate(run)


@router.get("/{run_id}/input", response_model=RunInputPayload)
async def get_run_input(
        run_id: UUID,
        service: RunService = Depends(DependUtils.get_run_service),
) -> RunInputPayload:
    if not await service.run_exists(run_id):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    try:
        return await asyncio.to_thread(service.get_run_input, run_id)
    except RunInputNotAvailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/deliveries/status", response_model=StatusDeliveryResponse)
async def deliver_status(
        run_id: UUID,
        request: Request,
        service: RunService = Depends(DependUtils.get_run_service),
) -> StatusDeliveryResponse:
    status = await HttpUtils.parse_json_body(request)
    try:
        run = await service.deliver_status(run_id, status)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StatusDeliveryResponse.model_validate(run)


@router.post("/{run_id}/deliveries/report", response_model=ReportDeliveryResponse)
async def deliver_report(
        run_id: UUID,
        request: Request,
        service: RunService = Depends(DependUtils.get_run_service),
) -> ReportDeliveryResponse:
    data = await HttpUtils.read_raw_body(request)
    try:
        run = await service.deliver_report(run_id, data)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactsDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReportDeliveryResponse.model_validate(run)


@router.post("/{run_id}/deliveries/log", response_model=LogDeliveryResponse)
async def deliver_log(
        run_id: UUID,
        request: Request,
        service: RunService = Depends(DependUtils.get_run_service),
) -> LogDeliveryResponse:
    append = (request.headers.get("x-pde-log-append") or "").lower().strip()
    if append == "true":
        raise HTTPException(status_code=501, detail="Log append delivery is not implemented")
    data = await HttpUtils.read_raw_body(request)
    try:
        run = await service.deliver_log(run_id, data)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactsDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LogDeliveryResponse.model_validate(run)


@router.post("/{run_id}/artifacts", response_model=ArtifactsUploadResponse)
async def upload_artifacts(
        run_id: UUID,
        state: UploadFile | None = File(default=None),
        log: UploadFile | None = File(default=None),
        x_debug: UploadFile | None = File(default=None),
        report: UploadFile | None = File(default=None),
        service: RunService = Depends(DependUtils.get_run_service),
) -> ArtifactsUploadResponse:
    state_bytes = await state.read() if state is not None else None
    log_bytes = await log.read() if log is not None else None
    x_debug_bytes = await x_debug.read() if x_debug is not None else None
    report_bytes = await report.read() if report is not None else None
    if state_bytes == b"":
        state_bytes = None
    if log_bytes == b"":
        log_bytes = None
    if x_debug_bytes == b"":
        x_debug_bytes = None
    if report_bytes == b"":
        report_bytes = None
    if state_bytes is None and log_bytes is None and x_debug_bytes is None and report_bytes is None:
        raise HTTPException(status_code=400, detail="at least one non-empty artifact is required")

    try:
        run = await service.upload_artifacts(
            run_id,
            state=state_bytes,
            log=log_bytes,
            x_debug=x_debug_bytes,
            report=report_bytes,
        )
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactsDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ArtifactsUploadResponse(id=run.id, state_location=run.state_location)


@router.get("/{run_id}/artifacts/{kind}")
async def download_artifact(
        run_id: UUID,
        kind: str,
        service: RunService = Depends(DependUtils.get_run_service),
) -> StreamingResponse:
    try:
        parsed_kind = ArtifactUtils.parse_artifact_kind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not await service.run_exists(run_id):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    try:
        obj = service.get_artifact(run_id, parsed_kind)
    except ArtifactsDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": f'attachment; filename="{ArtifactUtils.filename(parsed_kind)}"'
    }
    if obj.content_length is not None:
        headers["Content-Length"] = str(obj.content_length)
    return StreamingResponse(obj.body, media_type=obj.content_type, headers=headers)
