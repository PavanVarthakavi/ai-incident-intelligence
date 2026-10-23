"""Gateway service: the public entry point that load is sent to."""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shop.catalog import PRODUCTS
from shop.context import FaultedState

logger = logging.getLogger("shop.gateway")
router = APIRouter()


class CheckoutRequest(BaseModel):
    sku: str
    quantity: int = Field(default=1, ge=1, le=100)


@router.get("/products")
async def list_products(state: FaultedState) -> dict[str, dict[str, object]]:
    return PRODUCTS


@router.post("/checkout", status_code=201)
async def checkout(request: CheckoutRequest, state: FaultedState) -> dict[str, object]:
    log_extra = {"sku": request.sku, "release": state.faults.release}
    try:
        response = await state.client.post(
            f"{state.settings.orders_url}/orders", json=request.model_dump()
        )
    except httpx.TimeoutException:
        logger.error("timed out waiting for orders service", extra=log_extra)
        raise HTTPException(status_code=504, detail="checkout timed out") from None
    except httpx.TransportError as exc:
        logger.error("orders service unreachable: %s", type(exc).__name__, extra=log_extra)
        raise HTTPException(status_code=502, detail="checkout unavailable") from None

    if response.status_code in (404, 409):
        raise HTTPException(status_code=response.status_code, detail=response.json()["detail"])
    if response.is_error:
        logger.error(
            "checkout failed: orders returned %s",
            response.status_code,
            extra={**log_extra, "http.response.status_code": response.status_code},
        )
        raise HTTPException(status_code=502, detail="checkout failed")
    return response.json()
