"""Load evaluation cases into the database as incidents, for demos and end-to-end tests.

    python -m eval.seed                  # every case
    python -m eval.seed F14 F01 H05      # selected cases
    python -m eval.seed --no-diagnoses   # incidents and snapshots only
    python -m eval.seed --reset F14      # empty the database first (test databases only)

Each case becomes an incident with its frozen evidence snapshot. When the baseline run has a
result for the case, its real diagnosis is stored too, with the usage and cost recorded at the
time (those costs count toward the day's budget like any diagnosis created today). Free: no
model calls. Cases already seeded (same title, window, and evidence count) are skipped.
"""

import argparse
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import make_url, select, text

from app.config import Settings
from app.db.models import Diagnosis, EvidenceSnapshot, Incident
from app.db.session import Database
from app.diagnosis.schemas import DiagnosisOutput
from app.diagnosis.validation import citation_errors
from app.evidence.models import Evidence, EvidenceBundle, SourceError, TimeWindow
from app.incidents import repository
from app.incidents.schemas import IncidentCreate
from eval.grade import evidence_ids
from eval.run import RESULTS_DIR, load_cases

BASELINE = RESULTS_DIR / "baseline"


def baseline_results() -> dict[str, dict[str, Any]]:
    path = BASELINE / "results.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return {r["prompt_id"]: r for r in rows if r["rep"] == 0 and r["status"] == "ok"}


def bundle_of(case: dict[str, Any]) -> EvidenceBundle:
    snap = case["snapshot"]
    return EvidenceBundle(
        window=TimeWindow.model_validate(snap["window"]),
        services=case["incident"]["services"],
        collected_at=datetime.fromisoformat(snap["collected_at"]),
        evidence=[Evidence.model_validate(e) for e in snap["evidence"]],
        errors=[SourceError.model_validate(e) for e in snap["source_errors"]],
    )


def diagnosis_of(case: dict[str, Any], result: dict[str, Any], window_end: datetime) -> Diagnosis:
    trace = json.loads((BASELINE / "traces" / f"{case['id']}_rep0.json").read_text())
    output = DiagnosisOutput.model_validate_json(trace[-1]["content"])
    errors = citation_errors(output, evidence_ids(case))
    created = window_end + timedelta(minutes=1)
    cost = Decimal(result["cost_usd"])
    usage = result["usage"]
    return Diagnosis(
        status="invalid" if errors else "valid",
        created_at=created,
        completed_at=created + timedelta(seconds=result["latency_s"]),
        model_requested=result["requested_model"],
        model_used=result["model"],
        effort="medium",
        prompt_version="1",
        output=output.model_dump(mode="json"),
        validation_errors=errors,
        error_message=None,
        stop_reason=result["stop_reason"],
        fallback_used=False,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cache_read_tokens=usage["cache_read_input_tokens"],
        cache_creation_tokens=usage["cache_creation_input_tokens"],
        reserved_cost_usd=cost,
        cost_usd=cost,
        request_id=result["meta"]["request_id"],
    )


async def seed(
    ids: list[str] | None, with_diagnoses: bool, settings: Settings, reset: bool = False
) -> None:
    if settings.database_url is None:
        raise SystemExit("APP_DATABASE_URL is not set")
    url = settings.database_url.get_secret_value()
    name = make_url(url).database or ""
    if reset and not name.endswith("_test"):
        raise SystemExit(f"refusing to reset {name!r}: only databases ending in '_test'")
    database = Database.connect(url)
    results = baseline_results() if with_diagnoses else {}
    try:
        async with database.sessions() as session, session.begin():
            if reset:
                await session.execute(text("TRUNCATE incidents CASCADE"))
                print(f"emptied {name}")
            for case in load_cases(ids):
                bundle = bundle_of(case)
                info = case["incident"]
                # Derived cases share title and window with their base, not evidence count.
                existing = await session.scalar(
                    select(Incident.id)
                    .join(EvidenceSnapshot)
                    .where(
                        Incident.title == info["title"],
                        Incident.window_start == bundle.window.start,
                        EvidenceSnapshot.evidence_count == len(bundle.evidence),
                    )
                )
                if existing:
                    print(f"{case['id']}: already seeded, skipped")
                    continue
                incident = repository.add_incident(
                    session,
                    IncidentCreate(
                        title=info["title"],
                        description=info["description"],
                        severity=info["severity"],
                        window=bundle.window,
                        services=info["services"],
                        collect_evidence=False,
                    ),
                )
                snapshot = repository.add_snapshot(session, incident, bundle)
                await session.flush()
                note = ""
                if case["id"] in results:
                    diagnosis = diagnosis_of(case, results[case["id"]], bundle.window.end)
                    diagnosis.snapshot_id = snapshot.id
                    session.add(diagnosis)
                    note = f", diagnosis {diagnosis.status}"
                print(f"{case['id']}: seeded {len(bundle.evidence)} evidence items{note}")
    finally:
        await database.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="*")
    parser.add_argument("--no-diagnoses", action="store_true")
    parser.add_argument("--reset", action="store_true", help="empty the database first")
    args = parser.parse_args()
    asyncio.run(seed(args.cases or None, not args.no_diagnoses, Settings(), reset=args.reset))


if __name__ == "__main__":
    main()
