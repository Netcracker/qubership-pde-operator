from __future__ import annotations

import logging
from copy import deepcopy
from time import perf_counter

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint
from uvicorn.config import LOGGING_CONFIG


class LoggingUtils:
    @staticmethod
    def uvicorn_log_config(level: str) -> dict:
        config = deepcopy(LOGGING_CONFIG)
        config["loggers"]["pde_operator"] = {
            "handlers": ["default"],
            "level": level.upper(),
            "propagate": False,
        }
        config["loggers"]["uvicorn.access"]["level"] = "WARNING"
        return config

    @staticmethod
    def should_emit_access_log(method: str, path: str, status_code: int, *, api_prefix: str = "/api/v1") -> bool:
        """Return False for probe/poll noise; True for mutations, errors, and uncommon reads."""
        method = method.upper()
        path_only = path.split("?", 1)[0]
        prefix = api_prefix.rstrip("/") or "/api/v1"
        runs_root = f"{prefix}/runs"

        if method == "GET" and status_code == 404 and LoggingUtils._is_run_artifact_path(path_only, runs_root):
            return False

        if status_code >= 400:
            return True

        if method == "GET":
            if path_only.startswith("/health") or path_only.startswith("/ready") or path_only.startswith("/metrics") or path_only.startswith("/ui"):
                return False

            if path_only.startswith(f"{prefix}/mcp"):
                return False

            if path_only.startswith(runs_root) or path_only.startswith(f"{prefix}/profiles") or path_only.startswith(f"{prefix}/run-templates"):
                return False

        if method == "POST" and LoggingUtils._is_run_delivery_path(path_only, runs_root):
            return False

        if method == "POST" and LoggingUtils._is_declarative_options_path(path_only, prefix):
            return False

        return True

    @staticmethod
    def _is_run_artifact_path(path_only: str, runs_root: str) -> bool:
        if not path_only.startswith(f"{runs_root}/"):
            return False
        rest = path_only[len(runs_root) + 1 :].rstrip("/")
        parts = rest.split("/")
        return len(parts) == 3 and parts[1] == "artifacts"

    @staticmethod
    def _is_run_delivery_path(path_only: str, runs_root: str) -> bool:
        if not path_only.startswith(f"{runs_root}/"):
            return False
        rest = path_only[len(runs_root) + 1 :].rstrip("/")
        parts = rest.split("/")
        return len(parts) == 3 and parts[1] == "deliveries" and parts[2] in {"status", "report", "log"}

    @staticmethod
    def _is_declarative_options_path(path_only: str, api_prefix: str) -> bool:
        root = f"{api_prefix}/run-templates/"
        if not path_only.startswith(root):
            return False
        parts = path_only[len(root) :].rstrip("/").split("/")
        return len(parts) == 3 and parts[1] == "declarative" and parts[2] == "options"

    @staticmethod
    def access_logger() -> logging.Logger:
        return logging.getLogger("pde_operator.access")

    @staticmethod
    def install_access_log_middleware(app: FastAPI, *, api_prefix: str = "/api/v1") -> None:
        """Register filtered HTTP access logging (uvicorn access_log should stay off)."""

        @app.middleware("http")
        async def filtered_access_log(request: Request, call_next: RequestResponseEndpoint) -> Response:
            started = perf_counter()
            response = await call_next(request)
            path = request.url.path
            if request.url.query:
                path = f"{path}?{request.url.query}"
            if LoggingUtils.should_emit_access_log(request.method, path, response.status_code, api_prefix=api_prefix):
                client = request.client.host if request.client else "-"
                http_version = request.scope.get("http_version", "1.1")
                elapsed_ms = (perf_counter() - started) * 1000
                LoggingUtils.access_logger().info(
                    '%s - "%s %s HTTP/%s" %s %.1fms',
                    client,
                    request.method,
                    path,
                    http_version,
                    response.status_code,
                    elapsed_ms,
                )
            return response
