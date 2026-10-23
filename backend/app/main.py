"""FastAPI application entry point.

Run locally with:  uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anthropic
import httpx
from fastapi import FastAPI

from app import __version__
from app.api.budget import router as budget_router
from app.api.diagnoses import router as diagnoses_router
from app.api.evidence import router as evidence_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.backends import Backends
from app.config import Settings, get_settings
from app.db.session import Database
from app.diagnosis.llm import AnthropicDiagnosisModel, DiagnosisModel
from app.diagnosis.offline import OfflineDiagnosisModel


def build_diagnosis_model(settings: Settings) -> DiagnosisModel | None:
    if settings.llm_provider == "offline":
        return OfflineDiagnosisModel()
    if settings.anthropic_api_key is None:
        return None
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(), timeout=settings.llm_timeout_s
    )
    return AnthropicDiagnosisModel(
        client,
        model=settings.llm_model,
        effort=settings.llm_effort,
        max_tokens=settings.llm_max_tokens,
        fallbacks=settings.llm_fallbacks,
    )


def create_app(
    settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    """Build the app. ``transport`` replaces real network I/O in tests."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = (
            Database.connect(settings.database_url.get_secret_value())
            if settings.database_url
            else None
        )
        app.state.database = database
        app.state.diagnosis_model = build_diagnosis_model(settings)
        try:
            async with httpx.AsyncClient(
                timeout=settings.backend_timeout_s, transport=transport
            ) as http:
                app.state.backends = Backends.create(settings, http)
                yield
        finally:
            if database is not None:
                await database.engine.dispose()

    app = FastAPI(
        title="AI Incident Intelligence API",
        version=__version__,
        description=f"Incident investigation backend ({settings.environment}).",
        lifespan=lifespan,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.include_router(health_router)
    app.include_router(evidence_router)
    app.include_router(incidents_router)
    app.include_router(diagnoses_router)
    app.include_router(budget_router)
    return app


app = create_app()
