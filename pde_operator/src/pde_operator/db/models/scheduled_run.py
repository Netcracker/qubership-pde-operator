from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pde_operator.db.models.base import Base

SCHEDULE_TRIGGER_PREFIX = "schedule:"


def schedule_trigger_ref(schedule_id: UUID) -> str:
    """Value stored in Run.triggered_by for runs started by a schedule."""
    return f"{SCHEDULE_TRIGGER_PREFIX}{schedule_id}"


def schedule_id_from_trigger(triggered_by: str | None) -> UUID | None:
    if not triggered_by or not triggered_by.startswith(SCHEDULE_TRIGGER_PREFIX):
        return None
    try:
        return UUID(triggered_by[len(SCHEDULE_TRIGGER_PREFIX):])
    except ValueError:
        return None


class OverlapPolicy(StrEnum):
    SKIP = "skip"
    ALLOW = "allow"


class FireStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED_OVERLAP = "skipped_overlap"
    SKIPPED_MISSED = "skipped_missed"


class ScheduledRun(Base):
    __tablename__ = "scheduled_runs"
    __table_args__ = (Index("scheduled_runs_due_idx", "enabled", "next_fire_at"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    cron_expression: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    overlap_policy: Mapped[str] = mapped_column(Text, nullable=False, server_default=OverlapPolicy.ALLOW)

    profile_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="default")
    pde_image: Mapped[str | None] = mapped_column(Text)
    pipeline_data: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    pipeline_vars: Mapped[str | None] = mapped_column(Text)
    pipeline_vars_secure: Mapped[str | None] = mapped_column(Text)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    log_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="INFO")
    env_vars: Mapped[dict | None] = mapped_column(JSONB)

    created_from_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    next_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_fire_status: Mapped[str | None] = mapped_column(Text)
    last_fire_error: Mapped[str | None] = mapped_column(Text)
    last_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
