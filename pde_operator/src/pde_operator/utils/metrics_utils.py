"""Prometheus metrics helpers for PDE Operator."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.db.models.run import Run, RunStatus

_RUNS_QUEUED = Gauge("pde_operator_runs_queued", "Number of runs waiting in QUEUED")
_RUNS_IN_PROGRESS = Gauge("pde_operator_runs_in_progress", "Number of runs in NOT_STARTED or IN_PROGRESS")
_RUNS_TOTAL = Gauge("pde_operator_runs_total", "Total number of runs stored")


class MetricsUtils:
    CONTENT_TYPE = CONTENT_TYPE_LATEST

    @staticmethod
    async def run_counts(session: AsyncSession) -> tuple[int, int, int]:
        """Return (queued, in_progress, total) from the runs table."""
        result = await session.execute(select(Run.status, func.count()).group_by(Run.status))
        by_status = {status: count for status, count in result.all()}
        queued = int(by_status.get(RunStatus.QUEUED, 0))
        in_progress = int(by_status.get(RunStatus.NOT_STARTED, 0)) + int(by_status.get(RunStatus.IN_PROGRESS, 0))
        total = int(sum(by_status.values()))
        return queued, in_progress, total

    @staticmethod
    def set_run_gauges(*, queued: int, in_progress: int, total: int) -> None:
        _RUNS_QUEUED.set(queued)
        _RUNS_IN_PROGRESS.set(in_progress)
        _RUNS_TOTAL.set(total)

    @staticmethod
    async def render_metrics(session: AsyncSession) -> bytes:
        queued, in_progress, total = await MetricsUtils.run_counts(session)
        MetricsUtils.set_run_gauges(queued=queued, in_progress=in_progress, total=total)
        return generate_latest()
