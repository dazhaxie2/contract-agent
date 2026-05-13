"""C/D/F pipeline additions: search_text and ingestion stage events.

Revision ID: 20260406_0003
Revises: 20260406_0002
Create Date: 2026-04-06 22:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260406_0003"
down_revision = "20260406_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("search_text", sa.Text(), nullable=True))
    op.create_index("idx_chunk_tenant_search_text", "document_chunks", ["tenant_id", "search_text"], unique=False)

    op.create_table(
        "ingestion_stage_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_stage_events_job_id", "ingestion_stage_events", ["job_id"], unique=False)
    op.create_index("ix_ingestion_stage_events_tenant_id", "ingestion_stage_events", ["tenant_id"], unique=False)
    op.create_index(
        "idx_ingestion_event_job_stage",
        "ingestion_stage_events",
        ["job_id", "stage", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_ingestion_event_tenant_time",
        "ingestion_stage_events",
        ["tenant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("ingestion_stage_events")
    op.drop_index("idx_chunk_tenant_search_text", table_name="document_chunks")
    op.drop_column("document_chunks", "search_text")

