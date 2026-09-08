from fastapi import APIRouter, Depends, HTTPException, Query, Response

from pde_operator.schemas.profiles import (
    CreateProfileRequest,
    ProfileDetail,
    ProfileListItem,
    ProfileListResponse,
    UpdateProfileRequest,
)
from pde_operator.services.profile_service import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileProtectedError,
    ProfileService,
    ProfileValidationError,
)
from pde_operator.utils.depend_utils import DependUtils

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=ProfileListResponse)
async def list_profiles(
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=500),
        service: ProfileService = Depends(DependUtils.get_profile_service),
) -> ProfileListResponse:
    profiles, total = await service.list_profiles(offset=offset, limit=limit)
    items = [ProfileListItem.model_validate(p) for p in profiles]
    return ProfileListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=ProfileDetail, status_code=201)
async def create_profile(
        request: CreateProfileRequest,
        service: ProfileService = Depends(DependUtils.get_profile_service),
) -> ProfileDetail:
    try:
        profile = await service.create_profile(request)
    except ProfileAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProfileValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProfileDetail.model_validate(profile)


@router.get("/{profile_id}", response_model=ProfileDetail)
async def get_profile(
        profile_id: str,
        service: ProfileService = Depends(DependUtils.get_profile_service),
) -> ProfileDetail:
    profile = await service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")
    return ProfileDetail.model_validate(profile)


@router.put("/{profile_id}", response_model=ProfileDetail)
async def update_profile(
        profile_id: str,
        request: UpdateProfileRequest,
        service: ProfileService = Depends(DependUtils.get_profile_service),
) -> ProfileDetail:
    try:
        profile = await service.update_profile(profile_id, request)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProfileDetail.model_validate(profile)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
        profile_id: str,
        service: ProfileService = Depends(DependUtils.get_profile_service),
) -> Response:
    try:
        await service.delete_profile(profile_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileProtectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)
