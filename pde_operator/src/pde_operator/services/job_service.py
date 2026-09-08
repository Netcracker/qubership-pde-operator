import logging
from enum import StrEnum
from uuid import UUID

from kubernetes import client, config
from kubernetes.client import ApiClient, BatchV1Api, CoreV1Api
from kubernetes.client.exceptions import ApiException
from kubernetes.client.models import (
    V1ConfigMapVolumeSource,
    V1Container,
    V1EmptyDirVolumeSource,
    V1EnvVar,
    V1Job,
    V1JobSpec,
    V1ObjectMeta,
    V1PodSpec,
    V1PodTemplateSpec,
    V1SecretVolumeSource,
    V1Volume,
    V1VolumeMount,
)
from kubernetes.stream import stream

from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import Run
from pde_operator.utils.auth_utils import AuthUtils
from pde_operator.utils.env_utils import EnvUtils
from pde_operator.utils.finish_utils import FinishUtils
from pde_operator.utils.job_runtime_utils import JobRuntimeUtils
from pde_operator.utils.resource_utils import ResourceUtils

logger = logging.getLogger(__name__)


class JobPhase(StrEnum):
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    MISSING = "missing"


class JobService:
    """Creates Kubernetes Jobs that run PDE"""

    def __init__(
            self,
            settings: Settings,
            batch_api: BatchV1Api | None = None,
            core_api: CoreV1Api | None = None,
    ) -> None:
        self._settings = settings
        self._batch_api = batch_api
        self._core_api = core_api
        self._api_client: ApiClient | None = None

    def _ensure_kube_client(self) -> ApiClient:
        if self._api_client is not None:
            return self._api_client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self._api_client = ApiClient()
        return self._api_client

    def _get_batch_api(self) -> BatchV1Api:
        if self._batch_api is not None:
            return self._batch_api
        return client.BatchV1Api(self._ensure_kube_client())

    def _get_core_api(self) -> CoreV1Api:
        if self._core_api is not None:
            return self._core_api
        return client.CoreV1Api(self._ensure_kube_client())

    def create_run_job(self, run: Run, profile: Profile) -> str:
        job_name = self._job_name(run.id)
        job = self._build_job(run, profile, job_name)
        try:
            self._get_batch_api().create_namespaced_job(namespace=self._settings.k8s_namespace, body=job)
        except Exception as exc:
            raise JobCreationError(f"Failed to create Job '{job_name}': {exc}") from exc
        return job_name

    def get_job_phase(self, job_name: str) -> JobPhase:
        try:
            job = self._get_batch_api().read_namespaced_job(name=job_name, namespace=self._settings.k8s_namespace)
        except ApiException as exc:
            if exc.status == 404:
                return JobPhase.MISSING
            raise

        status = job.status
        if status is None:
            return JobPhase.ACTIVE
        if (status.succeeded or 0) >= 1:
            return JobPhase.SUCCEEDED
        if (status.failed or 0) >= 1:
            return JobPhase.FAILED
        return JobPhase.ACTIVE

    def delete_run_job(self, job_name: str) -> None:
        try:
            self._get_batch_api().delete_namespaced_job(
                name=job_name,
                namespace=self._settings.k8s_namespace,
                propagation_policy="Background",
            )
        except ApiException as exc:
            if exc.status == 404:
                return
            raise

    def find_job_pod(self, job_name: str) -> str | None:
        """Return a running (or pending) pod name for the Job, if any."""
        pod = self._find_job_pod_object(job_name)
        return pod.metadata.name if pod is not None and pod.metadata is not None else None

    def get_pod_diagnostic(self, job_name: str) -> str | None:
        pod = self._find_job_pod_object(job_name)
        if pod is None:
            return None
        return FinishUtils.summarize_pod_diagnostic(pod)

    def _find_job_pod_object(self, job_name: str):
        pods = self._get_core_api().list_namespaced_pod(
            namespace=self._settings.k8s_namespace,
            label_selector=f"job-name={job_name}",
        )
        if not pods.items:
            return None
        for pod in pods.items:
            phase = (pod.status.phase if pod.status else None) or ""
            if phase in {"Running", "Pending"}:
                return pod
        return pods.items[0]

    def signal_pod_sigint(self, pod_name: str) -> None:
        """Send SIGINT to PID 1 (entrypoint wrapper) in the PDE container."""
        try:
            stream(
                self._get_core_api().connect_get_namespaced_pod_exec,
                pod_name,
                self._settings.k8s_namespace,
                command=["/bin/sh", "-c", "kill -INT 1"],
                container="pde",
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )
        except ApiException as exc:
            raise JobSignalError(f"Failed to signal pod '{pod_name}': {exc}") from exc
        except Exception as exc:
            raise JobSignalError(f"Failed to signal pod '{pod_name}': {exc}") from exc

    def signal_run_job_sigint(self, job_name: str) -> str | None:
        """Find Job pod and SIGINT PID 1. Returns pod name, or None if no pod yet."""
        pod_name = self.find_job_pod(job_name)
        if pod_name is None:
            logger.warning("No pod found for Job '%s' when signalling cancel", job_name)
            return None
        self.signal_pod_sigint(pod_name)
        logger.info("Sent SIGINT to pod '%s' (Job '%s')", pod_name, job_name)
        return pod_name

    def _build_job(self, run: Run, profile: Profile, job_name: str) -> V1Job:
        run_id = str(run.id)

        job_runtime_name = self._settings.job_runtime_configmap_name
        secret_name = self._settings.external_secrets_name
        volumes = [
            V1Volume(name="workspace", empty_dir=V1EmptyDirVolumeSource()),
            V1Volume(name="external-secrets", secret=V1SecretVolumeSource(secret_name=secret_name, optional=True)),
            V1Volume(name="job-runtime", config_map=V1ConfigMapVolumeSource(name=job_runtime_name)),
        ]
        volume_mounts = [
            V1VolumeMount(name="workspace", mount_path=JobRuntimeUtils.WORKSPACE_DIR),
            V1VolumeMount(name="external-secrets", mount_path=self._settings.external_secrets_mount_path, read_only=True),
            V1VolumeMount(name="job-runtime", mount_path=self._settings.job_runtime_mount_path, read_only=True),
        ]

        container = V1Container(
            name="pde",
            image=run.pde_image,
            image_pull_policy="Always",
            command=self._build_container_command(run),
            env=self._build_env(run, profile),
            volume_mounts=volume_mounts,
            working_dir=JobRuntimeUtils.WORKSPACE_DIR,
            resources=ResourceUtils.to_v1(ResourceUtils.merge(self._settings.k8s_job_resources, profile.resources)),
        )

        pod_spec = V1PodSpec(
            restart_policy="Never",
            termination_grace_period_seconds=int(self._settings.cancel_grace_seconds),
            containers=[container],
            volumes=volumes,
        )

        return V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=V1ObjectMeta(
                name=job_name,
                namespace=self._settings.k8s_namespace,
                labels={
                    "app.kubernetes.io/part-of": "pde-operator",
                    "app.kubernetes.io/name": "pde-run",
                    "pde.run/id": run_id,
                    "pde.run/profile": run.profile_id,
                },
            ),
            spec=V1JobSpec(
                backoff_limit=0,
                ttl_seconds_after_finished=int(self._settings.k8s_job_ttl_seconds),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(
                        labels={
                            "app.kubernetes.io/part-of": "pde-operator",
                            "pde.run/id": run_id,
                        }
                    ),
                    spec=pod_spec,
                ),
            ),
        )

    def _build_container_command(self, run: Run) -> list[str]:
        return JobRuntimeUtils.build_container_command(mount_path=self._settings.job_runtime_mount_path, run=run)

    def _build_env(self, run: Run, profile: Profile) -> list[V1EnvVar]:
        merged = EnvUtils.merge_env_vars(
            EnvUtils.operator_default_env(
                self._settings,
                run_id=run.id,
                execution_url=self._execution_url(run.id),
            ),
            profile.env_vars,
            run.env_vars,
        )
        merged["PDE_OPERATOR_INPUT_URL"] = self._input_url(run.id)
        merged["PDE_OPERATOR_ARTIFACTS_URL"] = self._artifacts_url(run.id)
        merged["PDE_OPERATOR_EXTERNAL_SECRETS_MOUNT_PATH"] = self._settings.external_secrets_mount_path
        if run.retry_of_run_id is not None:
            merged["PDE_OPERATOR_PARENT_STATE_URL"] = self._parent_state_url(run.retry_of_run_id)
        merged["PDE_OPERATOR_TOKEN"] = AuthUtils.mint_run_token(
            signing_key=self._settings.job_token_signing_key,
            run_id=run.id,
            parent_run_id=run.retry_of_run_id,
            ttl_seconds=self._settings.job_token_ttl_seconds,
        )
        return [V1EnvVar(name=key, value=value) for key, value in sorted(merged.items())]

    def _execution_url(self, run_id: UUID) -> str:
        base = self._settings.operator_base_url.rstrip("/")
        prefix = self._settings.api_prefix.rstrip("/")
        return f"{base}{prefix}/runs/{run_id}"

    def _artifacts_url(self, run_id: UUID) -> str:
        base = self._settings.operator_base_url.rstrip("/")
        prefix = self._settings.api_prefix.rstrip("/")
        return f"{base}{prefix}/runs/{run_id}/artifacts"

    def _input_url(self, run_id: UUID) -> str:
        base = self._settings.operator_base_url.rstrip("/")
        prefix = self._settings.api_prefix.rstrip("/")
        return f"{base}{prefix}/runs/{run_id}/input"

    def _parent_state_url(self, parent_run_id: UUID) -> str:
        base = self._settings.operator_base_url.rstrip("/")
        prefix = self._settings.api_prefix.rstrip("/")
        return f"{base}{prefix}/runs/{parent_run_id}/artifacts/state"

    @staticmethod
    def _job_name(run_id: UUID) -> str:
        return f"pde-run-{run_id}"


class JobCreationError(RuntimeError):
    pass


class JobSignalError(RuntimeError):
    pass
