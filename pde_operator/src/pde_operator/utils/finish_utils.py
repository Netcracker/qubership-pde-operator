import json


class OperatorFinishCodes:
    """Operator-assigned finish codes when the run ends outside normal PDE reporting."""

    PREFIX = "PDE-OPERATOR-"
    RUN_STUCK_TIMEOUT = "PDE-OPERATOR-JOB-STUCK-TIMEOUT"
    RUN_JOB_FAILED = "PDE-OPERATOR-JOB-FAILED"
    RUN_JOB_MISSING = "PDE-OPERATOR-JOB-MISSING"
    RUN_CANCELLED = "PDE-OPERATOR-RUN-CANCELLED"


class FinishUtils:
    @staticmethod
    def is_operator_finish_code(code: str | None) -> bool:
        return bool(code and code.startswith(OperatorFinishCodes.PREFIX))

    @staticmethod
    def extract_finish_code_from_report(data: bytes) -> str | None:
        try:
            document = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(document, dict):
            return None
        code = document.get("code")
        if not isinstance(code, str):
            return None
        trimmed = code.strip()
        return trimmed or None

    @staticmethod
    def apply_report_finish_code(run, data: bytes) -> None:
        if FinishUtils.is_operator_finish_code(run.finish_code):
            return
        code = FinishUtils.extract_finish_code_from_report(data)
        if code:
            run.finish_code = code

    @staticmethod
    def summarize_pod_diagnostic(pod: object) -> str | None:
        status = getattr(pod, "status", None)
        if status is None:
            return None

        parts: list[str] = []
        for container_status in getattr(status, "container_statuses", None) or []:
            name = getattr(container_status, "name", "container")
            state = getattr(container_status, "state", None)
            if state is None:
                continue
            waiting = getattr(state, "waiting", None)
            if waiting is not None:
                reason = getattr(waiting, "reason", None) or "Waiting"
                message = (getattr(waiting, "message", None) or "").strip()
                parts.append(f"{name}: {reason}" + (f" ({message})" if message else ""))
                continue
            terminated = getattr(state, "terminated", None)
            if terminated is not None:
                reason = getattr(terminated, "reason", None) or "Terminated"
                message = (getattr(terminated, "message", None) or "").strip()
                exit_code = getattr(terminated, "exit_code", None)
                detail = f"{name}: {reason}"
                if exit_code is not None:
                    detail += f" (exit {exit_code})"
                if message:
                    detail += f" ({message})"
                parts.append(detail)

        for condition in getattr(status, "conditions", None) or []:
            if getattr(condition, "status", None) == "True":
                continue
            condition_type = getattr(condition, "type", "Condition")
            reason = getattr(condition, "reason", None) or condition_type
            message = (getattr(condition, "message", None) or "").strip()
            parts.append(f"{condition_type}: {reason}" + (f" ({message})" if message else ""))

        if not parts:
            phase = getattr(status, "phase", None)
            if isinstance(phase, str) and phase.strip():
                return f"Pod phase: {phase.strip()}"
            return None
        return "; ".join(parts)

    @staticmethod
    def stuck_finish_message(diagnostic: str | None) -> str:
        base = "Run exceeded progress timeout; Kubernetes Job deleted."
        if diagnostic:
            return f"{base} {diagnostic}"
        return base
