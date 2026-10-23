"""Database access for incidents. Callers own the transaction."""

import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Diagnosis, EvidenceItem, EvidenceSnapshot, Incident
from app.evidence.models import EvidenceBundle
from app.incidents.schemas import IncidentCreate


def add_incident(session: AsyncSession, data: IncidentCreate) -> Incident:
    incident = Incident(
        title=data.title,
        description=data.description,
        severity=data.severity.value if data.severity else None,
        window_start=data.window.start,
        window_end=data.window.end,
        services=data.services,
        snapshots=[],
    )
    session.add(incident)
    return incident


def add_snapshot(
    session: AsyncSession, incident: Incident, bundle: EvidenceBundle
) -> EvidenceSnapshot:
    snapshot = EvidenceSnapshot(
        collected_at=bundle.collected_at,
        window_start=bundle.window.start,
        window_end=bundle.window.end,
        services=bundle.services,
        evidence_count=len(bundle.evidence),
        source_counts=dict(Counter(e.source.value for e in bundle.evidence)),
        source_errors=[e.model_dump(mode="json") for e in bundle.errors],
        items=[
            EvidenceItem(
                evidence_id=e.id,
                position=position,
                source=e.source.value,
                kind=e.kind,
                service=e.service,
                observed_at=e.observed_at,
                summary=e.summary,
                query=e.query,
                reference=e.reference,
                data=e.model_dump(mode="json")["data"],
            )
            for position, e in enumerate(bundle.evidence)
        ],
    )
    incident.snapshots.append(snapshot)
    return snapshot


async def get_incident(session: AsyncSession, incident_id: uuid.UUID) -> Incident | None:
    return await session.scalar(
        select(Incident).where(Incident.id == incident_id).options(selectinload(Incident.snapshots))
    )


async def list_incidents(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Incident], int]:
    total = await session.scalar(select(func.count()).select_from(Incident))
    rows = await session.scalars(
        select(Incident)
        .order_by(Incident.created_at.desc(), Incident.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def get_snapshot(
    session: AsyncSession, incident_id: uuid.UUID, snapshot_id: uuid.UUID
) -> EvidenceSnapshot | None:
    return await session.scalar(
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.id == snapshot_id, EvidenceSnapshot.incident_id == incident_id)
        .options(selectinload(EvidenceSnapshot.items))
    )


async def list_diagnoses(session: AsyncSession, snapshot_id: uuid.UUID) -> list[Diagnosis]:
    rows = await session.scalars(
        select(Diagnosis)
        .where(Diagnosis.snapshot_id == snapshot_id)
        .order_by(Diagnosis.created_at.desc(), Diagnosis.id)
    )
    return list(rows)


async def get_diagnosis(
    session: AsyncSession, snapshot_id: uuid.UUID, diagnosis_id: uuid.UUID
) -> Diagnosis | None:
    return await session.scalar(
        select(Diagnosis).where(Diagnosis.id == diagnosis_id, Diagnosis.snapshot_id == snapshot_id)
    )
