"""ORM models.

Snapshots and their evidence items are written once and never updated, so a
diagnosis can always be checked against exactly the evidence it was based on.
Schema changes go through Alembic migrations in ``backend/migrations``.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Deterministic constraint names keep migrations reviewable and reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

SEVERITIES = ("critical", "high", "medium", "low")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[dict[str, Any]]: JSONB,
        list[str]: ARRAY(String(128)),
    }


class Incident(Base):
    __tablename__ = "incidents"
    # Fetch server-generated values (created_at) in the INSERT, so they are loaded
    # without a lazy refresh, which async sessions cannot do implicitly.
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("window_end > window_start", name="window_order"),
        CheckConstraint(
            "severity IN (" + ", ".join(f"'{s}'" for s in SEVERITIES) + ")", name="severity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(16))
    window_start: Mapped[datetime]
    window_end: Mapped[datetime]
    services: Mapped[list[str] | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    snapshots: Mapped[list["EvidenceSnapshot"]] = relationship(
        back_populates="incident",
        order_by="EvidenceSnapshot.collected_at",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EvidenceSnapshot(Base):
    __tablename__ = "evidence_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    collected_at: Mapped[datetime]
    window_start: Mapped[datetime]
    window_end: Mapped[datetime]
    services: Mapped[list[str] | None]
    # Denormalized at write time; snapshots are immutable, so these never drift.
    evidence_count: Mapped[int] = mapped_column(Integer)
    source_counts: Mapped[dict[str, Any]]
    source_errors: Mapped[list[dict[str, Any]]]

    incident: Mapped[Incident] = relationship(back_populates="snapshots")
    items: Mapped[list["EvidenceItem"]] = relationship(
        order_by="EvidenceItem.position", cascade="all, delete-orphan", passive_deletes=True
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    # The stable evidence ID (ev-...). Unique within a snapshot; citations use it.
    evidence_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(64))
    service: Mapped[str | None] = mapped_column(String(128))
    observed_at: Mapped[datetime | None]
    summary: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]]
