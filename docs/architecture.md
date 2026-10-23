# Architecture

> **Implemented vs. planned.** As of Milestone 4, the **synthetic telemetry environment**,
> **evidence collection**, **incident persistence**, and the **investigation agent**
> (cited, validated diagnoses of a snapshot) exist. Evaluation and the frontend are
> planned. Components marked Planned are proposals and may change.

## Goal

Given an incident (an alert, a time window, or an affected service), the platform gathers
relevant telemetry (logs, metrics, traces, and deployment events) and produces a diagnosis in
which every claim cites the specific evidence that supports it. The LLM is a reasoning layer
over retrieved evidence, not a source of facts.

## Proposed system overview

```
 +------------------------ Demo environment (synthetic) ------------------------+
 |  Sample microservices --OTel SDK--> OpenTelemetry Collector                   |
 |  Fault injection / load generator                                            |
 +--------------------------------------+---------------------------------------+
                                        |
            +---------------+-----------+----------+----------------+
            v               v                      v                v
       Prometheus        Jaeger               OpenSearch      Deployment events
       (metrics)        (traces)                (logs)        (OpenSearch)
            +---------------+-----------+----------+----------------+
                                        |  read-only query adapters
                                        v
 +---------------------------- API service (FastAPI) ---------------------------+
 |  Incident API -- Evidence collectors -- Investigation agent (LLM + tools)    |
 |                          |                          |                        |
 |                          +-------- PostgreSQL ------+                        |
 |                    (incidents, evidence snapshots, diagnoses)                |
 +--------------------------------------+---------------------------------------+
                                        v
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
| Evidence collectors | Typed, read-only adapters that query each backend for a time window and service set and normalize results ([details](evidence.md)) | **Implemented (M2)** |
| Readiness endpoint | `/ready` checks the database, Prometheus, Jaeger, and OpenSearch | **Implemented (M2, M3)** |
| PostgreSQL | Incidents and immutable evidence snapshots ([details](incidents.md)); diagnoses and audit trail later | **Implemented (M3)** |
| Investigation agent | Diagnoses a stored snapshot with Claude; every claim cites evidence IDs, checked server-side ([details](diagnosis.md)) | **Implemented (M4)** |
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

### D-014: One evidence model with stable IDs, queries, and references (M2)
Every observation, from any backend, becomes an `Evidence` record with a deterministic ID, the
exact query that produced it, and a link to the raw data. The agent (M4) will cite evidence
IDs, and anyone can re-run the query to check a claim. Summaries are computed from the
record's own `data` and contain no interpretation.

### D-015: Jaeger's `/api` endpoints instead of `/api/v3` (M2)
`/api/v3` (OTLP JSON) was the first choice as Jaeger's stable query API, but in Jaeger 2.3 it
accepted and silently ignored attribute filters (verified: `error=true` returned successful
traces). The UI's `/api` endpoints filter correctly. The format is isolated in
`app/integrations/jaeger.py`, so switching back after an upgrade touches one file.

### D-016: Partial results instead of all-or-nothing (M2)
Collectors run concurrently. A backend failure becomes a `SourceError` in the bundle and the
other sources are still returned, so an outage of one backend does not block an
investigation, and callers can tell "missing" from "empty". Only `BackendError` is caught;
programming errors still fail the request.

### D-017: Self time to attribute latency in traces (M2)
In a timeout cascade every caller reports an error, so error spans alone point at the wrong
service. Grouping slow traces by the span with the most self time (duration minus time
covered by children, clipped to the span) points at where time was actually spent. Fast
error traces are grouped by failing path only, because their largest span is noise.

### D-018: Fixtures recorded from the demo stack; integration tests pinned to a release (M2)
Unit tests replay real backend responses recorded during an incident, trimmed to the fields
the code reads, so they exercise real API formats without a network. Integration tests assert
on the specific release they deployed, because evidence from earlier incidents in the same
window would otherwise make them pass vacuously (observed during development).

### D-019: PostgreSQL with async SQLAlchemy and explicit Alembic migrations (M3)
SQLAlchemy 2 (asyncio) with psycopg 3 fits the async FastAPI stack and keeps one driver for
sync tooling and async requests. Migrations run only through `alembic upgrade head`, never
on app startup, so a deploy cannot change the schema by accident and several API processes
cannot race to migrate.

### D-020: Immutable snapshots with evidence stored as rows (M3)
A diagnosis is only checkable against the evidence it saw, so snapshots are append-only.
Items are rows keyed by (snapshot, evidence ID) rather than one JSON blob, so a cited
`ev-...` ID can be validated with a primary-key lookup. Counts are denormalized onto the
snapshot because the rows never change.

### D-021: Collect evidence outside the database transaction (M3)
Backend queries can take seconds. Collecting first and then writing in a short
transaction keeps connections free and avoids long-held locks; the cost is that a crash
between the two steps loses the collected evidence, which can simply be collected again.

### D-022: One root .env shared by compose and the backend; guarded test database (M3)
The database password lives once in a git-ignored root `.env`; both docker compose and
pydantic-settings expand `${POSTGRES_PASSWORD}` from it. CI generates a throwaway password
or uses trust auth on an ephemeral container, so no credential is committed. Tests use
settings that ignore `.env`, and database tests refuse any database not named `*_test`.

### D-023: Database tests run against real PostgreSQL (M3)
Tests use the same engine as production (JSONB, arrays, check constraints) instead of
SQLite, via the compose database locally and a service container in CI.

### D-024: One structured call per diagnosis, not a tool loop (M4)
A snapshot is small (4,000 to 6,000 input tokens measured) and already contains the collected evidence, so a
single request with structured outputs is cheaper, faster, reproducible from stored data,
and easy to test. A tool loop that fetches more telemetry would break reproducibility
unless that data were snapshotted too. Revisit if evaluation (M5) shows diagnoses fail for
lack of information.

### D-025: Claude Opus 5.5 at medium effort, configurable, with refusal fallback (M4)
Chosen by the project owner. Model and effort are settings so evaluation can compare
them on the same incidents. Server-side `fallbacks: "default"` handles the unlikely case
of a safety decline without code changes.

### D-026: Citations are validated by the backend, not trusted (M4)
Structured outputs guarantee the shape but cannot know which evidence IDs exist. The
backend checks that every claim cites at least one ID and that every ID is in the
snapshot. Failures are stored as `invalid` with the reasons, never shown as valid, and
not retried automatically.

### D-027: Budget reserved before each call under an advisory lock (M4)
The worst-case cost is reserved in the same transaction as the budget check, under a
PostgreSQL advisory lock, so concurrent requests cannot overspend. Failures whose cost is
unknown (timeouts) keep the reservation, so errors make the budget stricter, not looser.

### D-028: Replies parsed by the app rather than the SDK helper (M4)
The SDK's `parse()` helper can raise before returning usage when a reply is truncated
or invalid, and those tokens are still billed. The app calls `create()` with the SDK's
`transform_schema` output and validates the text itself, so usage and cost are always
recorded.

### D-029: No API calls in tests or CI (M4)
A fake model drives the service tests and a fake HTTP transport checks the real SDK
client, including against a reply recorded once from the live API. Live calls are run by
hand with `tests/record_llm_reply.py`, which needs an explicit `--yes`.

### D-030: Evaluation cases captured once from the demo stack and frozen (M5)
Cases are real collector output from scripted scenarios, so the model sees the same evidence
shape as in production, while freezing them as JSON makes runs reproducible, free of the
stack, and comparable across variants. Cost: cases go stale when collectors change and must be
recaptured.

### D-031: Exact checks only, no model-graded scores (M5)
Every case has a known root-cause service and, where relevant, a release, so correctness is
checkable with string matching and the backend's citation validator. This keeps grading free,
deterministic, and auditable; explanation quality is out of scope for now.

### D-032: Paid evaluation runs are gated and capped (M5)
A run starts only for a harness (runner, grader, prompt, client, validator, cases) whose hash
a person approved, and a spend cap reserves each call's worst case. Failed calls are recorded
separately so they cannot be mistaken for wrong answers. Evaluations are run by hand, never
in CI.

### D-033: React, Vite, and hand-written CSS for the frontend (M6)
A single-page app is enough for an internal tool that reads one JSON API. Styles are CSS
modules over a small token set rather than Tailwind or a component kit, so the interface follows
its own design system instead of a starter kit's defaults. TanStack Query handles server state;
there is no client-side store.

### D-034: Frontend types are generated from the backend's OpenAPI schema (M6)
`python -m app.openapi` exports the schema and `openapi-typescript` generates the types the
client uses. Both are committed, and CI regenerates them and fails on any difference, so an
API change cannot silently break the frontend.

### D-035: An offline stand-in model for end-to-end tests (M6)
`APP_LLM_PROVIDER=offline` returns a fixed, labelled diagnosis that cites the snapshot's
evidence, so end-to-end tests exercise the full flow, including citation validation and
storage, with no network calls or cost. Settings refuse it in production.

### D-036: Exhibit numbers follow collection order (M6)
`EX-5` always names the same evidence item in a snapshot, in every view and every diagnosis of
it, so a number can be quoted and checked. Numbering by first citation would read more neatly
but would change between diagnoses of the same snapshot.

### D-037: Design direction chosen by the project owner from concrete alternatives (M6)
Four visual directions were sketched with real diagnosis data, including the category
standard (sidebar, cards, pills), and the owner chose the investigation-report direction. A
separate design review then checked the build against that direction, and DESIGN.md records
the system as built rather than as planned.

### D-038: Sources without evidence are citable (M5 follow-up)
A diagnosis must cite something for every claim, but some claims are about data the snapshot
does not have: re-run a failed query, no deploys in the window. Rather than exempt those
claims, each source without evidence gets an ID, `src-<source>`, for either case: it failed to
collect, or it was queried and returned nothing. The rule stays strict and the citation stays
checkable. Every collection queries every source, so "no evidence and no error" means the
query returned nothing.

