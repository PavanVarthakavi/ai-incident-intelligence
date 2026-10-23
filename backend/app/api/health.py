"""Liveness and readiness endpoints.

``/health`` reports only that the process is up, so it stays cheap and never
fails because of a dependency. ``/ready`` checks that every observability
backend answers, and returns 503 if any does not.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app import __version__
from app.backends import BackendsDep
from app.config import Settings, get_settings
from app.integrations.base import BackendError

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class DependencyStatus(BaseModel):
    ok: bool
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, DependencyStatus]


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=__version__,
        environment=settings.environment,
    )


async def _check(ping: Callable[[], Awaitable[None]], timeout_s: float) -> DependencyStatus:
    try:
        await asyncio.wait_for(ping(), timeout=timeout_s)
    except BackendError as exc:
        return DependencyStatus(ok=False, error=exc.message)
    except TimeoutError:
        return DependencyStatus(ok=False, error=f"no response within {timeout_s}s")
    return DependencyStatus(ok=True)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "A dependency is unavailable."}},
)
async def ready(
    backends: BackendsDep,
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> ReadinessResponse:
    clients = {
        "prometheus": backends.prometheus,
        "jaeger": backends.jaeger,
        "opensearch": backends.opensearch,
    }
    results = await asyncio.gather(
        *(_check(c.ping, settings.readiness_timeout_s) for c in clients.values())
    )
    dependencies = dict(zip(clients, results, strict=True))
    is_ready = all(d.ok for d in dependencies.values())
    if not is_ready:
        response.status_code = 503
    return ReadinessResponse(status="ready" if is_ready else "not_ready", dependencies=dependencies)
