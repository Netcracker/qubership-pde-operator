from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pde_operator.db.models.base import Base


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES: frozenset[RunStatus] = frozenset({RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED})
RETRYABLE_STATUSES: frozenset[RunStatus] = frozenset({RunStatus.FAILED, RunStatus.CANCELLED})


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("runs_status_idx", "status"),
        Index("runs_created_at_idx", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    profile_id: Mapped[str] = mapped_column(Text, nullable=False)
    pde_image: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=RunStatus.QUEUED)

    pipeline_data: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_vars: Mapped[str | None] = mapped_column(Text)
    pipeline_vars_secure: Mapped[str | None] = mapped_column(Text)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    log_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="INFO")

    env_vars: Mapped[dict | None] = mapped_column(JSONB)
    retry_vars: Mapped[str | None] = mapped_column(Text)

    name: Mapped[str | None] = mapped_column(Text)
    k8s_job_name: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(Text)

    progress_json: Mapped[dict | None] = mapped_column(JSONB)
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    log_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state_location: Mapped[str | None] = mapped_column(Text)

    retry_of_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_from_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    execution_url: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finish_code: Mapped[str | None] = mapped_column(Text)
    finish_message: Mapped[str | None] = mapped_column(Text)
