import json
from uuid import uuid4

from pde_operator.config import Settings
from pde_operator.utils.env_utils import EnvUtils


def test_merge_env_vars_later_layers_override() -> None:
    merged = EnvUtils.merge_env_vars(
        {"A": "1", "B": "2"},
        {"B": "3", "C": {"nested": True}},
    )
    assert merged["A"] == "1"
    assert merged["B"] == "3"
    assert merged["C"] == json.dumps({"nested": True})


def test_operator_default_env_injects_remote_deliveries() -> None:
    run_id = uuid4()
    settings = Settings(
        operator_base_url="http://operator",
        api_prefix="/api/v1",
    )
    env = EnvUtils.operator_default_env(
        settings,
        run_id=run_id,
        execution_url="http://example/runs/1",
    )
    assert env["PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL"] == "http://example/runs/1"
    deliveries = json.loads(env["PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES"])
    assert len(deliveries) == 3
    assert deliveries[0]["payload"] == "status"
    assert deliveries[1]["payload"] == "report"
    assert deliveries[2]["payload"] == "log"
    assert deliveries[0]["endpoints"][0]["endpoint"] == f"http://operator/api/v1/runs/{run_id}/deliveries/status"
    assert deliveries[1]["endpoints"][0]["use_compression"] is True
    assert deliveries[0]["endpoints"][0]["use_compression"] is False


def test_execution_url_overridable_by_higher_layer() -> None:
    merged = EnvUtils.merge_env_vars(
        {"PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL": "http://operator/runs/1"},
        {"PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL": "https://github.com/org/repo/actions/runs/1"},
    )
    assert merged["PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL"] == "https://github.com/org/repo/actions/runs/1"
