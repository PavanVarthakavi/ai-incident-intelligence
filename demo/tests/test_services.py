"""Service behaviour, with downstream services replaced by in-process apps or stubs."""

from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shop.app import create_app
from shop.settings import Settings

SETTINGS = Settings(
    service_version="1.0.0",
    orders_url="http://orders",
    inventory_url="http://inventory",
)


def stub_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def app_client(app: FastAPI) -> httpx.AsyncClient:
    """An HTTP client that routes requests to another in-process app."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app))


@pytest.fixture
def inventory_app() -> FastAPI:
    return create_app("inventory", SETTINGS)


@pytest.fixture
def shop(inventory_app: FastAPI) -> TestClient:
    """Full gateway -> orders -> inventory chain, running in-process."""
    orders_app = create_app("orders", SETTINGS, http_client=app_client(inventory_app))
    gateway_app = create_app("gateway", SETTINGS, http_client=app_client(orders_app))
    # ASGITransport does not run lifespans, so start the downstream apps explicitly.
    with TestClient(inventory_app), TestClient(orders_app), TestClient(gateway_app) as client:
        yield client


def test_health_and_status() -> None:
    with TestClient(create_app("orders", SETTINGS)) as client:
        assert client.get("/health").json() == {"status": "ok", "service": "orders"}
        status = client.get("/admin/status").json()

    assert status["service"] == "orders"
    assert status["release"] == "1.0.0"
    assert status["faults"]["error_rate"] == 0.0


def test_checkout_happy_path(shop: TestClient) -> None:
    response = shop.post("/checkout", json={"sku": "SKU-1001", "quantity": 2})

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "SKU-1001"
    assert body["total_cents"] == 2 * 8900


def test_unknown_sku_is_rejected_end_to_end(shop: TestClient) -> None:
    response = shop.post("/checkout", json={"sku": "SKU-0000"})

    assert response.status_code == 404


def test_inventory_fault_cascades_to_gateway_as_502(
    shop: TestClient, inventory_app: FastAPI
) -> None:
    with TestClient(inventory_app) as inventory:
        inventory.put("/admin/faults", json={"error_rate": 1.0})

        response = shop.post("/checkout", json={"sku": "SKU-1002"})

    assert response.status_code == 502


def test_injected_failure_response_does_not_reveal_injection() -> None:
    with TestClient(create_app("inventory", SETTINGS)) as client:
        client.put("/admin/faults", json={"error_rate": 1.0, "error_message": "pool exhausted"})
        response = client.post("/reserve", json={"sku": "SKU-1001", "quantity": 1})

    assert response.status_code == 500
    assert response.json() == {"detail": "internal server error"}


def test_orders_maps_inventory_timeout_to_504() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    app = create_app("orders", SETTINGS, http_client=stub_client(timeout))
    with TestClient(app) as client:
        response = client.post("/orders", json={"sku": "SKU-1001", "quantity": 1})

    assert response.status_code == 504


def test_orders_maps_unreachable_inventory_to_502() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    app = create_app("orders", SETTINGS, http_client=stub_client(refused))
    with TestClient(app) as client:
        response = client.post("/orders", json={"sku": "SKU-1001", "quantity": 1})

    assert response.status_code == 502


def test_release_change_sets_version_and_faults() -> None:
    with TestClient(create_app("orders", SETTINGS)) as client:
        response = client.put(
            "/admin/release", json={"version": "2.0.0", "faults": {"latency_ms": 500}}
        )
        assert response.status_code == 200
        status = client.get("/admin/status").json()

    assert status["release"] == "2.0.0"
    assert status["faults"]["latency_ms"] == 500


def test_clear_faults() -> None:
    with TestClient(create_app("gateway", SETTINGS)) as client:
        client.put("/admin/faults", json={"error_rate": 1.0})
        assert client.get("/products").status_code == 500

        client.delete("/admin/faults")

        assert client.get("/products").status_code == 200


def test_invalid_fault_request_rejected() -> None:
    with TestClient(create_app("gateway", SETTINGS)) as client:
        response = client.put("/admin/faults", json={"error_rate": 2})

    assert response.status_code == 422
