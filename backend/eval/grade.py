"""Exact-check grading against each case's known answer. No model calls.

Metrics per case (None when a metric does not apply to the case):

- correct:     faulty case: root cause names the faulty service (or one of the
               case's also_accepted services, when it has two real faults).
               healthy case: no root cause.
- recall:      `correct` on faulty cases only.
- specificity: `correct` on healthy cases only.
- release:     deploy-caused cases: the root-cause statement names the bad release.
- citations:   every claim cites evidence from the snapshot (the app's own check).
- complete:    two-fault cases: every faulty service is named in the root cause, a
               contributing factor, or the timeline (a ruled-out mention does not count).
"""

import re
from typing import Any

from app.diagnosis.schemas import DiagnosisOutput
from app.diagnosis.validation import citable_ids, citation_errors

METRICS = ("correct", "recall", "specificity", "release", "citations", "complete")


def mentions_version(text: str, version: str) -> bool:
    """True if ``version`` appears as a whole version (3.2.1 does not match 3.2.10)."""
    # Not preceded by a digit or "digit.", not followed by a digit or ".digit".
    return re.search(rf"(?<!\d)(?<!\d\.){re.escape(version)}(?!\.?\d)", text) is not None


def names_service(text: str, service: str) -> bool:
    return re.search(rf"\b{re.escape(service)}\b", text, re.IGNORECASE) is not None


def identified_text(output: DiagnosisOutput) -> str:
    """The parts of a diagnosis that assert a problem: root cause, factors, timeline."""
    parts = (
        [f"{output.root_cause.service or ''} {output.root_cause.statement}"]
        if output.root_cause
        else []
    )
    parts += [c.statement for c in output.contributing_factors]
    parts += [e.event for e in output.timeline]
    return "\n".join(parts)


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
        accepted = {expected_service, *case["expected"].get("also_accepted", [])}
        correct = root is not None and (root.service or "").strip().lower() in accepted

    release = None
    if expected_release is not None:
        release = float(root is not None and mentions_version(root.statement, expected_release))

    complete = None
    also = case["expected"].get("also_accepted", [])
    if also:
        text = identified_text(output)
        complete = float(all(names_service(text, s) for s in (expected_service, *also)))

    return {
        "correct": float(correct),
        "recall": float(correct) if expected_service is not None else None,
        "specificity": float(correct) if expected_service is None else None,
        "release": release,
        "citations": float(not citation_errors(output, known_ids(case))),
        "complete": complete,
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
            "contributing_factors": [
                {"statement": f"{other} is also faulty", "evidence_ids": ids}
                for other in case["expected"].get("also_accepted", [])
            ],
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
