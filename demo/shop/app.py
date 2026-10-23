"""App factory shared by all demo services."""

import logging
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shop import admin, gateway, inventory, orders
from shop.context import ServiceState
from shop.faults import FaultInjector, SimulatedFailure
from shop.settings import Settings

ServiceName = Literal["gateway", "orders", "inventory"]
SERVICE_ROUTERS = {
    "gateway": gateway.router,
    "orders": orders.router,
    "inventory": inventory.router,
}

logger = logging.getLogger("shop")


def create_app(
    service: ServiceName,
    settings: Settings | None = None,
    http_client: httpx.AsyncClient | None = None,
    rng: random.Random | None = None,
) -> FastAPI:
    """Build a demo service. ``http_client`` and ``rng`` are injectable for tests."""
    settings = settings or Settings()
    state = ServiceState(
        name=service, settings=settings, faults=FaultInjector(settings.service_version, rng)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        state.http = http_client or httpx.AsyncClient(timeout=settings.downstream_timeout_s)
        try:
            yield
        finally:
            if http_client is None:
                await state.http.aclose()

    app = FastAPI(title=f"demo-shop {service}", version=settings.service_version, lifespan=lifespan)
    app.state.service = state
    app.include_router(admin.router)
    app.include_router(SERVICE_ROUTERS[service])

    @app.exception_handler(SimulatedFailure)
    async def handle_simulated_failure(request: Request, exc: SimulatedFailure) -> JSONResponse:
        # Logged without a traceback so the exception type doesn't reveal the failure is injected.
        logger.error(
            str(exc), extra={"release": state.faults.release, "url.path": request.url.path}
        )
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    return app
