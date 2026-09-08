from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from pde_operator.schemas.run_templates import (
    CreateRunFromTemplateRequest,
    CreateSimpleRunTemplateRequest,
    RunTemplateDetail,
    RunTemplateListResponse,
    RunTemplateSummary,
    UpdateSimpleRunTemplateRequest,
)
from pde_operator.schemas.runs import CreateRunResponse
from pde_operator.services.profile_service import ProfileNotFoundError
from pde_operator.services.run_service import RunService
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateNotFoundError, RunTemplateService
from pde_operator.utils.depend_utils import DependUtils

router = APIRouter(prefix="/run-templates", tags=["run-templates"])


@router.get("", response_model=RunTemplateListResponse)
async def list_run_templates(
        q: str | None = Query(default=None, description="Search id/name/description/tags"),
        tag: str | None = Query(default=None, description="Exact tag match"),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=500),
        service: RunTemplateService = Depends(DependUtils.get_run_template_service),
) -> RunTemplateListResponse:
    templates, total = await service.list_templates(q=q, tag=tag, offset=offset, limit=limit)
    items = [RunTemplateSummary.model_validate(t) for t in templates]
    return RunTemplateListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=RunTemplateDetail, status_code=201)
async def create_simple_run_template(
        request: CreateSimpleRunTemplateRequest,
        service: RunTemplateService = Depends(DependUtils.get_run_template_service),
) -> RunTemplateDetail:
    template = await service.create_template(request)
    return RunTemplateDetail.model_validate(template)


@router.get("/{template_id}", response_model=RunTemplateDetail)
async def get_run_template(
        template_id: UUID,
        service: RunTemplateService = Depends(DependUtils.get_run_template_service),
) -> RunTemplateDetail:
    template = await service.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Run template '{template_id}' not found")
    return RunTemplateDetail.model_validate(template)


@router.put("/{template_id}", response_model=RunTemplateDetail)
async def update_simple_run_template(
        template_id: UUID,
        request: UpdateSimpleRunTemplateRequest,
        service: RunTemplateService = Depends(DependUtils.get_run_template_service),
) -> RunTemplateDetail:
    try:
        template = await service.update_template(template_id, request)
    except RunTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunTemplateKindError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunTemplateDetail.model_validate(template)


@router.delete("/{template_id}", status_code=204)
async def delete_run_template(
        template_id: UUID,
        service: RunTemplateService = Depends(DependUtils.get_run_template_service),
) -> Response:
    try:
        await service.delete_template(template_id)
    except RunTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/{template_id}/runs", response_model=CreateRunResponse, status_code=201)
async def create_run_from_simple_template(
        template_id: UUID,
        request: CreateRunFromTemplateRequest | None = None,
        run_service: RunService = Depends(DependUtils.get_run_service),
) -> CreateRunResponse:
    try:
        run = await run_service.create_run_from_simple_template(template_id, request)
    except RunTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunTemplateKindError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CreateRunResponse.model_validate(run)
