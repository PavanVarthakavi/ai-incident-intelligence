"""add diagnoses

Revision ID: 999b2b42d850
Revises: 00234e6e8afb
Create Date: 2026-10-22 23:26:26.071803
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "999b2b42d850"
down_revision: str | None = "00234e6e8afb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnoses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_requested", sa.String(length=64), nullable=False),
        sa.Column("model_used", sa.String(length=64), nullable=True),
        sa.Column("effort", sa.String(length=16), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_errors", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stop_reason", sa.String(length=32), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=False),
        sa.Column("reserved_cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'valid', 'invalid', 'refused', 'error')",
            name=op.f("ck_diagnoses_status"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["evidence_snapshots.id"],
            name=op.f("fk_diagnoses_snapshot_id_evidence_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diagnoses")),
    )
    op.create_index(op.f("ix_diagnoses_created_at"), "diagnoses", ["created_at"], unique=False)
    op.create_index(op.f("ix_diagnoses_snapshot_id"), "diagnoses", ["snapshot_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_diagnoses_snapshot_id"), table_name="diagnoses")
    op.drop_index(op.f("ix_diagnoses_created_at"), table_name="diagnoses")
    op.drop_table("diagnoses")
