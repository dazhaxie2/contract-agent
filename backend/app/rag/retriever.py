"""Hybrid retrieval with Milvus + HiDB keyword + Nebula graph."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from loguru import logger
from sqlalchemy import and_, or_, select

from app.core.config import settings
from app.core.database import get_read_session
from app.core.tracing_utils import start_span
from app.models.document import Document, DocumentChunk
from app.services.connectors import milvus_connector, nebula_connector
from app.services.llm_service import llm_service


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    terms = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text.lower())
    dedup: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        dedup.append(term)
    return dedup[:24]


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:300], b[:300]).ratio()


def _document_filter_ids(filters: dict) -> list[uuid.UUID]:
    raw_ids: list[object] = []
    if filters.get("doc_id"):
        raw_ids.append(filters["doc_id"])
    if filters.get("document_ids"):
        value = filters["document_ids"]
        if isinstance(value, (list, tuple, set)):
            raw_ids.extend(value)
        else:
            raw_ids.append(value)

    doc_ids: list[uuid.UUID] = []
    for raw in raw_ids:
        if isinstance(raw, uuid.UUID):
            doc_ids.append(raw)
            continue
        if not isinstance(raw, str):
            continue
        try:
            doc_ids.append(uuid.UUID(raw))
        except ValueError:
            continue
    return doc_ids


def _uuid_values(values: list[object]) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    for value in values:
        if isinstance(value, uuid.UUID):
            parsed.append(value)
            continue
        if isinstance(value, str):
            try:
                parsed.append(uuid.UUID(value))
            except ValueError:
                continue
    return parsed


def _rrf_merge(sources: list[list["RetrievalResult"]], k: int = 60) -> list["RetrievalResult"]:
    rrf_scores: dict[str, float] = {}
    payloads: dict[str, RetrievalResult] = {}
    for items in sources:
        for rank, item in enumerate(items, start=1):
            rrf_scores[item.chunk_id] = rrf_scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)
            existing = payloads.get(item.chunk_id)
            if existing is None or item.score > existing.score:
                payloads[item.chunk_id] = item
    merged = list(payloads.values())
    for item in merged:
        item.score = float(rrf_scores.get(item.chunk_id, item.score))
    merged.sort(key=lambda x: x.score, reverse=True)
    return merged[:160]


@dataclass
class RetrievalResult:
    chunk_id: str
    content: str
    score: float
    source: str
    metadata: dict = field(default_factory=dict)
    rerank_score: float | None = None

    def payload(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "score": round(float(self.score), 6),
            "source": self.source,
            "rerank_score": round(float(self.rerank_score), 6) if self.rerank_score is not None else None,
            "metadata": self.metadata or {},
            "content": self.content,
        }


class QueryPreprocessor:
    async def preprocess(self, query: str) -> dict:
        prompt = (
            "You are a legal retrieval preprocessor. Return JSON only with keys: "
            "intent(string), entities(list of {text,type}), filters(object), rewritten_queries(list of strings)."
        )
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": query}]
        try:
            result = await llm_service.light_generate(messages=messages, max_tokens=512)
            import json

            parsed = json.loads(result["content"])
            if not isinstance(parsed, dict):
                raise ValueError("invalid preprocessor output")
            parsed.setdefault("intent", "other")
            parsed.setdefault("entities", [])
            parsed.setdefault("filters", {})
            parsed.setdefault("rewritten_queries", [query])
            parsed["original_query"] = query
            return parsed
        except Exception as exc:
            logger.debug(f"Query preprocess fallback: {exc}")
            return {
                "original_query": query,
                "intent": "other",
                "entities": [],
                "filters": {},
                "rewritten_queries": [query],
            }


class HybridRetriever:
    def __init__(self) -> None:
        self.preprocessor = QueryPreprocessor()

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        filters: dict | None = None,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        results, _debug = await self.retrieve_with_debug(
            query=query,
            tenant_id=tenant_id,
            filters=filters,
            top_k=top_k,
        )
        return results

    async def retrieve_with_debug(
        self,
        query: str,
        tenant_id: str,
        filters: dict | None = None,
        top_k: int | None = None,
    ) -> tuple[list[RetrievalResult], dict]:
        started = time.perf_counter()
        top_k = top_k or settings.rag.fine_rerank_top_k

        preprocessed = await self.preprocessor.preprocess(query)
        rewritten_queries = preprocessed.get("rewritten_queries") or [query]
        if query not in rewritten_queries:
            rewritten_queries.insert(0, query)
        merged_filters = {**(filters or {}), **(preprocessed.get("filters") or {})}

        vector_task = self._vector_search(rewritten_queries, tenant_id, merged_filters)
        keyword_task = self._keyword_search(rewritten_queries, tenant_id, merged_filters)
        graph_task = self._graph_search(preprocessed.get("entities") or [], tenant_id, merged_filters)
        vector_results, keyword_results, graph_results = await asyncio.gather(
            vector_task, keyword_task, graph_task, return_exceptions=True
        )

        channel_errors: list[dict] = []
        vector_hits: list[RetrievalResult] = []
        keyword_hits: list[RetrievalResult] = []
        graph_hits: list[RetrievalResult] = []
        for channel_name, channel_result in [
            ("vector", vector_results),
            ("keyword", keyword_results),
            ("graph", graph_results),
        ]:
            if isinstance(channel_result, Exception):
                channel_errors.append({"channel": channel_name, "error": str(channel_result)})
                continue
            if channel_name == "vector":
                vector_hits = channel_result
            elif channel_name == "keyword":
                keyword_hits = channel_result
            else:
                graph_hits = channel_result

        merged = _rrf_merge([vector_hits, keyword_hits, graph_hits], k=60)
        coarse = await self._coarse_rerank(query, merged)
        fine = await self._fine_rerank(query, coarse)
        with_parents = await self._attach_parent_context(fine, tenant_id)
        validated, filtered_out = self._validate_results(with_parents, merged_filters)

        supplementary_used = False
        if settings.rag.enable_self_rag and len(validated) < min(3, top_k):
            supplementary_used = True
            supplemental = await self._supplementary_search(query, tenant_id, merged_filters)
            validated = _rrf_merge([validated, supplemental], k=80)

        elapsed_ms = (time.perf_counter() - started) * 1000
        final_results = validated[:top_k]

        debug = {
            "query": query,
            "preprocessed": preprocessed,
            "filters": merged_filters,
            "channels": {
                "vector": [item.payload() for item in vector_hits],
                "keyword": [item.payload() for item in keyword_hits],
                "graph": [item.payload() for item in graph_hits],
            },
            "merged": [item.payload() for item in merged],
            "reranked": [item.payload() for item in fine],
            "filtered_out": filtered_out,
            "final": [item.payload() for item in final_results],
            "self_rag_triggered": supplementary_used,
            "errors": channel_errors,
            "latency_ms": round(elapsed_ms, 2),
        }
        return final_results, debug

    def _base_where(self, tenant_id: str, filters: dict) -> list[Any]:
        where_clauses: list[Any] = [
            DocumentChunk.tenant_id == tenant_id,
        ]
        doc_ids = _document_filter_ids(filters)
        if filters.get("doc_id") or filters.get("document_ids"):
            where_clauses.append(Document.id.in_(doc_ids or [uuid.uuid4()]))
        if filters.get("doc_type"):
            where_clauses.append(Document.doc_type == filters["doc_type"])
        if filters.get("effective") is True:
            where_clauses.append(Document.is_effective.is_(True))
        return where_clauses

    async def _keyword_search(self, queries: list[str], tenant_id: str, filters: dict) -> list[RetrievalResult]:
        with start_span("retrieval.keyword_search", {"tenant.id": tenant_id}):
            return await self._keyword_search_impl(queries, tenant_id, filters)

    async def _keyword_search_impl(self, queries: list[str], tenant_id: str, filters: dict) -> list[RetrievalResult]:
        terms: list[str] = []
        for query in queries:
            terms.extend(_tokenize(query))
        terms = terms[:24]
        if not terms:
            return []

        clauses = [
            or_(
                DocumentChunk.search_text.ilike(f"%{term}%"),
                DocumentChunk.content.ilike(f"%{term}%"),
            )
            for term in terms[:10]
        ]
        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.doc_id)
            .where(and_(*self._base_where(tenant_id, filters)), or_(*clauses))
            .limit(max(settings.rag.keyword_top_k * 5, 120))
        )
        async with get_read_session() as db:
            rows = (await db.execute(stmt)).all()

        hits: list[RetrievalResult] = []
        for chunk, doc in rows:
            haystack = (chunk.search_text or chunk.content or "").lower()
            matched_terms = [term for term in terms if term in haystack]
            if not matched_terms:
                continue
            score = min(1.0, 0.25 + (len(matched_terms) / max(1, len(terms))))
            hits.append(
                RetrievalResult(
                    chunk_id=str(chunk.id),
                    content=chunk.content,
                    score=score,
                    source="keyword",
                    metadata={
                        "doc_id": str(doc.id),
                        "doc_title": doc.title,
                        "doc_type": doc.doc_type,
                        "source": doc.file_name,
                        "hierarchy_path": chunk.hierarchy_path,
                        "is_effective": doc.is_effective,
                        "applicable_region": doc.applicable_region or [],
                        "applicable_industry": doc.applicable_industry or [],
                        "matched_terms": matched_terms[:12],
                        "keyword_score_explain": f"matched={len(matched_terms)}",
                    },
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: settings.rag.keyword_top_k]

    async def _vector_search(self, queries: list[str], tenant_id: str, filters: dict) -> list[RetrievalResult]:
        with start_span("retrieval.vector_search", {"tenant.id": tenant_id}):
            return await self._vector_search_impl(queries, tenant_id, filters)

    async def _vector_search_impl(self, queries: list[str], tenant_id: str, filters: dict) -> list[RetrievalResult]:
        query_text = " ".join(queries)[:1200]
        try:
            query_vector = (await llm_service.embed([query_text]))[0]
            vector_hits = await milvus_connector.search(
                tenant_id=tenant_id,
                query_vector=query_vector,
                top_k=max(settings.rag.vector_top_k * 3, 80),
            )
        except Exception as exc:
            logger.debug(f"vector search fallback to local similarity: {exc}")
            vector_hits = []

        chunk_ids = [item["chunk_id"] for item in vector_hits if item.get("chunk_id")]
        chunk_uuids = _uuid_values(chunk_ids)
        if not chunk_uuids:
            return []

        async with get_read_session() as db:
            rows = (
                await db.execute(
                    select(DocumentChunk, Document)
                    .join(Document, Document.id == DocumentChunk.doc_id)
                    .where(
                        and_(*self._base_where(tenant_id, filters)),
                        DocumentChunk.id.in_(chunk_uuids),
                    )
                )
            ).all()

        row_map = {str(chunk.id): (chunk, doc) for chunk, doc in rows}
        hits: list[RetrievalResult] = []
        for index, item in enumerate(vector_hits):
            chunk_id = str(item.get("chunk_id") or "")
            row = row_map.get(chunk_id)
            if row is None:
                continue
            chunk, doc = row
            distance = float(item.get("score", 0.0))
            score = 1.0 / (1.0 + max(distance, 0.0))
            hits.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    content=chunk.content,
                    score=min(1.0, score + 0.05),
                    source="vector",
                    metadata={
                        "doc_id": str(doc.id),
                        "doc_title": doc.title,
                        "doc_type": doc.doc_type,
                        "source": doc.file_name,
                        "hierarchy_path": chunk.hierarchy_path,
                        "is_effective": doc.is_effective,
                        "applicable_region": doc.applicable_region or [],
                        "applicable_industry": doc.applicable_industry or [],
                        "vector_rank": index + 1,
                        "vector_distance": distance,
                    },
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: settings.rag.vector_top_k]

    async def _graph_search(self, entities: list[dict], tenant_id: str, filters: dict) -> list[RetrievalResult]:
        with start_span("retrieval.graph_search", {"tenant.id": tenant_id}):
            return await self._graph_search_impl(entities, tenant_id, filters)

    async def _graph_search_impl(self, entities: list[dict], tenant_id: str, filters: dict) -> list[RetrievalResult]:
        entity_terms = [str(item.get("text", "")).strip() for item in entities if item.get("text")]
        entity_terms = [term for term in entity_terms if len(term) >= 2][:10]
        if not entity_terms:
            return []

        graph_hits = await nebula_connector.search_chunks_by_entities(
            tenant_id=tenant_id,
            entities=entity_terms,
            limit=max(settings.rag.graph_top_k * 4, 80),
        )
        chunk_ids = [str(item.get("chunk_id") or "") for item in graph_hits if item.get("chunk_id")]
        chunk_uuids = _uuid_values(chunk_ids)
        if not chunk_uuids:
            return []

        async with get_read_session() as db:
            rows = (
                await db.execute(
                    select(DocumentChunk, Document)
                    .join(Document, Document.id == DocumentChunk.doc_id)
                    .where(and_(*self._base_where(tenant_id, filters)), DocumentChunk.id.in_(chunk_uuids))
                )
            ).all()

        row_map = {str(chunk.id): (chunk, doc) for chunk, doc in rows}
        hits: list[RetrievalResult] = []
        for item in graph_hits:
            chunk_id = str(item.get("chunk_id") or "")
            row = row_map.get(chunk_id)
            if row is None:
                continue
            chunk, doc = row
            matched_entities = list(item.get("matched_entities") or [])
            score = min(1.0, 0.35 + 0.1 * len(matched_entities))
            hits.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    content=chunk.content,
                    score=score,
                    source="graph",
                    metadata={
                        "doc_id": str(doc.id),
                        "doc_title": doc.title,
                        "doc_type": doc.doc_type,
                        "source": doc.file_name,
                        "matched_entities": matched_entities,
                        "hierarchy_path": chunk.hierarchy_path,
                        "is_effective": doc.is_effective,
                        "applicable_region": doc.applicable_region or [],
                        "applicable_industry": doc.applicable_industry or [],
                    },
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: settings.rag.graph_top_k]

    async def _coarse_rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        if not results:
            return []
        boost = {"graph": 0.08, "keyword": 0.04, "vector": 0.03}
        for item in results:
            lexical = _similarity(query, item.content)
            item.rerank_score = min(1.0, item.score + boost.get(item.source, 0.0) + lexical * 0.15)
        ranked = sorted(results, key=lambda x: float(x.rerank_score or 0.0), reverse=True)
        return ranked[: settings.rag.coarse_rerank_top_k]

    async def _fine_rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        if not results:
            return []
        documents = [item.content for item in results[:40]]
        try:
            reranked = await llm_service.rerank(query=query, documents=documents, top_k=min(len(documents), 24))
            for item in reranked:
                idx = int(item.get("index", -1))
                if 0 <= idx < len(results):
                    results[idx].rerank_score = float(item.get("score", results[idx].score))
        except Exception as exc:
            logger.debug(f"fine rerank fallback: {exc}")
            for item in results:
                if item.rerank_score is None:
                    item.rerank_score = item.score
        ranked = sorted(results, key=lambda x: float(x.rerank_score or 0.0), reverse=True)
        return ranked[: settings.rag.fine_rerank_top_k]

    async def _attach_parent_context(self, results: list[RetrievalResult], tenant_id: str) -> list[RetrievalResult]:
        if not results:
            return results
        chunk_ids = _uuid_values([item.chunk_id for item in results])
        if not chunk_ids:
            return results
        async with get_read_session() as db:
            rows = (
                await db.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.tenant_id == tenant_id, DocumentChunk.id.in_(chunk_ids))
                )
            ).all()
            parent_ids = [row.parent_chunk_id for row in rows if row.parent_chunk_id]
            if not parent_ids:
                return results
            parents = (
                await db.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.tenant_id == tenant_id,
                        DocumentChunk.id.in_(parent_ids),
                    )
                )
            ).all()

        row_map = {str(row.id): row for row in rows}
        parent_map = {str(item.id): item for item in parents}
        for item in results:
            row = row_map.get(item.chunk_id)
            if not row or not row.parent_chunk_id:
                continue
            parent = parent_map.get(str(row.parent_chunk_id))
            if not parent:
                continue
            item.metadata["parent_chunk_id"] = str(parent.id)
            item.metadata["parent_hierarchy_path"] = parent.hierarchy_path
            item.metadata["parent_excerpt"] = (parent.content or "")[:300]
        return results

    def _validate_results(self, results: list[RetrievalResult], filters: dict) -> tuple[list[RetrievalResult], list[dict]]:
        if not results:
            return [], []
        threshold = float(settings.rag.relevance_threshold or 0.0)
        accepted: list[RetrievalResult] = []
        rejected: list[dict] = []
        for item in results:
            score = float(item.rerank_score if item.rerank_score is not None else item.score)
            if settings.rag.enable_crag and score < threshold:
                rejected.append({"chunk_id": item.chunk_id, "reason": "below_threshold", "score": score})
                continue
            if filters.get("effective") is True and not item.metadata.get("is_effective", True):
                rejected.append({"chunk_id": item.chunk_id, "reason": "ineffective_document"})
                continue
            if filters.get("region"):
                regions = str(item.metadata.get("applicable_region", ""))
                if filters["region"] not in regions and regions:
                    rejected.append({"chunk_id": item.chunk_id, "reason": "region_mismatch"})
                    continue
            if filters.get("industry"):
                industries = str(item.metadata.get("applicable_industry", ""))
                if filters["industry"] not in industries and industries:
                    rejected.append({"chunk_id": item.chunk_id, "reason": "industry_mismatch"})
                    continue
            accepted.append(item)
        return accepted, rejected

    async def _supplementary_search(self, query: str, tenant_id: str, filters: dict) -> list[RetrievalResult]:
        expanded = [query] + [f"{query} 法律依据", f"{query} 合规要点"]
        keyword = await self._keyword_search(expanded, tenant_id, filters=filters)
        vector = await self._vector_search(expanded, tenant_id, filters=filters)
        return _rrf_merge([keyword, vector], k=100)[:8]


hybrid_retriever = HybridRetriever()
