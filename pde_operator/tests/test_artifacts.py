from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from pde_operator.config import Settings
from pde_operator.db.models.run import Run, RunStatus
from pde_operator.services.artifacts_service import ArtifactsService
from pde_operator.services.run_service import RunNotFoundError, RunService
from pde_operator.utils.artifact_utils import ArtifactKind, ArtifactNotFoundError, ArtifactUtils
from pathlib import Path

CHART_ENTRYPOINT = Path(__file__).resolve().parents[1] / "charts" / "pde-operator" / "files" / "job-entrypoint.py"


def _settings(**overrides) -> Settings:
    data = {
        "k8s_job_creation_enabled": False,
        "minio_enabled": True,
        "minio_endpoint": "http://localhost:9000",
        "minio_access_key": "pde",
        "minio_secret_key": "pdepdepde",
        "minio_bucket": "pde-artifacts",
    }
    data.update(overrides)
    return Settings(**data)


def _run(**overrides) -> Run:
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "profile_id": "default",
        "status": RunStatus.IN_PROGRESS,
        "pde_image": "ghcr.io/example/pde:1",
        "pipeline_data": "https://example.com/pipeline.yaml",
        "created_at": now,
        "started_at": now,
    }
    data.update(overrides)
    return Run(**data)


def test_artifact_keys() -> None:
    service = ArtifactsService(_settings())
    run_id = uuid4()
    for kind in ArtifactKind:
        assert service._key(run_id, kind) == f"{run_id}/{ArtifactUtils.filename(kind)}"


def test_put_bytes_uses_bucket() -> None:
    s3 = MagicMock()
    service = ArtifactsService(_settings(), s3_client=s3)
    service._put_bytes("rid/pipeline_dir.zip", b"zip", "application/zip")
    s3.put_object.assert_called_once_with(
        Bucket="pde-artifacts",
        Key="rid/pipeline_dir.zip",
        Body=b"zip",
        ContentType="application/zip",
    )


def test_get_object_not_found() -> None:
    s3 = MagicMock()
    s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
        "GetObject",
    )
    service = ArtifactsService(_settings(), s3_client=s3)
    with pytest.raises(ArtifactNotFoundError):
        service._get_object("rid/x_debug.zip")


def test_put_run_input_uses_contract_key() -> None:
    s3 = MagicMock()
    service = ArtifactsService(_settings(), s3_client=s3)
    run_id = uuid4()
    key = service.put_run_input(run_id, b"cipher")
    assert key == f"{run_id}/input.json"
    s3.put_object.assert_called_once()
    assert s3.put_object.call_args.kwargs["Key"] == key


@pytest.mark.asyncio
async def test_upload_artifacts_sets_state_location() -> None:
    run = _run()
    session = AsyncMock()
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    artifacts = MagicMock()
    artifacts.put_artifact.side_effect = lambda run_id, kind, data: f"{run_id}/{ArtifactUtils.filename(kind)}"

    service = RunService(session, _settings(), artifacts_service=artifacts)
    result = await service.upload_artifacts(
        run.id,
        state=b"ZIP",
        log=b"LOG",
        x_debug=b"XDEBUGZIP",
        report=b'{"status":"SUCCESS"}',
    )

    assert result.state_location == f"{run.id}/pipeline_dir.zip"
    assert result.report_updated_at is not None
    assert result.log_updated_at is not None
    assert artifacts.put_artifact.call_count == 4
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upload_artifacts_log_only() -> None:
    run = _run()
    session = AsyncMock()
    session.get = AsyncMock(return_value=run)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    artifacts = MagicMock()
    artifacts.put_artifact.side_effect = lambda run_id, kind, data: f"{run_id}/{ArtifactUtils.filename(kind)}"

    service = RunService(session, _settings(), artifacts_service=artifacts)
    result = await service.upload_artifacts(run.id, log=b"console output")

    assert result.state_location is None
    artifacts.put_artifact.assert_called_once()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upload_artifacts_not_found() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    service = RunService(session, _settings(), artifacts_service=MagicMock())
    with pytest.raises(RunNotFoundError):
        await service.upload_artifacts(uuid4(), state=b"ZIP")


def test_upload_artifacts_is_best_effort() -> None:
    text = CHART_ENTRYPOINT.read_text(encoding="utf-8")
    assert "state zip missing:" in text
    assert "no artifacts to upload" in text
    assert '("log", CONSOLE_LOG)' in text
    assert "ARTIFACT_CANDIDATES" in text


def test_entrypoint_fetches_run_input() -> None:
    text = CHART_ENTRYPOINT.read_text(encoding="utf-8")
    assert "PDE_OPERATOR_INPUT_URL" in text
    assert "fetch_run_input()" in text
    assert "PDE_OPERATOR_RUN_PIPELINE_DATA" not in text


def test_finish_stages_x_debug_before_state_archive() -> None:
    text = CHART_ENTRYPOINT.read_text(encoding="utf-8")
    assert "stage_x_debug()" in text
    assert text.index("stage_x_debug()") < text.index("archive_once()")
    assert text.index("archive_once()") < text.index("zip_x_debug()")


def test_report_artifact_kind_filename() -> None:
    assert ArtifactUtils.filename(ArtifactKind.REPORT) == "pipeline_report.json"
    assert ArtifactUtils.content_type(ArtifactKind.REPORT) == "application/json"
    assert ArtifactUtils.parse_artifact_kind("report") is ArtifactKind.REPORT
