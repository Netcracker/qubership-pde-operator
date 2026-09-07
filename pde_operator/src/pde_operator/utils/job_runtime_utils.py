"""Job runtime helpers for PDE Kubernetes Jobs."""

from __future__ import annotations

from pde_operator.db.models.run import Run


class JobRuntimeUtils:
    WORKSPACE_DIR = "/workspace"
    ENTRYPOINT_FILENAME = "job-entrypoint.py"

    @staticmethod
    def entrypoint_path(mount_path: str) -> str:
        return f"{mount_path.rstrip('/')}/{JobRuntimeUtils.ENTRYPOINT_FILENAME}"

    @staticmethod
    def build_container_command(*, mount_path: str, run: Run) -> list[str]:
        subcommand = "retry" if run.retry_of_run_id is not None else "run"
        return ["python", JobRuntimeUtils.entrypoint_path(mount_path), subcommand]
