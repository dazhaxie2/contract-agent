"""Add user_profiles table for long-term user memory.

Revision ID: 20260514_0004
Revises: 20260406_0003
Create Date: 2026-05-14 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260514_0004"
down_revision = "20260406_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("industry", sa.String(128), nullable=False, server_default=""),
        sa.Column("company_type", sa.String(128), nullable=False, server_default=""),
        sa.Column("common_contract_types", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("focus_areas", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("compliance_rules", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("preferences", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_user_profile_tenant_user", "user_profiles", ["tenant_id", "user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_user_profile_tenant_user", table_name="user_profiles")
    op.drop_table("user_profiles")
