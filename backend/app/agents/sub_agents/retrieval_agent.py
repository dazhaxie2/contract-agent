"""Retrieval sub-agent: specialized in multi-channel legal document retrieval."""

from __future__ import annotations

from app.agents.base import BaseAgent, Tool


class _SearchTool(Tool):
    name = "search_knowledge_base"
    description = "Search contract/law chunks from the internal knowledge base using hybrid retrieval."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "search query in legal domain terms"},
                "top_k": {"type": "integer", "description": "result size", "default": 10},
                "tenant_id": {"type": "string", "description": "tenant scope"},
                "filters": {
                    "type": "object",
                    "description": "optional filters: doc_type, effective_date range, industry, region",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", top_k: int = 10, tenant_id: str = "default", filters: dict | None = None, **kwargs) -> str:
        from app.rag.retriever import hybrid_retriever

        results = await hybrid_retriever.retrieve(query=query, tenant_id=tenant_id, top_k=top_k, filters=filters)
        if not results:
            return "No relevant legal references found in the knowledge base."
        lines = []
        for i, item in enumerate(results, start=1):
            title = item.metadata.get("doc_title", "Untitled")
            hierarchy = item.metadata.get("hierarchy_path", "")
            path_info = f" ({hierarchy})" if hierarchy else ""
            lines.append(f"[{i}] {title}{path_info}: {item.content[:400]}")
        return "\n\n".join(lines)


class _ExpandQueryTool(Tool):
    name = "expand_search_query"
    description = "Rewrite and expand a user query into multiple legal-domain sub-queries for broader recall."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "original user query"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a legal query expansion assistant. Given a user query about contracts or compliance, "
                    "generate 3-5 alternative queries using precise legal terminology. "
                    "Output one query per line, no numbering, no explanations."
                ),
            },
            {"role": "user", "content": query},
        ]
        result = await llm_service.light_generate(messages)
        return result["content"]


class RetrievalAgent(BaseAgent):
    agent_type = "retrieval"
    description = "Specialized in multi-channel legal document retrieval and query expansion."

    def __init__(self):
        super().__init__()
        self.register_tool(_SearchTool())
        self.register_tool(_ExpandQueryTool())

    def _build_system_prompt(self) -> str:
        return (
            "You are a legal document retrieval specialist.\n"
            "Your job is to find the most relevant legal references from the knowledge base.\n"
            "Rules:\n"
            "1) Use search_knowledge_base to find relevant documents. Prefer legal-domain terms.\n"
            "2) If initial results are sparse, use expand_search_query to generate alternative queries and search again.\n"
            "3) Return structured results with document titles, hierarchy paths, and relevant excerpts.\n"
            "4) Never fabricate references — only report what the knowledge base returns.\n"
        )
