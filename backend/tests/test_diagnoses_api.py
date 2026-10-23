"""Diagnosis API against the test database, with a fake model (no API calls)."""

from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.diagnosis.llm import LLMError
from tests import fakes
from tests.diagnosis_fakes import FakeModel, output_citing, reply


@pytest.fixture
def model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def make_client(make_db_client: Callable[..., TestClient], model: FakeModel):
    def make(**settings) -> TestClient:
        client = make_db_client(**settings)
        client.app.state.diagnosis_model = model
        return client

    return make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def snapshot_url(client: TestClient) -> tuple[str, list[str]]:
    """Create an incident from the recorded fixtures; return its snapshot URL and evidence IDs."""
    incident = client.post(
        "/v1/incidents", json={"title": "Checkout failing", "window": fakes.window()}
    ).json()
    url = f"/v1/incidents/{incident['id']}/snapshots/{incident['snapshots'][0]['id']}"
    ids = [e["id"] for e in client.get(url).json()["evidence"]]
    return url, ids


def test_valid_diagnosis_is_stored_with_usage_and_cost(
    client: TestClient, model: FakeModel
) -> None:
    url, ids = snapshot_url(client)
    model.next = reply(output_citing(ids))

    response = client.post(f"{url}/diagnoses")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "valid"
    assert body["validation_errors"] == []
    assert body["output"]["root_cause"]["service"] == "inventory"
    assert (body["model_requested"], body["model_used"], body["effort"]) == (
        "claude-opus-5-5",
        "claude-opus-5-5",
        "medium",
    )
    assert (body["input_tokens"], body["output_tokens"]) == (5_000, 3_000)
    assert Decimal(body["cost_usd"]) == Decimal("0.08")
    assert body["prompt_version"] == "3"
    assert body["completed_at"] is not None
    assert client.get(f"{url}/diagnoses/{body['id']}").json() == body
    assert [d["id"] for d in client.get(f"{url}/diagnoses").json()] == [body["id"]]


def test_model_receives_the_snapshot_evidence(client: TestClient, model: FakeModel) -> None:
    url, ids = snapshot_url(client)
    model.next = reply(output_citing(ids))

    client.post(f"{url}/diagnoses")

    [(system, user)] = model.calls
    assert "incident investigator" in system
    assert all(f'"id":"{evidence_id}"' in user for evidence_id in ids)


def test_unknown_citation_makes_diagnosis_invalid(client: TestClient, model: FakeModel) -> None:
    url, ids = snapshot_url(client)
    model.next = reply(output_citing([ids[0], "ev-invented"]))

    body = client.post(f"{url}/diagnoses").json()

    assert body["status"] == "invalid"
    assert any("ev-invented" in e for e in body["validation_errors"])
    assert body["output"] is not None  # kept for inspection, but not marked valid


def test_refusal_is_recorded(client: TestClient, model: FakeModel) -> None:
    url, _ = snapshot_url(client)
    model.next = reply(stop_reason="refusal", refusal_category="cyber", output_tokens=0)

    body = client.post(f"{url}/diagnoses").json()

    assert body["status"] == "refused"
    assert body["error_message"] == "request declined (category: cyber)"
    assert body["output"] is None


def test_unparseable_reply_is_an_error_but_still_costed(
    client: TestClient, model: FakeModel
) -> None:
    url, _ = snapshot_url(client)
    model.next = reply(stop_reason="max_tokens", parse_error="reply was cut off at max_tokens")

    body = client.post(f"{url}/diagnoses").json()

    assert body["status"] == "error"
    assert body["error_message"] == "reply was cut off at max_tokens"
    assert Decimal(body["cost_usd"]) == Decimal("0.08")


def test_api_error_before_processing_costs_nothing(client: TestClient, model: FakeModel) -> None:
    url, _ = snapshot_url(client)
    model.next = LLMError("Claude API returned HTTP 529: overloaded", may_have_billed=False)

    body = client.post(f"{url}/diagnoses").json()

    assert body["status"] == "error"
    assert "529" in body["error_message"]
    assert Decimal(body["cost_usd"]) == 0


def test_timeout_keeps_its_reservation_against_the_budget(make_client, model: FakeModel) -> None:
    # Worst case per request is about $0.33; a timeout must keep counting it.
    client = make_client(llm_daily_budget_usd=0.5)
    url, ids = snapshot_url(client)
    model.next = LLMError("Claude API request failed: APITimeoutError", may_have_billed=True)

    first = client.post(f"{url}/diagnoses").json()
    model.next = reply(output_citing(ids))
    second = client.post(f"{url}/diagnoses")

    assert first["status"] == "error" and first["cost_usd"] is None
    assert second.status_code == 429


def test_budget_is_checked_before_calling_the_model(make_client, model: FakeModel) -> None:
    client = make_client(llm_daily_budget_usd=0.01)
    url, ids = snapshot_url(client)
    model.next = reply(output_citing(ids))

    response = client.post(f"{url}/diagnoses")

    assert response.status_code == 429
    assert "daily LLM budget" in response.json()["detail"]
    assert model.calls == []
    assert client.get(f"{url}/diagnoses").json() == []


def test_budget_counts_earlier_spend(make_client, model: FakeModel) -> None:
    # $0.40 budget: the first run reserves ~$0.33 and settles at $0.08; the second
    # needs $0.08 spent + ~$0.33 reserved > $0.40.
    client = make_client(llm_daily_budget_usd=0.4)
    url, ids = snapshot_url(client)
    model.next = reply(output_citing(ids))

    assert client.post(f"{url}/diagnoses").status_code == 201
    assert client.post(f"{url}/diagnoses").status_code == 429
    assert len(model.calls) == 1


def test_without_api_key_diagnoses_are_unavailable(client: TestClient) -> None:
    url, _ = snapshot_url(client)
    client.app.state.diagnosis_model = None

    response = client.post(f"{url}/diagnoses")

    assert response.status_code == 503
    assert response.json()["detail"] == "ANTHROPIC_API_KEY is not set"


def test_unknown_snapshot_or_diagnosis_returns_404(client: TestClient, model: FakeModel) -> None:
    url, ids = snapshot_url(client)
    other_url, _ = snapshot_url(client)
    model.next = reply(output_citing(ids))
    diagnosis = client.post(f"{url}/diagnoses").json()
    missing = "00000000-0000-0000-0000-000000000000"
    incident_url = url.rsplit("/snapshots/", 1)[0]

    assert client.post(f"{incident_url}/snapshots/{missing}/diagnoses").status_code == 404
    assert client.get(f"{other_url}/diagnoses/{diagnosis['id']}").status_code == 404
    assert client.get(f"{url}/diagnoses/{missing}").status_code == 404


def test_incidents_report_their_latest_diagnosis(client: TestClient, model: FakeModel) -> None:
    url, ids = snapshot_url(client)
    incident_url = url.split("/snapshots/")[0]
    assert client.get(incident_url).json()["latest_diagnosis"] is None

    model.next = reply(output_citing(ids))
    first = client.post(f"{url}/diagnoses").json()
    model.next = reply(None, stop_reason="refusal", refusal_category="cyber")
    second = client.post(f"{url}/diagnoses").json()

    latest = client.get(incident_url).json()["latest_diagnosis"]
    assert latest["id"] == second["id"] != first["id"]
    assert (latest["status"], latest["root_cause_service"], latest["confidence"]) == (
        "refused",
        None,
        None,
    )
    listed = client.get("/v1/incidents").json()["items"][0]["latest_diagnosis"]
    assert listed == latest


def test_budget_reports_spend_and_typical_cost(make_client, model: FakeModel) -> None:
    client = make_client(llm_daily_budget_usd=1.0)
    before = client.get("/v1/budget").json()
    assert Decimal(before["spent_usd"]) == 0
    assert Decimal(before["remaining_usd"]) == 1
    assert before["typical_cost_usd"] is None
    assert before["enabled"] is True

    url, ids = snapshot_url(client)
    model.next = reply(output_citing(ids))
    client.post(f"{url}/diagnoses")

    after = client.get("/v1/budget").json()
    assert Decimal(after["spent_usd"]) == Decimal("0.08")
    assert Decimal(after["remaining_usd"]) == Decimal("0.92")
    assert Decimal(after["typical_cost_usd"]) == Decimal("0.08")


def test_budget_without_a_model_is_disabled(client: TestClient) -> None:
    client.app.state.diagnosis_model = None
    body = client.get("/v1/budget").json()
    assert (body["enabled"], body["model"]) == (False, None)


def test_offline_provider_runs_the_full_flow_at_no_cost(
    make_db_client: Callable[..., TestClient],
) -> None:
    client = make_db_client(llm_provider="offline")
    url, ids = snapshot_url(client)

    body = client.post(f"{url}/diagnoses").json()

    assert body["status"] == "valid"
    assert body["model_used"] == "offline-stand-in"
    assert Decimal(body["cost_usd"]) == 0
    assert body["output"]["root_cause"]["evidence_ids"] == ids[:2]
    assert body["output"]["summary"].startswith("Offline stand-in")


def test_an_action_citing_a_failed_source_is_valid(
    make_client, model: FakeModel, transport: fakes.FixtureTransport
) -> None:
    transport.overrides["opensearch_search_otel_logs"] = 500
    client = make_client()
    url, ids = snapshot_url(client)
    output = output_citing(ids)
    output.recommended_actions[0].evidence_ids = ["src-logs"]
    model.next = reply(output)

    body = client.post(f"{url}/diagnoses").json()

    assert (body["status"], body["validation_errors"]) == ("valid", [])
    assert "src-logs: " in model.calls[0][1]
