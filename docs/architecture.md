# Architecture

> **Implemented vs. planned.** As of Milestone 0, only the **API service skeleton** (FastAPI app,
> `/health`, settings, tests, CI) exists. Every other component below is a proposal and may
> change as later milestones are designed in detail.

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
| Demo environment | Small instrumented services + fault injection producing realistic, synthetic telemetry | Planned (M1) |
| OpenTelemetry Collector | Receives OTLP from services; routes to backends | Planned (M1) |
| Prometheus / Jaeger / OpenSearch | Metrics / traces / logs storage and query | Planned (M1) |
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
