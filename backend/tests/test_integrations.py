"""Backend clients: error mapping and response parsing."""

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from app.integrations.base import BackendError, NotFoundError
from app.integrations.jaeger import JaegerClient
from app.integrations.prometheus import PrometheusClient

START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, 0, 10, tzinfo=UTC)


def client_for(cls, handler):
    return cls("http://backend:1234/", httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    ("handler", "error", "message"),
    [
        (lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")), BackendError, "reach"),
        (lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow")), BackendError, "timed out"),
        (lambda r: httpx.Response(500, text="boom"), BackendError, "HTTP 500"),
        (lambda r: httpx.Response(404), NotFoundError, "not found"),
        (lambda r: httpx.Response(200, text="not json"), BackendError, "invalid JSON"),
    ],
)
def test_failures_become_backend_errors(handler, error, message) -> None:
    prometheus = client_for(PrometheusClient, handler)

    with pytest.raises(error, match=message) as exc_info:
        run(prometheus.query_range("up", START, END, 15))

    assert exc_info.value.backend == "prometheus"


def test_prometheus_drops_non_finite_points() -> None:
    body = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [{"metric": {"job": "a"}, "values": [[1, "0.5"], [2, "NaN"], [3, "+Inf"]]}],
        },
    }
    prometheus = client_for(PrometheusClient, lambda r: httpx.Response(200, json=body))

    [series] = run(prometheus.query_range("x", START, END, 15))

    assert [v for _, v in series.points] == [0.5]


def test_prometheus_query_error_is_reported() -> None:
    body = {"status": "error", "error": "parse error", "data": {"resultType": "matrix"}}
    prometheus = client_for(PrometheusClient, lambda r: httpx.Response(200, json=body))

    with pytest.raises(BackendError, match="parse error"):
        run(prometheus.query_range("bad(", START, END, 15))


def test_jaeger_hides_its_own_service() -> None:
    body = {"data": ["orders", "jaeger", "gateway"]}
    jaeger = client_for(JaegerClient, lambda r: httpx.Response(200, json=body))

    assert run(jaeger.services()) == ["gateway", "orders"]


def test_jaeger_parses_spans() -> None:
    body = {
        "data": [
            {
                "traceID": "t1",
                "processes": {"p1": {"serviceName": "gateway"}, "p2": {"serviceName": "orders"}},
                "spans": [
                    {
                        "spanID": "a",
                        "processID": "p1",
                        "operationName": "POST /checkout",
                        "startTime": 1_000_000,
                        "duration": 500_000,
                        "references": [],
                        "tags": [
                            {"key": "error", "value": True},
                            {"key": "http.response.status_code", "value": 502},
                        ],
                    },
                    {
                        "spanID": "b",
                        "processID": "p2",
                        "operationName": "POST /orders",
                        "startTime": 1_100_000,
                        "duration": 300_000,
                        "references": [{"refType": "CHILD_OF", "spanID": "a"}],
                        "tags": [{"key": "otel.status_code", "value": "ERROR"}],
                    },
                ],
            }
        ]
    }
    jaeger = client_for(JaegerClient, lambda r: httpx.Response(200, json=body))

    [trace] = run(jaeger.find_traces("gateway", START, END, tags={"error": "true"}))
    root, child = trace.spans

    assert (root.parent_id, root.error, root.status_code) == (None, True, 502)
    assert (child.service, child.parent_id, child.error, child.status_code) == (
        "orders",
        "a",
        True,
        None,
    )
