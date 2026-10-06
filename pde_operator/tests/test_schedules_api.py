from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from pde_operator.app import create_app
from pde_operator.config import Settings
from pde_operator.db.models.run_template import RunTemplate
from pde_operator.utils.auth_utils import AuthUtils


def _client_with_session() -> tuple[TestClient, dict[str, str], AsyncMock]:
    settings = Settings(
        k8s_job_creation_enabled=False,
        ui_enabled=False,
        retention_enabled=False,
        schedules_enabled=False,
    )
    AuthUtils.ensure_auth_secrets(settings)
    app = create_app(settings)
    # Lifespan owns the real session factory; these endpoints only need a session-shaped object.
    session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None
    app.state.session_factory = MagicMock(return_value=session_cm)
    return TestClient(app), {"Authorization": f"Bearer {settings.api_admin_token}"}, session


def _client() -> tuple[TestClient, dict[str, str]]:
    client, headers, _session = _client_with_session()
    return client, headers


def test_timezones_endpoint_returns_iana_names() -> None:
    client, headers = _client()

    response = client.get("/api/v1/schedules/timezones", headers=headers)

    assert response.status_code == 200
    timezones = response.json()["timezones"]
    assert "UTC" in timezones
    assert "Europe/Berlin" in timezones
    assert not any(zone.startswith(("posix/", "right/")) for zone in timezones)


def test_preview_returns_next_fire_times_in_the_requested_zone() -> None:
    client, headers = _client()

    response = client.post(
        "/api/v1/schedules/preview",
        headers=headers,
        json={"cron_expression": "0 9 * * *", "timezone": "Europe/Berlin", "count": 3},
    )

    assert response.status_code == 200
    fire_times = response.json()["next_fire_times"]
    assert len(fire_times) == 3
    assert fire_times == sorted(fire_times)
    assert fire_times[0].endswith("Z") or "+00:00" in fire_times[0]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"cron_expression": "*/10 * * * * *", "timezone": "UTC"}, "minimum interval"),
        ({"cron_expression": "not a cron", "timezone": "UTC"}, "5 or 6 fields"),
        ({"cron_expression": "0 9 * * *", "timezone": "Mars/Olympus"}, "Unknown timezone"),
    ],
)
def test_preview_rejects_invalid_input(payload: dict, expected: str) -> None:
    client, headers = _client()

    response = client.post("/api/v1/schedules/preview", headers=headers, json=payload)

    assert response.status_code == 400
    assert expected in response.json()["detail"]


def test_create_from_declarative_template_returns_contract_error() -> None:
    client, headers, session = _client_with_session()
    template_id = uuid4()
    session.get = AsyncMock(
        return_value=RunTemplate(
            id=template_id,
            name="Deploy",
            pipeline_data="",
            template_kind="declarative",
            declarative_spec={
                "name": "Deploy",
                "fields": [
                    {
                        "name": "RELEASE_VERSION",
                        "label": "Release version",
                        "bind_to": "pipeline_var",
                        "required": True,
                        "validators": [
                            {
                                "type": "pattern",
                                "value": r"^v\d+\.\d+\.\d+$",
                                "message": "Use semantic version format like v1.2.3.",
                            }
                        ],
                    }
                ],
            },
        )
    )

    response = client.post(
        "/api/v1/schedules",
        headers=headers,
        json={
            "name": "Nightly",
            "cron_expression": "0 2 * * *",
            "timezone": "UTC",
            "created_from_template_id": str(template_id),
            "declarative_values": {"RELEASE_VERSION": "1.2.3"},
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "RELEASE_VERSION" in detail
    assert "Use semantic version format like v1.2.3." in detail


def test_schedule_endpoints_require_auth() -> None:
    client, _ = _client()

    assert client.get("/api/v1/schedules/timezones").status_code == 401
    assert client.get("/api/v1/schedules").status_code == 401
