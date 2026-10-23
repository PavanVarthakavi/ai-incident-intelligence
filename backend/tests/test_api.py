"""HTTP API: readiness and evidence collection."""

from fastapi.testclient import TestClient

from tests import fakes


def test_ready_when_all_backends_answer(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert set(body["dependencies"]) == {"prometheus", "jaeger", "opensearch"}


def test_not_ready_names_the_failing_backend(
    client: TestClient, transport: fakes.FixtureTransport
) -> None:
    transport.overrides["opensearch_health"] = 503

    response = client.get("/ready")

    assert response.status_code == 503
    deps = response.json()["dependencies"]
    assert deps["opensearch"]["ok"] is False
    assert "503" in deps["opensearch"]["error"]
    assert deps["prometheus"]["ok"] and deps["jaeger"]["ok"]


def test_health_does_not_touch_backends(
    client: TestClient, transport: fakes.FixtureTransport
) -> None:
    client.get("/health")

    assert transport.requests == []


def test_evidence_bundle_from_all_sources(client: TestClient) -> None:
    response = client.get("/v1/evidence", params=fakes.window())

    assert response.status_code == 200
    bundle = response.json()
    assert bundle["errors"] == []
    assert {e["source"] for e in bundle["evidence"]} == {
        "metrics",
        "traces",
        "logs",
        "deployments",
    }
    ids = [e["id"] for e in bundle["evidence"]]
    assert len(ids) == len(set(ids))


def test_failed_source_is_reported_not_fatal(
    client: TestClient, transport: fakes.FixtureTransport
) -> None:
    for key in ("prometheus_rate", "prometheus_error_ratio", "prometheus_p95"):
        transport.overrides[key] = 500

    response = client.get("/v1/evidence", params=fakes.window())

    assert response.status_code == 200
    bundle = response.json()
    assert [e["source"] for e in bundle["errors"]] == ["metrics"]
    assert "HTTP 500" in bundle["errors"][0]["message"]
    assert "metrics" not in {e["source"] for e in bundle["evidence"]}
    assert {"traces", "logs", "deployments"} <= {e["source"] for e in bundle["evidence"]}


def test_service_filter_is_applied(client: TestClient, transport: fakes.FixtureTransport) -> None:
    response = client.get("/v1/evidence", params={**fakes.window(), "service": "orders"})

    assert response.json()["services"] == ["orders"]
    jaeger_services = {
        r.url.params["service"] for r in transport.requests if r.url.path == "/api/traces"
    }
    assert jaeger_services == {"orders"}


def test_invalid_window_rejected(client: TestClient) -> None:
    w = fakes.window()

    response = client.get("/v1/evidence", params={"start": w["end"], "end": w["start"]})

    assert response.status_code == 422
    assert "end must be after start" in str(response.json()["detail"])


def test_window_without_timezone_rejected(client: TestClient) -> None:
    response = client.get(
        "/v1/evidence", params={"start": "2026-01-01T00:00:00", "end": "2026-01-01T00:10:00"}
    )

    assert response.status_code == 422
