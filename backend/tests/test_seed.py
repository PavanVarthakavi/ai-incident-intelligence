"""Loading evaluation cases into the database (eval/seed.py)."""

import asyncio

import pytest
from sqlalchemy import create_engine, text

from eval.seed import seed
from tests.conftest import hermetic_settings


def test_seed_stores_case_snapshot_and_baseline_diagnosis(test_database_url: str) -> None:
    settings = hermetic_settings(database_url=test_database_url)

    asyncio.run(seed(["F14", "F17"], True, settings, reset=True))
    asyncio.run(seed(["F14"], True, settings))  # already seeded: skipped

    engine = create_engine(test_database_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT i.title, s.evidence_count, d.status, d.validation_errors "
                "FROM incidents i JOIN evidence_snapshots s ON s.incident_id = i.id "
                "JOIN diagnoses d ON d.snapshot_id = s.id ORDER BY s.evidence_count"
            )
        ).all()
    engine.dispose()
    assert [(r.title, r.evidence_count, r.status) for r in rows] == [
        ("Checkout requests are failing", 5, "invalid"),
        ("Checkout failing since the gateway release", 8, "valid"),
    ]
    assert rows[0].validation_errors == ["recommended_actions[3]: no evidence cited"]


def test_reset_refuses_databases_not_named_for_tests() -> None:
    settings = hermetic_settings(database_url="postgresql+psycopg://u:p@localhost:1/incidents")
    with pytest.raises(SystemExit, match="refusing to reset 'incidents'"):
        asyncio.run(seed(["F14"], True, settings, reset=True))
