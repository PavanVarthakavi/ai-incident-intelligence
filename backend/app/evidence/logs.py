"""Warning and error log patterns from OpenSearch, grouped by service and message."""

import json
from datetime import datetime

from app.evidence.formatting import ts
from app.evidence.models import Evidence, EvidenceSource, TimeWindow
from app.integrations.base import NotFoundError
from app.integrations.opensearch import OpenSearchClient

WARN_SEVERITY_NUMBER = 13  # OpenTelemetry severity numbers: 13-16 WARN, 17+ ERROR
MAX_SERVICES = 20
MAX_MESSAGES_PER_SERVICE = 10
EXAMPLE_TRACES = 3


def build_query(window: TimeWindow, services: list[str] | None) -> dict:
    filters: list[dict] = [
        {"range": {"@timestamp": {"gte": window.start.isoformat(), "lt": window.end.isoformat()}}},
        {"range": {"severity.number": {"gte": WARN_SEVERITY_NUMBER}}},
    ]
    if services:
        filters.append({"terms": {"resource.service.name": services}})
    return {
        "size": 0,
        "query": {"bool": {"filter": filters}},
        "aggs": {
            "services": {
                "terms": {"field": "resource.service.name", "size": MAX_SERVICES},
                "aggs": {
                    "messages": {
                        "terms": {"field": "body.keyword", "size": MAX_MESSAGES_PER_SERVICE},
                        "aggs": {
                            "first_seen": {"min": {"field": "@timestamp"}},
                            "last_seen": {"max": {"field": "@timestamp"}},
                            "severity": {"terms": {"field": "severity.text", "size": 3}},
                            "releases": {"terms": {"field": "attributes.release", "size": 3}},
                            "examples": {
                                "top_hits": {
                                    "size": EXAMPLE_TRACES,
                                    "sort": [{"@timestamp": "desc"}],
                                    "_source": ["traceId", "@timestamp"],
                                }
                            },
                        },
                    }
                },
            }
        },
    }


def _time(bucket: dict) -> datetime:
    return datetime.fromisoformat(bucket["value_as_string"].replace("Z", "+00:00"))


class LogsCollector:
    source = EvidenceSource.LOGS

    def __init__(self, client: OpenSearchClient, index: str) -> None:
        self._client = client
        self._index = index

    async def collect(self, window: TimeWindow, services: list[str] | None) -> list[Evidence]:
        query = build_query(window, services)
        try:
            result = await self._client.search(self._index, query)
        except NotFoundError:
            return []  # no logs have been written yet

        evidence = []
        for service_bucket in result["aggregations"]["services"]["buckets"]:
            service = service_bucket["key"]
            for msg in service_bucket["messages"]["buckets"]:
                evidence.append(self._pattern(service, msg, window, query))
        return sorted(evidence, key=lambda e: -e.data["count"])

    def _pattern(self, service: str, msg: dict, window: TimeWindow, query: dict) -> Evidence:
        first, last = _time(msg["first_seen"]), _time(msg["last_seen"])
        severity = "/".join(b["key"] for b in msg["severity"]["buckets"])
        releases = [b["key"] for b in msg["releases"]["buckets"]]
        trace_ids = [
            hit["_source"]["traceId"]
            for hit in msg["examples"]["hits"]["hits"]
            if hit["_source"].get("traceId")
        ]
        summary = (
            f"{service} logged {severity} {msg['key']!r} {msg['doc_count']} times "
            f"from {ts(first)} to {ts(last)}"
        )
        if releases:
            summary += f" (release {', '.join(releases)})"
        if trace_ids:
            summary += f"; example traces: {', '.join(trace_ids)}"
        return Evidence.build(
            source=self.source,
            kind="log_pattern",
            key=f"{service}|{msg['key']}",
            window=window,
            service=service,
            observed_at=first,
            summary=summary,
            query=f"POST /{self._index}/_search {json.dumps(query, separators=(',', ':'))}",
            data={
                "message": msg["key"],
                "count": msg["doc_count"],
                "severity": severity,
                "first_seen": ts(first),
                "last_seen": ts(last),
                "releases": releases,
                "example_trace_ids": trace_ids,
            },
        )
