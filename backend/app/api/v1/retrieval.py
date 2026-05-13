"""Retrieval debug API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.retrieval import RetrievalLog
from app.rag.context_builder import context_builder
from app.rag.retriever import hybrid_retriever
from app.schemas.retrieval import RetrievalDebugResponse, RetrievalHit, RetrievalSearchRequest
from app.services.citation_service import citation_service
from app.services.session_memory_service import session_memory_service

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


@router.post("/search", response_model=RetrievalDebugResponse)
async def retrieval_search(
    req: RetrievalSearchRequest,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    tenant_id = req.tenant_id or ctx.tenant_id
    if tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")

    if req.session_id:
        session = await session_memory_service.get_session(db, req.session_id, tenant_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")

    results, debug = await hybrid_retriever.retrieve_with_debug(
        query=req.query,
        tenant_id=tenant_id,
        filters=req.filters,
        top_k=req.top_k,
    )
    built_context = context_builder.build(results)

    citation_by_chunk: dict[str, dict] = {}
    for item in results:
        citation = await citation_service.ensure_for_result(
            db=db,
            tenant_id=tenant_id,
            session_id=req.session_id,
            execution_id=None,
            chunk_id=item.chunk_id,
            document_id=item.metadata.get("doc_id"),
            excerpt=item.content[:1200],
            title=item.metadata.get("doc_title"),
            locator=item.metadata.get("hierarchy_path"),
            metadata=item.metadata,
        )
        citation_by_chunk[item.chunk_id] = {
            "citation_id": citation.id,
            "citation_code": citation.citation_code,
        }

    for ref in built_context["references"]:
        c = citation_by_chunk.get(ref.get("chunk_id"))
        if c:
            ref["citation_id"] = str(c["citation_id"])
            ref["citation_code"] = c["citation_code"]

    retrieval_id = uuid.uuid4()
    row = RetrievalLog(
        id=retrieval_id,
        tenant_id=tenant_id,
        session_id=req.session_id,
        execution_id=None,
        query=req.query,
        filters=req.filters,
        preprocessed=debug.get("preprocessed", {}),
        vector_hits=debug.get("channels", {}).get("vector", []),
        keyword_hits=debug.get("channels", {}).get("keyword", []),
        graph_hits=debug.get("channels", {}).get("graph", []),
        merged_hits=debug.get("merged", []),
        rerank_scores=debug.get("reranked", []),
        filtered_out=debug.get("filtered_out", []),
        final_context=built_context["references"],
        latency_ms=float(debug.get("latency_ms", 0.0)),
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()

    final_hits = []
    for item in results:
        c = citation_by_chunk.get(item.chunk_id, {})
        final_hits.append(
            RetrievalHit(
                chunk_id=item.chunk_id,
                content=item.content,
                score=float(item.score),
                source=item.source,
                metadata=item.metadata,
                rerank_score=item.rerank_score,
                citation_id=c.get("citation_id"),
                citation_code=c.get("citation_code"),
            )
        )

    return RetrievalDebugResponse(
        query=req.query,
        retrieval_id=retrieval_id,
        latency_ms=float(debug.get("latency_ms", 0.0)),
        preprocessed=debug.get("preprocessed", {}),
        channels=debug.get("channels", {}),
        merged=debug.get("merged", []),
        reranked=debug.get("reranked", []),
        filtered_out=debug.get("filtered_out", []),
        final_results=final_hits,
        context=built_context["context"],
        references=built_context["references"],
        created_at=row.created_at,
    )
