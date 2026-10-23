# Product

## Platform

web

## Stack

Frontend (Milestone 6, new): React, Vite, and TypeScript; hand-written CSS on project design
tokens, no Tailwind or prebuilt component kit; TanStack Query for server state; headless
accessible primitives only where needed (dialogs, popovers). Talks to the existing FastAPI
backend (`backend/`) through its JSON API; the dev server proxies `/v1` to it.

## Users

- **Primary: an on-call engineer during an incident.** Something is failing or slow, they are
  under time pressure, and they need to learn what broke, how sure the system is, and then
  check that claim against the evidence themselves before acting on it.
- **Secondary: engineers reviewing the project.** This is a portfolio project; experienced
  engineers will read the repository and use the app to judge its engineering. The interface
  must hold up to close inspection.

## Product Purpose

Turns logs, metrics, traces, and deployment events from a distributed system into an
evidence-grounded diagnosis: a root cause (or an explicit "no root cause"), what was ruled out,
what is unknown, and what to do next. Success is a correct diagnosis the engineer can verify in
seconds, and an honest "not sure" or "nothing wrong" when that is the truth.

## Positioning

Every claim cites the stored evidence that supports it, and the backend checks those citations;
a diagnosis that fails the check is shown as invalid, never as an answer. The system records
what it ruled out and what it does not know, and is measured against incidents with known root
causes (24 cases; see `docs/evaluation.md`).

## Operating Context

- An incident is created for a time window and optional services. The backend collects an
  immutable evidence snapshot from Prometheus, Jaeger, OpenSearch logs, and deployment events.
  Snapshots can be re-collected; old ones never change.
- A diagnosis is run on a snapshot. It is a paid model call (about $0.05, 10 to 35 seconds) under
  a daily budget; the request can be refused with 429 when the budget would be exceeded.
- Diagnosis statuses: `valid`, `invalid` (with the citation problems listed), `refused`,
  `error`, `running`. Root-cause confidence is `high`, `medium`, or `low`.
- Evidence items have a stable ID (`ev-...`), source, kind, service, time, one-line summary, the
  exact query used, and a link to the backend UI (Jaeger, Prometheus) where applicable.
- A source can fail during collection; the snapshot then records a source error and the
  diagnosis should account for the missing data.
- The demo system has three services: `gateway -> orders -> inventory`.

## Capabilities and Constraints

- In scope (M6): incident list; incident detail with evidence and timeline; diagnosis view
  with citations linked to evidence; creating an incident, collecting a snapshot, and running a
  diagnosis with cost and budget visible.
- Out of scope (M6): authentication, live updates, evaluation results screen.
- Tests and CI never call the model API; end-to-end tests use a fake model.
- Terminology: incident, snapshot, evidence, diagnosis, root cause, contributing factor,
  ruled out, unknowns, recommended action, citation, source error.

## Evidence on Hand

- Synthetic telemetry from the demo stack, and 24 captured incidents with known causes in
  `backend/eval/cases/` (realistic evidence and real model diagnoses in
  `backend/eval/results/baseline/traces/`).
- No real users, customers, production incidents, testimonials, or metrics exist. Do not
  fabricate any.

## Product Principles

1. **Verifiable over impressive.** Every statement leads to its evidence in one step.
2. **Uncertainty is information.** Confidence, unknowns, ruled-out causes, and invalid
   diagnoses are shown plainly, not softened or hidden.
3. **Fast to the answer under stress.** The root cause, its confidence, and its evidence are
   readable at a glance; detail is there when wanted.
4. **Costs are explicit.** Actions that spend money say so before they run.

## Accessibility & Inclusion

WCAG 2.2 AA, checked with axe in end-to-end tests; full keyboard operation; status never
conveyed by color alone.
