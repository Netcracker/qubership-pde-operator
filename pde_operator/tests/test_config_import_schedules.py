from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.scheduled_run import ScheduledRun
from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.services.config_import_service import ConfigImportService
from pde_operator.services.run_input_storage import RunInputStorage
from pde_operator.utils.input_crypto_utils import MASKED_VALUE, InputCryptoUtils

_PROFILE_YAML = """
apiVersion: v1
kind: Profile
id: default
pde_image: img:1
"""

SCHEDULE_YAML = """
apiVersion: v1
kind: ScheduledRun
name: Nightly Deploy
cron_expression: "30 2 * * *"
timezone: Europe/Berlin
pipeline_data: https://example.com/pipeline.yaml
pipeline_vars: |
  ENV_NAME=dev
pipeline_vars_secure: |
  API_TOKEN=plaintext-secret
"""


def _settings(**overrides) -> Settings:
    data = {"input_encryption_key": Fernet.generate_key().decode("ascii")}
    data.update(overrides)
    return Settings(**data)


def _result(*, rows=None) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows or []
    return result


def _session(*, profile: Profile | None = None, existing: ScheduledRun | None = None) -> AsyncMock:
    session = AsyncMock()

    async def get_model(model, key):
        if model is Profile:
            return profile if profile is not None and key == getattr(profile, "id", None) else None
        if model is ScheduledRun and existing is not None and key == existing.id:
            return existing
        return None

    session.get = AsyncMock(side_effect=get_model)
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=_result())
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def _stub_input_storage(monkeypatch):
    monkeypatch.setattr(RunInputStorage, "load", MagicMock(return_value=RunInputPayload(
        pipeline_data="https://example.com/pipeline.yaml",
        pipeline_vars="ENV_NAME=dev",
        pipeline_vars_secure="API_TOKEN=stored-secret",
        is_dry_run=False,
        log_level="INFO",
    )))
    monkeypatch.setattr(RunInputStorage, "store", AsyncMock())
    monkeypatch.setattr(RunInputStorage, "delete", AsyncMock(return_value=1))


@pytest.mark.asyncio
async def test_import_creates_schedule_and_encrypts_secrets() -> None:
    settings = _settings()
    session = _session(profile=Profile(id="default", pde_image="img:1", env_vars={}))
    service = ConfigImportService(session, settings)

    await service.import_config_from_yaml(yaml_text=SCHEDULE_YAML, mode="merge")

    schedules = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], ScheduledRun)]
    assert len(schedules) == 1
    schedule = schedules[0]
    assert schedule.name == "Nightly Deploy"
    assert schedule.timezone == "Europe/Berlin"
    assert schedule.next_fire_at is not None
    assert schedule.pipeline_vars_secure == f"API_TOKEN={MASKED_VALUE}"

    stored_id, payload = RunInputStorage.store.call_args.args
    assert stored_id == schedule.id  # payload keyed by the schedule id
    assert isinstance(payload, RunInputPayload)
    assert payload.pipeline_vars_secure == "API_TOKEN=plaintext-secret"


@pytest.mark.asyncio
async def test_import_with_existing_id_updates_in_place() -> None:
    settings = _settings()
    schedule_id = uuid4()
    existing = ScheduledRun(
        id=schedule_id,
        name="Old name",
        cron_expression="0 0 * * *",
        timezone="UTC",
        enabled=True,
        overlap_policy="skip",
        profile_id="default",
        pipeline_data="https://example.com/pipeline.yaml",
        pipeline_vars="ENV_NAME=old",
        pipeline_vars_secure=f"API_TOKEN={MASKED_VALUE}",
        is_dry_run=False,
        log_level="INFO",
    )
    yaml_text = SCHEDULE_YAML.replace("kind: ScheduledRun", f"kind: ScheduledRun\nid: {schedule_id}")
    session = _session(profile=Profile(id="default", pde_image="img:1", env_vars={}), existing=existing)
    service = ConfigImportService(session, settings)

    await service.import_config_from_yaml(yaml_text=yaml_text, mode="merge")

    assert session.add.call_args_list == []  # updated, not inserted
    assert existing.name == "Nightly Deploy"
    assert existing.cron_expression == "30 2 * * *"
    assert existing.timezone == "Europe/Berlin"
    payload = RunInputStorage.store.call_args.args[1]
    assert payload.pipeline_vars_secure == "API_TOKEN=plaintext-secret"  # re-encrypted from the file
    assert payload.pipeline_vars == "ENV_NAME=dev\n"


@pytest.mark.asyncio
async def test_replace_mode_wipes_schedules_and_their_payloads() -> None:
    settings = _settings()
    schedule_ids = [uuid4(), uuid4()]
    session = _session()
    session.execute = AsyncMock(side_effect=[_result(), _result(), _result(rows=schedule_ids), _result()])
    service = ConfigImportService(session, settings)

    await service.import_config_from_yaml(yaml_text=_PROFILE_YAML, mode="replace")

    assert RunInputStorage.delete.await_count == len(schedule_ids)
    deleted_ids = [call.args[0] for call in RunInputStorage.delete.await_args_list]
    assert deleted_ids == schedule_ids


@pytest.mark.asyncio
async def test_merge_mode_keeps_existing_schedules() -> None:
    settings = _settings()
    session = _session()
    service = ConfigImportService(session, settings)

    await service.import_config_from_yaml(yaml_text=_PROFILE_YAML, mode="merge")

    assert RunInputStorage.delete.await_count == 0


@pytest.mark.asyncio
async def test_import_rejects_invalid_cron_without_touching_storage() -> None:
    settings = _settings()
    session = _session(profile=Profile(id="default", pde_image="img:1", env_vars={}))
    service = ConfigImportService(session, settings)
    bad_yaml = SCHEDULE_YAML.replace('"30 2 * * *"', '"*/10 * * * * *"')

    with pytest.raises(ValueError, match="minimum interval"):
        await service.import_config_from_yaml(yaml_text=bad_yaml, mode="merge")

    assert RunInputStorage.store.await_count == 0


@pytest.mark.asyncio
async def test_imported_schedule_id_is_preserved() -> None:
    settings = _settings()
    schedule_id = UUID("6d2f8a41-0b7c-4e19-9c3a-5a1d7e2b4f06")
    yaml_text = SCHEDULE_YAML.replace("kind: ScheduledRun", f"kind: ScheduledRun\nid: {schedule_id}")
    session = _session(profile=Profile(id="default", pde_image="img:1", env_vars={}))
    service = ConfigImportService(session, settings)

    await service.import_config_from_yaml(yaml_text=yaml_text, mode="merge")

    schedules = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], ScheduledRun)]
    assert schedules[0].id == schedule_id


def test_masked_secure_round_trip_is_reused_from_the_run_helpers() -> None:
    # import path reuses the same masking helper as runs, so files may carry [MASKED] placeholders
    assert InputCryptoUtils.mask_secure_vars("TOKEN=secret") == f"TOKEN={MASKED_VALUE}"
