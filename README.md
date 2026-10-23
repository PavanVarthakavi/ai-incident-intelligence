# AI Incident Intelligence Platform

A system that analyzes distributed logs, metrics, traces, and deployment events to generate
evidence-grounded incident diagnoses.

> **Status: Milestone 1 (Synthetic Telemetry Environment).** A local demo system now produces
> logs, metrics, traces, and deployment events. The platform backend is still a skeleton: it
> does not read that telemetry yet (Milestone 2). See [`docs/roadmap.md`](docs/roadmap.md).

## What exists today

| Component | Status |
|---|---|
| FastAPI backend skeleton (`backend/`) | Implemented |
| `GET /health` liveness endpoint + tests | Implemented |
| Environment-based configuration (`APP_*` variables) | Implemented |
| GitHub Actions CI (lint, tests, stack smoke test) | Implemented |
| Demo microservices with fault injection + load generator (`demo/`) | Implemented |
| Telemetry stack: OTel Collector, Prometheus, Jaeger, OpenSearch (`compose.yaml`) | Implemented |
| Backend reading telemetry (evidence collectors) | Planned (M2) |
| PostgreSQL persistence for incidents | Planned |
| LLM investigation agent | Planned |
| Frontend | Planned |

See [`docs/architecture.md`](docs/architecture.md) for the target design,
[`docs/demo-environment.md`](docs/demo-environment.md) for the demo stack, and
[`docs/roadmap.md`](docs/roadmap.md) for milestones.

## Repository layout

```
backend/                 FastAPI service (Python 3.11+)
  app/
    main.py              App factory and ASGI entry point
    config.py            Settings loaded from environment variables
    api/health.py        Liveness endpoint
  tests/                 Pytest suite
  pyproject.toml         Dependencies and tool configuration
demo/                    Synthetic instrumented microservices (not production code)
  shop/                  gateway, orders, inventory, load generator, fault injection
  tools/                 incidentctl (inject faults/deploys), smoke_check
infra/                   Collector, Prometheus, Jaeger, OpenSearch configuration
compose.yaml             Local demo + telemetry stack
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

# Optional: local configuration
cp ../.env.example .env

# Run the API
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

Interactive API docs are served at `http://localhost:8000/docs`.

## Demo telemetry environment

Requires Docker. Tools require Python 3.11+.

```bash
docker compose up -d --build --wait
python3 demo/tools/smoke_check.py --wait 120
python3 demo/tools/incidentctl.py deploy inventory 3.2.0 --latency-ms 2500   # cause an incident
python3 demo/tools/incidentctl.py deploy inventory 3.1.5                      # roll back
```

Then explore Jaeger at http://localhost:16686 and Prometheus at http://localhost:9090. Details
in [`docs/demo-environment.md`](docs/demo-environment.md).

## Development

```bash
cd backend
pytest              # run tests
ruff check .        # lint
ruff format .       # format
```

Backend CI runs these on Python 3.11 and 3.13 for changes under `backend/`. Demo CI runs the
demo's unit tests and then starts the full Compose stack and runs the smoke check, for changes
under `demo/`, `infra/`, or `compose.yaml`.

## Data policy

This project uses only public or synthetic data. Never commit real production telemetry,
customer data, or secrets. Configuration secrets belong in a local `.env` file, which is
git-ignored.
