"""Master agent orchestration."""

from __future__ import annotations

from app.agents.base import BaseAgent, Tool


class RetrievalTool(Tool):
    name = "search_knowledge_base"
    description = "Search contract/law chunks from the internal knowledge base."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "search query"},
                "top_k": {"type": "integer", "description": "result size", "default": 10},
                "tenant_id": {"type": "string", "description": "tenant scope"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", top_k: int = 10, tenant_id: str = "default", **kwargs) -> str:
        from app.rag.retriever import hybrid_retriever

        results = await hybrid_retriever.retrieve(query=query, tenant_id=tenant_id, top_k=top_k)
        if not results:
            return "No relevant internal legal references were found."
        lines = []
        for i, item in enumerate(results, start=1):
            title = item.metadata.get("doc_title", "Untitled")
            lines.append(f"[{i}] {title}: {item.content[:300]}")
        return "\n\n".join(lines)


class ComplianceCheckTool(Tool):
    name = "compliance_check"
    description = "Analyze legal/compliance risk in provided text."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}, "check_type": {"type": "string", "default": "full"}},
            "required": ["text"],
        }

    async def execute(self, text: str = "", check_type: str = "full", **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a legal compliance reviewer. Return structured output with: "
                    "risk level, findings, legal basis, and remediation suggestions."
                ),
            },
            {"role": "user", "content": f"check_type={check_type}\n\n{text[:4000]}"},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class ContractComparisonTool(Tool):
    name = "compare_clauses"
    description = "Compare two contract texts and highlight meaningful diffs."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text_a": {"type": "string"}, "text_b": {"type": "string"}},
            "required": ["text_a", "text_b"],
        }

    async def execute(self, text_a: str = "", text_b: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": "Compare two legal documents and list additions, removals, and risk-impacting edits.",
            },
            {"role": "user", "content": f"TEXT_A:\n{text_a[:3500]}\n\nTEXT_B:\n{text_b[:3500]}"},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class LegalCalculationTool(Tool):
    name = "legal_calculation"
    description = "Compute legal calculations such as penalties, interest, or timeline estimates."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"calculation_type": {"type": "string"}, "parameters": {"type": "object"}},
            "required": ["calculation_type"],
        }

    async def execute(self, calculation_type: str = "", parameters: dict | None = None, **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": "Provide deterministic legal calculation steps and final numeric results.",
            },
            {"role": "user", "content": f"type={calculation_type}\nparameters={parameters or {}}"},
        ]
        result = await llm_service.light_generate(messages)
        return result["content"]


class MasterAgent(BaseAgent):
    agent_type = "master"
    description = "Top-level legal assistant that orchestrates retrieval, analysis, and drafting tools."

    def __init__(self):
        super().__init__()
        self.register_tool(RetrievalTool())
        self.register_tool(ComplianceCheckTool())
        self.register_tool(ContractComparisonTool())
        self.register_tool(LegalCalculationTool())

    def _build_system_prompt(self) -> str:
        return (
            "You are a contract compliance legal assistant.\n"
            "Rules:\n"
            "1) Ground every conclusion in provided retrieval context.\n"
            "2) If evidence is insufficient, explicitly state uncertainty.\n"
            "3) Use concise structure: findings, legal basis, risk level, recommendations.\n"
            "4) Prefer calling tools when retrieval or verification is needed."
        )


master_agent = MasterAgent()
