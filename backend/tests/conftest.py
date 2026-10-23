import os
from collections.abc import Iterator

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
    """Settings that ignore .env files, so tests never pick up a developer's database."""
    return Settings(
        _env_file=None,
        **{"service_name": "test-service", "environment": "test", "database_url": None} | overrides,
    )


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
def db_client(test_database_url: str, transport: FixtureTransport) -> Iterator[TestClient]:
    """API client backed by the test database, emptied before each test."""
    engine = create_engine(test_database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE incidents CASCADE"))
    engine.dispose()
    settings = hermetic_settings(database_url=test_database_url)
    with TestClient(create_app(settings, transport=transport)) as test_client:
        yield test_client
