# Roadmap

Milestones are incremental: each one should leave the system working, tested, and documented.
Scope for later milestones is a plan and will be refined when each begins.

## M0 — Project Foundation ✅

- [x] Repository structure (`backend/`, `docs/`, `.github/`)
- [x] FastAPI app factory and environment-based settings
- [x] `GET /health` liveness endpoint with tests
- [x] README, `.env.example`, `.gitignore`
- [x] Architecture and roadmap documents
- [x] GitHub Actions workflow running lint and tests

## M1 — Synthetic Telemetry Environment ✅

Goal: a reproducible local environment that emits realistic logs, metrics, and traces.

- [x] Docker Compose with OpenTelemetry Collector, Prometheus, Jaeger, and OpenSearch
- [x] Three instrumented demo services (`gateway → orders → inventory`)
- [x] Load generator and runtime fault injection (latency, errors, bad deploy)
- [x] Synthetic deployment events recorded in OpenSearch
- [x] Smoke check and CI job that boots the stack and verifies every signal
- [x] Documentation: [`demo-environment.md`](demo-environment.md), including known limitations

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
