from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from app.core.config import settings


def unwrap_json(resp) -> dict | list:
    payload = resp.json()
    if isinstance(payload, dict) and "data" in payload and "code" in payload:
        return payload["data"]
    return payload


async def _upload(client: AsyncClient, headers: dict, *, name: str, doc_type: str, title: str, body: bytes) -> str:
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": (name, body, "text/plain")},
        data={"doc_type": doc_type, "title": title, "sync": "true"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = unwrap_json(resp)
    assert payload["status"] == "completed", payload
    return payload["doc_id"]


@pytest.mark.asyncio
async def test_enterprise_rule_doc_type_listing(app_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    rule_doc_id = await _upload(
        app_client,
        auth_headers,
        name="rule.txt",
        doc_type="enterprise_rule",
        title="采购管理制度",
        body=("本公司采购合同管理制度规定：单笔采购金额超过五十万元必须经法务会签并走招标流程。" * 6).encode("utf-8"),
    )
    await _upload(
        app_client,
        auth_headers,
        name="law.txt",
        doc_type="law",
        title="民法典节选",
        body=("民法典规定当事人应当遵循诚信原则履行合同义务并承担违约责任。" * 6).encode("utf-8"),
    )

    listed = unwrap_json(
        (await app_client.get("/api/v1/documents?doc_type=enterprise_rule", headers=auth_headers))
    )
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == rule_doc_id
    assert listed["items"][0]["doc_type"] == "enterprise_rule"


@pytest.mark.asyncio
async def test_contract_review_injects_enterprise_rule_basis(
    app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings.rag, "enable_crag", False)

    # 企业制度独立入库（不属于待审合同）。用顿号分隔出可被关键词召回的短词。
    await _upload(
        app_client,
        auth_headers,
        name="purchase-policy.txt",
        doc_type="enterprise_rule",
        title="采购付款管理制度",
        body=("企业采购付款制度，关注付款、验收、会签、金额、采购：采购付款必须在验收合格后进行，金额超过五十万需会签。" * 8).encode("utf-8"),
    )
    # 待审合同
    contract_doc_id = await _upload(
        app_client,
        auth_headers,
        name="purchase.txt",
        doc_type="contract",
        title="采购合同",
        body=("采购合同条款，涉及付款、验收、金额、采购：甲方应在验收合格后付款，金额以合同为准。" * 8).encode("utf-8"),
    )

    session_id = unwrap_json(
        (await app_client.post("/api/v1/sessions", json={"title": "S", "metadata": {}}, headers=auth_headers))
    )["id"]

    async def fake_agent_execute(query: str, context: dict | None = None):
        from app.agents.base import AgentResult, AgentStep, StepType

        step = AgentStep(step_type=StepType.FINAL, content="done", tokens_used=10, latency_ms=1.0)
        return AgentResult(success=True, output="中风险：付款条款需结合企业制度核对。", steps=[step], metadata={})

    monkeypatch.setattr("app.api.v1.agents.orchestrator_agent.execute", fake_agent_execute)

    resp = await app_client.post(
        "/api/v1/agents/execute",
        json={
            "query": "审查范围：付款、验收、会签、金额、采购",
            "task_type": "contract_review",
            "session_id": session_id,
            "tenant_id": "default",
            "filters": {"doc_id": contract_doc_id},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    payload = unwrap_json(resp)

    doc_types = {ref.get("doc_type") for ref in payload["references"]}
    assert "enterprise_rule" in doc_types, payload["references"]

    report = payload["review_report"]
    assert report["enterprise_rule_count"] >= 1
    assert report["risk_items"][0]["enterprise_basis"]
    assert any(
        ref.get("basis_kind") == "enterprise" for ref in report["risk_items"][0]["references"]
    )


@pytest.mark.asyncio
async def test_export_renders_structured_report(
    app_client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings.rag, "enable_crag", False)
    contract_doc_id = await _upload(
        app_client,
        auth_headers,
        name="purchase.txt",
        doc_type="contract",
        title="采购合同",
        body=("采购合同条款，涉及付款、验收、金额：甲方应在验收合格后付款。" * 8).encode("utf-8"),
    )
    session_id = unwrap_json(
        (await app_client.post("/api/v1/sessions", json={"title": "S", "metadata": {}}, headers=auth_headers))
    )["id"]

    async def fake_agent_execute(query: str, context: dict | None = None):
        from app.agents.base import AgentResult, AgentStep, StepType

        step = AgentStep(step_type=StepType.FINAL, content="done", tokens_used=10, latency_ms=1.0)
        return AgentResult(success=True, output="高风险：付款条款缺少验收前置条件。", steps=[step], metadata={})

    monkeypatch.setattr("app.api.v1.agents.orchestrator_agent.execute", fake_agent_execute)

    execute_payload = unwrap_json(
        await app_client.post(
            "/api/v1/agents/execute",
            json={
                "query": "审查范围：付款、验收、金额",
                "task_type": "contract_review",
                "session_id": session_id,
                "tenant_id": "default",
                "filters": {"doc_id": contract_doc_id},
            },
            headers=auth_headers,
        )
    )
    execution_id = execute_payload["execution_id"]

    # Markdown：结构化分区
    md_resp = await app_client.get(
        f"/api/v1/agents/executions/{execution_id}/export", params={"format": "markdown"}, headers=auth_headers
    )
    assert md_resp.status_code == 200
    md_text = md_resp.content.decode("utf-8")
    assert "# 合同审查报告" in md_text
    assert "## 风险项" in md_text
    assert "法律依据" in md_text

    # DOCX：可被 python-docx 解析且含中文标题
    docx_resp = await app_client.get(
        f"/api/v1/agents/executions/{execution_id}/export", params={"format": "docx"}, headers=auth_headers
    )
    assert docx_resp.status_code == 200
    from docx import Document as DocxDocument

    docx_doc = DocxDocument(io.BytesIO(docx_resp.content))
    docx_text = "\n".join(p.text for p in docx_doc.paragraphs)
    assert "合同审查报告" in docx_text
    assert "法律依据" in docx_text

    # PDF：中文正确渲染（提取文本应含中文，非空白/乱码）
    pdf_resp = await app_client.get(
        f"/api/v1/agents/executions/{execution_id}/export", params={"format": "pdf"}, headers=auth_headers
    )
    assert pdf_resp.status_code == 200
    import fitz

    with fitz.open(stream=pdf_resp.content, filetype="pdf") as pdf_doc:
        pdf_text = "".join(page.get_text() for page in pdf_doc)
    assert "合同审查报告" in pdf_text
    assert "风险" in pdf_text
