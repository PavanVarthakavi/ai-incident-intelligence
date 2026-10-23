// Records API responses for component tests from a running backend seeded with
// `python -m eval.seed` (see docs/frontend.md). Synthetic data only.
//
//   node scripts/record-fixtures.mjs [http://127.0.0.1:8000]
import { writeFile } from "node:fs/promises";

const base = process.argv[2] ?? "http://127.0.0.1:8000";
const get = async (path) => {
  const response = await fetch(base + path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
};

const list = await get("/v1/incidents?limit=200");
const pick = {
  valid: list.items.find((i) => i.title === "Checkout failing since the gateway release"),
  invalid: list.items.find((i) => i.latest_diagnosis?.status === "invalid"),
  healthy: list.items.find((i) => i.title === "Checkout is completely down"),
};

const cases = {};
for (const [name, summary] of Object.entries(pick)) {
  if (!summary) throw new Error(`no seeded incident for ${name}; run python -m eval.seed`);
  const incident = await get(`/v1/incidents/${summary.id}`);
  const snapshotId = incident.snapshots.at(-1).id;
  const url = `/v1/incidents/${incident.id}/snapshots/${snapshotId}`;
  cases[name] = { incident, snapshot: await get(url), diagnoses: await get(`${url}/diagnoses`) };
}
const page = { items: Object.values(pick), total: 3, limit: 50, offset: 0 };
await writeFile(
  new URL("../src/test/fixtures/api.json", import.meta.url),
  // Escape non-ASCII (the model writes en dashes) so the file stays plain ASCII.
  JSON.stringify({ cases, incidents: page }, null, 2).replace(
    /[\u0080-\uffff]/g,
    (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`,
  ) + "\n",
);
console.log("wrote src/test/fixtures/api.json:", Object.keys(cases).join(", "));
