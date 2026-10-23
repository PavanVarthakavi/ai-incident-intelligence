"""Replay recorded backend responses (tests/fixtures/*.json) without a network.

Each request maps to a fixture name via ``route_key``. The recorder in
``tests/record_fixtures.py`` uses the same function, so recordings and replays
always agree.
"""

import json
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).parent / "fixtures"


def route_key(request: httpx.Request) -> str:
    path, params = request.url.path, request.url.params
    if path == "/api/v1/query_range":
        query = params["query"]
        if "histogram_quantile" in query:
            return "prometheus_p95"
        return "prometheus_error_ratio" if '"5.."' in query else "prometheus_rate"
    if path == "/api/traces":
        kind = "errors" if "tags" in params else "slow"
        return f"jaeger_traces_{params['service']}_{kind}"
    if path == "/api/services":
        return "jaeger_services"
    if path.endswith("/_search"):
        index = path.strip("/").split("/")[0]
        return f"opensearch_search_{index.replace('-', '_')}"
    if path == "/-/ready":
        return "prometheus_ready"
    if path == "/_cluster/health":
        return "opensearch_health"
    raise KeyError(f"no fixture route for {request.method} {request.url}")


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


class FixtureTransport(httpx.AsyncBaseTransport):
    """Serves recorded responses. ``overrides`` replaces a route with a status or handler."""

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self.overrides = overrides or {}
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = route_key(request)
        override = self.overrides.get(key)
        if callable(override):
            return override(request)
        if isinstance(override, int):
            return httpx.Response(override, json={"error": "simulated"})
        recorded = load(key)
        return httpx.Response(recorded["status"], json=recorded["body"])


def window() -> dict[str, str]:
    """The time window the fixtures were recorded for."""
    return load("meta")["window"]
