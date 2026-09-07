from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from pde_operator.declarative_templates.api.schemas import (
    CreateDeclarativeRunFromTemplateRequest,
    GetDeclarativeEnumOptionsRequest,
    GetDeclarativeEnumOptionsResponse,
)
from pde_operator.declarative_templates.contract.errors import DeclarativeContractError, DeclarativeOptionsProviderError
from pde_operator.schemas.run_templates import RunTemplateDetail
from pde_operator.schemas.runs import CreateRunResponse
from pde_operator.declarative_templates.services.options_service import DeclarativeOptionsService
from pde_operator.declarative_templates.services.template_store import DeclarativeTemplateStore
from pde_operator.services.profile_service import ProfileNotFoundError
from pde_operator.services.run_service import RunService
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateNotFoundError
from pde_operator.utils.depend_utils import DependUtils

router = APIRouter(prefix="/run-templates", tags=["declarative-run-templates"])


@router.post("/declarative/upload", response_model=RunTemplateDetail, status_code=201)
async def upload_declarative_run_template(
        file: UploadFile,
        store: DeclarativeTemplateStore = Depends(DependUtils.get_declarative_template_store),
) -> RunTemplateDetail:
    yaml_bytes = await file.read()
    yaml_text = yaml_bytes.decode("utf-8", errors="replace")
    now = datetime.now(UTC)
    try:
        template = await store.import_from_yaml(yaml_text=yaml_text, now=now)
    except (DeclarativeContractError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunTemplateDetail.model_validate(template)


@router.post("/{template_id}/declarative/options", response_model=GetDeclarativeEnumOptionsResponse)
async def get_declarative_enum_options(
        template_id: UUID,
        request: GetDeclarativeEnumOptionsRequest,
        service: DeclarativeOptionsService = Depends(DependUtils.get_declarative_options_service),
) -> GetDeclarativeEnumOptionsResponse:
    try:
        options = await service.get_enum_options(
            template_id=template_id,
            field_id=request.fieldId,
            context=request.context,
        )
    except RunTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunTemplateKindError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DeclarativeOptionsProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GetDeclarativeEnumOptionsResponse(options=options)


@router.post("/{template_id}/declarative-runs", response_model=CreateRunResponse, status_code=201)
async def create_run_from_declarative_template(
        template_id: UUID,
        request: CreateDeclarativeRunFromTemplateRequest,
        run_service: RunService = Depends(DependUtils.get_run_service),
) -> CreateRunResponse:
    try:
        run = await run_service.create_run_from_declarative_template(template_id, request.values)
    except RunTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunTemplateKindError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DeclarativeContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CreateRunResponse.model_validate(run)
