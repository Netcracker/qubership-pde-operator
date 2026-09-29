from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import Run
from pde_operator.db.models.scheduled_run import FireStatus, OverlapPolicy, ScheduledRun, schedule_trigger_ref
from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.services.run_input_storage import RunInputStorage
from pde_operator.services.schedule_dispatcher import ScheduleDispatcher


def _settings(**overrides) -> Settings:
    data = {
        "k8s_job_creation_enabled": False,
        "input_encryption_key": Fernet.generate_key().decode("ascii"),
        "schedules_missed_grace_seconds": 60,
    }
    data.update(overrides)
    return Settings(**data)


def _profile(profile_id: str = "default") -> Profile:
    return Profile(id=profile_id, pde_image="img:1", env_vars={})


def _schedule(**overrides) -> ScheduledRun:
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "name": "Nightly",
        "cron_expression": "0 2 * * *",
        "timezone": "UTC",
        "enabled": True,
        "overlap_policy": OverlapPolicy.SKIP,
        "profile_id": "default",
        "pipeline_data": "https://example.com/pipeline.yaml",
        "pipeline_vars": "ENV=dev",
        "pipeline_vars_secure": "TOKEN=[MASKED]",
        "is_dry_run": False,
        "log_level": "INFO",
        "next_fire_at": now,
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return ScheduledRun(**data)


def _result(*, rows=None, scalar: int = 0) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows or []
    result.scalar_one.return_value = scalar
    return result


def _session_factory(session: AsyncMock) -> MagicMock:
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None
    return MagicMock(return_value=session_cm)


def _session(schedule: ScheduledRun, *, active_runs: int = 0) -> AsyncMock:
    session = AsyncMock()
    # first execute: due schedules claim; second: triggered_by refs with a run still in flight
    active_refs = [schedule_trigger_ref(schedule.id)] * active_runs
    session.execute = AsyncMock(side_effect=[_result(rows=[schedule]), _result(rows=active_refs)])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def get_model(model, key):
        if model is Profile:
            return _profile() if key == "default" else None
        if model is ScheduledRun and key == schedule.id:
            return schedule
        return None

    session.get = AsyncMock(side_effect=get_model)
    return session


@pytest.fixture(autouse=True)
def _stub_input_storage(monkeypatch):
    payload = RunInputPayload(
        pipeline_data="https://example.com/pipeline.yaml",
        pipeline_vars="ENV=dev",
        pipeline_vars_secure="TOKEN=secret",
        is_dry_run=False,
        log_level="INFO",
    )
    monkeypatch.setattr(RunInputStorage, "load", lambda self, entity_id: payload)
    monkeypatch.setattr(RunInputStorage, "store", AsyncMock())


def _added_run(session: AsyncMock) -> Run:
    runs = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Run)]
    assert len(runs) == 1
    return runs[0]


@pytest.mark.asyncio
async def test_due_schedule_fires_and_advances_next_fire() -> None:
    now = datetime.now(UTC)
    schedule = _schedule(next_fire_at=now - timedelta(seconds=5))
    session = _session(schedule)
    dispatcher = ScheduleDispatcher(_settings(), _session_factory(session))

    fired = await dispatcher.fire_due_once(now=now)

    assert fired == 1
    run = _added_run(session)
    assert run.triggered_by == schedule_trigger_ref(schedule.id)
    assert run.pipeline_data == schedule.pipeline_data
    assert schedule.next_fire_at > now
    assert schedule.last_fire_status == FireStatus.SUCCESS
    assert schedule.last_run_id == run.id


@pytest.mark.asyncio
async def test_overdue_schedule_is_skipped_as_missed() -> None:
    now = datetime.now(UTC)
    schedule = _schedule(next_fire_at=now - timedelta(minutes=10))
    session = _session(schedule)
    dispatcher = ScheduleDispatcher(_settings(), _session_factory(session))

    fired = await dispatcher.fire_due_once(now=now)

    assert fired == 0
    assert session.add.call_args_list == []
    assert schedule.last_fire_status == FireStatus.SKIPPED_MISSED
    assert "missed fire at" in (schedule.last_fire_error or "")
    assert schedule.next_fire_at > now


@pytest.mark.asyncio
async def test_overlap_policy_skip_holds_fire_while_run_is_active() -> None:
    now = datetime.now(UTC)
    schedule = _schedule(next_fire_at=now - timedelta(seconds=5), overlap_policy=OverlapPolicy.SKIP)
    session = _session(schedule, active_runs=1)
    dispatcher = ScheduleDispatcher(_settings(), _session_factory(session))

    fired = await dispatcher.fire_due_once(now=now)

    assert fired == 0
    assert session.add.call_args_list == []
    assert schedule.last_fire_status == FireStatus.SKIPPED_OVERLAP
    assert schedule.next_fire_at > now


@pytest.mark.asyncio
async def test_overlap_policy_allow_fires_despite_active_run() -> None:
    now = datetime.now(UTC)
    schedule = _schedule(next_fire_at=now - timedelta(seconds=5), overlap_policy=OverlapPolicy.ALLOW)
    session = _session(schedule, active_runs=3)
    dispatcher = ScheduleDispatcher(_settings(), _session_factory(session))

    fired = await dispatcher.fire_due_once(now=now)

    assert fired == 1
    assert schedule.last_fire_status == FireStatus.SUCCESS


@pytest.mark.asyncio
async def test_schedule_without_anchor_is_reanchored_without_firing() -> None:
    now = datetime.now(UTC)
    schedule = _schedule(next_fire_at=None)
    session = _session(schedule)
    dispatcher = ScheduleDispatcher(_settings(), _session_factory(session))

    fired = await dispatcher.fire_due_once(now=now)

    assert fired == 0
    assert session.add.call_args_list == []
    assert schedule.next_fire_at is not None
    assert schedule.last_fire_status is None


@pytest.mark.asyncio
async def test_invalid_cron_disables_schedule() -> None:
    now = datetime.now(UTC)
    schedule = _schedule(cron_expression="not a cron", next_fire_at=now - timedelta(seconds=5))
    session = _session(schedule)
    dispatcher = ScheduleDispatcher(_settings(), _session_factory(session))

    fired = await dispatcher.fire_due_once(now=now)

    assert fired == 0
    assert schedule.enabled is False
    assert schedule.next_fire_at is None
    assert schedule.last_fire_status == FireStatus.FAILED


@pytest.mark.asyncio
async def test_fire_failure_is_recorded_and_does_not_stop_the_tick() -> None:
    now = datetime.now(UTC)
    schedule = _schedule(next_fire_at=now - timedelta(seconds=5))
    session = _session(schedule)

    async def get_model(model, key):
        if model is Profile:
            return None  # profile vanished -> fire raises
        if model is ScheduledRun and key == schedule.id:
            return schedule
        return None

    session.get = AsyncMock(side_effect=get_model)
    dispatcher = ScheduleDispatcher(_settings(), _session_factory(session))

    fired = await dispatcher.fire_due_once(now=now)

    assert fired == 0
    assert schedule.last_fire_status == FireStatus.FAILED
    assert "Profile" in (schedule.last_fire_error or "")
