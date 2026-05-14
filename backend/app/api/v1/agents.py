"""Agent execution APIs backed by relational persistence."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import orchestrator_agent
from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.agent import AgentExecution, AgentStep
from app.models.retrieval import RetrievalLog
from app.rag.context_builder import context_builder
from app.rag.retriever import hybrid_retriever
from app.schemas.agent import AgentExecuteRequest, AgentExecuteResponse
from app.services.citation_service import citation_service
from app.services.llm_service import llm_service
from app.services.session_memory_service import session_memory_service

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field_name}") from exc


def _step_payload(step: AgentStep) -> dict:
    content = step.observation or step.thought or step.action or ""
    return {
        "step_number": step.step_number,
        "step_type": step.step_type,
        "content": content,
        "action": step.action,
        "tool_name": step.tool_name,
        "tokens_used": step.tokens_used,
        "latency_ms": round(float(step.latency_ms or 0.0), 2),
    }


def _execution_payload(execution: AgentExecution, steps: list[dict] | None = None) -> dict:
    metadata = execution.result_metadata or {}
    usage = metadata.get("usage") or {}
    if "total_tokens" not in usage:
        usage["total_tokens"] = execution.total_tokens_used
    return {
        "execution_id": execution.id,
        "trace_id": execution.trace_id,
        "status": execution.status,
        "result": execution.result or "",
        "references": metadata.get("references", []),
        "review_report": metadata.get("review_report"),
        "steps": steps or [],
        "usage": usage,
        "latency_ms": round(float(execution.latency_ms or 0.0), 2),
        "task_type": execution.task_type,
        "created_at": execution.created_at,
        "completed_at": execution.completed_at,
    }


def _severity_from_text(text: str) -> str:
    lowered = text.lower()
    if any(marker in text for marker in ["高风�?, "严重", "重大"]) or any(
        marker in lowered for marker in ["high risk", "critical", "severe"]
    ):
        return "high"
    if any(marker in text for marker in ["低风�?, "轻微"]) or any(marker in lowered for marker in ["low risk", "minor"]):
        return "low"
    return "medium"


def _first_sentence(text: str, limit: int = 360) -> str:
    normalized = " ".join((text or "").strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _build_contract_review_report(result_text: str, references: list[dict], query: str) -> dict[str, Any]:
    citation_refs = [
        {
            "ref_id": ref.get("ref_id"),
            "citation_id": ref.get("citation_id"),
            "citation_code": ref.get("citation_code"),
            "doc_title": ref.get("doc_title"),
            "hierarchy": ref.get("hierarchy"),
            "chunk_id": ref.get("chunk_id"),
        }
        for ref in references
        if ref.get("citation_id") or ref.get("citation_code")
    ]
    has_citation = bool(citation_refs)
    severity = _severity_from_text(result_text)
    confidence = 0.72 if has_citation else 0.35
    risk_title = "合同审查结论" if has_citation else "不确定：缺少可追溯依�?

    return {
        "overall_risk": severity if has_citation else "uncertain",
        "summary": _first_sentence(result_text, limit=500) or "未生成有效审查结论�?,
        "risk_items": [
            {
                "severity": severity if has_citation else "uncertain",
                "clause_excerpt": _first_sentence(query, limit=320),
                "issue": risk_title,
                "legal_basis": "�?.join(
                    str(item.get("citation_code") or item.get("doc_title") or item.get("chunk_id"))
                    for item in citation_refs[:5]
                )
                or "未检索到可验证引用依�?,
                "recommendation": _first_sentence(result_text, limit=600)
                or "建议补充法规依据后再形成正式审查意见�?,
                "confidence": confidence,
                "references": citation_refs[:8],
            }
        ],
        "generated_from": "agent_execution",
    }


async def _persist_retrieval_log(
    db: AsyncSession,
    *,
    tenant_id: str,
    session_id: uuid.UUID,
    execution_id: uuid.UUID,
    query: str,
    filters: dict,
    debug: dict,
    context_refs: list[dict],
) -> RetrievalLog:
    row = RetrievalLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        session_id=session_id,
        execution_id=execution_id,
        query=query,
        filters=filters,
        preprocessed=debug.get("preprocessed", {}),
        vector_hits=debug.get("channels", {}).get("vector", []),
        keyword_hits=debug.get("channels", {}).get("keyword", []),
        graph_hits=debug.get("channels", {}).get("graph", []),
        merged_hits=debug.get("merged", []),
        rerank_scores=debug.get("reranked", []),
        filtered_out=debug.get("filtered_out", []),
        final_context=context_refs,
        latency_ms=float(debug.get("latency_ms", 0.0)),
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    req: AgentExecuteRequest,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    if req.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")

    await session_memory_service.ensure_session(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_uuid,
    )

    user_message = await session_memory_service.append_message(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
        role="user",
        content=req.query,
        user_id=ctx.user_uuid,
    )
    await session_memory_service.upsert_facts_from_message(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
        source_message_id=user_message.id,
        text=req.query,
    )

    execution_id = uuid.uuid4()
    trace_id = uuid.uuid4().hex[:32]
    start_time = time.perf_counter()

    retrieval_results, retrieval_debug = await hybrid_retriever.retrieve_with_debug(
        query=req.query,
        tenant_id=ctx.tenant_id,
        filters=req.filters,
    )

    built_context = context_builder.build(retrieval_results)
    # Create citation records and attach to references.
    citation_by_chunk: dict[str, dict] = {}
    for item in retrieval_results:
        citation = await citation_service.ensure_for_result(
            db=db,
            tenant_id=ctx.tenant_id,
            session_id=req.session_id,
            execution_id=execution_id,
            chunk_id=item.chunk_id,
            document_id=item.metadata.get("doc_id"),
            excerpt=item.content[:1200],
            title=item.metadata.get("doc_title"),
            locator=item.metadata.get("hierarchy_path"),
            metadata=item.metadata,
        )
        citation_by_chunk[item.chunk_id] = {
            "citation_id": str(citation.id),
            "citation_code": citation.citation_code,
        }

    for ref in built_context["references"]:
        citation_info = citation_by_chunk.get(ref.get("chunk_id"))
        if citation_info:
            ref.update(citation_info)

    memory_ctx = await session_memory_service.get_runtime_context(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
    )
    agent_context = {
        "tenant_id": ctx.tenant_id,
        "retrieval_context": built_context["context"],
        "references": built_context["references"],
        "conversation_history": memory_ctx["history_text"],
        "session_summary": memory_ctx["summary"],
        "memory_facts": memory_ctx["facts"],
    }

    generation_start = time.perf_counter()
    result = await orchestrator_agent.execute(req.query, context=agent_context)
    generation_latency_ms = (time.perf_counter() - generation_start) * 1000
    latency_ms = (time.perf_counter() - start_time) * 1000
    completed_at = datetime.now(timezone.utc)
    review_report = None
    if req.task_type == "contract_review":
        review_report = _build_contract_review_report(result.output or "", built_context["references"], req.query)

    execution = AgentExecution(
        id=execution_id,
        trace_id=trace_id,
        session_id=req.session_id,
        user_id=ctx.user_uuid,
        tenant_id=ctx.tenant_id,
        task_type=req.task_type,
        user_query=req.query,
        parsed_intent=(retrieval_debug.get("preprocessed") or {}).get("intent"),
        parsed_entities=(retrieval_debug.get("preprocessed") or {}).get("entities", []),
        agent_type=orchestrator_agent.agent_type,
        model_config_id=req.model_config_id,
        prompt_template_id=req.prompt_template_id,
        total_steps=len(result.steps),
        total_tokens_used=result.total_tokens,
        total_cost=0.0,
        status="completed" if result.success else "failed",
        result=result.output,
        result_metadata={
            "references": built_context["references"],
            "review_report": review_report,
            "usage": {
                "total_tokens": result.total_tokens,
                "retrieval_chunks": built_context["chunk_count"],
                "retrieval_latency_ms": retrieval_debug.get("latency_ms", 0.0),
            },
            "agent_metadata": result.metadata,
            "filters": req.filters,
        },
        error_message=None if result.success else result.output,
        relevance_score=None,
        factuality_score=None,
        user_feedback=None,
        latency_ms=latency_ms,
        retrieval_latency_ms=float(retrieval_debug.get("latency_ms", 0.0)),
        generation_latency_ms=generation_latency_ms,
        created_at=completed_at,
        completed_at=completed_at,
    )
    db.add(execution)

    await _persist_retrieval_log(
        db=db,
        tenant_id=ctx.tenant_id,
        session_id=req.session_id,
        execution_id=execution_id,
        query=req.query,
        filters=req.filters,
        debug=retrieval_debug,
        context_refs=built_context["references"],
    )

    step_rows: list[AgentStep] = []
    step_payloads: list[dict] = []
    for idx, step in enumerate(result.steps):
        step_started = datetime.fromtimestamp(step.timestamp, tz=timezone.utc)
        step_completed = step_started + timedelta(milliseconds=float(step.latency_ms or 0.0))
        try:
            step_id = uuid.UUID(step.id)
        except ValueError:
            step_id = uuid.uuid4()

        step_rows.append(
            AgentStep(
                id=step_id,
                execution_id=execution_id,
                trace_id=trace_id,
                span_id=uuid.uuid4().hex[:16],
                parent_span_id=None,
                step_number=idx + 1,
                step_type=step.step_type.value,
                agent_type=orchestrator_agent.agent_type,
                thought=step.content if step.step_type.value == "thought" else None,
                action=step.action,
                action_input=step.action_input or {},
                observation=step.observation or (step.content if step.step_type.value != "action" else None),
                tool_name=step.tool_name,
                tool_input=step.action_input or {},
                tool_output=step.observation,
                retrieved_chunks=[],
                retrieval_scores=[],
                tokens_used=step.tokens_used or 0,
                latency_ms=float(step.latency_ms or 0.0),
                status="completed",
                error_message=None,
                started_at=step_started,
                completed_at=step_completed,
            )
        )
        step_payloads.append(
            {
                "step_number": idx + 1,
                "step_type": step.step_type.value,
                "content": (step.content or "")[:500],
                "action": step.action,
                "tool_name": step.tool_name,
                "tokens_used": step.tokens_used,
                "latency_ms": round(float(step.latency_ms or 0.0), 2),
            }
        )

    db.add_all(step_rows)

    await session_memory_service.append_message(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
        role="assistant",
        content=result.output or "",
        user_id=ctx.user_uuid,
        trace_id=trace_id,
        metadata={"execution_id": str(execution_id), "task_type": req.task_type},
    )
    await session_memory_service.refresh_rolling_summary(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
    )

    await db.flush()
    return AgentExecuteResponse(
        execution_id=execution.id,
        trace_id=execution.trace_id,
        status=execution.status,
        result=execution.result or "",
        references=built_context["references"],
        steps=step_payloads,
        usage={
            "total_tokens": result.total_tokens,
            "retrieval_chunks": built_context["chunk_count"],
            "retrieval_latency_ms": retrieval_debug.get("latency_ms", 0.0),
        },
        latency_ms=round(latency_ms, 2),
        review_report=review_report,
    )


@router.post("/chat")
async def chat_stream(
    req: AgentExecuteRequest,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    if req.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")

    await session_memory_service.ensure_session(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_uuid,
    )
    user_message = await session_memory_service.append_message(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
        role="user",
        content=req.query,
        user_id=ctx.user_uuid,
    )
    await session_memory_service.upsert_facts_from_message(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
        source_message_id=user_message.id,
        text=req.query,
    )

    trace_id = uuid.uuid4().hex[:32]
    memory_ctx = await session_memory_service.get_runtime_context(
        db=db,
        session_id=req.session_id,
        tenant_id=ctx.tenant_id,
    )

    retrieval_results, _retrieval_debug = await hybrid_retriever.retrieve_with_debug(
        query=req.query,
        tenant_id=ctx.tenant_id,
        filters=req.filters,
    )
    built_context = context_builder.build(retrieval_results)

    messages = [{"role": "system", "content": orchestrator_agent._build_system_prompt()}]
    if built_context["context"]:
        messages.append({"role": "system", "content": f"Retrieval context:\n{built_context['context']}"})
    if memory_ctx["summary"]:
        messages.append({"role": "system", "content": f"Session summary:\n{memory_ctx['summary']}"})
    if memory_ctx["history_text"]:
        messages.append({"role": "system", "content": f"Recent conversation:\n{memory_ctx['history_text']}"})
    messages.append({"role": "user", "content": req.query})

    async def generate():
        chunks: list[str] = []
        async for chunk in llm_service.generate_stream(messages):
            chunks.append(chunk)
            yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"

        final_text = "".join(chunks).strip()
        if final_text:
            await session_memory_service.append_message(
                db=db,
                session_id=req.session_id,
                tenant_id=ctx.tenant_id,
                role="assistant",
                content=final_text,
                user_id=ctx.user_uuid,
                trace_id=trace_id,
                metadata={"stream": True, "references": built_context["references"][:10]},
            )
            await session_memory_service.refresh_rolling_summary(
                db=db,
                session_id=req.session_id,
                tenant_id=ctx.tenant_id,
            )

        refs_data = json.dumps({"type": "references", "data": built_context["references"][:10]}, ensure_ascii=False)
        yield f"data: {refs_data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/executions")
async def list_executions(
    task_type: str = Query(default=""),
    status: str = Query(default=""),
    session_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    query = select(AgentExecution).where(AgentExecution.tenant_id == ctx.tenant_id)
    if task_type:
        query = query.where(AgentExecution.task_type == task_type)
    if status:
        query = query.where(AgentExecution.status == status)
    if session_id:
        query = query.where(AgentExecution.session_id == _parse_uuid(session_id, "session_id"))

    total_stmt = select(func.count()).select_from(query.subquery())
    total = int((await db.scalar(total_stmt)) or 0)
    rows = (
        await db.scalars(
            query.order_by(AgentExecution.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return {
        "items": [_execution_payload(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/executions/{execution_id}")
async def get_execution_detail(
    execution_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    execution_uuid = _parse_uuid(execution_id, "execution_id")
    execution = await db.scalar(
        select(AgentExecution).where(
            AgentExecution.id == execution_uuid,
            AgentExecution.tenant_id == ctx.tenant_id,
        )
    )
    if not execution:
        raise HTTPException(status_code=404, detail="execution not found")

    step_rows = (
        await db.scalars(
            select(AgentStep)
            .where(AgentStep.execution_id == execution_uuid)
            .order_by(AgentStep.step_number.asc())
        )
    ).all()
    return _execution_payload(execution, steps=[_step_payload(step) for step in step_rows])


@router.get("/trace/{trace_id}")
async def get_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    execution = await db.scalar(
        select(AgentExecution).where(
            AgentExecution.trace_id == trace_id,
            AgentExecution.tenant_id == ctx.tenant_id,
        )
    )
    if not execution:
        raise HTTPException(status_code=404, detail="trace not found")

    step_rows = (
        await db.scalars(
            select(AgentStep)
            .where(AgentStep.execution_id == execution.id)
            .order_by(AgentStep.step_number.asc())
        )
    ).all()
    return _execution_payload(execution, steps=[_step_payload(step) for step in step_rows])


@router.post("/executions/{execution_id}/feedback")
async def submit_feedback(
    execution_id: str,
    score: int,
    comment: str = "",
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    if not 1 <= score <= 5:
        raise HTTPException(status_code=400, detail="score must be between 1 and 5")

    execution_uuid = _parse_uuid(execution_id, "execution_id")
    execution = await db.scalar(
        select(AgentExecution).where(
            AgentExecution.id == execution_uuid,
            AgentExecution.tenant_id == ctx.tenant_id,
        )
    )
    if not execution:
        raise HTTPException(status_code=404, detail="execution not found")

    metadata = dict(execution.result_metadata or {})
    metadata["user_comment"] = comment
    metadata["feedback_at"] = datetime.now(timezone.utc).isoformat()
    metadata["feedback_user_id"] = ctx.user_id
    execution.user_feedback = score
    execution.result_metadata = metadata
    await db.flush()
    return {"message": "feedback submitted"}

