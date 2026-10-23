"""Request-scoped access to per-service state stored on ``app.state``."""

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, Request
from opentelemetry import trace

from shop.faults import FaultInjector
from shop.settings import Settings


@dataclass
class ServiceState:
    name: str
    settings: Settings
    faults: FaultInjector
    http: httpx.AsyncClient | None = None  # set during app lifespan

    @property
    def client(self) -> httpx.AsyncClient:
        if self.http is None:
            raise RuntimeError("HTTP client is only available while the app is running")
        return self.http


def get_state(request: Request) -> ServiceState:
    return request.app.state.service


async def apply_faults(state: Annotated[ServiceState, Depends(get_state)]) -> ServiceState:
    """Dependency for business endpoints: tag the span with the release, then apply faults."""
    trace.get_current_span().set_attribute("app.release", state.faults.release)
    await state.faults.apply()
    return state


State = Annotated[ServiceState, Depends(get_state)]
FaultedState = Annotated[ServiceState, Depends(apply_faults)]
