"""Inventory service: reserves stock for an order."""

import asyncio
import logging
import random

from fastapi import APIRouter, HTTPException
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from shop.catalog import SKUS
from shop.context import FaultedState

logger = logging.getLogger("shop.inventory")
tracer = trace.get_tracer("shop.inventory")
reservations = metrics.get_meter("shop.inventory").create_counter(
    "inventory.reservations", description="Stock reservation attempts by outcome."
)

INITIAL_STOCK = 500
RESTOCK_THRESHOLD = 50

router = APIRouter()


class Stock:
    """In-memory stock levels. Restocks automatically so the demo can run indefinitely."""

    def __init__(self) -> None:
        self.levels = {sku: INITIAL_STOCK for sku in SKUS}

    def reserve(self, sku: str, quantity: int) -> int:
        available = self.levels[sku]
        if quantity > available:
            raise ValueError("insufficient stock")
        self.levels[sku] = available - quantity
        if self.levels[sku] < RESTOCK_THRESHOLD:
            self.levels[sku] = INITIAL_STOCK
            logger.info("restocked %s", sku, extra={"sku": sku})
        return self.levels[sku]


stock = Stock()


class ReservationRequest(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=100)


class Reservation(BaseModel):
    sku: str
    quantity: int
    remaining: int


@router.post("/reserve")
async def reserve(request: ReservationRequest, state: FaultedState) -> Reservation:
    attrs = {"release": state.faults.release}
    if request.sku not in stock.levels:
        reservations.add(1, {**attrs, "outcome": "unknown_sku"})
        raise HTTPException(status_code=404, detail="unknown sku")

    with tracer.start_as_current_span("inventory.db.query") as span:
        span.set_attribute("db.system.name", "postgresql")
        span.set_attribute("db.operation.name", "UPDATE")
        await asyncio.sleep(random.uniform(0.005, 0.025))  # baseline query latency
        try:
            remaining = stock.reserve(request.sku, request.quantity)
        except ValueError:
            reservations.add(1, {**attrs, "outcome": "out_of_stock"})
            logger.warning("insufficient stock for %s", request.sku, extra={"sku": request.sku})
            raise HTTPException(status_code=409, detail="insufficient stock") from None

    reservations.add(1, {**attrs, "outcome": "reserved"})
    return Reservation(sku=request.sku, quantity=request.quantity, remaining=remaining)
