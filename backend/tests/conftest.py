from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.fakes import FixtureTransport


@pytest.fixture
def settings() -> Settings:
    return Settings(service_name="test-service", environment="test")


@pytest.fixture
def transport() -> FixtureTransport:
    """Backend responses replayed from tests/fixtures. Set ``.overrides`` to inject failures."""
    return FixtureTransport()


@pytest.fixture
def client(settings: Settings, transport: FixtureTransport) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=transport)) as test_client:
        yield test_client
