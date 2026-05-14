"""Legal search sub-agent: specialized in searching and matching specific legal provisions."""

from __future__ import annotations

from app.agents.base import BaseAgent, Tool


class _LegalSearchTool(Tool):
    name = "search_law_provisions"
    description = "Search for specific law articles, judicial interpretations, or regulatory provisions."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "law_name": {"type": "string", "description": "name of the law or regulation"},
                "article_number": {"type": "string", "description": "specific article number (optional)"},
                "topic": {"type": "string", "description": "topic or keyword to search"},
                "tenant_id": {"type": "string", "description": "tenant scope"},
            },
            "required": ["topic"],
        }

    async def execute(
        self, topic: str = "", law_name: str = "", article_number: str = "", tenant_id: str = "default", **kwargs
    ) -> str:
        from app.rag.retriever import hybrid_retriever

        query_parts = [topic]
        if law_name:
            query_parts.append(law_name)
        if article_number:
            query_parts.append(f"第{article_number}条")
        query = " ".join(query_parts)

        results = await hybrid_retriever.retrieve(query=query, tenant_id=tenant_id, top_k=10)
        if not results:
            return "未找到相关法律条文。"
        lines = []
        for i, item in enumerate(results, start=1):
            title = item.metadata.get("doc_title", "")
            hierarchy = item.metadata.get("hierarchy_path", "")
            lines.append(f"[{i}] {title} - {hierarchy}\n{item.content[:300]}")
        return "\n\n".join(lines)


class _LegalCalculationTool(Tool):
    name = "legal_calculation"
    description = "Compute legal calculations: penalties, interest, limitation periods, etc."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "calculation_type": {
                    "type": "string",
                    "description": "Type: penalty_interest, limitation_period, damages, contract_amount, late_fee",
                },
                "parameters": {
                    "type": "object",
                    "description": "Calculation parameters as key-value pairs",
                },
            },
            "required": ["calculation_type"],
        }

    async def execute(self, calculation_type: str = "", parameters: dict | None = None, **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "Perform a legal calculation. Provide:\n"
                    "1) The legal basis (specific law article).\n"
                    "2) Step-by-step calculation.\n"
                    "3) Final numeric result.\n"
                    "Be precise with dates, rates, and amounts."
                ),
            },
            {"role": "user", "content": f"type={calculation_type}\nparameters={parameters or {}}"},
        ]
        result = await llm_service.light_generate(messages)
        return result["content"]


class LegalSearchAgent(BaseAgent):
    agent_type = "legal_search"
    description = "Specialized in searching specific legal provisions and performing legal calculations."

    def __init__(self):
        super().__init__()
        self.register_tool(_LegalSearchTool())
        self.register_tool(_LegalCalculationTool())

    def _build_system_prompt(self) -> str:
        return (
            "You are a legal provision search and calculation specialist.\n"
            "Your job is to find specific law articles and perform legal calculations.\n"
            "Rules:\n"
            "1) Use search_law_provisions to find relevant legal articles.\n"
            "2) Use legal_calculation for numeric legal computations.\n"
            "3) Always cite the specific law article as basis.\n"
            "4) Verify that cited provisions are currently effective.\n"
        )
