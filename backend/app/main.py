"""FastAPI application entry point.

Run locally with:  uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Incident Intelligence API",
        version=__version__,
        description=f"Incident investigation backend ({settings.environment}).",
    )
    app.include_router(health_router)
    return app


app = create_app()
