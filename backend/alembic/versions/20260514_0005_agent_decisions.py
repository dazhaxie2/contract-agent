"""Add persisted agent decision records.

Revision ID: 20260514_0005
Revises: 20260514_0004
Create Date: 2026-05-14 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260514_0005"
down_revision = "20260514_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_decisions",
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False, server_default="contract_review"),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("intent_summary", sa.Text(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("estimated_changes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("context", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("user_confirmation", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("execution_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index("ix_agent_decisions_tenant_id", "agent_decisions", ["tenant_id"], unique=False)
    op.create_index("ix_agent_decisions_user_id", "agent_decisions", ["user_id"], unique=False)
    op.create_index("ix_agent_decisions_session_id", "agent_decisions", ["session_id"], unique=False)
    op.create_index("ix_agent_decisions_execution_id", "agent_decisions", ["execution_id"], unique=False)
    op.create_index("ix_agent_decisions_trace_id", "agent_decisions", ["trace_id"], unique=False)
    op.create_index("idx_decision_tenant_status", "agent_decisions", ["tenant_id", "status"], unique=False)
    op.create_index("idx_decision_user_time", "agent_decisions", ["user_id", "created_at"], unique=False)
    op.create_index("idx_decision_expires", "agent_decisions", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_decision_expires", table_name="agent_decisions")
    op.drop_index("idx_decision_user_time", table_name="agent_decisions")
    op.drop_index("idx_decision_tenant_status", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_trace_id", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_execution_id", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_session_id", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_user_id", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_tenant_id", table_name="agent_decisions")
    op.drop_table("agent_decisions")
