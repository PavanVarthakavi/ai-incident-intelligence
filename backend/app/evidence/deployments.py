"""Deployment events from OpenSearch.

Deploys shortly *before* the window are included, because a bad deploy usually
precedes the symptoms an investigation starts from.
"""

import json
from datetime import datetime, timedelta

from app.evidence.formatting import ts
from app.evidence.models import Evidence, EvidenceSource, TimeWindow
from app.integrations.base import NotFoundError
from app.integrations.opensearch import OpenSearchClient

DEFAULT_LOOKBACK = timedelta(hours=1)
MAX_EVENTS = 50


def describe_offset(at: datetime, window: TimeWindow) -> str:
    if at >= window.start:
        return "during the window"
    minutes = (window.start - at).total_seconds() / 60
    return f"{minutes:.0f} min before the window"


class DeploymentsCollector:
    source = EvidenceSource.DEPLOYMENTS

    def __init__(
        self, client: OpenSearchClient, index: str, lookback: timedelta = DEFAULT_LOOKBACK
    ) -> None:
        self._client = client
        self._index = index
        self._lookback = lookback

    async def collect(self, window: TimeWindow, services: list[str] | None) -> list[Evidence]:
        filters: list[dict] = [
            {
                "range": {
                    "@timestamp": {
                        "gte": (window.start - self._lookback).isoformat(),
                        "lt": window.end.isoformat(),
                    }
                }
            }
        ]
        if services:
            filters.append({"terms": {"service": services}})
        query = {
            "size": MAX_EVENTS,
            "sort": [{"@timestamp": "asc"}],
            "query": {"bool": {"filter": filters}},
        }
        try:
            result = await self._client.search(self._index, query)
        except NotFoundError:
            return []  # no deployments recorded yet

        query_text = f"POST /{self._index}/_search {json.dumps(query, separators=(',', ':'))}"
        return [self._evidence(hit, window, query_text) for hit in result["hits"]["hits"]]

    def _evidence(self, hit: dict, window: TimeWindow, query: str) -> Evidence:
        event = hit["_source"]
        at = datetime.fromisoformat(event["@timestamp"].replace("Z", "+00:00"))
        summary = (
            f"{event['service']} deployed {event.get('previous_version') or '?'} -> "
            f"{event['version']} at {ts(at)} ({describe_offset(at, window)}) "
            f"by {event.get('author', 'unknown')}"
        )
        if event.get("description"):
            summary += f": {event['description']!r}"
        return Evidence.build(
            source=self.source,
            kind="deployment",
            key=event.get("event_id", hit["_id"]),
            window=window,
            service=event["service"],
            observed_at=at,
            summary=summary,
            query=query,
            reference=self._client.doc_url(self._index, hit["_id"]),
            data={k: v for k, v in event.items() if k != "@timestamp"} | {"timestamp": ts(at)},
        )
