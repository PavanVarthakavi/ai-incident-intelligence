from fastapi.testclient import TestClient

from app import __version__


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "test-service",
        "version": __version__,
        "environment": "test",
    }


def test_health_rejects_non_get(client: TestClient) -> None:
    response = client.post("/health")

    assert response.status_code == 405


def test_health_is_documented_in_openapi(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/health" in schema["paths"]
