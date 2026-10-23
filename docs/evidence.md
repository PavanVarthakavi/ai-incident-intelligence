# Evidence Collection (Milestone 2)

The backend queries the observability backends for a time window and returns
normalized, citable **evidence**. This is the raw material the investigation
agent (M4) will reason over. Collection is read-only.

## API

```bash
cd backend && uvicorn app.main:app --reload       # needs the demo stack running

curl localhost:8000/ready                          # 200 if every backend answers, else 503
curl 'localhost:8000/v1/evidence'                  # last 15 minutes, all services
curl 'localhost:8000/v1/evidence?start=2026-10-23T05:00:00Z&end=2026-10-23T05:20:00Z&service=orders'
```

`GET /v1/evidence` parameters: `start`, `end` (ISO 8601 with timezone; default the last 15
minutes, maximum 24 hours) and `service` (repeatable; default all). Interactive docs are at
`/docs`.

The response is an `EvidenceBundle`:

```json
{
  "window": {"start": "...", "end": "..."},
  "services": null,
  "collected_at": "...",
  "evidence": [ { "id": "ev-3d721a74c1d3", "source": "logs", "kind": "log_pattern", "...": "..." } ],
  "errors": []
}
```

If a backend fails, its source appears in `errors` and the rest of the bundle is still
returned. Missing evidence is therefore distinguishable from "nothing found".

## The evidence record

| Field | Meaning |
|---|---|
| `id` | Stable ID (`ev-` + hash of source, kind, key, and window). Same inputs, same ID, so it can be cited. |
| `source` / `kind` | Where it came from and what it is (table below). |
| `service` | Service the observation is about, if any. |
| `observed_at` | When the behaviour started, when known (onset, first log, deploy time). |
| `summary` | One factual line computed from `data`; no interpretation. |
| `query` | The exact backend query, so the observation can be reproduced. |
| `reference` | URL to the raw data: Prometheus API query, Jaeger trace, or OpenSearch document. |
| `data` | Normalized values the summary was built from. |

## Sources

| Source | Kind | What it contains |
|---|---|---|
| Prometheus | `service_http_metrics` | Per service: request rate, 5xx ratio, p95 latency (avg/max/last), the time each first reached its threshold, and the series (~60 points). |
| Jaeger | `trace_pattern` | Error traces and traces slower than 1 s, grouped by failing path (server spans, caller first) and, for slow traces, the span with the most **self time** (its own duration minus its children's). Includes releases and example trace links. |
| OpenSearch logs | `log_pattern` | WARN/ERROR logs grouped by service and exact message: count, first/last seen, release, example trace IDs. |
| OpenSearch deploys | `deployment` | Deploy events in the window and up to 1 hour before it (a bad deploy usually precedes symptoms). |

Thresholds used only for flagging onsets in summaries (`app/evidence/thresholds.py`): 5xx
ratio >= 5%, p95 latency >= 1 s, slow trace >= 1 s. All data is returned whether or not a
threshold is crossed.

### Example: bad inventory deploy

Recorded while inventory release 3.2.0 added ~2.5 s of latency (orders times out at 2 s).
The deploy reads `3.2.0 -> 3.2.0` because the same release had been deployed in an earlier
test; output abridged:

```
[deployments] inventory deployed 3.2.0 -> 3.2.0 at 05:14:20Z (during the window) by ci-pipeline: 'Switch stock lookups to new reservation query'
[traces] 20 of 41 sampled error/slow traces: gateway POST /checkout returned 502 in 2.01s-2.05s; failing: gateway POST /checkout (502) <- orders POST /orders (504); most self time in inventory POST /reserve (avg 2.40s, release 3.2.0)
[logs] orders logged ERROR 'timed out reserving inventory' 113 times from 05:14:24Z to 05:16:00Z (release 2.7.0); example traces: ...
[metrics] gateway: 2.01 req/s avg; 5xx ratio avg 8.0%, max 74.0%; ...; p95 latency avg 369ms, max 2.40s; first at or above 1.00s at 05:14:45Z
```

The trace evidence is the key one: orders and gateway *report* the errors, but self time puts
the time inside inventory's own handler, on the release that was just deployed.

## Testing

- **Unit tests** (`pytest`) replay responses recorded from the demo stack during that
  incident (`backend/tests/fixtures/`, synthetic data). Re-record with
  `python -m tests.record_fixtures --minutes 10` while a scenario is active.
- **Integration tests** (`pytest -m integration`) run against the live stack. With
  `INCIDENT_SCENARIO=bad-inventory-deploy INCIDENT_RELEASE=<version>` they also assert that a
  bad deploy of that exact release shows up in deploys, traces, logs, and metrics. CI
  (`integration.yml`) does this on every relevant change.

## Known limitations

- **Traces are sampled.** Up to 20 error and 20 slow traces per service per window; counts in
  trace patterns describe the sample, not all traffic. Use metrics for totals.
- **Recent traces can be incomplete.** Spans reach Jaeger independently. Traces without a root
  span are skipped (and counted), but a trace missing a child span can attribute self time to
  the caller.
- **Logs group by exact message.** Messages containing IDs or numbers will not group together.
- **Jaeger's internal `/api` endpoints** are used because the stable `/api/v3` endpoint ignored
  attribute filters in Jaeger 2.3 (D-015).
- **The Prometheus `job` label is assumed to be `<namespace>/<service>`**, as set by the
  OpenTelemetry Collector.
- Evidence is computed on request and not stored; persistence is M3. Backend connections have
  no authentication or TLS, matching the local demo stack.
