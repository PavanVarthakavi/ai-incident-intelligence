"""Orders service: reserves inventory, authorizes payment, and creates an order."""

import asyncio
import logging
import random
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from shop.catalog import PRODUCTS
from shop.context import FaultedState

logger = logging.getLogger("shop.orders")
tracer = trace.get_tracer("shop.orders")
orders_counter = metrics.get_meter("shop.orders").create_counter(
    "orders.created", description="Order attempts by status."
)

router = APIRouter()


class OrderRequest(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=100)


class Order(BaseModel):
    order_id: str
    sku: str
    quantity: int
    total_cents: int


@router.post("/orders", status_code=201)
async def create_order(request: OrderRequest, state: FaultedState) -> Order:
    attrs = {"release": state.faults.release}
    log_extra = {"sku": request.sku, "release": state.faults.release}

    try:
        response = await state.client.post(
            f"{state.settings.inventory_url}/reserve", json=request.model_dump()
        )
    except httpx.TimeoutException:
        orders_counter.add(1, {**attrs, "status": "inventory_timeout"})
        logger.error("timed out reserving inventory", extra=log_extra)
        raise HTTPException(status_code=504, detail="inventory timeout") from None
    except httpx.TransportError as exc:
        orders_counter.add(1, {**attrs, "status": "inventory_unreachable"})
        logger.error("inventory unreachable: %s", type(exc).__name__, extra=log_extra)
        raise HTTPException(status_code=502, detail="inventory unreachable") from None

    if response.status_code in (404, 409):
        orders_counter.add(1, {**attrs, "status": "rejected"})
        raise HTTPException(status_code=response.status_code, detail=response.json()["detail"])
    if response.is_error:
        orders_counter.add(1, {**attrs, "status": "inventory_error"})
        logger.error(
            "inventory reservation failed with status %s",
            response.status_code,
            extra={**log_extra, "http.response.status_code": response.status_code},
        )
        raise HTTPException(status_code=502, detail="inventory error")

    with tracer.start_as_current_span("payment.authorize"):
        await asyncio.sleep(random.uniform(0.02, 0.06))  # simulated payment provider call

    order = Order(
        order_id=str(uuid.uuid4()),
        sku=request.sku,
        quantity=request.quantity,
        total_cents=int(PRODUCTS[request.sku]["price_cents"]) * request.quantity,
    )
    orders_counter.add(1, {**attrs, "status": "created"})
    logger.info("order created", extra={**log_extra, "order_id": order.order_id})
    return order
