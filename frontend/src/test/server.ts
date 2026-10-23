import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import fixtures from "./fixtures/api.json";
import type { BudgetRead } from "../api/client";

export type CaseName = keyof typeof fixtures.cases;
export const cases = fixtures.cases;

export const budget: BudgetRead = {
  day: "2026-10-23",
  limit_usd: "2.0",
  spent_usd: "0.2",
  remaining_usd: "1.8",
  typical_cost_usd: "0.0508",
  enabled: true,
  model: "claude-opus-5-5",
};

const byIncident = (id: string) => Object.values(fixtures.cases).find((c) => c.incident.id === id);

/** Default handlers: the recorded API, read-only. Tests add writes with server.use(). */
export const handlers = [
  http.get("*/v1/budget", () => HttpResponse.json(budget)),
  http.get("*/v1/incidents", () => HttpResponse.json(fixtures.incidents)),
  http.get("*/v1/incidents/:id", ({ params }) => {
    const found = byIncident(String(params.id));
    return found
      ? HttpResponse.json(found.incident)
      : HttpResponse.json({ detail: "incident not found" }, { status: 404 });
  }),
  http.get("*/v1/incidents/:id/snapshots/:sid", ({ params }) =>
    HttpResponse.json(byIncident(String(params.id))?.snapshot),
  ),
  http.get("*/v1/incidents/:id/snapshots/:sid/diagnoses", ({ params }) =>
    HttpResponse.json(byIncident(String(params.id))?.diagnoses ?? []),
  ),
];

export const server = setupServer(...handlers);
