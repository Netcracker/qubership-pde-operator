from fastapi.testclient import TestClient

from pde_operator.app import create_app
from pde_operator.config import Settings


def test_health() -> None:
    client = TestClient(create_app(Settings(k8s_job_creation_enabled=False, ui_enabled=False)))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_without_lifespan_is_unavailable() -> None:
    # Without lifespan, engine is not on app.state - readiness must fail closed.
    client = TestClient(create_app(Settings(k8s_job_creation_enabled=False, ui_enabled=False)))
    response = client.get("/ready")
    assert response.status_code == 503
