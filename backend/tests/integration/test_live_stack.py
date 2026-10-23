"""Integration tests against the running demo stack (docker compose up).

    pytest -m integration

The scenario test additionally needs an active bad inventory deploy:

    python3 demo/tools/incidentctl.py deploy inventory 9.9.9 --latency-ms 2500
    INCIDENT_SCENARIO=bad-inventory-deploy INCIDENT_RELEASE=9.9.9 pytest -m integration

Assertions target INCIDENT_RELEASE, so evidence left over from earlier
incidents in the same window cannot make the test pass.
"""

import os
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration

SCENARIO = os.getenv("INCIDENT_SCENARIO")
RELEASE = os.getenv("INCIDENT_RELEASE", "9.9.9")
POLL_TIMEOUT_S = float(os.getenv("INTEGRATION_POLL_TIMEOUT_S", "180"))


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as c:
        yield c


def eventually(check: Callable[[], None], timeout_s: float = POLL_TIMEOUT_S) -> None:
    """Retry ``check`` until it stops raising AssertionError; telemetry arrives with a delay."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            check()
            return
        except AssertionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(10)


def test_stack_is_ready(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200, response.json()


def test_evidence_from_every_source(client: TestClient) -> None:
    def check() -> None:
        bundle = client.get("/v1/evidence", params={"service": "gateway"}).json()
        assert bundle["errors"] == []
        assert "metrics" in {e["source"] for e in bundle["evidence"]}

    eventually(check)


def assert_bad_deploy_evidence(evidence: list[dict]) -> None:
    """The scenario must be visible in deploys, traces, logs, and metrics."""
    assert any(
        e["kind"] == "deployment"
        and e["service"] == "inventory"
        and e["data"]["version"] == RELEASE
        for e in evidence
    ), f"no deploy event for inventory {RELEASE}"
    assert any(
        e["kind"] == "trace_pattern"
        and (e["data"]["dominant_self_time"] or {}).get("service") == "inventory"
        and e["data"]["dominant_self_time"]["release"] == RELEASE
        for e in evidence
    ), f"no trace pattern attributing latency to inventory {RELEASE}"
    assert any(
        e["kind"] == "log_pattern"
        and e["service"] == "orders"
        and e["data"]["message"] == "timed out reserving inventory"
        for e in evidence
    ), "no orders timeout log pattern"
    gateway = next(e for e in evidence if e["source"] == "metrics" and e["service"] == "gateway")
    assert gateway["data"]["stats"]["error_ratio"]["max"] > 0.2


scenario_only = pytest.mark.skipif(SCENARIO != "bad-inventory-deploy", reason="scenario not active")


@scenario_only
def test_bad_inventory_deploy_is_visible_in_every_source(client: TestClient) -> None:
    def check() -> None:
        bundle = client.get("/v1/evidence").json()
        assert bundle["errors"] == []
        assert_bad_deploy_evidence(bundle["evidence"])

    eventually(check)


@scenario_only
def test_incident_snapshot_preserves_bad_deploy_evidence(client: TestClient) -> None:
    eventually(lambda: assert_bad_deploy_evidence(client.get("/v1/evidence").json()["evidence"]))
    end = datetime.now(UTC)
    window = {"start": (end - timedelta(minutes=15)).isoformat(), "end": end.isoformat()}

    created = client.post(
        "/v1/incidents",
        json={"title": f"Integration: bad inventory {RELEASE} deploy", "window": window},
    )

    assert created.status_code == 201, created.json()
    incident = created.json()
    [summary] = incident["snapshots"]
    assert summary["source_errors"] == []
    snapshot = client.get(f"/v1/incidents/{incident['id']}/snapshots/{summary['id']}").json()
    assert_bad_deploy_evidence(snapshot["evidence"])
