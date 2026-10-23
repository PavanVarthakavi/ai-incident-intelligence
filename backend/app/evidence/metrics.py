"""RED metrics (rate, errors, duration) per service from Prometheus."""

import asyncio
import urllib.parse
from datetime import datetime
from statistics import fmean

from app.evidence import thresholds
from app.evidence.formatting import pct, secs, ts
from app.evidence.models import Evidence, EvidenceSource, TimeWindow
from app.integrations.prometheus import PrometheusClient, Series

TARGET_POINTS = 60
MIN_STEP_S = 15
METRIC = "http_server_request_duration_seconds"


def step_for(window: TimeWindow) -> int:
    return max(MIN_STEP_S, int(window.duration.total_seconds() // TARGET_POINTS))


def queries(rate_window: str) -> dict[str, str]:
    total = f"sum by (job) (rate({METRIC}_count[{rate_window}]))"
    errors = (
        f'sum by (job) (rate({METRIC}_count{{http_response_status_code=~"5.."}}[{rate_window}]))'
    )
    return {
        "request_rate_rps": total,
        # `or ... * 0` yields 0 instead of no data when a service has no 5xx responses.
        "error_ratio": f"({errors} or {total} * 0) / {total}",
        "p95_latency_s": (
            f"histogram_quantile(0.95, sum by (job, le) (rate({METRIC}_bucket[{rate_window}])))"
        ),
    }


def service_name(job: str) -> str:
    # The collector sets job to "<service.namespace>/<service.name>".
    return job.rsplit("/", 1)[-1]


def first_crossing(points: list[tuple[datetime, float]], threshold: float) -> datetime | None:
    """First time the value rises to or above the threshold from below it.

    Returns the window start if the value is already above the threshold there.
    """
    previous_below = False
    for index, (at, value) in enumerate(points):
        if value >= threshold and (previous_below or index == 0):
            return at
        previous_below = value < threshold
    return None


def onset_text(onset: datetime, points: list[tuple[datetime, float]], threshold: str) -> str:
    if onset == points[0][0]:
        return f"already at or above {threshold} at window start"
    return f"first at or above {threshold} at {ts(onset)}"


def stats(points: list[tuple[datetime, float]]) -> dict[str, float]:
    values = [v for _, v in points]
    return {"avg": fmean(values), "max": max(values), "last": values[-1]}


class MetricsCollector:
    source = EvidenceSource.METRICS

    def __init__(self, client: PrometheusClient) -> None:
        self._client = client

    async def collect(self, window: TimeWindow, services: list[str] | None) -> list[Evidence]:
        step = step_for(window)
        rate_window = f"{max(60, 2 * step)}s"
        promql = queries(rate_window)

        results = await asyncio.gather(
            *(self._client.query_range(q, window.start, window.end, step) for q in promql.values())
        )
        by_service: dict[str, dict[str, Series]] = {}
        for name, result in zip(promql, results, strict=True):
            for series in result:
                service = service_name(series.labels.get("job", ""))
                if series.points and (services is None or service in services):
                    by_service.setdefault(service, {})[name] = series

        return [
            self._evidence(service, signals, window, step, promql)
            for service, signals in sorted(by_service.items())
            if "request_rate_rps" in signals
        ]

    def _evidence(
        self,
        service: str,
        signals: dict[str, Series],
        window: TimeWindow,
        step: int,
        promql: dict[str, str],
    ) -> Evidence:
        summary_stats = {name: stats(s.points) for name, s in signals.items()}
        error_onset = latency_onset = None
        parts = [f"{service}: {summary_stats['request_rate_rps']['avg']:.2f} req/s avg"]

        if "error_ratio" in signals:
            e = summary_stats["error_ratio"]
            parts.append(f"5xx ratio avg {pct(e['avg'])}, max {pct(e['max'])}")
            points = signals["error_ratio"].points
            error_onset = first_crossing(points, thresholds.ERROR_RATIO)
            if error_onset:
                parts.append(onset_text(error_onset, points, pct(thresholds.ERROR_RATIO)))
        if "p95_latency_s" in signals:
            p = summary_stats["p95_latency_s"]
            parts.append(f"p95 latency avg {secs(p['avg'])}, max {secs(p['max'])}")
            points = signals["p95_latency_s"].points
            latency_onset = first_crossing(points, thresholds.P95_LATENCY_S)
            if latency_onset:
                parts.append(onset_text(latency_onset, points, secs(thresholds.P95_LATENCY_S)))

        onsets = [t for t in (error_onset, latency_onset) if t]
        query_text = "\n".join(f"{name}: {q}" for name, q in promql.items())
        reference_query = urllib.parse.urlencode(
            {
                "query": promql["error_ratio"],
                "start": window.start.timestamp(),
                "end": window.end.timestamp(),
                "step": step,
            }
        )
        return Evidence.build(
            source=self.source,
            kind="service_http_metrics",
            key=service,
            window=window,
            service=service,
            observed_at=min(onsets) if onsets else None,
            summary="; ".join(parts),
            query=query_text,
            reference=self._client.url(f"/api/v1/query_range?{reference_query}"),
            data={
                "step_s": step,
                "stats": summary_stats,
                "error_ratio_onset": error_onset,
                "p95_latency_onset": latency_onset,
                "series": {
                    name: [(ts(at), round(v, 6)) for at, v in s.points]
                    for name, s in signals.items()
                },
            },
        )
