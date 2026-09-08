import pytest

from pde_operator.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(k8s_job_creation_enabled=False)
