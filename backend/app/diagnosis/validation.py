"""Citation checks: every claim must cite evidence that exists in the snapshot."""

from app.diagnosis.schemas import DiagnosisOutput


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
