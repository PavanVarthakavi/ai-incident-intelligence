# AI Incident Intelligence Platform

A system that analyzes distributed logs, metrics, traces, and deployment events to generate
evidence-grounded incident diagnoses.

> **Status: Milestone 0 (Project Foundation).** Only the backend skeleton and a health-check
> endpoint exist today. Everything else described in [`docs/`](docs/) is planned, not built.

## What exists today

| Component | Status |
|---|---|
| FastAPI backend skeleton (`backend/`) | Implemented |
| `GET /health` liveness endpoint + tests | Implemented |
| Environment-based configuration (`APP_*` variables) | Implemented |
| GitHub Actions CI (lint + tests) | Implemented |
| Telemetry ingestion (OpenTelemetry, Prometheus, Jaeger, OpenSearch) | Planned |
| PostgreSQL persistence for incidents | Planned |
| LLM investigation agent | Planned |
| Frontend | Planned |

See [`docs/architecture.md`](docs/architecture.md) for the target design and
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
docs/                    Architecture, roadmap, and technical decisions
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

## Development

```bash
cd backend
pytest              # run tests
ruff check .        # lint
ruff format .       # format
```

CI runs the same lint and test commands on Python 3.11 and 3.13, on every push to `main` and on pull requests that
touch `backend/`.

## Data policy

This project uses only public or synthetic data. Never commit real production telemetry,
customer data, or secrets. Configuration secrets belong in a local `.env` file, which is
git-ignored.
