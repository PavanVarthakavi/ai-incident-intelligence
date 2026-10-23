"""Runtime fault injection.

Each service process holds one ``FaultInjector``. Faults are changed at runtime
through the admin API (see ``shop.admin``) and reset when the process restarts.

Error log messages are configurable so scenarios can produce realistic symptoms
(for example "connection pool exhausted") without the telemetry revealing that
the failure was injected.
"""

import asyncio
import random

from pydantic import BaseModel, Field

DEFAULT_ERROR_MESSAGE = "internal error while processing request"


class FaultConfig(BaseModel):
    latency_ms: int = Field(default=0, ge=0, le=30_000, description="Mean added latency.")
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Probability of failure.")
    error_message: str = Field(default=DEFAULT_ERROR_MESSAGE, min_length=1, max_length=200)

    @property
    def active(self) -> bool:
        return self.latency_ms > 0 or self.error_rate > 0


class SimulatedFailure(Exception):
    """Raised when an injected error fires. Converted to an HTTP 500 by the app."""


class FaultInjector:
    LATENCY_JITTER = 0.2  # +/- 20% so injected latency doesn't look artificially constant

    def __init__(self, release: str, rng: random.Random | None = None) -> None:
        self.release = release
        self.config = FaultConfig()
        self._rng = rng or random.Random()

    def set(self, config: FaultConfig) -> None:
        self.config = config

    def clear(self) -> None:
        self.config = FaultConfig()

    async def apply(self) -> None:
        config = self.config
        if config.latency_ms:
            jitter = self._rng.uniform(1 - self.LATENCY_JITTER, 1 + self.LATENCY_JITTER)
            await asyncio.sleep(config.latency_ms * jitter / 1000)
        if config.error_rate and self._rng.random() < config.error_rate:
            raise SimulatedFailure(config.error_message)
