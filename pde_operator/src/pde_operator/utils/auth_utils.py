"""API token helpers: admin Bearer + per-Job HS256 JWTs (PyJWT)."""

from __future__ import annotations

import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import jwt

from pde_operator.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    role: Literal["admin", "run"]
    run_id: UUID | None = None
    parent_run_id: UUID | None = None


class AuthUtils:
    @staticmethod
    def ensure_auth_secrets(settings: Settings) -> None:
        """Fill missing auth secrets with ephemeral values and warn (set explicitly for stable deploys)."""
        if not settings.api_admin_token.strip():
            settings.api_admin_token = secrets.token_urlsafe(32)
            logger.warning(f"PDE_OPERATOR_API_ADMIN_TOKEN was not set; generated ephemeral admin token: {settings.api_admin_token}")
        if not settings.job_token_signing_key.strip():
            settings.job_token_signing_key = secrets.token_urlsafe(48)
            logger.warning(f"PDE_OPERATOR_JOB_TOKEN_SIGNING_KEY was not set; generated ephemeral signing key: {settings.job_token_signing_key}")

    @staticmethod
    def tokens_equal(provided: str, expected: str) -> bool:
        if len(provided) != len(expected):
            return False
        return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))

    @staticmethod
    def mint_run_token(
            *,
            signing_key: str,
            run_id: UUID,
            parent_run_id: UUID | None = None,
            ttl_seconds: int = 172800,
    ) -> str:
        now = int(time.time())
        payload: dict[str, object] = {
            "role": "run",
            "run_id": str(run_id),
            "iat": now,
            "exp": now + max(ttl_seconds, 60),
        }
        if parent_run_id is not None:
            payload["parent_run_id"] = str(parent_run_id)
        return jwt.encode(payload, signing_key, algorithm="HS256")

    @staticmethod
    def verify_run_token(token: str, signing_key: str) -> AuthPrincipal | None:
        try:
            payload = jwt.decode(token, signing_key, algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
        if payload.get("role") != "run":
            return None
        try:
            run_id = UUID(str(payload["run_id"]))
        except (KeyError, ValueError, TypeError):
            return None
        parent_run_id = None
        raw_parent = payload.get("parent_run_id")
        if raw_parent:
            try:
                parent_run_id = UUID(str(raw_parent))
            except (ValueError, TypeError):
                return None
        return AuthPrincipal(role="run", run_id=run_id, parent_run_id=parent_run_id)

    @staticmethod
    def resolve_principal(*, provided: str | None, api_admin_token: str,
                          job_token_signing_key: str) -> AuthPrincipal | None:
        if not provided:
            return None
        if AuthUtils.tokens_equal(provided, api_admin_token):
            return AuthPrincipal(role="admin")
        return AuthUtils.verify_run_token(provided, job_token_signing_key)

    @staticmethod
    def run_token_allows(principal: AuthPrincipal, *, method: str, path: str, api_prefix: str) -> bool:
        """Worker tokens: POST own deliveries/artifacts; GET parent state only."""
        if principal.role != "run" or principal.run_id is None:
            return False
        prefix = api_prefix.rstrip("/")
        runs_root = f"{prefix}/runs/"
        if not path.startswith(runs_root):
            return False
        rest = path[len(runs_root):]
        run_id_str, _, tail = rest.partition("/")
        try:
            path_run_id = UUID(run_id_str)
        except ValueError:
            return False

        method = method.upper()
        if method == "POST" and path_run_id == principal.run_id and tail.startswith("deliveries/"):
            delivery_kind = tail.removeprefix("deliveries/").split("/", 1)[0]
            return delivery_kind in {"status", "report", "log"}
        if method == "POST" and path_run_id == principal.run_id and tail == "artifacts":
            return True
        if method == "GET" and path_run_id == principal.run_id and tail == "input":
            return True
        if method == "GET" and principal.parent_run_id is not None and path_run_id == principal.parent_run_id and tail == "artifacts/state":
            return True
        return False
