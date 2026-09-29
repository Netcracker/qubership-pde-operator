from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.scheduled_run import FireStatus, OverlapPolicy, ScheduledRun, schedule_trigger_ref
from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.schemas.schedules import CreateScheduledRunRequest, UpdateScheduledRunRequest
from pde_operator.services.profile_service import ProfileNotFoundError
from pde_operator.services.run_input_storage import RunInputStorage
from pde_operator.services.schedule_service import (
    ScheduleNotFoundError,
    ScheduleService,
    ScheduleValidationError,
)
from pde_operator.utils.input_crypto_utils import MASKED_VALUE, InputCryptoError, InputCryptoUtils


def _settings(**overrides) -> Settings:
    data = {
        "k8s_job_creation_enabled": False,
        "input_encryption_key": Fernet.generate_key().decode("ascii"),
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
        "description": None,
        "cron_expression": "0 2 * * *",
        "timezone": "UTC",
        "enabled": True,
        "overlap_policy": OverlapPolicy.SKIP,
        "profile_id": "default",
        "pde_image": None,
        "pipeline_data": "https://example.com/pipeline.yaml",
        "pipeline_vars": "ENV=dev",
        "pipeline_vars_secure": f"TOKEN={MASKED_VALUE}",
        "is_dry_run": False,
        "log_level": "INFO",
        "env_vars": None,
        "created_from_template_id": None,
        "next_fire_at": now + timedelta(hours=1),
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return ScheduledRun(**data)


def _session(*, profile: Profile | None = None, schedule: ScheduledRun | None = None) -> AsyncMock:
    session = AsyncMock()

    async def get_model(model, key):
        if model is Profile:
            return profile if profile is not None and key == profile.id else None
        if model is ScheduledRun and schedule is not None and key == schedule.id:
            return schedule
        return None

    session.get = AsyncMock(side_effect=get_model)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _artifacts() -> MagicMock:
    artifacts = MagicMock()
    artifacts.put_run_input = MagicMock()
    artifacts.get_run_input_bytes = MagicMock()
    artifacts.delete_run_artifacts = MagicMock(return_value=1)
    return artifacts


def _inline_threads(monkeypatch) -> None:
    inline = AsyncMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
    monkeypatch.setattr("pde_operator.services.run_input_storage.asyncio.to_thread", inline)
    monkeypatch.setattr("pde_operator.services.run_service.asyncio.to_thread", inline)


def _service(settings: Settings, session: AsyncMock, artifacts: MagicMock) -> ScheduleService:
    storage = RunInputStorage(settings, artifacts_service=artifacts)
    return ScheduleService(session, settings, artifacts_service=artifacts, run_input_storage=storage)


# --- secrets ---------------------------------------------------------------------------------

def test_merge_masked_secure_keeps_replaced_and_dropped_keys() -> None:
    existing = "TOKEN=real\nOTHER=keepme"

    assert InputCryptoUtils.merge_masked_secure(f"TOKEN={MASKED_VALUE}", existing) == "TOKEN=real"
    assert InputCryptoUtils.merge_masked_secure("TOKEN=fresh", existing) == "TOKEN=fresh"
    assert InputCryptoUtils.merge_masked_secure("TOKEN=new\nOTHER=keepme", existing) == "TOKEN=new\nOTHER=keepme"
    assert InputCryptoUtils.merge_masked_secure("OTHER=keepme", existing) == "OTHER=keepme"
    assert InputCryptoUtils.merge_masked_secure(None, existing) is None
    assert InputCryptoUtils.merge_masked_secure("   ", existing) is None


def test_merge_masked_secure_rejects_unknown_masked_key() -> None:
    with pytest.raises(InputCryptoError, match="unknown secure key"):
        InputCryptoUtils.merge_masked_secure(f"NOPE={MASKED_VALUE}", "TOKEN=real")


# --- create / update -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_schedule_masks_row_and_encrypts_payload(monkeypatch) -> None:
    _inline_threads(monkeypatch)
    settings = _settings()
    artifacts = _artifacts()
    session = _session(profile=_profile())
    service = _service(settings, session, artifacts)

    schedule = await service.create_schedule(
        CreateScheduledRunRequest(
            name="Nightly",
            cron_expression="0 2 * * *",
            timezone="Europe/Berlin",
            pipeline_data="https://example.com/pipeline.yaml",
            pipeline_vars="ENV=dev",
            pipeline_vars_secure="TOKEN=secret",
        )
    )

    assert schedule.pipeline_vars_secure == f"TOKEN={MASKED_VALUE}"
    assert schedule.next_fire_at is not None
    assert schedule.timezone == "Europe/Berlin"
    stored_id, ciphertext = artifacts.put_run_input.call_args.args
    assert stored_id == schedule.id
    payload = RunInputPayload.model_validate_json(
        InputCryptoUtils.decrypt(settings.input_encryption_key, ciphertext)
    )
    assert payload.pipeline_vars_secure == "TOKEN=secret"
    assert payload.pipeline_data == "https://example.com/pipeline.yaml"


@pytest.mark.asyncio
async def test_create_schedule_disabled_has_no_next_fire() -> None:
    settings = _settings()
    artifacts = _artifacts()
    service = _service(settings, _session(profile=_profile()), artifacts)

    schedule = await service.create_schedule(
        CreateScheduledRunRequest(
            name="Paused",
            cron_expression="0 2 * * *",
            pipeline_data="https://example.com/pipeline.yaml",
            enabled=False,
        )
    )

    assert schedule.next_fire_at is None


@pytest.mark.asyncio
async def test_create_schedule_rejects_masked_placeholder_for_a_new_secret() -> None:
    settings = _settings()
    service = _service(settings, _session(profile=_profile()), _artifacts())

    with pytest.raises(ScheduleValidationError, match="unknown secure key"):
        await service.create_schedule(
            CreateScheduledRunRequest(
                name="Copied from a run",
                cron_expression="0 2 * * *",
                pipeline_data="https://example.com/pipeline.yaml",
                pipeline_vars_secure=f"TOKEN={MASKED_VALUE}",
            )
        )


@pytest.mark.asyncio
async def test_create_schedule_rejects_sub_minute_cron() -> None:
    settings = _settings()
    service = _service(settings, _session(profile=_profile()), _artifacts())

    with pytest.raises(ScheduleValidationError, match="minimum interval"):
        await service.create_schedule(
            CreateScheduledRunRequest(
                name="Too often",
                cron_expression="*/10 * * * * *",
                pipeline_data="https://example.com/pipeline.yaml",
            )
        )


@pytest.mark.asyncio
async def test_create_schedule_rejects_unknown_timezone() -> None:
    settings = _settings()
    service = _service(settings, _session(profile=_profile()), _artifacts())

    with pytest.raises(ScheduleValidationError, match="Unknown timezone"):
        await service.create_schedule(
            CreateScheduledRunRequest(
                name="Wrong tz",
                cron_expression="0 2 * * *",
                timezone="Mars/Olympus",
                pipeline_data="https://example.com/pipeline.yaml",
            )
        )


@pytest.mark.asyncio
async def test_create_schedule_requires_existing_profile() -> None:
    settings = _settings()
    service = _service(settings, _session(profile=None), _artifacts())

    with pytest.raises(ProfileNotFoundError):
        await service.create_schedule(
            CreateScheduledRunRequest(
                name="No profile",
                cron_expression="0 2 * * *",
                profile_id="missing",
                pipeline_data="https://example.com/pipeline.yaml",
            )
        )


@pytest.mark.asyncio
async def test_update_schedule_keeps_masked_secret_and_recomputes_next_fire(monkeypatch) -> None:
    _inline_threads(monkeypatch)
    settings = _settings()
    artifacts = _artifacts()
    schedule = _schedule(cron_expression="0 2 * * *", timezone="UTC")
    service = _service(settings, _session(profile=_profile(), schedule=schedule), artifacts)
    service._storage.load = MagicMock(
        return_value=RunInputPayload(
            pipeline_data=schedule.pipeline_data,
            pipeline_vars=schedule.pipeline_vars,
            pipeline_vars_secure="TOKEN=secret",
            is_dry_run=False,
            log_level="INFO",
        )
    )
    previous_next_fire = schedule.next_fire_at

    updated = await service.update_schedule(
        schedule.id,
        UpdateScheduledRunRequest(
            name="Nightly (new)",
            cron_expression="0 3 * * *",
            timezone="UTC",
            pipeline_data="https://example.com/pipeline.yaml",
            pipeline_vars="ENV=prod",
            pipeline_vars_secure=f"TOKEN={MASKED_VALUE}",
        ),
    )

    assert updated.name == "Nightly (new)"
    assert updated.pipeline_vars_secure == f"TOKEN={MASKED_VALUE}"
    assert updated.next_fire_at != previous_next_fire
    stored = artifacts.put_run_input.call_args.args[1]
    payload = RunInputPayload.model_validate_json(
        InputCryptoUtils.decrypt(settings.input_encryption_key, stored)
    )
    assert payload.pipeline_vars_secure == "TOKEN=secret"
    assert payload.pipeline_vars == "ENV=prod"


@pytest.mark.asyncio
async def test_update_schedule_unknown_masked_key_is_rejected(monkeypatch) -> None:
    _inline_threads(monkeypatch)
    settings = _settings()
    artifacts = _artifacts()
    schedule = _schedule()
    service = _service(settings, _session(profile=_profile(), schedule=schedule), artifacts)
    service._storage.load = MagicMock(
        return_value=RunInputPayload(
            pipeline_data=schedule.pipeline_data,
            is_dry_run=False,
            log_level="INFO",
            pipeline_vars_secure="TOKEN=secret",
        )
    )

    with pytest.raises(ScheduleValidationError, match="unknown secure key"):
        await service.update_schedule(
            schedule.id,
            UpdateScheduledRunRequest(
                name=schedule.name,
                cron_expression=schedule.cron_expression,
                pipeline_data=schedule.pipeline_data,
                pipeline_vars_secure=f"OTHER={MASKED_VALUE}",
            ),
        )


@pytest.mark.asyncio
async def test_set_enabled_clears_and_restores_next_fire() -> None:
    settings = _settings()
    schedule = _schedule()
    service = _service(settings, _session(profile=_profile(), schedule=schedule), _artifacts())

    disabled = await service.set_enabled(schedule.id, False)
    assert disabled.enabled is False
    assert disabled.next_fire_at is None

    enabled = await service.set_enabled(schedule.id, True)
    assert enabled.enabled is True
    assert enabled.next_fire_at is not None


@pytest.mark.asyncio
async def test_delete_schedule_removes_row_and_stored_input() -> None:
    settings = _settings()
    artifacts = _artifacts()
    schedule = _schedule()
    session = _session(schedule=schedule)
    service = _service(settings, session, artifacts)

    await service.delete_schedule(schedule.id)

    session.delete.assert_awaited_once_with(schedule)
    artifacts.delete_run_artifacts.assert_called_once_with(schedule.id)


@pytest.mark.asyncio
async def test_delete_missing_schedule_raises() -> None:
    service = _service(_settings(), _session(), _artifacts())

    with pytest.raises(ScheduleNotFoundError):
        await service.delete_schedule(uuid4())


# --- firing ----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fire_creates_run_with_real_secrets_and_schedule_trigger(monkeypatch) -> None:
    _inline_threads(monkeypatch)
    settings = _settings()
    artifacts = _artifacts()
    schedule = _schedule()
    session = _session(profile=_profile(), schedule=schedule)
    service = _service(settings, session, artifacts)
    service._storage.load = MagicMock(
        return_value=RunInputPayload(
            pipeline_data=schedule.pipeline_data,
            pipeline_vars=schedule.pipeline_vars,
            pipeline_vars_secure="TOKEN=secret",
            is_dry_run=False,
            log_level="INFO",
        )
    )

    run = await service.fire(schedule)

    assert run.triggered_by == schedule_trigger_ref(schedule.id)
    assert run.pipeline_vars_secure == f"TOKEN={MASKED_VALUE}"
    assert run.pipeline_data == schedule.pipeline_data
    # the run's own input payload is encrypted under the new run id, with the real secret
    stored_id, ciphertext = artifacts.put_run_input.call_args.args
    assert stored_id == run.id
    payload = RunInputPayload.model_validate_json(
        InputCryptoUtils.decrypt(settings.input_encryption_key, ciphertext)
    )
    assert payload.pipeline_vars_secure == "TOKEN=secret"


@pytest.mark.asyncio
async def test_fire_takes_payload_values_over_row_values(monkeypatch) -> None:
    _inline_threads(monkeypatch)
    settings = _settings()
    artifacts = _artifacts()
    schedule = _schedule(
        pipeline_data="https://row.example.com/pipeline.yaml",
        log_level="INFO",
        pde_image="img:override",
        env_vars={"ROW_ONLY": "1"},
    )
    service = _service(settings, _session(profile=_profile(), schedule=schedule), artifacts)
    service._storage.load = MagicMock(
        return_value=RunInputPayload(
            pipeline_data="https://payload.example.com/pipeline.yaml",
            pipeline_vars="ENV=payload",
            pipeline_vars_secure="TOKEN=secret",
            is_dry_run=True,
            log_level="DEBUG",
        )
    )

    run = await service.fire(schedule)

    assert run.pipeline_data == "https://payload.example.com/pipeline.yaml"
    assert run.pipeline_vars == "ENV=payload"
    assert run.is_dry_run is True
    assert run.log_level == "DEBUG"
    # fields the payload does not carry still come from the row
    assert run.profile_id == schedule.profile_id
    assert run.pde_image == "img:override"
    assert run.env_vars == {"ROW_ONLY": "1"}


@pytest.mark.asyncio
async def test_fire_fails_when_profile_is_gone(monkeypatch) -> None:
    _inline_threads(monkeypatch)
    settings = _settings()
    artifacts = _artifacts()
    schedule = _schedule()
    service = _service(settings, _session(profile=None, schedule=schedule), artifacts)
    service._storage.load = MagicMock(
        return_value=RunInputPayload(pipeline_data=schedule.pipeline_data, is_dry_run=False, log_level="INFO")
    )

    with pytest.raises(ProfileNotFoundError):
        await service.fire(schedule)


@pytest.mark.asyncio
async def test_trigger_now_records_success(monkeypatch) -> None:
    _inline_threads(monkeypatch)
    settings = _settings()
    artifacts = _artifacts()
    schedule = _schedule()
    session = _session(profile=_profile(), schedule=schedule)
    service = _service(settings, session, artifacts)
    service._storage.load = MagicMock(
        return_value=RunInputPayload(pipeline_data=schedule.pipeline_data, is_dry_run=False, log_level="INFO")
    )

    run = await service.trigger_now(schedule.id)

    assert schedule.last_run_id == run.id
    assert schedule.last_fire_status == FireStatus.SUCCESS
    assert schedule.last_fire_at is not None
