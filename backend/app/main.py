"""FastAPI application entry point.

Run locally with:  uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import __version__
from app.api.evidence import router as evidence_router
from app.api.health import router as health_router
from app.backends import Backends
from app.config import Settings, get_settings


def create_app(
    settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    """Build the app. ``transport`` replaces real network I/O in tests."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(
            timeout=settings.backend_timeout_s, transport=transport
        ) as http:
            app.state.backends = Backends.create(settings, http)
            yield

    app = FastAPI(
        title="AI Incident Intelligence API",
        version=__version__,
        description=f"Incident investigation backend ({settings.environment}).",
        lifespan=lifespan,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.include_router(health_router)
    app.include_router(evidence_router)
    return app


app = create_app()
