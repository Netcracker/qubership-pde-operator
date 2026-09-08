import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pde_operator.app import create_app
from pde_operator.config import Settings
from pde_operator.db.models.profile import Profile
from pde_operator.mcp.embedded import _build_mcp
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
from pde_operator.utils.auth_utils import AuthUtils

MCP_PATH = "/api/v1/mcp/"


def test_mcp_endpoint_requires_admin_token() -> None:
    settings = Settings(k8s_job_creation_enabled=False, ui_enabled=False, retention_enabled=False)
    # No lifespan: auth wrapper rejects before StreamableHTTPSessionManager is needed.
    client = TestClient(create_app(settings))
    response = client.post(MCP_PATH)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing Bearer token"


def test_mcp_endpoint_rejects_run_token() -> None:
    settings = Settings(k8s_job_creation_enabled=False, ui_enabled=False, retention_enabled=False)
    AuthUtils.ensure_auth_secrets(settings)
    run_token = AuthUtils.mint_run_token(signing_key=settings.job_token_signing_key, run_id=uuid4())
    client = TestClient(create_app(settings))
    response = client.post(MCP_PATH, headers={"Authorization": f"Bearer {run_token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Token is not allowed for this operation"


def _parse_sse_json_result(body: str) -> dict:
    """Extract first JSON-RPC result payload from a Streamable HTTP SSE response."""
    for line in body.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line.removeprefix("data: ").strip())
            if isinstance(payload, dict) and "result" in payload:
                return payload["result"]
    payload = json.loads(body)
    assert "result" in payload
    return payload["result"]


def test_mcp_streamable_initialize_with_admin_token() -> None:
    settings = Settings(k8s_job_creation_enabled=False, ui_enabled=False, retention_enabled=False)
    AuthUtils.ensure_auth_secrets(settings)
    # Lifespan starts StreamableHTTPSessionManager (required for initialize).
    with TestClient(create_app(settings)) as client:
        response = client.post(
            MCP_PATH,
            headers={
                "Authorization": f"Bearer {settings.api_admin_token}",
                # FastMCP default DNS-rebinding allowlist is localhost/127.0.0.1 with a port.
                "Host": "127.0.0.1:8000",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pde-operator-test", "version": "0"},
                },
            },
        )
        assert response.status_code == 200
        assert response.headers.get("mcp-session-id")
        assert "event: message" in response.text or '"protocolVersion"' in response.text
        result = _parse_sse_json_result(response.text)
        assert result["serverInfo"]["name"] == MCP_SERVER_NAME
        assert result.get("instructions") == MCP_INSTRUCTIONS
        assert "PDE Operator" in result["instructions"]
        assert "pde_create_run" in result["instructions"]
        assert "pde_create_run_from_template" in result["instructions"]
        assert "pde://lifecycle" in result["instructions"]
        assert "pde://run-templates" in result["instructions"]


@pytest.mark.asyncio
async def test_mcp_resources_static_and_profiles() -> None:
    settings = Settings(k8s_job_creation_enabled=False, ui_enabled=False, retention_enabled=False)
    app = FastAPI()
    now = datetime.now(UTC)
    profile = Profile(id="default", pde_image="pde:dev", env_vars={"A": "1"}, resources={}, created_at=now, updated_at=now)
    session = AsyncMock()
    # ProfileService.list_profiles: count query then select query
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one=MagicMock(return_value=1)),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[profile])))),
        ]
    )
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None
    app.state.session_factory = MagicMock(return_value=session_cm)

    mcp = _build_mcp(app, settings)
    listed = await mcp.list_resources()
    uris = {str(r.uri) for r in listed}
    assert uris == {URI_LIFECYCLE, URI_PIPELINE_INPUTS, URI_PROFILES, URI_RUN_TEMPLATES}

    lifecycle = list(await mcp.read_resource(URI_LIFECYCLE))
    assert lifecycle[0].content == LIFECYCLE_MARKDOWN
    assert lifecycle[0].mime_type == "text/markdown"

    inputs = list(await mcp.read_resource(URI_PIPELINE_INPUTS))
    assert inputs[0].content == PIPELINE_INPUTS_MARKDOWN

    templates_doc = list(await mcp.read_resource(URI_RUN_TEMPLATES))
    assert templates_doc[0].content == RUN_TEMPLATES_MARKDOWN

    profiles = list(await mcp.read_resource(URI_PROFILES))
    payload = json.loads(profiles[0].content)
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "default"
    assert payload["items"][0]["pde_image"] == "pde:dev"
    assert "env_vars" not in payload["items"][0]
    assert "resources" not in payload["items"][0]
    assert profiles[0].mime_type == "application/json"
