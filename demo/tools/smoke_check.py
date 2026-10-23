#!/usr/bin/env python3
"""Verify the demo stack end to end: services up and telemetry landing in every backend.

    python demo/tools/smoke_check.py            # check once
    python demo/tools/smoke_check.py --wait 180 # retry until passing or 180s elapse

Exits non-zero if any check fails.
"""

import argparse
import os
import sys
import time
import urllib.parse
from collections.abc import Callable

from _http import HttpError, request

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")
PROMETHEUS = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
JAEGER = os.getenv("JAEGER_URL", "http://localhost:16686")
OPENSEARCH = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
SERVICES = {"gateway", "orders", "inventory"}


def check_gateway() -> str:
    request("GET", f"{GATEWAY}/health")
    return "gateway healthy"


def check_prometheus() -> str:
    query = "sum by (job) (rate(http_server_request_duration_seconds_count[2m]))"
    url = f"{PROMETHEUS}/api/v1/query?query={urllib.parse.quote(query)}"
    jobs = {r["metric"]["job"].split("/")[-1] for r in request("GET", url)["data"]["result"]}
    missing = SERVICES - jobs
    if missing:
        raise AssertionError(f"no request-rate metrics for {sorted(missing)}")
    return f"request-rate metrics for {sorted(jobs)}"


def check_jaeger() -> str:
    services = set(request("GET", f"{JAEGER}/api/services")["data"] or [])
    if not SERVICES <= services:
        raise AssertionError(f"Jaeger services {sorted(services)}; expected {sorted(SERVICES)}")
    url = f"{JAEGER}/api/traces?service=gateway&operation=POST%20%2Fcheckout&limit=20&lookback=5m"
    traces = request("GET", url)["data"]
    for trace in traces:
        seen = {p["serviceName"] for p in trace["processes"].values()}
        if SERVICES <= seen:
            return f"distributed checkout trace {trace['traceID']} spans {sorted(seen)}"
    raise AssertionError(f"no checkout trace spanning all services among {len(traces)} traces")


def check_opensearch_logs() -> str:
    query = {
        "size": 0,
        "query": {"range": {"@timestamp": {"gte": "now-5m"}}},
        "aggs": {"services": {"terms": {"field": "resource.service.name"}}},
    }
    result = request("POST", f"{OPENSEARCH}/otel-logs/_search", query)
    services = {b["key"] for b in result["aggregations"]["services"]["buckets"]}
    if not services:
        raise AssertionError("no logs in the last 5 minutes")
    return f"{result['hits']['total']['value']} logs in last 5m from {sorted(services)}"


CHECKS: list[tuple[str, Callable[[], str]]] = [
    ("gateway", check_gateway),
    ("prometheus", check_prometheus),
    ("jaeger", check_jaeger),
    ("opensearch", check_opensearch_logs),
]


def run_checks() -> list[str]:
    lines = []
    for name, check in CHECKS:
        try:
            lines.append(f"PASS {name:<11} {check()}")
        except (AssertionError, HttpError, KeyError) as exc:
            lines.append(f"FAIL {name:<11} {exc}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the demo stack end to end.")
    parser.add_argument("--wait", type=float, default=0, help="Seconds to keep retrying.")
    args = parser.parse_args()

    deadline = time.monotonic() + args.wait
    while True:
        lines = run_checks()
        failed = any(line.startswith("FAIL") for line in lines)
        if not failed or time.monotonic() >= deadline:
            break
        time.sleep(10)
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
