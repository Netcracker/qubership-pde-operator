"""Unit tests for Prometheus run gauges."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pde_operator.db.models.run import RunStatus
from pde_operator.utils.metrics_utils import MetricsUtils


@pytest.mark.asyncio
async def test_run_counts_from_status_groups() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = [
        (RunStatus.QUEUED, 2),
        (RunStatus.NOT_STARTED, 1),
        (RunStatus.IN_PROGRESS, 3),
        (RunStatus.SUCCESS, 10),
        (RunStatus.FAILED, 4),
    ]
    session.execute = AsyncMock(return_value=result)

    queued, in_progress, total = await MetricsUtils.run_counts(session)

    assert queued == 2
    assert in_progress == 4  # NOT_STARTED + IN_PROGRESS
    assert total == 20


@pytest.mark.asyncio
async def test_render_metrics_includes_gauge_names() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(RunStatus.QUEUED, 1), (RunStatus.IN_PROGRESS, 2), (RunStatus.SUCCESS, 5)]
    session.execute = AsyncMock(return_value=result)

    body = (await MetricsUtils.render_metrics(session)).decode("utf-8")

    assert "pde_operator_runs_queued" in body
    assert "pde_operator_runs_in_progress" in body
    assert "pde_operator_runs_total" in body
    assert "pde_operator_runs_queued 1.0" in body
    assert "pde_operator_runs_in_progress 2.0" in body
    assert "pde_operator_runs_total 8.0" in body
