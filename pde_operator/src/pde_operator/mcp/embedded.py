from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from pde_operator.config import Settings
from pde_operator.mcp.instructions import MCP_INSTRUCTIONS, MCP_SERVER_NAME
from pde_operator.mcp.resources_content import (
    LIFECYCLE_MARKDOWN,
    PIPELINE_INPUTS_MARKDOWN,
    RUN_TEMPLATES_MARKDOWN,
    URI_LIFECYCLE,
    URI_PIPELINE_INPUTS,
    URI_PROFILES,
    URI_RUN_TEMPLATES,
)
from pde_operator.schemas.profiles import ProfileListItem
from pde_operator.schemas.run_templates import CreateRunFromTemplateRequest, RunTemplateDetail, RunTemplateSummary
from pde_operator.schemas.runs import CreateRunRequest, CreateRunResponse, RetryRunRequest, RunDetail, RunSummary
from pde_operator.services.profile_service import ProfileNotFoundError, ProfileService
from pde_operator.services.run_service import (
    RunNotCancellableError,
    RunNotFoundError,
    RunNotRetriableError,
    RunService,
    RunStateNotAvailableError,
)
from pde_operator.services.run_template_service import RunTemplateKindError, RunTemplateNotFoundError, RunTemplateService
from pde_operator.utils.artifact_utils import ArtifactKind, ArtifactNotFoundError, ArtifactsDisabledError
from pde_operator.utils.auth_utils import AuthUtils


def _dumps(payload: object) -> str:
    return json.dumps(payload, indent=2, default=str)


def _error_message(exc: Exception) -> str:
    return str(exc) if str(exc) else exc.__class__.__name__


def _build_mcp(app: FastAPI, settings: Settings) -> FastMCP:
    mcp = FastMCP(MCP_SERVER_NAME, instructions=MCP_INSTRUCTIONS, streamable_http_path="/")

    @mcp.tool()
    async def pde_list_runs(
        q: Annotated[
            str | None,
            Field(description="Optional free-text substring search across status, profile_id, and name."),
        ] = None,
        status: Annotated[
            str | None,
            Field(description="Optional status filter: QUEUED, NOT_STARTED, IN_PROGRESS, SUCCESS, FAILED, CANCELLED."),
        ] = None,
        profile_id: Annotated[str | None, Field(description="Optional profile id filter (e.g. default).")] = None,
        created_from_template_id: Annotated[UUID | None, Field(description="Optional created_from_template_id filter (template UUID).")] = None,
        offset: Annotated[int, Field(description="Pagination offset (newest-first list).", ge=0)] = 0,
        limit: Annotated[int, Field(description="Page size (max useful ~100).", ge=1, le=100)] = 20,
    ) -> str:
        """List pipeline runs (newest first).

        Use to find runs by status/profile before get/cancel/retry. Returns items[], total, offset, limit.
        """
        session_factory = app.state.session_factory
        async with session_factory() as session:
            service = RunService(session, settings)
            runs, total = await service.list_runs(
                q=q,
                status=status,
                profile_id=profile_id,
                created_from_template_id=created_from_template_id,
                offset=offset,
                limit=limit,
            )
        items = [RunSummary.model_validate(run).model_dump(mode="json") for run in runs]
        return _dumps({"items": items, "total": total, "offset": offset, "limit": limit})

    @mcp.tool()
    async def pde_get_run(run_id: Annotated[str, Field(description="Run UUID from create/list/retry.")]) -> str:
        """Get full run detail including status, timings, pipeline_data, and progress_json when present.

        Prefer this after list, and while polling until a terminal status. Use artifact endpoints for full report/log.
        """
        session_factory = app.state.session_factory
        async with session_factory() as session:
            service = RunService(session, settings)
            run = await service.get_run(UUID(run_id))
        if run is None:
            raise ValueError(f"Run '{run_id}' not found")
        return _dumps(run.model_dump(mode="json"))

    @mcp.tool()
    async def pde_create_run(
        pipeline_data: Annotated[
            str,
            Field(description="PDE pipeline source(s), `;`-separated URLs/paths. See resource pde://pipeline-inputs."),
        ],
        pipeline_vars: Annotated[
            str | None,
            Field(description="Optional KEY=VALUE lines (newline-separated) passed to PDE as --pipeline_vars."),
        ] = None,
        pipeline_vars_secure: Annotated[
            str | None,
            Field(
                description=(
                    "Optional secure KEY=VALUE lines for PDE --pipeline_vars_secure (secrets). "
                    "Same format as pipeline_vars. Stored on the run but omitted from pde_get_run responses."
                ),
            ),
        ] = None,
        profile_id: Annotated[
            str,
            Field(description="Execution profile (image/env). Default profile is usually correct."),
        ] = "default",
        is_dry_run: Annotated[
            bool,
            Field(description="If true, ask PDE to dry-run when supported (safer for experiments)."),
        ] = False,
        log_level: Annotated[
            str,
            Field(description="PDE log level, e.g. INFO or DEBUG."),
        ] = "INFO",
        pde_image: Annotated[
            str | None,
            Field(description="Optional PDE container image override for this run only."),
        ] = None,
    ) -> str:
        """Queue a new PDE run. Returns id, status (usually QUEUED), execution_url, created_at.

        Optional pipeline_vars_secure for secrets (not echoed later by pde_get_run). After create, poll
        pde_get_run until SUCCESS/FAILED/CANCELLED. Do not create duplicates for the same intent while a
        run is still active unless the user asks.
        """
        session_factory = app.state.session_factory
        req = CreateRunRequest(
            pipeline_data=pipeline_data,
            pipeline_vars=pipeline_vars,
            pipeline_vars_secure=pipeline_vars_secure,
            profile_id=profile_id,
            is_dry_run=is_dry_run,
            log_level=log_level,
            pde_image=pde_image,
        )
        async with session_factory() as session:
            service = RunService(session, settings)
            try:
                run = await service.create_run(req)
            except ProfileNotFoundError as exc:
                raise ValueError(_error_message(exc)) from exc
        return _dumps(CreateRunResponse.model_validate(run).model_dump(mode="json"))

    @mcp.tool()
    async def pde_list_run_templates(
        q: Annotated[
            str | None,
            Field(description="Optional search across id, name, description, and tags (substring)."),
        ] = None,
        tag: Annotated[
            str | None,
            Field(description="Optional exact tag filter (e.g. deploy, nightly)."),
        ] = None,
        offset: Annotated[int, Field(description="Pagination offset.", ge=0)] = 0,
        limit: Annotated[int, Field(description="Page size.", ge=1, le=100)] = 20,
    ) -> str:
        """List run templates from the catalog (named/tagged create-run presets).

        Use when the user asks to start a pipeline by name/tags. Returns id, name, description,
        tags, profile_id (not full pipeline bodies). Then call pde_create_run_from_template.
        """
        session_factory = app.state.session_factory
        async with session_factory() as session:
            service = RunTemplateService(session)
            templates, total = await service.list_templates(q=q, tag=tag, offset=offset, limit=limit)
        items = [RunTemplateSummary.model_validate(t).model_dump(mode="json") for t in templates]
        return _dumps({"items": items, "total": total, "offset": offset, "limit": limit})

    @mcp.tool()
    async def pde_get_run_template(
        template_id: Annotated[str, Field(description="Run template UUID from list/catalog.")],
    ) -> str:
        """Get full run template detail including pipeline_data and pipeline_vars_secure.

        Prefer for inspection/overrides. Do not echo secure vars to the user unless asked.
        To start a run, prefer pde_create_run_from_template.
        """
        session_factory = app.state.session_factory
        async with session_factory() as session:
            template = await RunTemplateService(session).get_template(UUID(template_id))
        if template is None:
            raise ValueError(f"Run template '{template_id}' not found")
        return _dumps(RunTemplateDetail.model_validate(template).model_dump(mode="json"))

    @mcp.tool()
    async def pde_create_run_from_template(
        template_id: Annotated[str, Field(description="Catalog run template UUID to start from.")],
        profile_id: Annotated[
            str | None,
            Field(description="Optional profile override. Missing template profile remaps to default."),
        ] = None,
        pipeline_data: Annotated[
            str | None,
            Field(description="Optional pipeline_data override; omit to use the template."),
        ] = None,
        pipeline_vars: Annotated[
            str | None,
            Field(description="Optional pipeline_vars override; omit to use the template."),
        ] = None,
        pipeline_vars_secure: Annotated[
            str | None,
            Field(description="Optional secure vars override; omit to use the template."),
        ] = None,
        is_dry_run: Annotated[
            bool | None,
            Field(description="Optional dry-run override; omit to use the template."),
        ] = None,
        log_level: Annotated[
            str | None,
            Field(description="Optional log level override; omit to use the template."),
        ] = None,
        pde_image: Annotated[
            str | None,
            Field(description="Optional PDE image override; omit to use the template."),
        ] = None,
    ) -> str:
        """Queue a new PDE run from a catalog template. Sets created_from_template_id for audit.

        Prefer this over manually copying template fields into pde_create_run. After create, poll
        pde_get_run until SUCCESS/FAILED/CANCELLED.
        """
        session_factory = app.state.session_factory
        req = CreateRunFromTemplateRequest(
            profile_id=profile_id,
            pipeline_data=pipeline_data,
            pipeline_vars=pipeline_vars,
            pipeline_vars_secure=pipeline_vars_secure,
            is_dry_run=is_dry_run,
            log_level=log_level,
            pde_image=pde_image,
        )
        async with session_factory() as session:
            service = RunService(session, settings)
            try:
                run = await service.create_run_from_simple_template(UUID(template_id), req)
            except (RunTemplateNotFoundError, RunTemplateKindError, ProfileNotFoundError) as exc:
                raise ValueError(_error_message(exc)) from exc
        return _dumps(CreateRunResponse.model_validate(run).model_dump(mode="json"))

    @mcp.tool()
    async def pde_cancel_run(run_id: Annotated[str, Field(description="UUID of a non-terminal run to cancel.")]) -> str:
        """Request cancellation of a QUEUED / NOT_STARTED / IN_PROGRESS run.

        Sends cooperative SIGINT into the Job; status becomes CANCELLED after PDE finishes shutting down
        (or after grace). Poll pde_get_run; do not assume instant CANCELLED. Fails if already terminal.
        """
        session_factory = app.state.session_factory
        async with session_factory() as session:
            service = RunService(session, settings)
            try:
                run = await service.cancel_run(UUID(run_id))
            except (RunNotFoundError, RunNotCancellableError) as exc:
                raise ValueError(_error_message(exc)) from exc
        return _dumps(RunDetail.model_validate(run).model_dump(mode="json"))

    @mcp.tool()
    async def pde_retry_run(
        run_id: Annotated[str, Field(description="UUID of a FAILED or CANCELLED parent run with archived state.")],
        retry_vars: Annotated[
            str | None,
            Field(description="Optional KEY=VALUE overrides for the retry (PDE --retry_vars)."),
        ] = None,
        pde_image: Annotated[
            str | None,
            Field(description="Optional PDE image override for the new run."),
        ] = None,
    ) -> str:
        """Smart-retry: create a *new* run from the parent's archived pipeline state.

        Parent must be FAILED or CANCELLED with state in MinIO. Returns the new run (id differs).
        Parent env is reused when not overridden. Use after diagnosing with get_run / get_run_log.
        """
        session_factory = app.state.session_factory
        req = RetryRunRequest(retry_vars=retry_vars, pde_image=pde_image)
        async with session_factory() as session:
            service = RunService(session, settings)
            try:
                run = await service.retry_run(UUID(run_id), req)
            except (RunNotFoundError, RunNotRetriableError, RunStateNotAvailableError, ProfileNotFoundError) as exc:
                raise ValueError(_error_message(exc)) from exc
        return _dumps(CreateRunResponse.model_validate(run).model_dump(mode="json"))

    @mcp.tool()
    async def pde_get_run_log(
        run_id: Annotated[str, Field(description="Run UUID whose console.log artifact to read.")],
        tail_lines: Annotated[
            int,
            Field(description="Return only the last N lines (0 = full log). Default 400.", ge=0),
        ] = 400,
    ) -> str:
        """Fetch the run console log from MinIO (trailing lines by default).

        Available after the Job archives artifacts (including cancel). Use to diagnose FAILED/CANCELLED.
        If artifacts are missing, the run may still be running or archive failed — check pde_get_run status.
        """
        session_factory = app.state.session_factory
        async with session_factory() as session:
            service = RunService(session, settings)
            try:
                obj = service.get_artifact(UUID(run_id), ArtifactKind.LOG)
            except (ArtifactsDisabledError, ArtifactNotFoundError) as exc:
                raise ValueError(_error_message(exc)) from exc
        try:
            raw = obj.body.read()
        finally:
            obj.body.close()
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if 0 < tail_lines < len(lines):
            lines = lines[-tail_lines:]
            return f"... ({tail_lines} trailing lines)\n" + "\n".join(lines)
        return text

    @mcp.prompt()
    def investigate_run(run_id: str) -> str:
        """Guided workflow to investigate a run's outcome (status, report, log, next actions)."""
        return (
            f"Investigate PDE Operator run `{run_id}`.\n\n"
            "1. Call pde_get_run with this run_id and summarize status, profile_id, timings, "
            "retry_of_run_id, cancel_requested_at, and progress_json from pde_get_run.\n"
            "2. If status is not terminal, explain the lifecycle step and whether cancel is appropriate.\n"
            "3. If FAILED or CANCELLED, call pde_get_run_log (tail ~400) and quote the most relevant "
            "error lines (not the whole log).\n"
            "4. Recommend one next action: wait/poll, cancel, retry (only if FAILED/CANCELLED with state), "
            "or create a new run with adjusted pipeline_vars — and why.\n"
            "5. Do not invent statuses or invent log content; only use tool results."
        )

    @mcp.resource(
        URI_LIFECYCLE,
        name="Run lifecycle",
        description="Run statuses, cancel/retry rules, and diagnose tips (static markdown).",
        mime_type="text/markdown",
    )
    def pde_lifecycle() -> str:
        return LIFECYCLE_MARKDOWN

    @mcp.resource(
        URI_PIPELINE_INPUTS,
        name="Pipeline inputs",
        description="How to format pipeline_data / pipeline_vars / pipeline_vars_secure (static markdown).",
        mime_type="text/markdown",
    )
    def pde_pipeline_inputs() -> str:
        return PIPELINE_INPUTS_MARKDOWN

    @mcp.resource(
        URI_PROFILES,
        name="Execution profiles",
        description="Live profiles (id, pde_image, timestamps). Use get/detail for env_vars and resources.",
        mime_type="application/json",
    )
    async def pde_profiles() -> str:
        session_factory = app.state.session_factory
        async with session_factory() as session:
            profiles, total = await ProfileService(session).list_profiles(offset=0, limit=100)
        items = [ProfileListItem.model_validate(p).model_dump(mode="json") for p in profiles]
        return _dumps({"items": items, "total": total, "offset": 0, "limit": 100})

    @mcp.resource(
        URI_RUN_TEMPLATES,
        name="Run templates",
        description="How to discover and start runs from the catalog (static markdown).",
        mime_type="text/markdown",
    )
    def pde_run_templates_doc() -> str:
        return RUN_TEMPLATES_MARKDOWN

    return mcp


def _admin_only_wrapper(inner, settings: Settings):
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await inner(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
        principal = AuthUtils.resolve_principal(
            provided=token,
            api_admin_token=settings.api_admin_token,
            job_token_signing_key=settings.job_token_signing_key,
        )
        if principal is None:
            response = JSONResponse(
                {"detail": "Invalid or missing Bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        if principal.role != "admin":
            response = JSONResponse({"detail": "Token is not allowed for this operation"}, status_code=403)
            await response(scope, receive, send)
            return
        await inner(scope, receive, send)

    return app


def mount_embedded_mcp(app: FastAPI, settings: Settings) -> None:
    mcp = _build_mcp(app, settings)
    # Streamable HTTP at /api/v1/mcp/
    mcp_http_app = mcp.streamable_http_app()
    app.state.mcp_session_manager = mcp.session_manager
    app.mount(f"{settings.api_prefix.rstrip('/')}/mcp", _admin_only_wrapper(mcp_http_app, settings))
