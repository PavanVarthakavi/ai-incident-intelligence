"""Incident API.

Evidence is collected before the database transaction starts, so slow
backends never hold a transaction open.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.backends import BackendsDep
from app.db.models import Incident
from app.db.session import SessionDep
from app.incidents import repository
from app.incidents.mapping import incident_read, incident_summary, snapshot_read, window_of
from app.incidents.schemas import IncidentCreate, IncidentPage, IncidentRead, SnapshotRead

router = APIRouter(prefix="/v1/incidents", tags=["incidents"])


async def _require_incident(session: SessionDep, incident_id: uuid.UUID) -> Incident:
    incident = await repository.get_incident(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@router.post("", status_code=status.HTTP_201_CREATED, response_model=IncidentRead)
async def create_incident(
    data: IncidentCreate, session: SessionDep, backends: BackendsDep
) -> IncidentRead:
    """Create an incident and, by default, snapshot the evidence for its window.

    Backend failures do not block creation: they are stored in the snapshot's
    `source_errors`.
    """
    bundle = (
        await backends.evidence.collect(data.window, data.services)
        if data.collect_evidence
        else None
    )
    async with session.begin():
        incident = repository.add_incident(session, data)
        if bundle is not None:
            repository.add_snapshot(session, incident, bundle)
    return incident_read(incident)


@router.get("", response_model=IncidentPage)
async def list_incidents(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IncidentPage:
    incidents, total = await repository.list_incidents(session, limit=limit, offset=offset)
    latest = await repository.latest_diagnoses(session, [i.id for i in incidents])
    return IncidentPage(
        items=[incident_summary(i, latest.get(i.id)) for i in incidents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: uuid.UUID, session: SessionDep) -> IncidentRead:
    incident = await _require_incident(session, incident_id)
    latest = await repository.latest_diagnoses(session, [incident.id])
    return incident_read(incident, latest.get(incident.id))


@router.post(
    "/{incident_id}/snapshots", status_code=status.HTTP_201_CREATED, response_model=SnapshotRead
)
async def create_snapshot(
    incident_id: uuid.UUID, session: SessionDep, backends: BackendsDep
) -> SnapshotRead:
    """Collect evidence for the incident's window again and store it as a new snapshot.

    Useful when telemetry arrived after the incident was created. Earlier
    snapshots are kept unchanged.
    """
    incident = await _require_incident(session, incident_id)
    await session.commit()  # end the read transaction before calling backends
    bundle = await backends.evidence.collect(window_of(incident), incident.services)
    async with session.begin():
        snapshot = repository.add_snapshot(session, incident, bundle)
    return snapshot_read(snapshot)


@router.get("/{incident_id}/snapshots/{snapshot_id}", response_model=SnapshotRead)
async def get_snapshot(
    incident_id: uuid.UUID, snapshot_id: uuid.UUID, session: SessionDep
) -> SnapshotRead:
    snapshot = await repository.get_snapshot(session, incident_id, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return snapshot_read(snapshot)
