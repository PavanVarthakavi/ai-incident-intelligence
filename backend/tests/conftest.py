import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, make_url, text

from app.config import BACKEND_DIR, ENV_FILES, Settings
from app.main import create_app
from tests.fakes import FixtureTransport


class _TestEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=ENV_FILES, extra="ignore")
    test_database_url: SecretStr | None = None


def hermetic_settings(**overrides) -> Settings:
    """Settings that ignore .env files and the API key, so tests never use a developer's
    database or spend money. The key is passed by its env name because the field reads
    ANTHROPIC_API_KEY through an alias."""
    defaults = {
        "service_name": "test-service",
        "environment": "test",
        "database_url": None,
        "ANTHROPIC_API_KEY": None,
    }
    return Settings(_env_file=None, **(defaults | overrides))


@pytest.fixture
def settings() -> Settings:
    return hermetic_settings()


@pytest.fixture
def transport() -> FixtureTransport:
    """Backend responses replayed from tests/fixtures. Set ``.overrides`` to inject failures."""
    return FixtureTransport()


@pytest.fixture
def client(settings: Settings, transport: FixtureTransport) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=transport)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """URL of a migrated test database (APP_TEST_DATABASE_URL). Skips locally if unset."""
    secret = _TestEnv().test_database_url
    if secret is None:
        if os.getenv("CI"):
            pytest.fail("APP_TEST_DATABASE_URL must be set in CI")
        pytest.skip("APP_TEST_DATABASE_URL is not set (see .env.example)")
    url = secret.get_secret_value()
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.fail(f"refusing to run tests against {database!r}: name must end with '_test'")

    config = Config(BACKEND_DIR / "alembic.ini")
    config.attributes["database_url"] = url
    config.attributes["skip_logging"] = True
    command.upgrade(config, "head")
    return url


@pytest.fixture
def make_db_client(
    test_database_url: str, transport: FixtureTransport
) -> Iterator[Callable[..., TestClient]]:
    """Factory for API clients on the emptied test database; kwargs override settings."""
    engine = create_engine(test_database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE incidents CASCADE"))
    engine.dispose()
    with ExitStack() as stack:

        def make(**overrides) -> TestClient:
            settings = hermetic_settings(database_url=test_database_url, **overrides)
            return stack.enter_context(TestClient(create_app(settings, transport=transport)))

        yield make


@pytest.fixture
def db_client(make_db_client: Callable[..., TestClient]) -> TestClient:
    """API client backed by the test database, emptied before each test."""
    return make_db_client()
