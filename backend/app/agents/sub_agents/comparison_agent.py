"""Comparison sub-agent: specialized in contract version comparison."""

from __future__ import annotations

from app.agents.base import BaseAgent, Tool


class _CompareClausesTool(Tool):
    name = "compare_clauses"
    description = "Compare two contract texts and highlight meaningful diffs, risk-impacting edits, and additions/removals."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text_a": {"type": "string", "description": "original contract text"},
                "text_b": {"type": "string", "description": "revised contract text"},
                "focus": {
                    "type": "string",
                    "description": "comparison focus: risk, financial, liability, full",
                    "default": "full",
                },
            },
            "required": ["text_a", "text_b"],
        }

    async def execute(self, text_a: str = "", text_b: str = "", focus: str = "full", **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a legal contract comparison specialist. Compare two contract texts and produce:\n"
                    "## 新增条款\n"
                    "## 删除条款\n"
                    "## 修改条款 (highlight risk-impacting changes)\n"
                    "## 风险影响评估\n"
                    f"Comparison focus: {focus}\n"
                    "Be thorough and precise. Cite specific clause numbers where applicable."
                ),
            },
            {"role": "user", "content": f"原合同:\n{text_a[:3500]}\n\n修改后合同:\n{text_b[:3500]}"},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class ComparisonAgent(BaseAgent):
    agent_type = "comparison"
    description = "Specialized in comparing contract versions and identifying risk-impacting changes."

    def __init__(self):
        super().__init__()
        self.register_tool(_CompareClausesTool())

    def _build_system_prompt(self) -> str:
        return (
            "You are a contract version comparison expert.\n"
            "Your job is to compare contract versions and identify all meaningful differences.\n"
            "Rules:\n"
            "1) Use compare_clauses tool for detailed comparison.\n"
            "2) Focus on risk-impacting changes: liability shifts, payment terms, termination clauses.\n"
            "3) Clearly categorize changes as additions, removals, or modifications.\n"
            "4) Assess the risk impact of each change.\n"
        )
