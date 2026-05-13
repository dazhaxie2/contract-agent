"""baseline schema for hidb cutover

Revision ID: 20260406_0001
Revises:
Create Date: 2026-04-06 00:01:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260406_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("industry", sa.String(length=64), nullable=True),
        sa.Column("company_type", sa.String(length=64), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"], unique=False)
    op.create_index("idx_user_tenant_role", "users", ["tenant_id", "role"], unique=False)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_history", sa.JSON(), nullable=False),
        sa.Column("entity_memory", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_index("ix_user_sessions_tenant_id", "user_sessions", ["tenant_id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("issuing_authority", sa.String(length=256), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applicable_industry", sa.JSON(), nullable=False),
        sa.Column("applicable_region", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("metadata_extra", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_effective", sa.Boolean(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("process_error", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"], unique=False)
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"], unique=False)
    op.create_index("idx_doc_type_status", "documents", ["doc_type", "status"], unique=False)
    op.create_index("idx_doc_tenant_type_date", "documents", ["tenant_id", "doc_type", "effective_date"], unique=False)
    op.create_index("idx_doc_effective", "documents", ["is_effective", "effective_date"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("doc_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("chunk_type", sa.String(length=32), nullable=False),
        sa.Column("parent_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("hierarchy_path", sa.String(length=512), nullable=True),
        sa.Column("hierarchy_level", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("legal_priority", sa.Integer(), nullable=False),
        sa.Column("entity_tags", sa.JSON(), nullable=False),
        sa.Column("metadata_extra", sa.JSON(), nullable=False),
        sa.Column("vector_status", sa.String(length=32), nullable=False),
        sa.Column("graph_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_doc_id", "document_chunks", ["doc_id"], unique=False)
    op.create_index("ix_document_chunks_tenant_id", "document_chunks", ["tenant_id"], unique=False)
    op.create_index("idx_chunk_doc_index", "document_chunks", ["doc_id", "chunk_index"], unique=False)
    op.create_index("idx_chunk_hierarchy", "document_chunks", ["doc_id", "hierarchy_path"], unique=False)
    op.create_index("idx_chunk_tenant_type", "document_chunks", ["tenant_id", "chunk_type"], unique=False)

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("target_model_type", sa.String(length=32), nullable=True),
        sa.Column("target_agent", sa.String(length=64), nullable=True),
        sa.Column("output_format", sa.String(length=32), nullable=True),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("validation_rules", sa.JSON(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("avg_quality_score", sa.Float(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_templates_tenant_id", "prompt_templates", ["tenant_id"], unique=False)
    op.create_index("idx_prompt_tenant_category", "prompt_templates", ["tenant_id", "category"], unique=False)
    op.create_index("idx_prompt_task_type", "prompt_templates", ["task_type", "status"], unique=False)
    op.create_index("idx_prompt_agent", "prompt_templates", ["target_agent", "status"], unique=False)

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("output_format", sa.String(length=32), nullable=True),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("validation_rules", sa.JSON(), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("evaluation_results", sa.JSON(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_versions_template_id", "prompt_versions", ["template_id"], unique=False)
    op.create_index("ix_prompt_versions_tenant_id", "prompt_versions", ["tenant_id"], unique=False)
    op.create_index("idx_prompt_version_template", "prompt_versions", ["template_id", "version"], unique=True)

    op.create_table(
        "model_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("top_p", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("frequency_penalty", sa.Float(), nullable=False),
        sa.Column("presence_penalty", sa.Float(), nullable=False),
        sa.Column("stop_sequences", sa.JSON(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("supports_function_calling", sa.Boolean(), nullable=False),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("max_concurrent_requests", sa.Integer(), nullable=False),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("api_endpoint", sa.String(length=512), nullable=True),
        sa.Column("api_key_encrypted", sa.String(length=1024), nullable=True),
        sa.Column("extra_headers", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("avg_tokens_per_second", sa.Float(), nullable=True),
        sa.Column("error_rate", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("extra_config", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_configs_tenant_id", "model_configs", ["tenant_id"], unique=False)
    op.create_index("idx_model_tenant_type", "model_configs", ["tenant_id", "model_type"], unique=False)
    op.create_index("idx_model_provider_active", "model_configs", ["provider", "is_active"], unique=False)

    op.create_table(
        "model_deployments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_config_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("deployment_name", sa.String(length=128), nullable=False),
        sa.Column("deployment_type", sa.String(length=32), nullable=False),
        sa.Column("endpoint_url", sa.String(length=512), nullable=True),
        sa.Column("replicas", sa.Integer(), nullable=False),
        sa.Column("gpu_type", sa.String(length=32), nullable=True),
        sa.Column("gpu_count", sa.Integer(), nullable=False),
        sa.Column("cpu_limit", sa.String(length=16), nullable=True),
        sa.Column("memory_limit", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("health_status", sa.String(length=32), nullable=False),
        sa.Column("current_qps", sa.Float(), nullable=False),
        sa.Column("max_qps", sa.Float(), nullable=False),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False),
        sa.Column("p99_latency_ms", sa.Float(), nullable=False),
        sa.Column("deploy_config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_deployments_model_config_id", "model_deployments", ["model_config_id"], unique=False)
    op.create_index("ix_model_deployments_tenant_id", "model_deployments", ["tenant_id"], unique=False)

    op.create_table(
        "ab_tests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("test_type", sa.String(length=32), nullable=False),
        sa.Column("control_config_id", sa.Uuid(), nullable=False),
        sa.Column("treatment_config_id", sa.Uuid(), nullable=False),
        sa.Column("traffic_split", sa.Float(), nullable=False),
        sa.Column("primary_metric", sa.String(length=64), nullable=False),
        sa.Column("metrics_config", sa.JSON(), nullable=False),
        sa.Column("control_metrics", sa.JSON(), nullable=False),
        sa.Column("treatment_metrics", sa.JSON(), nullable=False),
        sa.Column("winner", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ab_tests_tenant_id", "ab_tests", ["tenant_id"], unique=False)

    op.create_table(
        "agent_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("parsed_intent", sa.String(length=128), nullable=True),
        sa.Column("parsed_entities", sa.JSON(), nullable=False),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column("model_config_id", sa.Uuid(), nullable=True),
        sa.Column("prompt_template_id", sa.Uuid(), nullable=True),
        sa.Column("total_steps", sa.Integer(), nullable=False),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("result_metadata", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("factuality_score", sa.Float(), nullable=True),
        sa.Column("user_feedback", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("retrieval_latency_ms", sa.Float(), nullable=True),
        sa.Column("generation_latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_executions_trace_id", "agent_executions", ["trace_id"], unique=True)
    op.create_index("ix_agent_executions_session_id", "agent_executions", ["session_id"], unique=False)
    op.create_index("ix_agent_executions_user_id", "agent_executions", ["user_id"], unique=False)
    op.create_index("ix_agent_executions_tenant_id", "agent_executions", ["tenant_id"], unique=False)
    op.create_index("idx_exec_tenant_status", "agent_executions", ["tenant_id", "status"], unique=False)
    op.create_index("idx_exec_user_time", "agent_executions", ["user_id", "created_at"], unique=False)
    op.create_index("idx_exec_task_type", "agent_executions", ["task_type", "created_at"], unique=False)

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("span_id", sa.String(length=64), nullable=False),
        sa.Column("parent_span_id", sa.String(length=64), nullable=True),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=32), nullable=False),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column("thought", sa.Text(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=True),
        sa.Column("action_input", sa.JSON(), nullable=False),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column("tool_input", sa.JSON(), nullable=False),
        sa.Column("tool_output", sa.Text(), nullable=True),
        sa.Column("retrieved_chunks", sa.JSON(), nullable=False),
        sa.Column("retrieval_scores", sa.JSON(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_steps_execution_id", "agent_steps", ["execution_id"], unique=False)
    op.create_index("ix_agent_steps_trace_id", "agent_steps", ["trace_id"], unique=False)
    op.create_index("idx_step_execution", "agent_steps", ["execution_id", "step_number"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("request_method", sa.String(length=10), nullable=True),
        sa.Column("request_path", sa.String(length=512), nullable=True),
        sa.Column("request_body", sa.JSON(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"], unique=False)
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"], unique=False)
    op.create_index("idx_audit_tenant_time", "audit_logs", ["tenant_id", "created_at"], unique=False)
    op.create_index("idx_audit_action_resource", "audit_logs", ["action", "resource_type"], unique=False)
    op.create_index("idx_audit_user_time", "audit_logs", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("agent_steps")
    op.drop_table("agent_executions")
    op.drop_table("ab_tests")
    op.drop_table("model_deployments")
    op.drop_table("model_configs")
    op.drop_table("prompt_versions")
    op.drop_table("prompt_templates")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("user_sessions")
    op.drop_table("users")
