"""Environment variable merge helpers for PDE Jobs."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pde_operator.config import Settings


class EnvUtils:
    @staticmethod
    def env_value_to_str(value: object) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    @staticmethod
    def merge_env_vars(*layers: dict[str, Any] | None) -> dict[str, str]:
        merged: dict[str, str] = {}
        for layer in layers:
            if not layer:
                continue
            for key, value in layer.items():
                if value is None:
                    continue
                merged[str(key)] = EnvUtils.env_value_to_str(value)
        return merged

    @staticmethod
    def operator_default_env(settings: Settings, *, run_id: UUID, execution_url: str) -> dict[str, str]:
        return {
            "PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES": json.dumps(EnvUtils.remote_deliveries(settings, run_id)),
            "PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL": execution_url,
        }

    @staticmethod
    def remote_deliveries(settings: Settings, run_id: UUID) -> list[dict[str, object]]:
        base = settings.operator_base_url.rstrip("/") + settings.api_prefix.rstrip("/")
        return [
            {
                "payload": "status",
                "mode": "periodic",
                "interval_seconds": settings.pde_delivery_status_interval,
                "endpoints": [
                    EnvUtils._http_endpoint(
                        base_url=base,
                        run_id=run_id,
                        suffix="status",
                        content_type="application/json",
                        use_compression=False,
                    ),
                ],
            },
            {
                "payload": "report",
                "mode": "periodic",
                "interval_seconds": settings.pde_delivery_report_interval,
                "endpoints": [
                    EnvUtils._http_endpoint(
                        base_url=base,
                        run_id=run_id,
                        suffix="report",
                        content_type="application/json",
                        use_compression=True,
                    ),
                ],
            },
            {
                "payload": "log",
                "mode": "periodic",
                "interval_seconds": settings.pde_delivery_log_interval,
                "endpoints": [
                    EnvUtils._http_endpoint(
                        base_url=base,
                        run_id=run_id,
                        suffix="log",
                        content_type="text/plain",
                        use_compression=True,
                    ),
                ],
            },
        ]

    @staticmethod
    def parse_key_value_lines(text: str | None) -> dict[str, str]:
        if not text or not text.strip():
            return {}
        result: dict[str, str] = {}
        for raw_line in text.replace("\r\n", "\n").split("\n"):
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key:
                result[key] = value
        return result

    @staticmethod
    def format_key_value_lines(env_vars: dict[str, Any] | None) -> str:
        if not env_vars:
            return ""
        return "\n".join(f"{key}={EnvUtils.env_value_to_str(value)}" for key, value in env_vars.items())

    @staticmethod
    def _http_endpoint(
        *, base_url: str, run_id: UUID, suffix: str, content_type: str, use_compression: bool,
    ) -> dict[str, object]:
        return {
            "type": "http",
            "endpoint": f"{base_url}/runs/{run_id}/deliveries/{suffix}",
            "headers": {"Authorization": "Bearer {token}", "Content-Type": content_type},
            "token_env_var": "PDE_OPERATOR_TOKEN",
            "use_compression": use_compression,
        }
