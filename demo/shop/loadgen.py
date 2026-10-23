"""Steady synthetic traffic against the gateway.

Requests arrive as a Poisson process at the configured average rate, with a mix
of catalog browsing and checkouts. Not instrumented: the gateway is the root of
each trace, as it would be for real user traffic.
"""

import asyncio
import logging
import random
import signal
import time
from collections import Counter

import httpx

from shop.catalog import SKUS

logger = logging.getLogger("shop.loadgen")

CHECKOUT_SHARE = 0.7
SUMMARY_INTERVAL_S = 30.0


async def _send_one(client: httpx.AsyncClient, target: str, outcomes: Counter[str]) -> None:
    try:
        if random.random() < CHECKOUT_SHARE:
            payload = {"sku": random.choice(SKUS), "quantity": random.randint(1, 3)}
            response = await client.post(f"{target}/checkout", json=payload)
        else:
            response = await client.get(f"{target}/products")
        outcomes[str(response.status_code)] += 1
    except httpx.HTTPError as exc:
        outcomes[type(exc).__name__] += 1


async def run(target: str, rps: float, timeout_s: float) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    outcomes: Counter[str] = Counter()
    in_flight: set[asyncio.Task[None]] = set()
    last_summary = time.monotonic()
    logger.info("sending ~%.1f req/s to %s", rps, target)

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        while not stop.is_set():
            task = asyncio.create_task(_send_one(client, target, outcomes))
            in_flight.add(task)
            task.add_done_callback(in_flight.discard)

            if time.monotonic() - last_summary >= SUMMARY_INTERVAL_S:
                logger.info("last %.0fs: %s", SUMMARY_INTERVAL_S, dict(sorted(outcomes.items())))
                outcomes.clear()
                last_summary = time.monotonic()

            try:
                await asyncio.wait_for(stop.wait(), timeout=random.expovariate(rps))
            except TimeoutError:
                pass

        if in_flight:
            await asyncio.wait(in_flight, timeout=timeout_s)
    logger.info("stopped")
