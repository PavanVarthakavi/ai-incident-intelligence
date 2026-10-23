"""Conversion from ORM rows to API models."""

from app.db.models import Diagnosis, EvidenceSnapshot, Incident
from app.diagnosis.schemas import DiagnosisBrief, DiagnosisStatus
from app.evidence.models import Evidence, EvidenceSource, TimeWindow
from app.incidents.schemas import (
    IncidentRead,
    IncidentSummary,
    Severity,
    SnapshotRead,
    SnapshotSummary,
)


def window_of(row: Incident | EvidenceSnapshot) -> TimeWindow:
    return TimeWindow(start=row.window_start, end=row.window_end)


def diagnosis_brief(diagnosis: Diagnosis | None) -> DiagnosisBrief | None:
    if diagnosis is None:
        return None
    root = (diagnosis.output or {}).get("root_cause")
    return DiagnosisBrief(
        id=diagnosis.id,
        snapshot_id=diagnosis.snapshot_id,
        status=DiagnosisStatus(diagnosis.status),
        created_at=diagnosis.created_at,
        root_cause_service=root.get("service") if root else None,
        confidence=root.get("confidence") if root else None,
    )


def incident_summary(incident: Incident, latest: Diagnosis | None = None) -> IncidentSummary:
    return IncidentSummary(
        id=incident.id,
        title=incident.title,
        severity=Severity(incident.severity) if incident.severity else None,
        window=window_of(incident),
        services=incident.services,
        created_at=incident.created_at,
        latest_diagnosis=diagnosis_brief(latest),
    )


def incident_read(incident: Incident, latest: Diagnosis | None = None) -> IncidentRead:
    return IncidentRead(
        **incident_summary(incident, latest).model_dump(),
        description=incident.description,
        snapshots=[SnapshotSummary.model_validate(s) for s in incident.snapshots],
    )


def snapshot_read(snapshot: EvidenceSnapshot) -> SnapshotRead:
    return SnapshotRead(
        **SnapshotSummary.model_validate(snapshot).model_dump(),
        incident_id=snapshot.incident_id,
        window=window_of(snapshot),
        services=snapshot.services,
        evidence=[
            Evidence(
                id=item.evidence_id,
                source=EvidenceSource(item.source),
                kind=item.kind,
                service=item.service,
                observed_at=item.observed_at,
                summary=item.summary,
                query=item.query,
                reference=item.reference,
                data=item.data,
            )
            for item in snapshot.items
        ],
    )
