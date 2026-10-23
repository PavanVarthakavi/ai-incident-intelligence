"""Citation checks: every claim must cite evidence that exists in the snapshot.

A source with no evidence in the snapshot is citable too, as ``src-<source>``: either it
could not be collected (a source error), or it was queried and returned nothing. Claims
about missing or absent data, such as an action to re-run a failed query or to look for
records the snapshot lacks, then point at the gap they respond to instead of citing nothing.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.diagnosis.schemas import DiagnosisOutput
from app.evidence.models import EvidenceSource


def source_error_id(source: str) -> str:
    return f"src-{source}"


@dataclass(frozen=True)
class SourceGap:
    source: str
    kind: Literal["failed", "empty"]
    message: str | None = None  # the collection error, for failed sources


def source_gaps(
    present_sources: Iterable[str], source_errors: Iterable[Mapping[str, Any]]
) -> dict[str, SourceGap]:
    """Sources without evidence, keyed by their citable ID.

    Every collection queries every source, so a source with neither evidence nor an error
    was queried and returned nothing.
    """
    failed = {e["source"]: e["message"] for e in source_errors}
    present = set(present_sources)
    gaps: dict[str, SourceGap] = {}
    for source in EvidenceSource:
        if source in failed:
            gaps[source_error_id(source)] = SourceGap(source, "failed", failed[source])
        elif source not in present:
            gaps[source_error_id(source)] = SourceGap(source, "empty")
    return gaps


def citable_ids(
    evidence: Iterable[tuple[str, str]], source_errors: Iterable[Mapping[str, Any]]
) -> set[str]:
    """Evidence IDs, given as (id, source) pairs, plus one ID per source without evidence."""
    pairs = list(evidence)
    return {i for i, _ in pairs} | set(source_gaps((s for _, s in pairs), source_errors))


def citation_errors(output: DiagnosisOutput, known_ids: set[str]) -> list[str]:
    """Return human-readable problems; an empty list means the diagnosis is valid."""
    errors: list[str] = []

    def check(where: str, ids: list[str]) -> None:
        if not ids:
            errors.append(f"{where}: no evidence cited")
        for evidence_id in ids:
            if evidence_id not in known_ids:
                errors.append(f"{where}: cites {evidence_id!r}, which is not in the snapshot")

    if output.root_cause is not None:
        check("root_cause", output.root_cause.evidence_ids)
    for i, claim in enumerate(output.contributing_factors):
        check(f"contributing_factors[{i}]", claim.evidence_ids)
    for i, entry in enumerate(output.timeline):
        check(f"timeline[{i}]", entry.evidence_ids)
    for i, claim in enumerate(output.ruled_out):
        check(f"ruled_out[{i}]", claim.evidence_ids)
    for i, action in enumerate(output.recommended_actions):
        check(f"recommended_actions[{i}]", action.evidence_ids)
    return errors
