"""roadmap core tables for sessions, memory, ingestion, retrieval and citations

Revision ID: 20260406_0002
Revises: 20260406_0001
Create Date: 2026-04-06 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260406_0002"
down_revision = "20260406_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_extra", sa.JSON(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"], unique=False)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("idx_session_tenant_user_time", "sessions", ["tenant_id", "user_id", "updated_at"], unique=False)
    op.create_index("idx_session_tenant_status", "sessions", ["tenant_id", "status"], unique=False)

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_extra", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_messages_session_id", "conversation_messages", ["session_id"], unique=False)
    op.create_index("ix_conversation_messages_tenant_id", "conversation_messages", ["tenant_id"], unique=False)
    op.create_index("ix_conversation_messages_user_id", "conversation_messages", ["user_id"], unique=False)
    op.create_index("idx_message_session_order", "conversation_messages", ["session_id", "message_index"], unique=True)
    op.create_index("idx_message_tenant_time", "conversation_messages", ["tenant_id", "created_at"], unique=False)

    op.create_table(
        "memory_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("fact_key", sa.String(length=128), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_facts_session_id", "memory_facts", ["session_id"], unique=False)
    op.create_index("ix_memory_facts_tenant_id", "memory_facts", ["tenant_id"], unique=False)
    op.create_index("idx_memory_fact_session_key", "memory_facts", ["session_id", "fact_key"], unique=True)
    op.create_index("idx_memory_fact_tenant_time", "memory_facts", ["tenant_id", "updated_at"], unique=False)

    op.create_table(
        "memory_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("summary_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("window_start_index", sa.Integer(), nullable=False),
        sa.Column("window_end_index", sa.Integer(), nullable=False),
        sa.Column("metadata_extra", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_summaries_session_id", "memory_summaries", ["session_id"], unique=False)
    op.create_index("ix_memory_summaries_tenant_id", "memory_summaries", ["tenant_id"], unique=False)
    op.create_index(
        "idx_memory_summary_session_type",
        "memory_summaries",
        ["session_id", "summary_type", "updated_at"],
        unique=False,
    )
    op.create_index("idx_memory_summary_tenant_time", "memory_summaries", ["tenant_id", "updated_at"], unique=False)

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("doc_id", sa.Uuid(), nullable=True),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("doc_type", sa.String(length=32), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_jobs_tenant_id", "ingestion_jobs", ["tenant_id"], unique=False)
    op.create_index("ix_ingestion_jobs_doc_id", "ingestion_jobs", ["doc_id"], unique=False)
    op.create_index("ix_ingestion_jobs_file_hash", "ingestion_jobs", ["file_hash"], unique=False)
    op.create_index("idx_ingestion_tenant_status", "ingestion_jobs", ["tenant_id", "status", "created_at"], unique=False)
    op.create_index("idx_ingestion_tenant_doc", "ingestion_jobs", ["tenant_id", "doc_id"], unique=False)

    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("preprocessed", sa.JSON(), nullable=False),
        sa.Column("vector_hits", sa.JSON(), nullable=False),
        sa.Column("keyword_hits", sa.JSON(), nullable=False),
        sa.Column("graph_hits", sa.JSON(), nullable=False),
        sa.Column("merged_hits", sa.JSON(), nullable=False),
        sa.Column("rerank_scores", sa.JSON(), nullable=False),
        sa.Column("filtered_out", sa.JSON(), nullable=False),
        sa.Column("final_context", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_logs_tenant_id", "retrieval_logs", ["tenant_id"], unique=False)
    op.create_index("ix_retrieval_logs_session_id", "retrieval_logs", ["session_id"], unique=False)
    op.create_index("ix_retrieval_logs_execution_id", "retrieval_logs", ["execution_id"], unique=False)
    op.create_index("idx_retrieval_tenant_time", "retrieval_logs", ["tenant_id", "created_at"], unique=False)
    op.create_index("idx_retrieval_session_time", "retrieval_logs", ["session_id", "created_at"], unique=False)

    op.create_table(
        "citation_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("citation_code", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("locator", sa.String(length=256), nullable=True),
        sa.Column("metadata_extra", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citation_records_tenant_id", "citation_records", ["tenant_id"], unique=False)
    op.create_index("ix_citation_records_session_id", "citation_records", ["session_id"], unique=False)
    op.create_index("ix_citation_records_execution_id", "citation_records", ["execution_id"], unique=False)
    op.create_index("ix_citation_records_document_id", "citation_records", ["document_id"], unique=False)
    op.create_index("ix_citation_records_chunk_id", "citation_records", ["chunk_id"], unique=False)
    op.create_index("ix_citation_records_citation_code", "citation_records", ["citation_code"], unique=False)
    op.create_index("idx_citation_tenant_chunk", "citation_records", ["tenant_id", "chunk_id"], unique=False)
    op.create_index("idx_citation_tenant_code", "citation_records", ["tenant_id", "citation_code"], unique=True)

    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(64)")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS record_hash VARCHAR(64) DEFAULT ''")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant_hash ON audit_logs (tenant_id, record_hash)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_audit_tenant_hash")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS record_hash")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS previous_hash")

    op.drop_table("citation_records")
    op.drop_table("retrieval_logs")
    op.drop_table("ingestion_jobs")
    op.drop_table("memory_summaries")
    op.drop_table("memory_facts")
    op.drop_table("conversation_messages")
    op.drop_table("sessions")
