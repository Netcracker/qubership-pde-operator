from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pde_operator.schemas.job_resources import JobResources
from pde_operator.utils.resource_utils import ResourceUtils


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PDE_OPERATOR_")

    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    ui_enabled: bool = True
    api_admin_token: str = ""
    job_token_signing_key: str = ""
    job_token_ttl_seconds: int = 172800  # 48h
    input_encryption_key: str = ""

    database_url: str = "postgresql+asyncpg://pde:pde@localhost:5432/pde_operator"
    execution_url_base: str = "http://localhost:8000"  # URL for API responses
    operator_base_url: str = "http://host.minikube.internal:8000"  # URL pods use to reach the operator (k8s -> host)
    k8s_namespace: str = "pde-system"
    k8s_job_ttl_seconds: int = 60
    k8s_job_creation_enabled: bool = True  # When False, POST /runs only persists to DB, no real jobs start
    k8s_job_resources: JobResources = Field(default_factory=JobResources.lab_defaults)  # Default Job container resources

    queue_enabled: bool = True
    queue_poll_seconds: float = 5.0
    max_concurrent_runs: int = 8  # limit works only when queue is enabled

    reconciler_enabled: bool = True
    reconciler_interval_seconds: float = 30.0  # how often we check for stuck pods
    reconciler_stuck_timeout_seconds: int = 300  # fail stuck runs with no progress (5 min)
    cancel_grace_seconds: int = 60  # wait after SIGINT before hard-stopping the Job

    pde_default_image: str = "ghcr.io/netcracker/qubership-pipelines-declarative-executor:v2.2.1"
    pde_delivery_status_interval: int = 5
    pde_delivery_report_interval: int = 15
    pde_delivery_log_interval: int = 15

    retention_enabled: bool = True
    retention_days: int = 30
    retention_cron: str = "0 0 * * *"  # daily at 00:00

    minio_enabled: bool = True
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "pde"
    minio_secret_key: str = "pdepdepde"
    minio_bucket: str = "pde-artifacts"
    minio_region: str = "us-east-1"

    external_secrets_name: str = "pde-operator-external-secrets"
    external_secrets_mount_path: str = "/var/run/secrets/pde-external"

    job_runtime_configmap_name: str = "pde-operator-job-runtime"
    job_runtime_mount_path: str = "/opt/pde-operator/job-runtime"

    @model_validator(mode="after")
    def _fill_job_resources_from_lab_defaults(self) -> Self:
        self.k8s_job_resources = ResourceUtils.merge(JobResources.lab_defaults(), self.k8s_job_resources)
        return self
