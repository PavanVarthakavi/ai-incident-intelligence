from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Per-service configuration, read from environment variables."""

    service_version: str = "1.0.0"
    orders_url: str = "http://localhost:8001"
    inventory_url: str = "http://localhost:8002"
    # Kept short on purpose: latency faults downstream should surface as timeouts upstream.
    downstream_timeout_s: float = 2.0
