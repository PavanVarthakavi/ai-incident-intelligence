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


@lru_cache
def get_settings() -> Settings:
    """Return cached settings. Override in tests via FastAPI dependency overrides."""
    return Settings()
