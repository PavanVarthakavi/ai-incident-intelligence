import asyncio
import random

import pytest
from pydantic import ValidationError

from shop.faults import FaultConfig, FaultInjector, SimulatedFailure


def run(coro):
    return asyncio.run(coro)


def test_no_faults_by_default() -> None:
    injector = FaultInjector("1.0.0")

    assert not injector.config.active
    run(injector.apply())  # does not raise


def test_error_rate_one_always_fails_with_configured_message() -> None:
    injector = FaultInjector("1.0.0")
    injector.set(FaultConfig(error_rate=1.0, error_message="connection pool exhausted"))

    with pytest.raises(SimulatedFailure, match="connection pool exhausted"):
        run(injector.apply())


def test_error_rate_is_probabilistic() -> None:
    injector = FaultInjector("1.0.0", rng=random.Random(42))
    injector.set(FaultConfig(error_rate=0.3))

    failures = 0
    for _ in range(1000):
        try:
            run(injector.apply())
        except SimulatedFailure:
            failures += 1

    assert 250 < failures < 350


def test_latency_is_applied_with_jitter(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("shop.faults.asyncio.sleep", fake_sleep)
    injector = FaultInjector("1.0.0", rng=random.Random(1))
    injector.set(FaultConfig(latency_ms=1000))

    for _ in range(50):
        run(injector.apply())

    assert all(0.8 <= s <= 1.2 for s in sleeps)
    assert len(set(sleeps)) > 1


def test_clear_resets_faults() -> None:
    injector = FaultInjector("1.0.0")
    injector.set(FaultConfig(latency_ms=100, error_rate=0.5))

    injector.clear()

    assert injector.config == FaultConfig()


@pytest.mark.parametrize(
    "kwargs",
    [{"error_rate": 1.5}, {"error_rate": -0.1}, {"latency_ms": -1}, {"latency_ms": 60_000}],
)
def test_invalid_fault_config_rejected(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        FaultConfig(**kwargs)
