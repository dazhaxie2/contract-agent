from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import ReadSessionLocal
from app.core.config import settings
from app.services.connectors.legal_source_connector import LegalSourceDocument
from app.services.llm_service import llm_service


def unwrap_json(resp) -> dict | list:
    payload = resp.json()
    if isinstance(payload, dict) and "data" in payload and "code" in payload:
        return payload["data"]
    return payload


@pytest.mark.asyncio
async def test_models_crud_and_compat(app_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "name": "gpt-legal",
        "display_name": "GPT Legal",
        "description": "test model",
        "model_type": "generation",
        "provider": "aliyun",
        "model_id": "qwen-max",
        "temperature": 0.2,
        "top_p": 0.8,
        "max_tokens": 4096,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "stop_sequences": [],
        "context_window": 32768,
        "supports_function_calling": False,
        "supports_streaming": True,
        "timeout_seconds": 60,
        "max_retries": 3,
        "max_concurrent_requests": 20,
        "requests_per_minute": 300,
        "api_endpoint": "",
        "api_key": "",
        "extra_headers": {},
        "extra_config": {},
    }
    create_resp = await app_client.post("/api/v1/models", json=payload, headers=auth_headers)
    assert create_resp.status_code == 200, create_resp.text
    created = unwrap_json(create_resp)
    model_id = created["id"]

    list_resp = await app_client.get("/api/v1/models?page=1&page_size=10", headers=auth_headers)
    assert list_resp.status_code == 200
    listed = unwrap_json(list_resp)
    assert "items" in listed and "total_pages" in listed
    assert listed["total"] == 1

    metrics_resp = await app_client.get(f"/api/v1/models/{model_id}/metrics", headers=auth_headers)
    assert metrics_resp.status_code == 200
    assert metrics_resp.headers.get("Deprecation") == "true"

    deploy_resp = await app_client.post(
        f"/api/v1/models/{model_id}/deploy",
        json={"deployment_name": "compat-deploy", "replicas": 1},
        headers=auth_headers,
    )
    assert deploy_resp.status_code == 200
    assert deploy_resp.headers.get("Deprecation") == "true"

    undeploy_resp = await app_client.post(f"/api/v1/models/{model_id}/undeploy", headers=auth_headers)
    assert undeploy_resp.status_code == 200
    assert undeploy_resp.headers.get("Deprecation") == "true"


@pytest.mark.asyncio
async def test_prompts_crud_and_compat(app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch) -> None:
    async def fake_generate(**_: dict):
        return {"content": "mock-output", "model": "mock-model", "usage": {"total_tokens": 42}}

    monkeypatch.setattr(llm_service, "generate", fake_generate)

    payload = {
        "name": "contract-review",
        "display_name": "Contract Review",
        "description": "prompt template",
        "category": "task",
        "task_type": "review",
        "system_prompt": "You are a reviewer",
        "user_prompt_template": "Review: {{content}}",
        "variables": [{"name": "content", "type": "string", "default_value": "", "description": "", "required": True}],
        "target_model_type": "generation",
        "target_agent": "master",
        "output_format": "text",
        "output_schema": None,
        "validation_rules": [],
        "tags": ["test"],
    }
    create_resp = await app_client.post("/api/v1/prompts", json=payload, headers=auth_headers)
    assert create_resp.status_code == 200, create_resp.text
    created = unwrap_json(create_resp)
    prompt_id = created["id"]

    compat_test_resp = await app_client.post(
        f"/api/v1/prompts/{prompt_id}/test",
        json={"variables": {"content": "hello"}},
        headers=auth_headers,
    )
    assert compat_test_resp.status_code == 200
    assert compat_test_resp.headers.get("Deprecation") == "true"
    compat_data = unwrap_json(compat_test_resp)
    assert compat_data["output"] == "mock-output"


@pytest.mark.asyncio
async def test_sessions_memory_documents_retrieval_and_citations(
    app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    session_resp = await app_client.post("/api/v1/sessions", json={"title": "S1", "metadata": {}}, headers=auth_headers)
    assert session_resp.status_code == 200, session_resp.text
    session_id = unwrap_json(session_resp)["id"]

    upload_resp = await app_client.post(
        "/api/v1/documents/upload",
        files={"file": ("demo.txt", b"payment clause and liability terms", "text/plain")},
        data={"doc_type": "contract", "title": "Demo Contract", "sync": "true"},
        headers=auth_headers,
    )
    assert upload_resp.status_code == 200, upload_resp.text
    upload_data = unwrap_json(upload_resp)
    job_id = upload_data["job_id"]
    assert upload_data["status"] in {"queued", "processing", "completed"}

    job_resp = await app_client.get(f"/api/v1/documents/jobs/{job_id}", headers=auth_headers)
    assert job_resp.status_code == 200
    job_payload = unwrap_json(job_resp)
    assert job_payload["status"] == "completed", job_payload
    assert "events" in job_payload
    doc_id = job_payload["doc_id"]
    assert doc_id is not None

    docs_resp = await app_client.get("/api/v1/documents?page=1&page_size=10", headers=auth_headers)
    assert docs_resp.status_code == 200
    docs_data = unwrap_json(docs_resp)
    assert docs_data["total"] >= 1

    async def fake_agent_execute(query: str, context: dict | None = None):
        from app.agents.base import AgentResult, AgentStep, StepType

        step = AgentStep(step_type=StepType.FINAL, content="done", tokens_used=12, latency_ms=1.0)
        return AgentResult(success=True, output="analysis complete", steps=[step], metadata={"mock": True})

    monkeypatch.setattr("app.api.v1.agents.master_agent.execute", fake_agent_execute)

    execute_resp = await app_client.post(
        "/api/v1/agents/execute",
        json={
            "query": "review payment terms",
            "task_type": "review",
            "session_id": session_id,
            "tenant_id": "default",
            "filters": {},
        },
        headers=auth_headers,
    )
    assert execute_resp.status_code == 200, execute_resp.text
    exec_payload = unwrap_json(execute_resp)
    assert exec_payload["status"] == "completed"
    assert isinstance(exec_payload["references"], list)

    messages_resp = await app_client.get(f"/api/v1/sessions/{session_id}/messages", headers=auth_headers)
    assert messages_resp.status_code == 200
    messages_data = unwrap_json(messages_resp)
    assert messages_data["total"] >= 2

    memory_resp = await app_client.get(f"/api/v1/memory/{session_id}", headers=auth_headers)
    assert memory_resp.status_code == 200
    memory_data = unwrap_json(memory_resp)
    assert memory_data["session_id"] == session_id

    retrieval_resp = await app_client.post(
        "/api/v1/retrieval/search",
        json={"query": "payment liability", "session_id": session_id, "tenant_id": "default", "top_k": 5},
        headers=auth_headers,
    )
    assert retrieval_resp.status_code == 200, retrieval_resp.text
    retrieval_payload = unwrap_json(retrieval_resp)
    assert "channels" in retrieval_payload
    if retrieval_payload["final_results"]:
        citation_id = retrieval_payload["final_results"][0]["citation_id"]
        if citation_id:
            citation_resp = await app_client.get(f"/api/v1/citations/{citation_id}", headers=auth_headers)
            assert citation_resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_compat_and_alembic_version(app_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    system_resp = await app_client.get("/api/v1/dashboard/system", headers=auth_headers)
    assert system_resp.status_code == 200
    assert system_resp.headers.get("Deprecation") == "true"

    retrieval_resp = await app_client.get("/api/v1/dashboard/retrieval", headers=auth_headers)
    assert retrieval_resp.status_code == 200
    assert retrieval_resp.headers.get("Deprecation") == "true"

    async with ReadSessionLocal() as session:
        try:
            version_num = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        except Exception:
            version_num = None
    assert version_num in {None, "20260406_0001", "20260406_0002", "20260406_0003"}


@pytest.mark.asyncio
async def test_system_connectors_health_endpoint(app_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await app_client.get("/api/v1/system/connectors/health", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    payload = unwrap_json(resp)
    assert "ok" in payload
    assert "services" in payload
    for name in ["minio", "milvus", "nebula", "kafka", "legal_source"]:
        assert name in payload["services"]


@pytest.mark.asyncio
async def test_legal_sync_endpoint_creates_jobs(app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch) -> None:
    async def fake_fetch_documents(*, limit: int | None = None):
        _ = limit
        return [
            LegalSourceDocument(
                source_url="https://www.gov.cn/test-rule-1",
                title="Mock Regulation",
                content="This is a legal regulation text with enough content for ingestion pipeline." * 10,
                published_at=datetime.now(timezone.utc),
                authority="gov.cn",
            )
        ]

    async def fake_enqueue(**kwargs):
        _ = kwargs
        return True

    monkeypatch.setattr("app.services.legal_sync_service.legal_source_connector.fetch_documents", fake_fetch_documents)
    monkeypatch.setattr("app.services.legal_sync_service.ingestion_orchestrator.enqueue_document_job", fake_enqueue)
    monkeypatch.setattr(settings.legal_source, "enabled", True)

    resp = await app_client.post("/api/v1/legal/sync", json={"tenant_id": "default", "limit": 5}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    payload = unwrap_json(resp)
    assert payload["tenant_id"] == "default"
    assert payload["total"] == 1
    assert payload["enqueued"] == 1
    assert len(payload["job_ids"]) == 1
