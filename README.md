# AI Incident Intelligence Platform

A system that analyzes distributed logs, metrics, traces, and deployment events to generate
evidence-grounded incident diagnoses.

> **Status: Milestone 6 (Frontend).** A local demo system produces logs, metrics, traces,
> and deployment events; the backend collects them into citable evidence, stores incidents
> with immutable snapshots in PostgreSQL, and diagnoses a snapshot with Claude, checking that
> every claim cites stored evidence. An evaluation of 24 incidents with known root causes
> measures diagnosis quality, and a web interface presents each diagnosis as a report whose
> claims link to their evidence. See [`docs/roadmap.md`](docs/roadmap.md).

## What exists today

| Component | Status |
|---|---|
| FastAPI backend skeleton (`backend/`) | Implemented |
| `GET /health` liveness and `GET /ready` readiness endpoints | Implemented |
| Evidence collection from Prometheus, Jaeger, OpenSearch (`GET /v1/evidence`) | Implemented |
| Environment-based configuration (`APP_*` variables) | Implemented |
| GitHub Actions CI (lint, unit tests, full-stack integration test) | Implemented |
| Demo microservices with fault injection + load generator (`demo/`) | Implemented |
| Telemetry stack: OTel Collector, Prometheus, Jaeger, OpenSearch (`compose.yaml`) | Implemented |
| Incidents with evidence snapshots in PostgreSQL (`/v1/incidents`) | Implemented |
| Investigation agent: cited diagnoses with Claude (`.../diagnoses`) | Implemented |
| Evaluation: 24 frozen incidents, exact-check grading, baseline report (`backend/eval/`) | Implemented |
| Web interface: incident list, report with linked evidence, new incident (`frontend/`) | Implemented |

See [`docs/architecture.md`](docs/architecture.md) for the target design,
[`docs/demo-environment.md`](docs/demo-environment.md) for the demo stack,
[`docs/evidence.md`](docs/evidence.md) for evidence collection,
[`docs/incidents.md`](docs/incidents.md) for incidents and snapshots,
[`docs/diagnosis.md`](docs/diagnosis.md) for the investigation agent,
[`docs/evaluation.md`](docs/evaluation.md) for the evaluation,
[`docs/frontend.md`](docs/frontend.md) for the web interface, and
[`docs/roadmap.md`](docs/roadmap.md) for milestones.

## Repository layout

```
backend/                 FastAPI service (Python 3.11+)
  app/
    main.py              App factory and ASGI entry point
    config.py            Settings loaded from environment variables
    api/                 HTTP endpoints (health, readiness, evidence)
    integrations/        Read-only clients for Prometheus, Jaeger, OpenSearch
    evidence/            Evidence model and one collector per source
    db/                  ORM models and database sessions
    incidents/           Incident schemas, storage, and API mapping
    diagnosis/           Investigation agent: prompt, Claude client, validation, budget
  eval/                  Evaluation: scenarios, capture, grader, runner, cases, results
  migrations/            Alembic migrations
  tests/                 Unit tests (recorded fixtures) and integration tests
  pyproject.toml         Dependencies and tool configuration
frontend/                Web interface (React, TypeScript, Vite)
  src/pages/             Incident list, incident report, new incident form
  src/components/        Report, exhibits, layout
  src/api/               Typed client generated from the backend's OpenAPI schema
  e2e/                   End-to-end tests (Playwright, axe)
demo/                    Synthetic instrumented microservices (not production code)
  shop/                  gateway, orders, inventory, load generator, fault injection
  tools/                 incidentctl (inject faults/deploys), smoke_check
infra/                   Collector, Prometheus, Jaeger, OpenSearch, Postgres configuration
compose.yaml             Local demo, telemetry, and database stack
docs/                    Architecture, roadmap, demo environment, decisions
.github/workflows/       CI pipelines
```

## Getting started

Requires Python 3.11 or newer.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Local configuration (database password and URLs), in the repository root
cp ../.env.example ../.env

# Start the database (see below for the full stack), apply migrations, run the API
docker compose up -d --wait postgres
alembic upgrade head
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

Interactive API docs are served at `http://localhost:8000/docs`.

## Demo telemetry environment

Requires Docker. Tools require Python 3.11+.

```bash
cp .env.example .env                    # once; set POSTGRES_PASSWORD
docker compose up -d --build --wait
python3 demo/tools/smoke_check.py --wait 120
python3 demo/tools/incidentctl.py deploy inventory 3.2.0 --latency-ms 2500   # cause an incident
python3 demo/tools/incidentctl.py deploy inventory 3.1.5                      # roll back
```

Then explore Jaeger at http://localhost:16686 and Prometheus at http://localhost:9090, or run
the backend (`cd backend && uvicorn app.main:app`) and open http://localhost:8000/v1/evidence.
Details in [`docs/demo-environment.md`](docs/demo-environment.md) and
[`docs/evidence.md`](docs/evidence.md).

## Development

```bash
cd backend
pytest                  # unit tests (database tests use APP_TEST_DATABASE_URL)
pytest -m integration   # against the running demo stack
ruff check .            # lint
ruff format .           # format

cd frontend             # Node 22 or newer
npm install
npm run dev             # http://localhost:5173 (backend on :8000)
npm test                # component tests
npm run e2e             # end-to-end tests against the backend, offline model
```

Backend CI runs lint, migration checks, and unit tests (with a PostgreSQL service) on
Python 3.11 and 3.13; Demo CI runs the demo's unit tests. Frontend CI type-checks, lints, and
tests the frontend, checks its API types against the backend, and runs the end-to-end tests.
The Integration workflow starts the full Compose stack, runs the smoke check, injects a bad
deploy, and checks that the backend finds it in every telemetry source.

## Web interface

With the backend running, `python -m eval.seed` (from `backend/`) loads the 24 evaluation
incidents with their real diagnoses; then `npm run dev` in `frontend/`. Details in
[`docs/frontend.md`](docs/frontend.md).

## Data policy

This project uses only public or synthetic data. Never commit real production telemetry,
customer data, or secrets. Configuration secrets, including the database password, belong
in the git-ignored `.env` file in the repository root.
