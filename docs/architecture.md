# Architecture

> **Implemented vs. planned.** As of Milestone 1, the **API service skeleton** and the
> **synthetic telemetry environment** (demo services, collector, Prometheus, Jaeger, OpenSearch)
> exist. The backend does not read telemetry yet. Components marked Planned are proposals and
> may change as later milestones are designed.

## Goal

Given an incident (an alert, a time window, or an affected service), the platform gathers
relevant telemetry — logs, metrics, traces, and deployment events — and produces a diagnosis in
which every claim cites the specific evidence that supports it. The LLM is a reasoning layer
over retrieved evidence, not a source of facts.

## Proposed system overview

```
 ┌──────────────────────── Demo environment (synthetic) ────────────────────────┐
 │  Sample microservices ──OTel SDK──▶ OpenTelemetry Collector                   │
 │  Fault injection / load generator                                            │
 └──────────────────────────────────────┬───────────────────────────────────────┘
                                        │
            ┌───────────────┬───────────┴──────────┬────────────────┐
            ▼               ▼                      ▼                ▼
       Prometheus        Jaeger               OpenSearch      Deployment events
       (metrics)        (traces)                (logs)        (webhook / file)
            └───────────────┴───────────┬──────────┴────────────────┘
                                        │  read-only query adapters
                                        ▼
 ┌──────────────────────────── API service (FastAPI) ───────────────────────────┐
 │  Incident API ── Evidence collectors ── Investigation agent (LLM + tools)    │
 │                          │                          │                        │
 │                          └──────── PostgreSQL ──────┘                        │
 │                    (incidents, evidence snapshots, diagnoses)                │
 └──────────────────────────────────────┬───────────────────────────────────────┘
                                        ▼
                                Frontend (later)
```

## Components

| Component | Responsibility | Status |
|---|---|---|
| API service (FastAPI) | HTTP API, orchestration, configuration | **Skeleton implemented** |
| Health endpoint | Liveness signal for CI, containers, load balancers | **Implemented** |
| Demo environment | Three instrumented services + load generator + fault injection producing synthetic telemetry ([details](demo-environment.md)) | **Implemented (M1)** |
| OpenTelemetry Collector | Receives OTLP from services; routes to backends | **Implemented (M1)** |
| Prometheus / Jaeger / OpenSearch | Metrics / traces / logs + deploy events storage and query | **Implemented (M1)** |
| Evidence collectors | Typed, read-only adapters that query each backend for a time window and service set and normalize results | Planned (M2) |
| PostgreSQL | Incidents, evidence snapshots, diagnoses, audit trail | Planned (M3) |
| Investigation agent | LLM that calls evidence collectors as tools and produces a cited diagnosis | Planned (M4) |
| Evaluation harness | Replays injected faults and scores diagnoses against known root causes | Planned (M5) |
| Frontend | Incident timeline and diagnosis review UI | Planned (M6) |

## Key design principles

1. **Evidence first.** Diagnoses must reference concrete evidence (a metric series, a trace ID,
   a log query, a deploy event). Unsupported claims are treated as defects.
2. **Read-only integrations.** The platform queries observability backends; it never mutates
   production systems.
3. **Snapshot evidence.** Evidence used in a diagnosis is persisted so that investigations are
   reproducible after telemetry retention expires.
4. **Thin adapters, typed models.** Each backend sits behind an interface returning Pydantic
   models, so the agent and tests do not depend on vendor-specific response formats.
5. **Synthetic data only.** All telemetry comes from the demo environment or public datasets.

## Decisions

Decisions made so far. Add new entries rather than rewriting old ones.

### D-001: Python + FastAPI for the backend (M0)
Python has the strongest ecosystem for both observability clients and LLM tooling. FastAPI gives
typed request/response models via Pydantic and auto-generated OpenAPI docs.

### D-002: Monorepo with a `backend/` directory (M0)
The repo will later hold the demo environment, infrastructure config, and a frontend. Isolating
the Python project in `backend/` keeps its tooling self-contained and lets CI filter by path.

### D-003: App factory + dependency-injected settings (M0)
`create_app()` builds the application; settings come from `pydantic-settings` with an `APP_`
prefix and are injected via `Depends(get_settings)`. Tests override the dependency instead of
mutating environment variables, keeping them isolated and deterministic.

### D-004: Liveness only, readiness later (M0)
`/health` reports that the process is running and checks no dependencies. When external
dependencies arrive, a separate readiness endpoint will check them, so a slow database never
makes the process look dead.

### D-005: pip + `pyproject.toml`, Ruff for lint/format (M0)
Standard tooling with no extra installer required. Ruff replaces flake8/isort/black with one
fast tool. Dependency lock files can be introduced once deployment artifacts are built.

### D-006: `httpx2` for the test client (M0)
The installed Starlette version (1.9) deprecates `httpx` for `TestClient` in favor of `httpx2`.
Using `httpx2` avoids the deprecation warning; FastAPI's minimum version is set to the release
that was tested with it (0.161).

### D-007: CI tests the oldest supported and the development Python versions (M0)
CI runs on Python 3.11 (the `requires-python` minimum) and 3.13 (the local development
version), so both the supported floor and the developer environment are verified.

### D-008: Demo services are one Python package and one image (M1)
`gateway`, `orders`, and `inventory` live in `demo/shop` and share a Docker image, selected by
command (`python -m shop serve <service>`). One codebase keeps the synthetic system small while
still producing real cross-service traces. It is isolated from `backend/` so test
infrastructure never leaks into product code.

### D-009: The OpenTelemetry Collector is the only ingestion point (M1)
Services export OTLP/HTTP only and know nothing about the backends. Swapping or adding a backend
changes collector config, not application code. Prometheus scrapes the collector's Prometheus
exporter (standard pull model) rather than receiving remote-write.

### D-010: Bounded in-memory Jaeger storage (M1)
Jaeger v2 keeps up to 50,000 traces in memory. Durable trace storage (e.g. in OpenSearch) adds
memory and setup cost the demo does not need yet; evidence snapshots (M3) will preserve the
traces an investigation actually used.

### D-011: Runtime fault injection; deploy events written by the control tool (M1)
Faults are changed at runtime through each service's admin API, so scenarios need no restarts.
`incidentctl deploy` writes deployment events straight to OpenSearch (`deploy-events`), standing
in for a CD webhook. `incidentctl fault` deliberately writes nothing, simulating failures with no
change record. Error messages are configurable and injected failures are logged without
tracebacks, so the telemetry exposes symptoms, not the injection itself.

### D-012: Local-only security posture for the demo stack (M1)
OpenSearch security is disabled and admin APIs are unauthenticated to keep setup trivial.
Mitigation: every published port binds to 127.0.0.1. This stack must never be exposed on a
network; any shared or hosted environment needs authentication first.

### D-013: Stable HTTP semantic conventions and explicit index templates (M1)
Services opt into the stable OpenTelemetry HTTP conventions
(`http_server_request_duration_seconds`, `http_response_status_code`) so later evidence
collectors do not depend on deprecated names. A one-shot `opensearch-init` container installs
index templates (strings as `keyword`, zero replicas for single-node) before any data arrives,
so field types are predictable for querying.
