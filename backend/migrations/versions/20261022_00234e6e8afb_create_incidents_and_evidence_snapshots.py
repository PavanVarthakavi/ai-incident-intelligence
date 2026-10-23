"""create incidents and evidence snapshots

Revision ID: 00234e6e8afb
Revises:
Create Date: 2026-10-22 22:46:27.260532
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "00234e6e8afb"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("services", sa.ARRAY(sa.String(length=128)), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')", name=op.f("ck_incidents_severity")
        ),
        sa.CheckConstraint("window_end > window_start", name=op.f("ck_incidents_window_order")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(op.f("ix_incidents_created_at"), "incidents", ["created_at"], unique=False)
    op.create_table(
        "evidence_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("services", sa.ARRAY(sa.String(length=128)), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("source_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_evidence_snapshots_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_snapshots")),
    )
    op.create_index(
        op.f("ix_evidence_snapshots_incident_id"),
        "evidence_snapshots",
        ["incident_id"],
        unique=False,
    )
    op.create_table(
        "evidence_items",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("service", sa.String(length=128), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["evidence_snapshots.id"],
            name=op.f("fk_evidence_items_snapshot_id_evidence_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "evidence_id", name=op.f("pk_evidence_items")),
    )


def downgrade() -> None:
    op.drop_table("evidence_items")
    op.drop_index(op.f("ix_evidence_snapshots_incident_id"), table_name="evidence_snapshots")
    op.drop_table("evidence_snapshots")
    op.drop_index(op.f("ix_incidents_created_at"), table_name="incidents")
    op.drop_table("incidents")
