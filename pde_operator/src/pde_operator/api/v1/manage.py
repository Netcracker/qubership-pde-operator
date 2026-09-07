from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError

from pde_operator.schemas.manage import CleanupRequest, CleanupResponse
from pde_operator.services.config_import_service import ConfigImportService
from pde_operator.services.profile_service import ProfileValidationError
from pde_operator.services.retention_service import RetentionService
from pde_operator.utils.depend_utils import DependUtils

router = APIRouter(prefix="/manage", tags=["manage"])


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_runs(
        body: CleanupRequest,
        service: RetentionService = Depends(DependUtils.get_retention_service),
) -> CleanupResponse:
    result = await service.cleanup_older_than(body.older_than)
    return CleanupResponse(older_than=result.older_than, deleted=result.deleted, failed=result.failed)


@router.post("/config/import", status_code=200)
async def import_config(
        file: UploadFile = File(...),
        mode: Literal["merge", "replace"] = Form(default="merge"),
        service: ConfigImportService = Depends(DependUtils.get_config_import_service),
) -> Response:
    yaml_bytes = await file.read()
    yaml_text = yaml_bytes.decode("utf-8", errors="replace")
    try:
        await service.import_config_from_yaml(yaml_text=yaml_text, mode=mode)
    except (ValidationError, ValueError, ProfileValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=200)
