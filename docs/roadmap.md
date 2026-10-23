# Roadmap

Milestones are incremental: each one should leave the system working, tested, and documented.
Scope for later milestones is a plan and will be refined when each begins.

## M0 — Project Foundation ✅ (current)

- [x] Repository structure (`backend/`, `docs/`, `.github/`)
- [x] FastAPI app factory and environment-based settings
- [x] `GET /health` liveness endpoint with tests
- [x] README, `.env.example`, `.gitignore`
- [x] Architecture and roadmap documents
- [x] GitHub Actions workflow running lint and tests

## M1 — Synthetic Telemetry Environment

Goal: a reproducible local environment that emits realistic logs, metrics, and traces.

- Docker Compose with OpenTelemetry Collector, Prometheus, Jaeger, and OpenSearch
- Two or three small instrumented demo services with a request flow across them
- Load generator and a simple fault-injection mechanism (latency, errors, bad deploy)
- Synthetic deployment events emitted alongside faults
- Documentation for starting the stack and viewing data in each tool

## M2 — Evidence Collection

Goal: the backend can retrieve and normalize telemetry for a time window.

- Typed adapters for Prometheus, Jaeger, OpenSearch, and deployment events
- Common evidence model (source, query, time range, summary, raw reference)
- Readiness endpoint that checks backend connectivity
- Unit tests with recorded fixtures; integration tests against the M1 stack

## M3 — Incident Persistence

Goal: incidents and their evidence are stored and queryable.

- PostgreSQL with migrations (Alembic)
- Incident create/read/list API
- Evidence snapshots linked to incidents

## M4 — LLM Investigation Agent

Goal: an agent that investigates an incident and produces a cited diagnosis.

- Agent loop with evidence collectors exposed as tools
- Structured diagnosis output where every claim references stored evidence
- Guardrails: tool budgets, timeouts, and rejection of uncited claims

## M5 — Evaluation

Goal: measure diagnosis quality objectively.

- Scenario library of injected faults with known root causes
- Automated scoring (root-cause accuracy, citation validity, time-to-diagnosis)
- Evaluation results tracked in CI or on demand

## M6 — Frontend

Goal: a UI for reviewing incidents and diagnoses.

- Incident list and timeline view
- Diagnosis view with links to underlying evidence
