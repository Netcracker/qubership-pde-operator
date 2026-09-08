from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.db.models.profile import Profile
from pde_operator.declarative_templates.contract.models import EnumOption, FieldSpec


class ProfilesProvider:
    INTERFACE_NAME = "Profiles"

    @staticmethod
    async def list_options(session: AsyncSession, field: FieldSpec, context: dict[str, Any]) -> list[EnumOption]:
        _ = field, context
        result = await session.execute(select(Profile.id).order_by(Profile.id))
        return [EnumOption(value=profile_id, label=profile_id) for profile_id in result.scalars().all()]
