from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.config import Settings
from pde_operator.declarative_templates.services.options_service import DeclarativeOptionsService
from pde_operator.declarative_templates.services.template_store import DeclarativeTemplateStore
from pde_operator.services.config_import_service import ConfigImportService
from pde_operator.services.profile_service import ProfileService
from pde_operator.services.retention_service import RetentionService
from pde_operator.services.run_service import RunService
from pde_operator.services.run_template_service import RunTemplateService
from pde_operator.utils.auth_utils import AuthUtils

_bearer_scheme = HTTPBearer(auto_error=False)


class DependUtils:
    """FastAPI dependency helpers."""

    @staticmethod
    async def require_api_token(
            request: Request,
            credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    ) -> None:
        settings: Settings = request.app.state.settings
        provided = credentials.credentials if credentials is not None else None
        principal = AuthUtils.resolve_principal(
            provided=provided,
            api_admin_token=settings.api_admin_token,
            job_token_signing_key=settings.job_token_signing_key,
        )
        if principal is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing Bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if principal.role == "admin":
            return
        if AuthUtils.run_token_allows(
                principal,
                method=request.method,
                path=request.url.path,
                api_prefix=settings.api_prefix,
        ):
            return
        raise HTTPException(status_code=403, detail="Token is not allowed for this operation")

    @staticmethod
    async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield session

    @staticmethod
    async def get_run_service(request: Request) -> AsyncIterator[RunService]:
        session_factory = request.app.state.session_factory
        settings: Settings = request.app.state.settings
        async with session_factory() as session:
            yield RunService(session, settings)

    @staticmethod
    async def get_profile_service(request: Request) -> AsyncIterator[ProfileService]:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield ProfileService(session)

    @staticmethod
    async def get_run_template_service(request: Request) -> AsyncIterator[RunTemplateService]:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield RunTemplateService(session)

    @staticmethod
    async def get_declarative_template_store(request: Request) -> AsyncIterator[DeclarativeTemplateStore]:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield DeclarativeTemplateStore(session)

    @staticmethod
    async def get_declarative_options_service(request: Request) -> AsyncIterator[DeclarativeOptionsService]:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield DeclarativeOptionsService(session)

    @staticmethod
    async def get_config_import_service(request: Request) -> AsyncIterator[ConfigImportService]:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield ConfigImportService(session)

    @staticmethod
    def get_retention_service(request: Request) -> RetentionService:
        return RetentionService(request.app.state.settings, request.app.state.session_factory)
