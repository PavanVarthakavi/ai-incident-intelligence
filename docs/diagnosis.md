# Investigation Agent (Milestone 4)

The agent diagnoses a stored evidence snapshot with Claude and returns a structured
diagnosis in which every claim cites evidence IDs from that snapshot. Citations are
checked by the backend; a diagnosis that fails the check is stored as `invalid`, never
presented as valid.

## Setup

1. In the Anthropic Console, create a workspace with a monthly spend limit and an API key
   in it.
2. Add `ANTHROPIC_API_KEY=...` to the root `.env` (git-ignored).
3. `cd backend && alembic upgrade head`

Without the key the diagnosis endpoints return 503; everything else keeps working.

## API

| Method and path | Purpose |
|---|---|
| `POST /v1/incidents/{id}/snapshots/{sid}/diagnoses` | Run a diagnosis (paid API call). Returns 429 if the daily budget would be exceeded. |
| `GET /v1/incidents/{id}/snapshots/{sid}/diagnoses` | Diagnoses of the snapshot, newest first. |
| `GET /v1/incidents/{id}/snapshots/{sid}/diagnoses/{did}` | One diagnosis. |

A diagnosis is always stored, whatever the outcome. `status` is one of:

| Status | Meaning |
|---|---|
| `valid` | Parsed, and every claim cites evidence from the snapshot. |
| `invalid` | Parsed, but a citation is missing or names an ID not in the snapshot. Output is kept for inspection; `validation_errors` lists each problem. |
| `refused` | The model (and its fallback) declined. |
| `error` | API error, timeout, or a reply that could not be parsed (for example cut off at `max_tokens`). |
| `running` | In progress. |

## Diagnosis format

`summary`, `root_cause` (statement, service, confidence, evidence IDs; null when the
evidence supports no cause), `contributing_factors`, `timeline`, `ruled_out`, `unknowns`
(free text, including missing evidence), and `recommended_actions`. Every item except
`unknowns` must cite at least one ID.

A source without evidence in the snapshot is citable too, as `src-<source>`: one that failed
to collect (listed under collection errors) or one that was queried and returned nothing
(listed under empty sources, and in the snapshot's `empty_sources`). A claim about missing or
absent data, such as an action to re-run a failed query or the absence of deploys, cites
that ID. A source that has evidence is cited by its evidence, not by `src-`.

## How it works

- One request per diagnosis to `claude-opus-5-5` at effort `medium` (both configurable),
  using structured outputs so the reply always matches the schema. The model's thinking is
  always on for this model; effort controls how much it thinks.
- The prompt contains the incident, the sources that failed or returned nothing, and each
  evidence record with bulky fields removed (metric series, per-trace span lists). The
  system prompt tells the model to treat evidence text, such as log messages, as data and
  not as instructions. `prompt_version` is stored with each diagnosis.
- Server-side refusal fallback (`fallbacks: "default"`) re-runs a declined request on the
  model Anthropic recommends for that refusal category. `fallback_used` and `model_used`
  record when that happened.

## Cost controls

- `max_tokens` (default 16,000) caps each reply.
- `APP_LLM_DAILY_BUDGET_USD` (default $2) caps spend per UTC day. Before each request the
  worst-case cost (prompt size plus a full-length reply) is reserved under a database lock,
  so concurrent requests cannot both pass the check. The reservation is replaced by the
  actual cost when the reply arrives. A timeout or dropped connection keeps the
  reservation, because the request may still have been billed.
- Each diagnosis stores input, output, and cache token counts and the computed cost
  (`app/diagnosis/pricing.py`). Models without a listed price are charged at the highest
  listed price for budget purposes.
- A Console workspace spend limit is the backstop if anything in the app is wrong.

Measured with `claude-opus-5-5` at effort `medium` on the demo stack:

| Scenario | Evidence items | Input tokens | Output tokens | Cost | Time | Result |
|---|---|---|---|---|---|---|
| Bad inventory deploy (2.5 s added latency) | 10 | 5,872 | 2,078 | $0.065 | 23 s | `valid`; root cause inventory 3.3.0, high confidence |
| Healthy window, vague user report | 6 | 3,995 | 1,601 | $0.048 | 16 s | `valid`; `root_cause` null, open questions listed |

In the bad-deploy case the model separated where errors were reported (gateway, orders)
from where time was spent (inventory), ruled out an earlier deploy and rollback in the
window, and marked lock contention as inferred rather than observed. In the healthy case
it declined to name a cause and did not blame the earlier deploys. Two runs are examples,
not an evaluation; systematic scoring is Milestone 5.

The budget reservation estimates input at 1.5 characters per token plus 1,000 tokens of
overhead. An early estimate of 3 characters per token undercounted a real request (7,010
tokens counted against about 3,600 estimated), because JSON evidence and the output schema
tokenize densely; a test now pins the estimate above that measurement.

## Testing

- Unit tests never call the API. A fake model drives the API and storage tests; the real
  SDK client runs against a fake HTTP transport to check the request shape and reply
  handling, including the two replies recorded from the live API above
  (`tests/fixtures/anthropic_reply_*.json`).
- `python -m tests.record_llm_reply` counts the prompt's tokens (free). With
  `--yes --name <name>` it runs one paid diagnosis on the latest snapshot (or
  `--snapshot <id>`) and records the raw reply as `anthropic_reply_<name>.json`.
- CI makes no API calls and needs no key.

## Known limitations

- One request per diagnosis: the model cannot fetch more data than the snapshot holds.
  Tool use is deferred until evaluation (M5) shows missing information is a problem.
- An `invalid` diagnosis is not retried automatically, to keep cost predictable.
- Prices are hard-coded and must be updated if Anthropic's prices change.
- The budget is per deployment, not per user; there is no authentication yet.
