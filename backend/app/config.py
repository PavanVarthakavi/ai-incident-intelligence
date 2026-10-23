"""Application settings loaded from environment variables.

All settings use the ``APP_`` prefix (e.g. ``APP_ENVIRONMENT=production``).
Secrets must never be hard-coded here; provide them via the environment.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    service_name: str = "incident-intelligence-api"
    environment: Literal["local", "test", "staging", "production"] = "local"

    # Observability backends (defaults match the local demo stack in compose.yaml).
    prometheus_url: str = "http://localhost:9090"
    jaeger_url: str = "http://localhost:16686"
    opensearch_url: str = "http://localhost:9200"
    logs_index: str = "otel-logs"
    deploy_events_index: str = "deploy-events"
    backend_timeout_s: float = 10.0
    readiness_timeout_s: float = 2.0


@lru_cache
def get_settings() -> Settings:
    """Return cached settings. Override in tests via FastAPI dependency overrides."""
    return Settings()
