from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from pde_operator.db.models.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    pde_image: Mapped[str] = mapped_column(Text, nullable=False)
    env_vars: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    resources: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
