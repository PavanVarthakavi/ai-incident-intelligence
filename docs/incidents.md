# Incidents and Evidence Snapshots (Milestone 3)

Incidents are stored in PostgreSQL. Creating one collects evidence for its time window and
stores it as an immutable snapshot, so an investigation can be reproduced after the
telemetry backends have dropped the data (Jaeger keeps traces in memory only).

## Setup

```bash
cp .env.example .env              # once; set POSTGRES_PASSWORD
docker compose up -d --wait       # includes the postgres service (127.0.0.1:5433)
cd backend && alembic upgrade head
uvicorn app.main:app --reload
```

The root `.env` is read by both docker compose and the backend. Migrations are applied
explicitly with `alembic upgrade head`; the API never migrates on startup.

## API

| Method and path | Purpose |
|---|---|
| `POST /v1/incidents` | Create an incident. Collects a snapshot unless `collect_evidence` is false. |
| `GET /v1/incidents?limit=50&offset=0` | List incidents, newest first. |
| `GET /v1/incidents/{id}` | Incident with snapshot summaries (oldest first). |
| `POST /v1/incidents/{id}/snapshots` | Collect the incident's window again as a new snapshot. |
| `GET /v1/incidents/{id}/snapshots/{snapshot_id}` | A snapshot with all of its evidence. |

```bash
curl -X POST localhost:8000/v1/incidents -H 'Content-Type: application/json' -d '{
  "title": "Checkout failures after inventory deploy",
  "severity": "high",
  "window": {"start": "2026-10-23T05:00:00Z", "end": "2026-10-23T05:30:00Z"},
  "services": null
}'
```

Fields: `title` (1-200 characters), optional `description`, `severity` (`critical`, `high`,
`medium`, `low`), `window` (same rules as `/v1/evidence`: timezone required, at most 24
hours), `services` (up to 20; null means all).

If a backend is down during collection, the incident is still created and the failure is
stored in the snapshot's `source_errors`. A later `POST .../snapshots` can fill the gap.

Without `APP_DATABASE_URL` the incident endpoints return 503 and `/ready` reports the
database as not configured; `/health` and `/v1/evidence` keep working.

## Data model

```
incidents            1 --- n   evidence_snapshots   1 --- n   evidence_items
  id, title,                     id, incident_id,               (snapshot_id, evidence_id) PK
  description,                   collected_at, window,          position, source, kind,
  severity, window,              services, evidence_count,      service, observed_at, summary,
  services, created_at           source_counts, source_errors   query, reference, data (JSONB)
```

- Snapshots and items are written once and never updated. Re-collecting adds a snapshot.
- Evidence items are rows, keyed by their stable evidence ID within the snapshot, so a
  diagnosis (M4) can cite `ev-...` IDs and the citation can be checked with a lookup.
- `position` keeps the order the collectors returned. A stored snapshot is returned exactly
  as `/v1/evidence` returned it at collection time (covered by a test).
- Evidence is collected before the database transaction opens, so slow backends never
  hold a transaction or connection.

Schema changes go through Alembic (`backend/migrations/`). CI applies all migrations, runs
`alembic check` to confirm the models match them, downgrades to an empty schema, and
upgrades again.

## Testing

Database tests use `APP_TEST_DATABASE_URL` (the `incidents_test` database, created when the
compose volume is first initialized). Each test starts from empty tables. As a safeguard,
the tests refuse to run unless the database name ends in `_test`. Without the variable they
are skipped locally and fail in CI. Test settings ignore `.env` files, so other tests never
connect to a developer's database.

## Known limitations

- No authentication or authorization on any endpoint.
- Incidents cannot be updated or deleted yet, and there is no status field (open/resolved);
  both are left for when the investigation workflow needs them.
- No retention policy: snapshots accumulate until the database is reset.
- The incident window is fixed at creation; re-snapshots always use the same window.
- The listing has no filters beyond pagination.
