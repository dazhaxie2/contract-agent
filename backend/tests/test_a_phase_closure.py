from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from app.core.database import ReadSessionLocal, WriteSessionLocal
from app.core.config import settings
from app.core.security import create_access_token
from app.models.agent import AgentDecision, AgentExecution
from app.models.user import User
from app.services.connectors.legal_source_connector import LegalSourceDocument
from app.services.llm_service import llm_service


def unwrap_json(resp) -> dict | list:
    payload = resp.json()
    if isinstance(payload, dict) and "data" in payload and "code" in payload:
        return payload["data"]
    return payload


@pytest.mark.asyncio
async def test_models_crud_and_compat(app_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    me_resp = await app_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200
    me_payload = unwrap_json(me_resp)
    assert me_payload["role"] == "admin"
    assert "model:write" in me_payload["permissions"]

    viewer_token = create_access_token(
        {
            "sub": "00000000-0000-0000-0000-000000000002",
            "username": "viewer",
            "role": "viewer",
            "tenant_id": "default",
        }
    )
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

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
    stale_token_resp = await app_client.post("/api/v1/models", json=payload, headers=viewer_headers)
    assert stale_token_resp.status_code == 401

    register_viewer_resp = await app_client.post(
        "/api/v1/auth/register",
        json={
            "username": "viewer",
            "email": "viewer@example.com",
            "password": "password123",
            "tenant_id": "default",
        },
    )
    assert register_viewer_resp.status_code == 200, register_viewer_resp.text
    viewer_login_resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "password123"},
    )
    assert viewer_login_resp.status_code == 200, viewer_login_resp.text
    viewer_login_data = unwrap_json(viewer_login_resp)
    viewer_headers = {"Authorization": f"Bearer {viewer_login_data['access_token']}"}
    viewer_create_resp = await app_client.post("/api/v1/models", json=payload, headers=viewer_headers)
    assert viewer_create_resp.status_code == 403

    async with WriteSessionLocal() as session:
        viewer = await session.scalar(select(User).where(User.username == "viewer"))
        assert viewer is not None
        viewer.is_active = False
        await session.commit()

    disabled_resp = await app_client.get("/api/v1/auth/me", headers=viewer_headers)
    assert disabled_resp.status_code == 403
    disabled_refresh_resp = await app_client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": viewer_login_data["refresh_token"]},
    )
    assert disabled_refresh_resp.status_code == 403

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
    assert compat_data["trace_id"].startswith("prompt_")
    assert compat_data["rendered_prompt"] == "Review: hello"


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

    monkeypatch.setattr("app.api.v1.agents.orchestrator_agent.execute", fake_agent_execute)

    execute_resp = await app_client.post(
        "/api/v1/agents/execute",
        json={
            "query": "review payment terms",
            "task_type": "contract_review",
            "session_id": session_id,
            "tenant_id": "default",
            "filters": {"doc_id": doc_id},
        },
        headers=auth_headers,
    )
    assert execute_resp.status_code == 200, execute_resp.text
    exec_payload = unwrap_json(execute_resp)
    assert exec_payload["status"] == "completed"
    assert isinstance(exec_payload["references"], list)
    assert exec_payload["review_report"]["risk_items"]

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
async def test_agent_plan_confirm_execute_and_feedback_regression(
    app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    session_resp = await app_client.post(
        "/api/v1/sessions",
        json={"title": "Plan Confirm", "metadata": {}},
        headers=auth_headers,
    )
    assert session_resp.status_code == 200, session_resp.text
    session_id = unwrap_json(session_resp)["id"]

    async with ReadSessionLocal() as session:
        before_count = await session.scalar(select(func.count()).select_from(AgentExecution))

    plan_resp = await app_client.post(
        "/api/v1/agents/plan",
        json={
            "query": "帮我审这份采购合同，重点看付款、违约、解除，并生成修改建议",
            "task_type": "contract_review",
            "session_id": session_id,
            "tenant_id": "default",
            "context": {"review_type": "purchase"},
            "filters": {},
        },
        headers=auth_headers,
    )
    assert plan_resp.status_code == 200, plan_resp.text
    plan_payload = unwrap_json(plan_resp)
    assert plan_payload["decision_id"].startswith("dec_")
    assert plan_payload["requires_confirmation"] is True
    assert [step["step_id"] for step in plan_payload["steps"]]
    assert any(step["domain"] == "review" for step in plan_payload["steps"])

    catalog_resp = await app_client.get("/api/v1/agents/tool-catalog", headers=auth_headers)
    assert catalog_resp.status_code == 200
    catalog_payload = unwrap_json(catalog_resp)
    assert "contract" in catalog_payload["domains"]
    assert any(item["name"] == "retrieval.search" for item in catalog_payload["domains"]["knowledge"])

    extension_resp = await app_client.get("/api/v1/agents/workspace-extension-schema", headers=auth_headers)
    assert extension_resp.status_code == 200
    extension_payload = unwrap_json(extension_resp)
    assert extension_payload["status"] == "reserved"
    assert {"contract_matter", "performance_event", "expense_evidence"}.issubset(extension_payload["schemas"])

    async with ReadSessionLocal() as session:
        after_plan_count = await session.scalar(select(func.count()).select_from(AgentExecution))
        decision = await session.get(AgentDecision, plan_payload["decision_id"])
    assert after_plan_count == before_count
    assert decision is not None
    assert decision.status == "planned"

    rejected_resp = await app_client.post(
        f"/api/v1/agents/decisions/{plan_payload['decision_id']}/execute",
        json={"confirmed": False, "comment": "not yet"},
        headers=auth_headers,
    )
    assert rejected_resp.status_code == 409

    async def fake_agent_execute(query: str, context: dict | None = None):
        from app.agents.base import AgentResult, AgentStep, StepType

        assert "采购合同" in query
        step = AgentStep(
            step_type=StepType.OBSERVATION,
            content="review tool completed",
            tool_name="compliance.review",
            tokens_used=18,
            latency_ms=2.0,
        )
        return AgentResult(success=True, output="中风险：付款期限需要补充验收条件。", steps=[step], metadata={"mock": True})

    monkeypatch.setattr("app.api.v1.agents.orchestrator_agent.execute", fake_agent_execute)

    execute_resp = await app_client.post(
        f"/api/v1/agents/decisions/{plan_payload['decision_id']}/execute",
        json={"confirmed": True, "comment": "confirmed"},
        headers=auth_headers,
    )
    assert execute_resp.status_code == 200, execute_resp.text
    execute_payload = unwrap_json(execute_resp)
    assert execute_payload["status"] == "completed"
    assert execute_payload["decision_id"] == plan_payload["decision_id"]
    assert execute_payload["plan"]["steps"]
    assert execute_payload["tool_results"]
    assert execute_payload["review_report"]["risk_items"]

    detail_resp = await app_client.get(
        f"/api/v1/agents/executions/{execute_payload['execution_id']}",
        headers=auth_headers,
    )
    assert detail_resp.status_code == 200
    detail_payload = unwrap_json(detail_resp)
    assert detail_payload["decision_id"] == plan_payload["decision_id"]
    assert detail_payload["plan"]["decision_id"] == plan_payload["decision_id"]

    async with ReadSessionLocal() as session:
        executed_decision = await session.get(AgentDecision, plan_payload["decision_id"])
    assert executed_decision is not None
    assert executed_decision.status == "executed"
    assert str(executed_decision.execution_id) == execute_payload["execution_id"]

    for export_format in ["markdown", "docx", "pdf"]:
        export_resp = await app_client.get(
            f"/api/v1/agents/executions/{execute_payload['execution_id']}/export",
            params={"format": export_format},
            headers=auth_headers,
        )
        assert export_resp.status_code == 200
        assert export_resp.content

    feedback_resp = await app_client.post(
        f"/api/v1/agents/executions/{execute_payload['execution_id']}/feedback",
        params={"score": 2, "comment": "付款风险应引用验收条款"},
        headers=auth_headers,
    )
    assert feedback_resp.status_code == 200, feedback_resp.text
    feedback_payload = unwrap_json(feedback_resp)
    assert feedback_payload["regression_case_id"].startswith("reg_")

    detail_after_feedback = await app_client.get(
        f"/api/v1/agents/executions/{execute_payload['execution_id']}",
        headers=auth_headers,
    )
    assert detail_after_feedback.status_code == 200
    feedback_detail = unwrap_json(detail_after_feedback)
    assert feedback_detail["user_feedback"] == 2
    assert feedback_detail["regression_case_id"] == feedback_payload["regression_case_id"]

    regression_list_resp = await app_client.get("/api/v1/agents/regression-cases", headers=auth_headers)
    assert regression_list_resp.status_code == 200
    regression_list = unwrap_json(regression_list_resp)
    assert regression_list["total"] == 1
    assert regression_list["items"][0]["regression_case_id"] == feedback_payload["regression_case_id"]

    regression_detail_resp = await app_client.get(
        f"/api/v1/agents/regression-cases/{feedback_payload['regression_case_id']}",
        headers=auth_headers,
    )
    assert regression_detail_resp.status_code == 200
    regression_detail = unwrap_json(regression_detail_resp)
    assert regression_detail["expected_correction"] == "付款风险应引用验收条款"

    metrics_resp = await app_client.get("/api/v1/system/metrics/overview", headers=auth_headers)
    assert metrics_resp.status_code == 200
    metrics = unwrap_json(metrics_resp)
    workbench = metrics["contract_workbench"]
    assert workbench["planned_executions"] >= 1
    assert workbench["plan_success_rate"] == 1.0
    assert workbench["user_feedback_avg"] == 2
    assert workbench["regression_cases_total"] == 1


@pytest.mark.asyncio
async def test_contract_workbench_api_e2e_acceptance(
    app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings.rag, "enable_crag", False)

    headers = auth_headers

    contract_text = (
        "采购合同。付款条款：甲方应在验收合格后十个工作日内付款。"
        "违约条款：任一方迟延履行应承担违约责任。"
        "解除条款：连续违约超过十五日守约方可以解除合同。"
        "争议解决：提交上海仲裁委员会仲裁。"
    ) * 8
    upload_resp = await app_client.post(
        "/api/v1/documents/upload",
        files={"file": ("purchase-contract.txt", contract_text.encode("utf-8"), "text/plain")},
        data={"doc_type": "contract", "title": "采购合同 E2E", "sync": "true"},
        headers=headers,
    )
    assert upload_resp.status_code == 200, upload_resp.text
    upload_payload = unwrap_json(upload_resp)
    assert upload_payload["status"] == "completed"
    doc_id = upload_payload["doc_id"]

    session_resp = await app_client.post(
        "/api/v1/sessions",
        json={"title": "合同助手 E2E", "metadata": {"doc_id": doc_id}},
        headers=headers,
    )
    assert session_resp.status_code == 200, session_resp.text
    session_id = unwrap_json(session_resp)["id"]

    async def fake_agent_execute(query: str, context: dict | None = None):
        from app.agents.base import AgentResult, AgentStep, StepType

        assert "采购合同" in query
        assert context and context["references"]
        return AgentResult(
            success=True,
            output="中风险：付款条款需要明确验收标准和发票提交条件。建议补充验收流程、付款前置条件和逾期付款责任。",
            steps=[
                AgentStep(
                    step_type=StepType.OBSERVATION,
                    content="compliance review completed",
                    tool_name="compliance.review",
                    tokens_used=31,
                    latency_ms=4.0,
                )
            ],
            metadata={"mode": "api_e2e"},
        )

    monkeypatch.setattr("app.api.v1.agents.orchestrator_agent.execute", fake_agent_execute)

    plan_resp = await app_client.post(
        "/api/v1/agents/plan",
        json={
            "query": "帮我审这份采购合同，重点看付款、违约、解除，并生成修改稿和 Markdown 报告",
            "task_type": "contract_review",
            "session_id": session_id,
            "tenant_id": "default",
            "filters": {"doc_id": doc_id, "document_ids": [doc_id]},
            "context": {"doc_id": doc_id, "doc_title": "采购合同 E2E", "review_type": "purchase"},
        },
        headers=headers,
    )
    assert plan_resp.status_code == 200, plan_resp.text
    plan_payload = unwrap_json(plan_resp)
    assert plan_payload["requires_confirmation"] is True
    assert plan_payload["decision_id"].startswith("dec_")

    execute_resp = await app_client.post(
        f"/api/v1/agents/decisions/{plan_payload['decision_id']}/execute",
        json={"confirmed": True, "comment": "E2E 确认执行"},
        headers=headers,
    )
    assert execute_resp.status_code == 200, execute_resp.text
    execute_payload = unwrap_json(execute_resp)
    assert execute_payload["status"] == "completed"
    assert execute_payload["review_report"]["risk_items"]
    assert execute_payload["references"]

    citation_id = execute_payload["references"][0]["citation_id"]
    citation_resp = await app_client.get(f"/api/v1/citations/{citation_id}", headers=headers)
    assert citation_resp.status_code == 200, citation_resp.text
    citation_payload = unwrap_json(citation_resp)
    assert citation_payload["chunk_id"]
    assert "付款" in citation_payload["excerpt"] or citation_payload["excerpt"]

    feedback_resp = await app_client.post(
        f"/api/v1/agents/executions/{execute_payload['execution_id']}/feedback",
        params={"score": 4, "comment": "E2E 结果可用，后续补充修改稿格式"},
        headers=headers,
    )
    assert feedback_resp.status_code == 200, feedback_resp.text
    assert unwrap_json(feedback_resp)["regression_case_id"].startswith("reg_")


@pytest.mark.asyncio
async def test_contract_workbench_failure_scenarios(
    app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    unauthorized_resp = await app_client.get("/api/v1/documents")
    assert unauthorized_resp.status_code == 401

    empty_upload_resp = await app_client.post(
        "/api/v1/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"doc_type": "contract", "title": "Empty", "sync": "true"},
        headers=auth_headers,
    )
    assert empty_upload_resp.status_code == 400
    assert "empty" in empty_upload_resp.text

    async def failing_process_once(**_: dict):
        raise RuntimeError("parser exploded")

    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr("app.services.ingestion_service.ingestion_service._process_once", failing_process_once)
        failed_upload_resp = await app_client.post(
            "/api/v1/documents/upload",
            files={"file": ("broken.txt", b"not really a valid contract" * 8, "text/plain")},
            data={"doc_type": "contract", "title": "Broken", "sync": "true"},
            headers=auth_headers,
        )
    assert failed_upload_resp.status_code == 200, failed_upload_resp.text
    failed_payload = unwrap_json(failed_upload_resp)
    assert failed_payload["status"] == "failed"
    assert "parser exploded" in failed_payload["error_message"]
    assert failed_payload["dead_letter"] is True

    session_resp = await app_client.post(
        "/api/v1/sessions",
        json={"title": "Failure Scenarios", "metadata": {}},
        headers=auth_headers,
    )
    assert session_resp.status_code == 200
    session_id = unwrap_json(session_resp)["id"]

    async def no_results_retrieve(*_: object, **__: dict):
        return [], {
            "preprocessed": {"intent": "contract_review", "entities": []},
            "channels": {"vector": [], "keyword": [], "graph": []},
            "merged": [],
            "reranked": [],
            "filtered_out": [],
            "latency_ms": 0.0,
        }

    async def no_evidence_agent_execute(query: str, context: dict | None = None):
        from app.agents.base import AgentResult, AgentStep, StepType

        assert context and not context["references"]
        return AgentResult(
            success=True,
            output="未检索到可验证依据，不能形成确定审查结论。",
            steps=[
                AgentStep(
                    step_type=StepType.FINAL,
                    content="no evidence",
                    tokens_used=7,
                    latency_ms=1.0,
                )
            ],
            metadata={"no_evidence": True},
        )

    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr("app.api.v1.agents.hybrid_retriever.retrieve_with_debug", no_results_retrieve)
        patch_ctx.setattr("app.api.v1.agents.orchestrator_agent.execute", no_evidence_agent_execute)
        no_results_resp = await app_client.post(
            "/api/v1/agents/execute",
            json={
                "query": "审查一个不存在依据的合同条款",
                "task_type": "contract_review",
                "session_id": session_id,
                "tenant_id": "default",
                "filters": {"doc_id": "00000000-0000-0000-0000-000000000099"},
            },
            headers=auth_headers,
        )
    assert no_results_resp.status_code == 200, no_results_resp.text
    no_results_payload = unwrap_json(no_results_resp)
    assert no_results_payload["references"] == []
    assert no_results_payload["review_report"]["overall_risk"] == "uncertain"
    assert no_results_payload["review_report"]["risk_items"][0]["severity"] == "uncertain"

    with monkeypatch.context() as patch_ctx:
        import app.services.llm_service as llm_module

        patch_ctx.setattr(settings.llm, "require_external", True)
        patch_ctx.setattr(settings.llm, "api_key", "")
        patch_ctx.setattr(llm_module, "HAS_DASHSCOPE", False)
        patch_ctx.setattr("app.api.v1.agents.hybrid_retriever.retrieve_with_debug", no_results_retrieve)
        patch_ctx.setattr("app.api.v1.agents.orchestrator_agent.max_iterations", 1)
        llm_failure_resp = await app_client.post(
            "/api/v1/agents/execute",
            json={
                "query": "LLM 未配置时审查合同",
                "task_type": "contract_review",
                "session_id": session_id,
                "tenant_id": "default",
                "filters": {},
            },
            headers=auth_headers,
        )
    assert llm_failure_resp.status_code == 200, llm_failure_resp.text
    llm_failure_payload = unwrap_json(llm_failure_resp)
    assert llm_failure_payload["status"] == "failed"
    assert "LLM provider is not configured" in llm_failure_payload["result"]


def test_sub_agent_contract_schema_roundtrip() -> None:
    from app.agents.base import AgentResult, AgentStep, StepType
    from app.agents.contracts import SUB_AGENT_CONTRACTS, build_sub_agent_input, build_sub_agent_output
    from app.agents.tool_catalog import tool_catalog_by_domain

    expected_agents = {"retrieval", "compliance", "comparison", "drafting", "validation"}
    assert expected_agents.issubset(SUB_AGENT_CONTRACTS)
    catalog = tool_catalog_by_domain()
    assert {"contract", "review", "knowledge", "observability"}.issubset(catalog)
    assert any(item["name"] == "compliance.review" for item in catalog["review"])

    task_input = build_sub_agent_input(
        agent_type="compliance",
        task_description="review payment and termination clauses",
        context_payload={
            "tenant_id": "default",
            "session_id": "session-1",
            "decision_id": "dec_1",
            "filters": {"doc_id": "doc-1"},
            "references": [
                {
                    "citation_id": "cit-1",
                    "citation_code": "CIT-1",
                    "doc_title": "Mock Regulation",
                    "chunk_id": "chunk-1",
                    "excerpt": "legal basis",
                }
            ],
        },
    )
    assert task_input.schema_version
    assert task_input.agent_type == "compliance"
    assert task_input.tenant_id == "default"
    assert task_input.document_ids == ["doc-1"]
    assert task_input.references[0].citation_id == "cit-1"

    result = AgentResult(
        success=True,
        output="中风险：付款期限需要补充验收条件。",
        steps=[
            AgentStep(
                step_type=StepType.OBSERVATION,
                content="checked",
                tool_name="compliance_check",
                tokens_used=11,
                latency_ms=3.0,
            )
        ],
        metadata={"mock": True},
    )
    task_output = build_sub_agent_output(task_input, result)
    dumped = task_output.model_dump(mode="json")

    assert dumped["schema_version"] == task_input.schema_version
    assert dumped["agent_type"] == "compliance"
    assert dumped["success"] is True
    assert dumped["findings"][0]["severity"] == "medium"
    assert dumped["references"][0]["citation_id"] == "cit-1"
    assert dumped["tool_results"][0]["tool_name"] == "compliance_check"


def test_local_contract_review_samples_replay() -> None:
    from app.api.v1.agents import _build_agent_plan
    from app.schemas.agent import AgentPlanRequest

    fixture = Path(__file__).resolve().parent / "fixtures" / "contract_review_samples.jsonl"
    cases = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(cases) >= 20

    for case in cases:
        request = AgentPlanRequest(
            query=case["query"],
            session_id="00000000-0000-0000-0000-000000000001",
            tenant_id="default",
            task_type="contract_review",
            context=case.get("context", {}),
            filters=case.get("filters", {}),
        )
        plan = _build_agent_plan(request)
        step_ids = {step["step_id"] for step in plan["steps"]}
        assert set(case["expected_step_ids"]).issubset(step_ids), case["case_id"]
        assert plan["requires_confirmation"] is case["requires_confirmation"]


@pytest.mark.asyncio
async def test_orchestrator_route_tool_returns_contract_output(monkeypatch) -> None:
    from app.agents.base import AgentResult, AgentStep, StepType
    from app.agents.orchestrator import _IntentRoutingTool
    import app.agents.orchestrator as orchestrator_module

    class FakeComplianceAgent:
        async def execute(self, query: str, context: dict | None = None):
            assert context is not None
            assert context["agent_contract"]["agent_type"] == "compliance"
            assert context["agent_contract"]["document_ids"] == ["doc-1"]
            return AgentResult(
                success=True,
                output="中风险：需要补充付款验收条件。",
                steps=[
                    AgentStep(
                        step_type=StepType.OBSERVATION,
                        content="checked",
                        tool_name="compliance_check",
                        tokens_used=8,
                        latency_ms=1.5,
                    )
                ],
                metadata={"fake": True},
            )

    monkeypatch.setitem(orchestrator_module.SUB_AGENTS, "compliance", FakeComplianceAgent)
    tool = _IntentRoutingTool()
    raw = await tool.execute(
        agent_type="compliance",
        task_description="review payment clause",
        context_payload=json.dumps({"tenant_id": "default", "filters": {"doc_id": "doc-1"}}, ensure_ascii=False),
    )
    payload = json.loads(raw)
    assert payload["schema_version"]
    assert payload["agent_type"] == "compliance"
    assert payload["success"] is True
    assert payload["metadata"]["input_contract"]["document_ids"] == ["doc-1"]
    assert payload["tool_results"][0]["tool_name"] == "compliance_check"


@pytest.mark.asyncio
async def test_document_chunks_full_and_retrieval_doc_filter(
    app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings.rag, "enable_crag", False)

    first_upload = await app_client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "alpha.txt",
                (b"alphaonly payment delivery clause with warranty obligation and acceptance standard. " * 4),
                "text/plain",
            )
        },
        data={"doc_type": "contract", "title": "Alpha Contract", "sync": "true"},
        headers=auth_headers,
    )
    assert first_upload.status_code == 200, first_upload.text
    first_doc_id = unwrap_json(first_upload)["doc_id"]

    second_upload = await app_client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "beta.txt",
                (b"betaonly confidentiality renewal clause with data protection and notice period. " * 4),
                "text/plain",
            )
        },
        data={"doc_type": "contract", "title": "Beta Contract", "sync": "true"},
        headers=auth_headers,
    )
    assert second_upload.status_code == 200, second_upload.text
    second_doc_id = unwrap_json(second_upload)["doc_id"]

    chunks_resp = await app_client.get(f"/api/v1/documents/{first_doc_id}/chunks?full=true", headers=auth_headers)
    assert chunks_resp.status_code == 200
    chunks = unwrap_json(chunks_resp)
    assert chunks and "alphaonly payment delivery clause" in chunks[0]["content"]

    filtered_resp = await app_client.post(
        "/api/v1/retrieval/search",
        json={"query": "betaonly", "tenant_id": "default", "filters": {"doc_id": second_doc_id}, "top_k": 5},
        headers=auth_headers,
    )
    assert filtered_resp.status_code == 200, filtered_resp.text
    filtered_payload = unwrap_json(filtered_resp)
    assert filtered_payload["final_results"]
    assert all(item["metadata"]["doc_id"] == second_doc_id for item in filtered_payload["final_results"])


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
    assert version_num in {None, "20260406_0001", "20260406_0002", "20260406_0003", "20260514_0004", "20260514_0005"}


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
