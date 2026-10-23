"""Error and slow traces from Jaeger, with per-span self time.

Self time (a span's duration minus time covered by its children) shows where
latency was actually spent: a slow request whose time is mostly in one
service's own span points at that service, not its callers.
"""

import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from app.evidence import thresholds
from app.evidence.formatting import secs, ts
from app.evidence.models import Evidence, EvidenceSource, TimeWindow
from app.integrations.jaeger import JaegerClient, Span, Trace

TRACES_PER_QUERY = 20
EXAMPLE_TRACES_PER_PATTERN = 3


class SpanTime(BaseModel):
    service: str
    operation: str
    self_time_s: float
    release: str | None


class TraceSummary(BaseModel):
    trace_id: str
    start: datetime
    root_service: str
    root_operation: str
    duration_s: float
    status_code: int | None
    error_path: list[tuple[str, str, int | None]]  # failing server spans, caller first
    top_self_time: list[SpanTime]
    releases: dict[str, str]

    @property
    def dominant(self) -> SpanTime | None:
        """Where a slow trace spent its time. Not meaningful for fast traces."""
        if self.duration_s * 1000 < thresholds.SLOW_TRACE_MS or not self.top_self_time:
            return None
        return self.top_self_time[0]

    @property
    def signature(self) -> tuple[Any, ...]:
        dominant = self.dominant
        return (
            self.root_service,
            self.root_operation,
            self.status_code,
            tuple(self.error_path),
            (dominant.service, dominant.operation) if dominant else None,
        )


def self_time(span: Span, children: list[Span]) -> timedelta:
    """Span duration minus the union of its children's intervals, clipped to the span."""
    intervals = sorted(
        (max(c.start, span.start), min(c.end, span.end))
        for c in children
        if c.end > span.start and c.start < span.end
    )
    covered = timedelta()
    current_start = current_end = None
    for start, end in intervals:
        if current_end is None or start > current_end:
            if current_end is not None:
                covered += current_end - current_start
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None:
        covered += current_end - current_start
    return span.end - span.start - covered


def summarize(trace: Trace) -> TraceSummary | None:
    """Summarize a trace, or return None if it is incomplete (no root span yet).

    Spans arrive in Jaeger independently, so a recent trace can be missing its
    root span; summarizing it would misattribute where the request started.
    """
    roots = [s for s in trace.spans if s.parent_id is None]
    if not roots:
        return None
    root = min(roots, key=lambda s: s.start)
    children: dict[str, list[Span]] = defaultdict(list)
    for span in trace.spans:
        if span.parent_id:
            children[span.parent_id].append(span)

    times = sorted(
        (
            SpanTime(
                service=s.service,
                operation=s.operation,
                self_time_s=self_time(s, children[s.span_id]).total_seconds(),
                release=s.attributes.get("app.release"),
            )
            for s in trace.spans
        ),
        key=lambda t: -t.self_time_s,
    )
    releases = {
        s.service: str(s.attributes["app.release"])
        for s in trace.spans
        if "app.release" in s.attributes
    }
    # Server spans describe each service's own result; client spans repeat them.
    failing = sorted(
        (s for s in trace.spans if s.error and s.attributes.get("span.kind") == "server"),
        key=lambda s: s.start,
    )
    error_path = list(dict.fromkeys((s.service, s.operation, s.status_code) for s in failing))
    return TraceSummary(
        trace_id=trace.trace_id,
        start=root.start,
        root_service=root.service,
        root_operation=root.operation,
        duration_s=root.duration_us / 1_000_000,
        status_code=root.status_code,
        error_path=error_path,
        top_self_time=times[:3],
        releases=releases,
    )


def describe_path(error_path: list[tuple[str, str, int | None]]) -> str:
    return " <- ".join(
        f"{service} {operation}" + (f" ({code})" if code else "")
        for service, operation, code in error_path
    )


class TracesCollector:
    source = EvidenceSource.TRACES

    def __init__(self, client: JaegerClient) -> None:
        self._client = client

    async def collect(self, window: TimeWindow, services: list[str] | None) -> list[Evidence]:
        targets = services or await self._client.services()
        searches = [
            self._client.find_traces(
                service, window.start, window.end, limit=TRACES_PER_QUERY, **filters
            )
            for service in targets
            for filters in (
                {"tags": {"error": "true"}},
                {"min_duration_ms": thresholds.SLOW_TRACE_MS},
            )
        ]
        # A trace can match several searches (error and slow, or via several services).
        found: dict[str, Trace] = {
            trace.trace_id: trace for result in await asyncio.gather(*searches) for trace in result
        }

        all_summaries = [summarize(trace) for trace in found.values()]
        summaries = [s for s in all_summaries if s]
        incomplete = len(all_summaries) - len(summaries)
        groups: dict[tuple[Any, ...], list[TraceSummary]] = defaultdict(list)
        for summary in summaries:
            groups[summary.signature].append(summary)

        query = (
            f"Jaeger /api/traces for services {sorted(targets)}: tags error=true, and "
            f"minDuration={thresholds.SLOW_TRACE_MS}ms; limit {TRACES_PER_QUERY} per query"
        )
        return [
            self._pattern(group, len(summaries), incomplete, window, query)
            for group in sorted(groups.values(), key=len, reverse=True)
        ]

    def _pattern(
        self,
        group: list[TraceSummary],
        total: int,
        incomplete: int,
        window: TimeWindow,
        query: str,
    ) -> Evidence:
        first = group[0]
        durations = [t.duration_s for t in group]
        dominant = first.dominant
        dominant_times = [t.dominant.self_time_s for t in group if t.dominant]
        releases = Counter(f"{svc}={rel}" for t in group for svc, rel in sorted(t.releases.items()))

        parts = [
            f"{len(group)} of {total} sampled error/slow traces:",
            f"{first.root_service} {first.root_operation}"
            + (f" returned {first.status_code}" if first.status_code else ""),
            f"in {secs(min(durations))}-{secs(max(durations))}",
        ]
        if first.error_path:
            parts.append(f"; failing: {describe_path(first.error_path)}")
        if dominant:
            avg = sum(dominant_times) / len(dominant_times)
            parts.append(
                f"; most self time in {dominant.service} {dominant.operation} (avg {secs(avg)}"
                + (f", release {dominant.release}" if dominant.release else "")
                + ")"
            )
        examples = sorted(group, key=lambda t: -t.duration_s)[:EXAMPLE_TRACES_PER_PATTERN]
        return Evidence.build(
            source=self.source,
            kind="trace_pattern",
            key=repr(first.signature),
            window=window,
            service=dominant.service if dominant else first.root_service,
            observed_at=min(t.start for t in group),
            summary=" ".join(parts).replace(" ;", ";"),
            query=query,
            reference=self._client.trace_url(examples[0].trace_id),
            data={
                "trace_count": len(group),
                "sampled_traces": total,
                "incomplete_traces_skipped": incomplete,
                "root": {
                    "service": first.root_service,
                    "operation": first.root_operation,
                    "status_code": first.status_code,
                },
                "error_path": first.error_path,
                "duration_s": {"min": min(durations), "max": max(durations)},
                "dominant_self_time": dominant.model_dump() if dominant else None,
                "releases": dict(releases),
                "first_seen": ts(min(t.start for t in group)),
                "last_seen": ts(max(t.start for t in group)),
                "example_traces": [
                    {
                        "trace_id": t.trace_id,
                        "url": self._client.trace_url(t.trace_id),
                        "start": ts(t.start),
                        "duration_s": t.duration_s,
                        "top_self_time": [s.model_dump() for s in t.top_self_time],
                    }
                    for t in examples
                ],
            },
        )
