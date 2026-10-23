"""Conversion from ORM rows to API models."""

from app.db.models import EvidenceSnapshot, Incident
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


def incident_summary(incident: Incident) -> IncidentSummary:
    return IncidentSummary(
        id=incident.id,
        title=incident.title,
        severity=Severity(incident.severity) if incident.severity else None,
        window=window_of(incident),
        services=incident.services,
        created_at=incident.created_at,
    )


def incident_read(incident: Incident) -> IncidentRead:
    return IncidentRead(
        **incident_summary(incident).model_dump(),
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
