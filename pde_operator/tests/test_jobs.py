import json

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import Run
from pde_operator.schemas.job_resources import JobResources, ResourceDict
from pde_operator.services.job_service import JobService
from pde_operator.utils.resource_utils import ResourceUtils


def _profile(**overrides) -> Profile:
    data = {
        "id": "default",
        "pde_image": "ghcr.io/example/pde:1",
        "env_vars": {"PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH": "/custom"},
        "resources": {},
    }
    data.update(overrides)
    return Profile(**data)


def _run(**overrides) -> Run:
    data = {
        "profile_id": "default",
        "pipeline_data": "https://example.com/pipeline.yaml",
        "pde_image": "ghcr.io/example/pde:1",
        "env_vars": {"MANUAL": "override"},
    }
    data.update(overrides)
    return Run(**data)


def test_build_env_sets_default_execution_url() -> None:
    settings = Settings(
        operator_base_url="http://operator",
        api_prefix="/api/v1",
        api_admin_token="admin",
        job_token_signing_key="test-job-token-signing-key-32b!!",
    )
    service = JobService(settings)
    run = _run()
    env = {item.name: item.value for item in service._build_env(run, _profile())}
    assert env["PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL"] == f"http://operator/api/v1/runs/{run.id}"
    assert env["PDE_OPERATOR_TOKEN"]
    deliveries = json.loads(env["PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES"])
    assert len(deliveries) == 3


def test_build_env_execution_url_overridable_by_run_env_vars() -> None:
    settings = Settings(
        operator_base_url="http://operator",
        api_prefix="/api/v1",
        api_admin_token="admin",
        job_token_signing_key="test-job-token-signing-key-32b!!",
    )
    service = JobService(settings)
    run = _run(
        env_vars={
            "MANUAL": "override",
            "PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL": "https://github.com/org/repo/actions/runs/1",
        },
    )
    env = {item.name: item.value for item in service._build_env(run, _profile())}
    assert env["PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL"] == "https://github.com/org/repo/actions/runs/1"
    assert env["MANUAL"] == "override"


def test_resource_utils_partial_merge() -> None:
    base = JobResources.lab_defaults()
    merged = ResourceUtils.merge(base, {"limits": {"memory": "1Gi"}})
    assert merged.requests.cpu == "100m"
    assert merged.requests.memory == "128Mi"
    assert merged.limits.cpu == "500m"
    assert merged.limits.memory == "1Gi"
    assert ResourceUtils.merge(base, {}) == base


def test_build_job_applies_merged_resources() -> None:
    settings = Settings(
        operator_base_url="http://operator",
        api_prefix="/api/v1",
        api_admin_token="admin",
        job_token_signing_key="test-job-token-signing-key-32b!!",
        k8s_job_resources=JobResources(
            requests=ResourceDict(cpu="100m", memory="128Mi"),
            limits=ResourceDict(cpu="500m", memory="512Mi"),
        ),
    )
    service = JobService(settings)
    run = _run()
    profile = _profile(resources={"requests": {"memory": "512Mi"}})
    job = service._build_job(run, profile, "pde-run-test")
    resources = job.spec.template.spec.containers[0].resources
    assert resources.requests["cpu"] == "100m"
    assert resources.requests["memory"] == "512Mi"
    assert resources.limits["cpu"] == "500m"
    assert resources.limits["memory"] == "512Mi"


def test_settings_job_resources_partial_env_merges_lab_defaults(monkeypatch) -> None:
    monkeypatch.setenv("PDE_OPERATOR_K8S_JOB_RESOURCES", '{"requests":{"memory":"1Gi"}}')
    settings = Settings()
    assert settings.k8s_job_resources.requests.memory == "1Gi"
    assert settings.k8s_job_resources.requests.cpu == "100m"
    assert settings.k8s_job_resources.limits.memory == "512Mi"
    assert settings.k8s_job_resources.limits.cpu == "500m"


def test_build_job_mounts_external_secrets_and_job_runtime() -> None:
    settings = Settings(
        operator_base_url="http://operator",
        api_prefix="/api/v1",
        api_admin_token="admin",
        job_token_signing_key="test-job-token-signing-key-32b!!",
        external_secrets_name="pde-operator-external-secrets",
        external_secrets_mount_path="/var/run/secrets/pde-external",
        job_runtime_configmap_name="pde-operator-job-runtime",
        job_runtime_mount_path="/opt/pde-operator/job-runtime",
    )
    service = JobService(settings)
    run = _run()
    job = service._build_job(run, _profile(), "pde-run-test")
    pod_spec = job.spec.template.spec
    container = pod_spec.containers[0]

    secret_vols = [v for v in pod_spec.volumes if v.name == "external-secrets"]
    assert len(secret_vols) == 1
    assert secret_vols[0].secret.secret_name == "pde-operator-external-secrets"
    assert secret_vols[0].secret.optional is True

    runtime_vols = [v for v in pod_spec.volumes if v.name == "job-runtime"]
    assert len(runtime_vols) == 1
    assert runtime_vols[0].config_map.name == "pde-operator-job-runtime"

    mounts = {m.name: m for m in container.volume_mounts}
    assert mounts["external-secrets"].mount_path == "/var/run/secrets/pde-external"
    assert mounts["job-runtime"].mount_path == "/opt/pde-operator/job-runtime"

    assert container.command == [
        "python",
        "/opt/pde-operator/job-runtime/job-entrypoint.py",
        "run",
    ]

    env = {item.name: item.value for item in container.env}
    assert env["PDE_OPERATOR_INPUT_URL"] == f"http://operator/api/v1/runs/{run.id}/input"
    assert env["PDE_OPERATOR_EXTERNAL_SECRETS_MOUNT_PATH"] == "/var/run/secrets/pde-external"
    assert container.env_from in (None, [])
