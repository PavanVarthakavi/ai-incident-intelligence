# Frontend (Milestone 6)

A web interface for reviewing incidents and their diagnoses. Every claim in a diagnosis links
to the evidence it cites, so an engineer can check the claim before acting on it. Product
context is in [`PRODUCT.md`](PRODUCT.md); the visual system is in [`DESIGN.md`](DESIGN.md).

## Screens

| Route | Purpose |
|---|---|
| `/` | Incidents, newest first, with severity and the latest diagnosis (service and confidence, or its failure). |
| `/incidents/:id` | The incident as a report: probable cause, summary, findings, timeline, recommended actions, and the snapshot's numbered exhibits beside them. `?snapshot=` and `?diagnosis=` select earlier ones. |
| `/incidents/new` | Create an incident for a time window; the backend collects a snapshot immediately (free). |

On the incident page, pointing at or focusing an exhibit tag (`EX-5`) highlights that evidence
in the exhibits column; clicking it opens the details: charts of metric series with the onset
marked, the failing call path of a trace pattern, the log message and count, or the deploy, plus
the exact query, a link to the source system, and every claim that cites it.

States are shown as they are, never softened: a diagnosis that failed the backend's citation
check is boxed in red with each problem named and marked on the claim it belongs to; refusals
and errors say so; a healthy window says "No probable cause"; sources that could not be
collected are listed above the exhibits. Running a diagnosis is a paid call, so the button
states the typical cost and the budget left, and is disabled when there is no model or no
evidence to diagnose.

## Design

The direction ("Probable Cause") follows air-accident investigation reports: the probable
cause stated first in a ruled box, numbered findings, and evidence as numbered exhibits. The
project owner chose it from four sketched alternatives, each drawn with a real diagnosis: a
research-paper direction, an airline-coupon direction, and the category standard (sidebar,
cards, pills). Colours each
have one job: navy for structure and actions, yellow only for exhibit tags and the active
exhibit, red only for high severity and failed states. Public Sans and Source Code Pro are
self-hosted; monospace is used only for IDs, queries, and releases. Text contrast is at least
5.2:1 everywhere.

## Running locally

```bash
# Backend with the demo stack and database (see the README), plus demo data:
cd backend
python -m eval.seed          # 24 evaluation incidents with their real diagnoses (free)
uvicorn app.main:app         # or APP_LLM_PROVIDER=offline to make runs free stand-ins

# Frontend (Node 22 or newer)
cd frontend
npm install
npm run dev                  # http://localhost:5173, proxies /v1 to 127.0.0.1:8000
```

`BACKEND_URL` changes the proxy target. With `APP_LLM_PROVIDER=offline`, "Run diagnosis"
stores a clearly labelled stand-in at no cost instead of calling Claude.

## Commands

| Command | Purpose |
|---|---|
| `npm run typecheck` / `lint` / `format:check` | TypeScript (strict), oxlint, Prettier |
| `npm test` | Component and unit tests (Vitest, Testing Library, MSW) |
| `npm run e2e` | End-to-end tests (Playwright, axe) against the real backend |
| `npm run api:types` | Regenerate `src/api/schema.d.ts` from `openapi.json` |
| `npm run fixtures` | Re-record test fixtures from a seeded backend |
| `python -m app.openapi ../frontend/openapi.json` | (from `backend/`) export the API schema |

## Testing

No test calls the Claude API.

- **API contract.** The backend exports its OpenAPI schema (`backend/app/openapi.py`) and the
  frontend's types are generated from it. CI regenerates both and fails if they differ from the
  committed files, so a backend change that breaks the frontend fails the pull request.
- **Component tests** (28) render the real routes with responses recorded from three seeded
  evaluation cases (`src/test/fixtures/api.json`): a valid diagnosis, the invalid F17, and a
  healthy window. They cover every diagnosis state, the exhibit interaction, running a diagnosis
  (success, budget refusal, no model), the form, and worst cases (no evidence, a 2,000-character
  report).
- **End-to-end tests** (7) start the backend with the offline model against a PostgreSQL test
  database seeded with `python -m eval.seed --reset F14 F17 H05`, start Vite, and drive Chrome:
  browsing, the exhibit interaction by pointer and keyboard, running a diagnosis, creating an
  incident, and a missing incident. Each main screen is checked with axe against WCAG 2.2 AA.
  Locally they read the test database from `APP_TEST_DATABASE_URL`; `--reset` refuses any
  database whose name does not end in `_test`.
- **Worst-case data** (long unbreakable names, 40 exhibits, 12 citations on one claim, missing
  fields, markup in titles) was checked visually against the running page; the two failures
  it found are fixed and covered by component tests.

CI (`.github/workflows/frontend-ci.yml`) runs the checks, the contract check, and the
end-to-end tests on every change to `frontend/` or `backend/`.

## Backend additions for the frontend

- `GET /v1/budget`: today's diagnosis budget, what has been spent or reserved, the median cost
  of recent diagnoses, and whether a model is configured.
- `latest_diagnosis` on incident summaries and details (status, root-cause service,
  confidence), from one extra query per page.
- `APP_LLM_PROVIDER=offline`: a stand-in model for end-to-end tests and demos; refused when
  `APP_ENVIRONMENT=production`.
- `python -m eval.seed`: loads evaluation cases and their baseline diagnoses into a database.

## Known limitations

- **No authentication.** Anyone who can reach the frontend can run paid diagnoses up to the
  daily budget. Run it locally only.
- **Synchronous diagnosis.** Running a diagnosis is one request that returns after 10 to 35
  seconds; the page shows elapsed time but no progress, and leaving the page does not cancel it.
- **No live updates.** Lists and the budget refresh on navigation (the budget every minute).
- **Narrow screens.** Below 1100px the exhibits move under the report; opening an exhibit
  scrolls down to it, with a link back to the citation.
- **Light theme only.**
- **No visual regression tests.** Layout was reviewed from screenshots, not compared
  automatically.
- **Seeded costs count.** Seeded diagnoses keep their recorded cost, so seeding on the day of
  the evaluation run counts toward that day's budget.
