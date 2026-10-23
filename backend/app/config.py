"""Application settings loaded from environment variables.

All settings use the ``APP_`` prefix (e.g. ``APP_ENVIRONMENT=production``).
Values are also read from ``.env`` in the repository root (shared with
docker compose) and then ``backend/.env``. Secrets must never be hard-coded
here; provide them via the environment.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILES = (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=ENV_FILES, extra="ignore")

    service_name: str = "incident-intelligence-api"
    environment: Literal["local", "test", "staging", "production"] = "local"

    # Platform database. Without it the API still serves health and evidence,
    # but incident endpoints return 503 and /ready reports the database as down.
    database_url: SecretStr | None = None

    # Observability backends (defaults match the local demo stack in compose.yaml).
    prometheus_url: str = "http://localhost:9090"
    jaeger_url: str = "http://localhost:16686"
    opensearch_url: str = "http://localhost:9200"
    logs_index: str = "otel-logs"
    deploy_events_index: str = "deploy-events"
    backend_timeout_s: float = 10.0
    readiness_timeout_s: float = 2.0

    # Investigation agent. The key is read from the standard ANTHROPIC_API_KEY
    # variable (no APP_ prefix); without it, diagnosis endpoints return 503.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_max_tokens: int = Field(default=16000, ge=1024, le=64000)
    llm_timeout_s: float = 300.0
    # Retry a refused request on Anthropic's recommended fallback model.
    llm_fallbacks: bool = True
    # Spend cap across all diagnoses per UTC day, enforced before each request.
    llm_daily_budget_usd: float = Field(default=2.0, ge=0)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings. Override in tests via FastAPI dependency overrides."""
    return Settings()
