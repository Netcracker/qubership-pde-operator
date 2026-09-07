import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.db.models.profile import Profile
from pde_operator.schemas.profiles import CreateProfileRequest, UpdateProfileRequest

DEFAULT_PROFILE_ID = "default"
_PROFILE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_profiles(self, *, offset: int = 0, limit: int = 20) -> tuple[list[Profile], int]:
        count_query = select(func.count()).select_from(Profile)
        total = int((await self._session.execute(count_query)).scalar_one())

        query = select(Profile).order_by(Profile.updated_at.desc(), Profile.id.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def get_profile(self, profile_id: str) -> Profile | None:
        return await self._session.get(Profile, profile_id)

    async def create_profile(self, request: CreateProfileRequest) -> Profile:
        self.validate_profile_id(request.id)
        existing = await self._session.get(Profile, request.id)
        if existing is not None:
            raise ProfileAlreadyExistsError(request.id)

        profile = Profile(
            id=request.id,
            pde_image=request.pde_image,
            env_vars=request.env_vars,
            resources=request.resources,
        )
        self._session.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def update_profile(self, profile_id: str, request: UpdateProfileRequest) -> Profile:
        profile = await self._session.get(Profile, profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)

        profile.pde_image = request.pde_image
        profile.env_vars = request.env_vars
        profile.resources = request.resources
        profile.updated_at = datetime.now(UTC)

        await self._session.commit()
        await self._session.refresh(profile)
        return profile

    async def delete_profile(self, profile_id: str) -> None:
        if profile_id == DEFAULT_PROFILE_ID:
            raise ProfileProtectedError(f"Profile '{DEFAULT_PROFILE_ID}' cannot be deleted")

        profile = await self._session.get(Profile, profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)

        await self._session.delete(profile)
        await self._session.commit()

    @staticmethod
    def validate_profile_id(profile_id: str) -> None:
        if not _PROFILE_ID_PATTERN.fullmatch(profile_id):
            raise ProfileValidationError("Profile id must be 1-64 chars, start with alphanumeric, and use only letters, digits, '.', '_', '-'")


class ProfileNotFoundError(LookupError):
    def __init__(self, profile_id: str, *, message: str | None = None) -> None:
        self.profile_id = profile_id
        super().__init__(message or f"Profile '{profile_id}' not found")


class ProfileAlreadyExistsError(ValueError):
    def __init__(self, profile_id: str) -> None:
        self.profile_id = profile_id
        super().__init__(f"Profile '{profile_id}' already exists")


class ProfileProtectedError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ProfileValidationError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
