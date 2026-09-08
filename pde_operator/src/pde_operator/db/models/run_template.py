from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pde_operator.db.models.base import Base


class RunTemplate(Base):
    __tablename__ = "run_templates"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    template_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="simple")

    profile_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="default")
    pipeline_data: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_vars: Mapped[str | None] = mapped_column(Text)
    pipeline_vars_secure: Mapped[str | None] = mapped_column(Text)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    log_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="INFO")
    env_vars: Mapped[dict | None] = mapped_column(JSONB)
    pde_image: Mapped[str | None] = mapped_column(Text)
    declarative_spec: Mapped[dict | None] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
