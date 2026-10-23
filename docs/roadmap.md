# Roadmap

Milestones are incremental: each one should leave the system working, tested, and documented.
Scope for later milestones is a plan and will be refined when each begins.

## M0: Project Foundation

- [x] Repository structure (`backend/`, `docs/`, `.github/`)
- [x] FastAPI app factory and environment-based settings
- [x] `GET /health` liveness endpoint with tests
- [x] README, `.env.example`, `.gitignore`
- [x] Architecture and roadmap documents
- [x] GitHub Actions workflow running lint and tests

## M1: Synthetic Telemetry Environment

Goal: a reproducible local environment that emits realistic logs, metrics, and traces.

- [x] Docker Compose with OpenTelemetry Collector, Prometheus, Jaeger, and OpenSearch
- [x] Three instrumented demo services (`gateway -> orders -> inventory`)
- [x] Load generator and runtime fault injection (latency, errors, bad deploy)
- [x] Synthetic deployment events recorded in OpenSearch
- [x] Smoke check and CI job that boots the stack and verifies every signal
- [x] Documentation: [`demo-environment.md`](demo-environment.md), including known limitations

## M2: Evidence Collection

Goal: the backend can retrieve and normalize telemetry for a time window.

- [x] Typed adapters for Prometheus, Jaeger, OpenSearch, and deployment events
- [x] Common evidence model (source, query, reference, summary, stable ID)
- [x] `GET /v1/evidence` with partial results when a backend fails
- [x] Readiness endpoint that checks backend connectivity
- [x] Unit tests with recorded fixtures; integration tests against the M1 stack in CI
- [x] Documentation: [`evidence.md`](evidence.md), including known limitations

## M3: Incident Persistence

Goal: incidents and their evidence are stored and queryable.

- [x] PostgreSQL in the compose stack, with migrations (Alembic) checked in CI
- [x] Incident create/read/list API
- [x] Immutable evidence snapshots linked to incidents, re-collectable on demand
- [x] Readiness includes the database
- [x] Documentation: [`incidents.md`](incidents.md), including known limitations

## M4: LLM Investigation Agent

Goal: an agent that investigates an incident and produces a cited diagnosis.

- [x] Diagnosis of a stored snapshot with Claude, as one structured-output request
- [x] Every claim cites evidence IDs; citations validated server-side, failures stored as invalid
- [x] Guardrails: per-reply token cap, daily budget with reservation, timeouts, refusal fallback
- [x] Usage and cost recorded per diagnosis
- [x] Documentation: [`diagnosis.md`](diagnosis.md), including known limitations
- Deferred: an agent loop with evidence collectors as tools, pending M5 results

## M5: Evaluation

Goal: measure diagnosis quality objectively.

- [x] 24 cases captured from scripted scenarios with known root causes, frozen as JSON
- [x] Exact-check grading (root cause, healthy specificity, release, citation validity),
  with oracle and null checks of the grader
- [x] Resumable runner with harness approval, spend cap, timeouts, and served-model check
- [x] Baseline run and report with 95% intervals; latency and cost per case
- [x] Documentation: [`evaluation.md`](evaluation.md), including known limitations
- [x] Claims about failed or empty sources cite them (`src-<source>`), fixing the F17
  finding; measured as variants `v1` and `v2`
- Next: harder cases to add headroom
- Not planned: running paid evaluations in CI

## M6: Frontend

Goal: a UI for reviewing incidents and diagnoses.

- [x] Incident list, incident report with numbered exhibits, and new incident form (React,
  TypeScript, Vite)
- [x] Every claim links to the evidence it cites; invalid, refused, and failed diagnoses shown
  as such; cost and budget shown before a paid run
- [x] Types generated from the backend's OpenAPI schema, with a CI check that they match
- [x] Component tests, end-to-end tests with axe (WCAG 2.2 AA), offline model for tests
- [x] Documentation: [`frontend.md`](frontend.md), [`PRODUCT.md`](PRODUCT.md),
  [`DESIGN.md`](DESIGN.md), including known limitations
- Not planned: authentication, live updates
