"""API models for incidents and evidence snapshots."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.diagnosis.schemas import DiagnosisBrief
from app.evidence.models import Evidence, EvidenceSource, SourceError, TimeWindow

ServiceName = Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=True)]


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentCreate(BaseModel):
    title: Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
    description: str | None = Field(default=None, max_length=5000)
    severity: Severity | None = None
    window: TimeWindow
    services: list[ServiceName] | None = Field(
        default=None, max_length=20, description="Services in scope; null means all."
    )
    collect_evidence: bool = Field(
        default=True, description="Collect and store an evidence snapshot on creation."
    )


class SnapshotSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collected_at: datetime
    evidence_count: int
    source_counts: dict[EvidenceSource, int]
    source_errors: list[SourceError]


class IncidentSummary(BaseModel):
    id: uuid.UUID
    title: str
    severity: Severity | None
    window: TimeWindow
    services: list[str] | None
    created_at: datetime
    latest_diagnosis: DiagnosisBrief | None = Field(
        description="Newest diagnosis across the incident's snapshots."
    )


class IncidentRead(IncidentSummary):
    description: str | None
    snapshots: list[SnapshotSummary] = Field(description="Oldest first.")


class IncidentPage(BaseModel):
    items: list[IncidentSummary] = Field(description="Newest first.")
    total: int
    limit: int
    offset: int


class SnapshotRead(SnapshotSummary):
    incident_id: uuid.UUID
    window: TimeWindow
    services: list[str] | None
    evidence: list[Evidence] = Field(description="In the order they were collected.")
