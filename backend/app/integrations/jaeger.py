"""Jaeger query client.

Uses Jaeger's ``/api`` JSON endpoints (the ones its UI uses). The stable
``/api/v3`` endpoint was evaluated first, but in Jaeger 2.3 it silently ignores
attribute filters, so error traces could not be selected server-side. See
docs/architecture.md (D-015).
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from app.integrations.base import JsonHttpClient

# Jaeger reports its own traces; they are never evidence about the application.
INTERNAL_SERVICES = {"jaeger"}


class Span(BaseModel):
    span_id: str
    parent_id: str | None
    service: str
    operation: str
    start: datetime
    duration_us: int
    error: bool
    status_code: int | None
    attributes: dict[str, Any]

    @property
    def end(self) -> datetime:
        return self.start + timedelta(microseconds=self.duration_us)


class Trace(BaseModel):
    trace_id: str
    spans: list[Span]


def _parse_trace(raw: dict[str, Any]) -> Trace:
    processes = {pid: p["serviceName"] for pid, p in raw["processes"].items()}
    spans = []
    for s in raw["spans"]:
        tags = {t["key"]: t["value"] for t in s.get("tags", [])}
        parent = next(
            (r["spanID"] for r in s.get("references", []) if r["refType"] == "CHILD_OF"), None
        )
        status = tags.get("http.response.status_code")
        spans.append(
            Span(
                span_id=s["spanID"],
                parent_id=parent,
                service=processes[s["processID"]],
                operation=s["operationName"],
                start=datetime.fromtimestamp(s["startTime"] / 1_000_000, UTC),
                duration_us=s["duration"],
                error=tags.get("error") is True or tags.get("otel.status_code") == "ERROR",
                status_code=int(status) if status is not None else None,
                attributes=tags,
            )
        )
    return Trace(trace_id=raw["traceID"], spans=spans)


class JaegerClient(JsonHttpClient):
    name = "jaeger"

    async def ping(self) -> None:
        await self.get_json("/api/services")

    async def services(self) -> list[str]:
        body = await self.get_json("/api/services")
        return sorted(set(body.get("data") or []) - INTERNAL_SERVICES)

    async def find_traces(
        self,
        service: str,
        start: datetime,
        end: datetime,
        *,
        tags: dict[str, str] | None = None,
        min_duration_ms: int | None = None,
        limit: int = 20,
    ) -> list[Trace]:
        params: dict[str, Any] = {
            "service": service,
            "start": int(start.timestamp() * 1_000_000),
            "end": int(end.timestamp() * 1_000_000),
            "limit": limit,
        }
        if tags:
            params["tags"] = json.dumps(tags)
        if min_duration_ms is not None:
            params["minDuration"] = f"{min_duration_ms}ms"
        body = await self.get_json("/api/traces", params=params)
        return [_parse_trace(raw) for raw in body.get("data") or []]

    def trace_url(self, trace_id: str) -> str:
        return self.url(f"/trace/{trace_id}")
