"""Collectors against responses recorded during a bad inventory deploy.

The fixtures were recorded while inventory release 3.2.0 added ~2.5s latency
(past the orders service's 2s timeout), shortly after a burst of injected
inventory 500s. See tests/record_fixtures.py.
"""

import asyncio
from datetime import datetime

import httpx
import pytest

from app.config import Settings
from app.evidence.deployments import DeploymentsCollector
from app.evidence.logs import LogsCollector
from app.evidence.metrics import MetricsCollector
from app.evidence.models import Evidence, TimeWindow
from app.evidence.traces import TracesCollector
from app.integrations.jaeger import JaegerClient
from app.integrations.opensearch import OpenSearchClient
from app.integrations.prometheus import PrometheusClient
from tests import fakes

SETTINGS = Settings()


@pytest.fixture
def window() -> TimeWindow:
    w = fakes.window()
    return TimeWindow(
        start=datetime.fromisoformat(w["start"]), end=datetime.fromisoformat(w["end"])
    )


@pytest.fixture
def transport() -> fakes.FixtureTransport:
    return fakes.FixtureTransport()


@pytest.fixture
def http(transport: fakes.FixtureTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport)


def collect(collector, window: TimeWindow, services=None) -> list[Evidence]:
    return asyncio.run(collector.collect(window, services))


def by_service(evidence: list[Evidence]) -> dict[str, Evidence]:
    return {e.service: e for e in evidence}


class TestMetrics:
    def test_one_record_per_service_with_onsets(self, http, window) -> None:
        evidence = by_service(
            collect(MetricsCollector(PrometheusClient(SETTINGS.prometheus_url, http)), window)
        )

        assert set(evidence) == {"gateway", "orders", "inventory"}
        gateway = evidence["gateway"]
        assert gateway.kind == "service_http_metrics"
        assert gateway.data["stats"]["error_ratio"]["max"] > 0.5
        assert gateway.data["p95_latency_onset"] is not None
        assert gateway.observed_at is not None
        assert "5xx ratio" in gateway.summary and "p95 latency" in gateway.summary
        assert gateway.reference.startswith(SETTINGS.prometheus_url + "/api/v1/query_range?")

    def test_service_filter(self, http, window) -> None:
        collector = MetricsCollector(PrometheusClient(SETTINGS.prometheus_url, http))
        assert set(by_service(collect(collector, window, ["orders"]))) == {"orders"}


class TestTraces:
    def test_timeout_cascade_attributed_to_slow_inventory_release(self, http, window) -> None:
        evidence = collect(TracesCollector(JaegerClient(SETTINGS.jaeger_url, http)), window)
        slow = [
            e
            for e in evidence
            if (e.data["dominant_self_time"] or {}).get("service") == "inventory"
        ]

        assert slow, [e.summary for e in evidence]
        top = slow[0]
        assert top.data["dominant_self_time"]["operation"] == "POST /reserve"
        assert top.data["dominant_self_time"]["release"] == "3.2.0"
        assert top.data["dominant_self_time"]["self_time_s"] > 2.0
        assert [tuple(step)[:2] for step in top.data["error_path"]] == [
            ("gateway", "POST /checkout"),
            ("orders", "POST /orders"),
        ]
        assert top.reference.startswith(SETTINGS.jaeger_url + "/trace/")

    def test_error_burst_shows_full_failing_path(self, http, window) -> None:
        evidence = collect(TracesCollector(JaegerClient(SETTINGS.jaeger_url, http)), window)
        paths = [[step[0] for step in e.data["error_path"]] for e in evidence]

        assert ["gateway", "orders", "inventory"] in paths

    def test_queries_only_requested_services(self, http, transport, window) -> None:
        collect(TracesCollector(JaegerClient(SETTINGS.jaeger_url, http)), window, ["orders"])

        services = {r.url.params.get("service") for r in transport.requests}
        assert services == {"orders"}


class TestLogs:
    def test_patterns_carry_counts_and_trace_ids(self, http, window) -> None:
        collector = LogsCollector(
            OpenSearchClient(SETTINGS.opensearch_url, http), SETTINGS.logs_index
        )
        evidence = collect(collector, window)
        messages = {(e.service, e.data["message"]): e for e in evidence}

        timeout = messages[("orders", "timed out reserving inventory")]
        assert timeout.data["count"] > 0
        assert timeout.data["example_trace_ids"]
        assert timeout.observed_at is not None
        counts = [e.data["count"] for e in evidence]
        assert counts == sorted(counts, reverse=True)

    def test_missing_index_means_no_logs(self, window) -> None:
        transport = fakes.FixtureTransport({"opensearch_search_otel_logs": 404})
        client = OpenSearchClient(SETTINGS.opensearch_url, httpx.AsyncClient(transport=transport))
        assert collect(LogsCollector(client, SETTINGS.logs_index), window) == []


class TestDeployments:
    def test_deploy_event(self, http, window) -> None:
        collector = DeploymentsCollector(
            OpenSearchClient(SETTINGS.opensearch_url, http), SETTINGS.deploy_events_index
        )
        [deploy] = collect(collector, window)

        assert deploy.service == "inventory"
        assert deploy.data["version"] == "3.2.0"
        assert "inventory deployed" in deploy.summary
        assert deploy.reference.startswith(SETTINGS.opensearch_url + "/deploy-events/_doc/")

    def test_missing_index_means_no_deployments(self, window) -> None:
        transport = fakes.FixtureTransport({"opensearch_search_deploy_events": 404})
        client = OpenSearchClient(SETTINGS.opensearch_url, httpx.AsyncClient(transport=transport))
        assert collect(DeploymentsCollector(client, SETTINGS.deploy_events_index), window) == []
