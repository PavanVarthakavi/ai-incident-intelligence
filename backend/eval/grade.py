"""Exact-check grading against each case's known answer. No model calls.

Metrics per case (None when a metric does not apply to the case):

- correct:     faulty case: root cause names the faulty service.
               healthy case: no root cause.
- recall:      `correct` on faulty cases only.
- specificity: `correct` on healthy cases only.
- release:     deploy-caused cases: the root-cause statement names the bad release.
- citations:   every claim cites evidence from the snapshot (the app's own check).
"""

import re
from typing import Any

from app.diagnosis.schemas import DiagnosisOutput
from app.diagnosis.validation import citable_ids, citation_errors

METRICS = ("correct", "recall", "specificity", "release", "citations")


def mentions_version(text: str, version: str) -> bool:
    """True if ``version`` appears as a whole version (3.2.1 does not match 3.2.10)."""
    # Not preceded by a digit or "digit.", not followed by a digit or ".digit".
    return re.search(rf"(?<!\d)(?<!\d\.){re.escape(version)}(?!\.?\d)", text) is not None


def evidence_ids(case: dict[str, Any]) -> set[str]:
    return {e["id"] for e in case["snapshot"]["evidence"]}


def known_ids(case: dict[str, Any]) -> set[str]:
    """What a diagnosis of this case may cite: its evidence and its failed sources."""
    snap = case["snapshot"]
    return citable_ids(((e["id"], e["source"]) for e in snap["evidence"]), snap["source_errors"])


def grade(case: dict[str, Any], output: DiagnosisOutput) -> dict[str, float | None]:
    expected_service = case["expected"]["root_cause_service"]
    expected_release = case["expected"]["release"]
    root = output.root_cause

    if expected_service is None:
        correct = root is None
    else:
        correct = root is not None and (root.service or "").strip().lower() == expected_service

    release = None
    if expected_release is not None:
        release = float(root is not None and mentions_version(root.statement, expected_release))

    return {
        "correct": float(correct),
        "recall": float(correct) if expected_service is not None else None,
        "specificity": float(correct) if expected_service is None else None,
        "release": release,
        "citations": float(not citation_errors(output, known_ids(case))),
    }


def oracle_output(case: dict[str, Any]) -> DiagnosisOutput:
    """A diagnosis that matches the known answer, for checking the grader end to end."""
    ids = sorted(evidence_ids(case))[:1] or ["ev-none"]
    service = case["expected"]["root_cause_service"]
    release = case["expected"]["release"]
    root = None
    if service is not None:
        statement = f"{service} is the origin" + (f" after release {release}" if release else "")
        root = {
            "statement": statement,
            "service": service,
            "confidence": "high",
            "evidence_ids": ids,
        }
    return DiagnosisOutput.model_validate(
        {
            "summary": "oracle",
            "root_cause": root,
            "contributing_factors": [],
            "timeline": [],
            "ruled_out": [],
            "unknowns": [],
            "recommended_actions": [],
        }
    )


def constant_output(service: str | None) -> DiagnosisOutput:
    """A null baseline: the same answer for every case, citing nothing."""
    oracle = oracle_output(
        {"snapshot": {"evidence": []}, "expected": {"root_cause_service": service, "release": None}}
    )
    if oracle.root_cause:
        oracle.root_cause.evidence_ids = []
    return oracle
