# Demo Environment (Milestone 1)

A local, fully synthetic system that produces the logs, metrics, traces, and deployment events
the platform will investigate. Nothing here touches real systems or real data.

## What runs

| Service | Purpose | Host URL |
|---|---|---|
| `gateway` | Public entry point (`POST /checkout`, `GET /products`) | http://localhost:8080 |
| `orders` | Creates orders; calls inventory, simulates payment authorization | http://localhost:8081 |
| `inventory` | Reserves stock (simulated database query) | http://localhost:8082 |
| `loadgen` | Steady synthetic traffic to the gateway (default ~2 req/s) | — |
| `otel-collector` | Receives OTLP from services; routes each signal to its backend | — |
| `jaeger` | Trace storage and UI | http://localhost:16686 |
| `prometheus` | Metrics storage and query | http://localhost:9090 |
| `opensearch` | Log and deployment-event storage | http://localhost:9200 |
| `opensearch-init` | One-shot: installs index templates, then exits | — |
| `opensearch-dashboards` | Optional log UI (`ui` profile) | http://localhost:5601 |

Request flow: `loadgen → gateway → orders → inventory`. Every hop is traced, so one checkout
produces a single distributed trace spanning all three services.

```
services ──OTLP/HTTP──▶ otel-collector ──┬── traces  ──▶ Jaeger
                                         ├── metrics ──▶ (scraped by) Prometheus
                                         └── logs    ──▶ OpenSearch  index: otel-logs
incidentctl ── deploy events ────────────────────────▶ OpenSearch  index: deploy-events
```

## Running it

Requires Docker with ~2 GB of memory available to containers (about 1.2 GB in use when
measured; add ~300 MB for Dashboards). The host tools need Python 3.11+ and no extra packages.

```bash
docker compose up -d --build --wait           # start (first build takes a minute or two)
python3 demo/tools/smoke_check.py --wait 120  # verify telemetry reaches every backend
docker compose --profile ui up -d             # optional: OpenSearch Dashboards
docker compose down                           # stop, keep data
docker compose down -v                        # stop and delete all stored telemetry
```

`LOADGEN_RPS=5 docker compose up -d loadgen` changes the traffic rate.

## Injecting incidents

`demo/tools/incidentctl.py` controls each service's runtime behaviour through its admin API.

```bash
python3 demo/tools/incidentctl.py status
python3 demo/tools/incidentctl.py fault orders --error-rate 0.3 --message "connection pool exhausted"
python3 demo/tools/incidentctl.py deploy inventory 3.2.0 --latency-ms 2500 \
    --description "Switch stock lookups to new reservation query"
python3 demo/tools/incidentctl.py deploy inventory 3.1.5   # roll back (healthy release)
python3 demo/tools/incidentctl.py clear                    # remove faults everywhere
```

- **`fault`**: changes behaviour with no deployment event, like an infrastructure problem.
- **`deploy`**: switches the running release (optionally with faults that ship with it) and
  writes a deployment event, like a CD pipeline would. The new release appears as the
  `app.release` span attribute and the `release` label on business metrics.
- Error messages are configurable, and injected failures are logged without tracebacks, so the
  telemetry shows symptoms without revealing that a failure was injected.

### Example: bad deploy causing cascading timeouts

`deploy inventory 3.2.0 --latency-ms 2500` exceeds the 2 s timeout orders uses for inventory
(the gateway waits 3 s for orders). Observed within a minute:

- **Deploy event:** `inventory 3.1.5 → 3.2.0` in `deploy-events`.
- **Metrics:** gateway checkouts switch from 201 to 502, orders returns 504, and p95 latency
  rises above 2 s for all three services; `orders_created_total{status="inventory_timeout"}` rises.
- **Logs:** `orders` logs "timed out reserving inventory"; `gateway` logs "checkout failed:
  orders returned 504". Each log line carries the `traceId` of its request.
- **Traces:** gateway 502 → orders 504 at ~2.0 s → inventory `POST /reserve` taking ~2.5 s
  with `app.release=3.2.0`.

## Where the data lives

| Signal | Location | Useful fields / names |
|---|---|---|
| Traces | Jaeger API `GET /api/traces?service=gateway` | `app.release`, `http.response.status_code` |
| HTTP metrics | Prometheus `http_server_request_duration_seconds_*` | `job="demo-shop/<service>"`, `http_route`, `http_response_status_code` |
| Business metrics | `orders_created_total`, `inventory_reservations_total` | `release`, `status` / `outcome` |
| Logs | OpenSearch `otel-logs` | `resource.service.name`, `severity.text`, `body`, `traceId`, `attributes.release` |
| Deploy events | OpenSearch `deploy-events` | `service`, `version`, `previous_version`, `@timestamp` |

## Known limitations

- Injected latency is applied when a request starts, so it shows up as time inside the service's
  server span that no child span accounts for, rather than inside a specific child span such
  as the database query.
- If OpenSearch is down, the collector drops logs instead of retrying (its OpenSearch exporter
  treats connection errors as permanent). Startup ordering prevents this in normal use.
- Jaeger keeps up to 50,000 traces in memory; traces are lost when Jaeger restarts.
- Fault state lives in each service process. Restarting a container resets its release to the
  version in `compose.yaml` and clears faults.
- Injected faults are not recorded as ground truth anywhere yet; that is planned for evaluation
  (M5). Deploy events are deliberately *observable* evidence, not ground truth.
- Admin APIs are unauthenticated and OpenSearch security is disabled. Every port is bound to
  127.0.0.1; do not expose this stack on a network.
