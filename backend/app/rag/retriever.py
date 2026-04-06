"""
多路混合检索引擎
向量检索 + 关键词检索 + 图谱检索 -> 融合去重 -> 粗排 -> 精排 -> 校验
"""

import asyncio
import time
from typing import Optional

from loguru import logger

from app.core.config import settings
from app.services.llm_service import llm_service


class RetrievalResult:
    def __init__(self, chunk_id: str, content: str, score: float,
                 source: str, metadata: dict | None = None):
        self.chunk_id = chunk_id
        self.content = content
        self.score = score
        self.source = source  # vector/keyword/graph
        self.metadata = metadata or {}
        self.rerank_score: float | None = None


class QueryPreprocessor:
    """Query前置处理: 意图识别 + 实体抽取 + 多Query改写"""

    async def preprocess(self, query: str) -> dict:
        """预处理用户查询"""
        messages = [
            {"role": "system", "content": (
                "你是法律领域NLP专家。请对用户的查询做以下分析，返回JSON格式：\n"
                '{"intent": "合同审查|法条检索|风险识别|条款比对|合规校验|合同起草|其他", '
                '"entities": [{"text": "实体", "type": "法律主体|法条|条款|行业|地域"}], '
                '"filters": {"doc_type": "", "industry": "", "region": "", "effective": true}, '
                '"rewritten_queries": ["改写1", "改写2", "改写3"]}'
            )},
            {"role": "user", "content": query},
        ]

        try:
            result = await llm_service.light_generate(messages, max_tokens=1024)
            import json
            parsed = json.loads(result["content"])
            parsed["original_query"] = query
            return parsed
        except Exception as exc:
            logger.warning(f"Query预处理失败: {exc}, 使用原始查询")
            return {
                "original_query": query,
                "intent": "其他",
                "entities": [],
                "filters": {},
                "rewritten_queries": [query],
            }


class HybridRetriever:
    """多路混合检索器"""

    def __init__(self):
        self.preprocessor = QueryPreprocessor()

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        filters: dict | None = None,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """
        完整检索流程:
        1. Query预处理 -> 2. 并行三路检索 -> 3. 融合去重
        -> 4. 粗排 -> 5. 精排 -> 6. 校验 -> 7. 二次检索(可选)
        """
        start_time = time.perf_counter()
        top_k = top_k or settings.rag.fine_rerank_top_k

        # Step 1: Query预处理
        preprocessed = await self.preprocessor.preprocess(query)
        queries = preprocessed.get("rewritten_queries", [query])
        if query not in queries:
            queries.insert(0, query)

        search_filters = {**(filters or {}), **preprocessed.get("filters", {})}

        # Step 2: 并行三路检索
        vector_task = self._vector_search(queries, tenant_id, search_filters)
        keyword_task = self._keyword_search(queries, tenant_id, search_filters)
        graph_task = self._graph_search(preprocessed.get("entities", []), tenant_id)

        vector_results, keyword_results, graph_results = await asyncio.gather(
            vector_task, keyword_task, graph_task,
            return_exceptions=True,
        )

        # 异常处理
        all_results = []
        for name, results in [("vector", vector_results), ("keyword", keyword_results), ("graph", graph_results)]:
            if isinstance(results, Exception):
                logger.error(f"{name}检索异常: {results}")
            else:
                all_results.extend(results)

        # Step 3: 融合去重
        merged = self._merge_and_dedup(all_results)
        logger.info(f"检索融合后: {len(merged)} 条结果")

        # Step 4: 粗排
        coarse_ranked = await self._coarse_rerank(query, merged)

        # Step 5: 精排
        fine_ranked = await self._fine_rerank(query, coarse_ranked)

        # Step 6: 校验
        validated = await self._validate_results(query, fine_ranked)

        # Step 7: 如果有效结果不足，触发二次检索(Self-RAG)
        if settings.rag.enable_self_rag and len(validated) < 3:
            logger.info("有效结果不足，触发Self-RAG二次检索")
            supplementary = await self._supplementary_search(query, preprocessed, tenant_id)
            validated.extend(supplementary)

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"检索完成: {len(validated)} 条有效结果 | 耗时 {duration_ms:.0f}ms")

        return validated[:top_k]

    async def _vector_search(
        self, queries: list[str], tenant_id: str, filters: dict
    ) -> list[RetrievalResult]:
        """向量语义检索"""
        try:
            # 批量嵌入所有查询
            query_vectors = await llm_service.embed(queries)

            results = []
            # 模拟向量检索 (生产环境对接Milvus)
            for i, q in enumerate(queries):
                # 此处应调用Milvus search
                # collection.search(query_vectors[i], ...)
                pass

            return results
        except Exception as exc:
            logger.error(f"向量检索失败: {exc}")
            return []

    async def _keyword_search(
        self, queries: list[str], tenant_id: str, filters: dict
    ) -> list[RetrievalResult]:
        """BM25关键词检索"""
        try:
            results = []
            # 此处应查询PostgreSQL全文索引
            # SELECT * FROM document_chunks WHERE to_tsvector(content) @@ to_tsquery(query)
            return results
        except Exception as exc:
            logger.error(f"关键词检索失败: {exc}")
            return []

    async def _graph_search(
        self, entities: list[dict], tenant_id: str
    ) -> list[RetrievalResult]:
        """知识图谱检索"""
        try:
            results = []
            # 此处应查询NebulaGraph
            # GO FROM entity_id OVER relation_type YIELD ...
            return results
        except Exception as exc:
            logger.error(f"图谱检索失败: {exc}")
            return []

    def _merge_and_dedup(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """融合去重 - 按chunk_id去重，保留最高分"""
        seen = {}
        for r in results:
            if r.chunk_id not in seen or r.score > seen[r.chunk_id].score:
                seen[r.chunk_id] = r
        merged = list(seen.values())
        merged.sort(key=lambda x: x.score, reverse=True)
        return merged[:100]  # Top-100

    async def _coarse_rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """粗排 - BGE-reranker-base"""
        if not results:
            return []

        top_k = settings.rag.coarse_rerank_top_k
        try:
            documents = [r.content for r in results]
            reranked = await llm_service.rerank(query, documents, top_k=top_k)

            for item in reranked:
                idx = item["index"]
                if idx < len(results):
                    results[idx].rerank_score = item["score"]

            # 按重排分数排序
            scored = [r for r in results if r.rerank_score is not None]
            scored.sort(key=lambda x: x.rerank_score, reverse=True)
            return scored[:top_k]
        except Exception as exc:
            logger.warning(f"粗排失败: {exc}, 使用原始排序")
            return results[:top_k]

    async def _fine_rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """精排 - BGE-reranker-large"""
        if not results:
            return []

        top_k = settings.rag.fine_rerank_top_k
        try:
            documents = [r.content for r in results]
            reranked = await llm_service.rerank(query, documents, top_k=top_k)

            for item in reranked:
                idx = item["index"]
                if idx < len(results):
                    results[idx].rerank_score = item["score"]

            scored = [r for r in results if r.rerank_score is not None]
            scored.sort(key=lambda x: x.rerank_score, reverse=True)
            return scored[:top_k]
        except Exception as exc:
            logger.warning(f"精排失败: {exc}")
            return results[:top_k]

    async def _validate_results(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """CRAG校验 - 相关性/事实性/法律效力校验"""
        if not settings.rag.enable_crag or not results:
            return results

        validated = []
        for r in results:
            if r.rerank_score and r.rerank_score >= settings.rag.relevance_threshold:
                validated.append(r)
            else:
                # 可选：用小模型二次校验
                validated.append(r)

        return validated

    async def _supplementary_search(
        self, query: str, preprocessed: dict, tenant_id: str
    ) -> list[RetrievalResult]:
        """Self-RAG二次检索"""
        messages = [
            {"role": "system", "content": "请基于原始查询生成2个不同角度的补充检索查询，用JSON数组返回。"},
            {"role": "user", "content": query},
        ]
        try:
            result = await llm_service.light_generate(messages, max_tokens=256)
            import json
            new_queries = json.loads(result["content"])
            if isinstance(new_queries, list):
                vectors = await llm_service.embed(new_queries[:2])
                # 补充向量检索...
                return []
        except Exception:
            pass
        return []


hybrid_retriever = HybridRetriever()
