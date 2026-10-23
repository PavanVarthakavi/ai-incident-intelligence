"""Incident API against a real PostgreSQL test database.

Evidence comes from the recorded fixtures (see tests/fakes.py), so snapshots
contain the same bad-deploy evidence the collector tests use.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests import fakes

MISSING = str(uuid.UUID(int=0))


def incident(**overrides) -> dict:
    return {"title": "Checkout failing", "window": fakes.window()} | overrides


def create(client: TestClient, **overrides) -> dict:
    response = client.post("/v1/incidents", json=incident(**overrides))
    assert response.status_code == 201, response.json()
    return response.json()


def test_create_stores_snapshot_of_all_sources(db_client: TestClient) -> None:
    body = create(db_client, severity="high", description="502s on checkout")

    assert body["title"] == "Checkout failing"
    assert body["severity"] == "high"
    assert body["window"] == {k: v.replace("+00:00", "Z") for k, v in fakes.window().items()}
    [snapshot] = body["snapshots"]
    assert snapshot["source_errors"] == []
    assert set(snapshot["source_counts"]) == {"metrics", "traces", "logs", "deployments"}
    assert snapshot["evidence_count"] == sum(snapshot["source_counts"].values())


def test_snapshot_preserves_evidence_exactly(db_client: TestClient) -> None:
    live = db_client.get("/v1/evidence", params=fakes.window()).json()["evidence"]
    body = create(db_client)

    stored = db_client.get(
        f"/v1/incidents/{body['id']}/snapshots/{body['snapshots'][0]['id']}"
    ).json()

    assert [e["id"] for e in stored["evidence"]] == [e["id"] for e in live]
    assert stored["evidence"] == live
    assert stored["incident_id"] == body["id"]


def test_get_incident(db_client: TestClient) -> None:
    created = create(db_client)

    response = db_client.get(f"/v1/incidents/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_create_without_collection_then_snapshot_later(db_client: TestClient) -> None:
    created = create(db_client, collect_evidence=False)
    assert created["snapshots"] == []

    response = db_client.post(f"/v1/incidents/{created['id']}/snapshots")

    assert response.status_code == 201
    assert response.json()["evidence_count"] > 0
    assert len(db_client.get(f"/v1/incidents/{created['id']}").json()["snapshots"]) == 1


def test_new_snapshot_leaves_earlier_ones_unchanged(db_client: TestClient) -> None:
    created = create(db_client)
    first = created["snapshots"][0]
    first_url = f"/v1/incidents/{created['id']}/snapshots/{first['id']}"
    before = db_client.get(first_url).json()

    db_client.post(f"/v1/incidents/{created['id']}/snapshots")

    snapshots = db_client.get(f"/v1/incidents/{created['id']}").json()["snapshots"]
    assert len(snapshots) == 2
    assert snapshots[0] == first
    assert db_client.get(first_url).json() == before


def test_backend_failure_is_recorded_in_snapshot(
    db_client: TestClient, transport: fakes.FixtureTransport
) -> None:
    transport.overrides["opensearch_search_otel_logs"] = 500

    [snapshot] = create(db_client)["snapshots"]

    assert [e["source"] for e in snapshot["source_errors"]] == ["logs"]
    assert "logs" not in snapshot["source_counts"]


def test_service_scope_limits_collection(
    db_client: TestClient, transport: fakes.FixtureTransport
) -> None:
    created = create(db_client, services=["orders"])

    assert created["services"] == ["orders"]
    jaeger = {r.url.params["service"] for r in transport.requests if r.url.path == "/api/traces"}
    assert jaeger == {"orders"}


def test_list_newest_first_with_pagination(db_client: TestClient) -> None:
    ids = [create(db_client, title=f"incident {n}", collect_evidence=False)["id"] for n in range(3)]

    first = db_client.get("/v1/incidents", params={"limit": 2}).json()
    second = db_client.get("/v1/incidents", params={"limit": 2, "offset": 2}).json()

    assert first["total"] == 3
    assert [i["id"] for i in first["items"] + second["items"]] == list(reversed(ids))


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},
        {"title": "x" * 201},
        {"severity": "urgent"},
        {"services": [f"svc-{n}" for n in range(21)]},
        {"window": {"start": fakes.window()["end"], "end": fakes.window()["start"]}},
    ],
)
def test_invalid_incident_rejected(db_client: TestClient, overrides: dict) -> None:
    assert db_client.post("/v1/incidents", json=incident(**overrides)).status_code == 422


def test_title_is_trimmed(db_client: TestClient) -> None:
    assert create(db_client, title="  Checkout failing  ")["title"] == "Checkout failing"


def test_unknown_incident_and_snapshot_return_404(db_client: TestClient) -> None:
    a, b = create(db_client), create(db_client)

    assert db_client.get(f"/v1/incidents/{MISSING}").status_code == 404
    assert db_client.post(f"/v1/incidents/{MISSING}/snapshots").status_code == 404
    # A snapshot is only reachable through the incident it belongs to.
    foreign = f"/v1/incidents/{a['id']}/snapshots/{b['snapshots'][0]['id']}"
    assert db_client.get(foreign).status_code == 404


def test_incident_endpoints_need_a_database(client: TestClient) -> None:
    response = client.post("/v1/incidents", json=incident())

    assert response.status_code == 503
    assert response.json()["detail"] == "database is not configured"
