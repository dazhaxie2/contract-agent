"""Compliance sub-agent: specialized in contract compliance risk analysis."""

from __future__ import annotations

from app.agents.base import BaseAgent, Tool


class _ComplianceCheckTool(Tool):
    name = "compliance_check"
    description = "Analyze legal/compliance risk in provided contract text against applicable laws."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "contract text to check"},
                "check_type": {
                    "type": "string",
                    "description": "Type of check: full, risk_only, clause_validity",
                    "default": "full",
                },
                "context_refs": {
                    "type": "string",
                    "description": "Relevant legal references retrieved from knowledge base (optional)",
                },
            },
            "required": ["text"],
        }

    async def execute(self, text: str = "", check_type: str = "full", context_refs: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service

        context_block = f"\n\n参考法规上下文:\n{context_refs}" if context_refs else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior legal compliance reviewer specializing in Chinese contract law.\n"
                    "Return structured output in markdown with sections:\n"
                    "## 风险等级 (high/medium/low)\n"
                    "## 审查发现\n"
                    "## 法律依据 (cite specific articles)\n"
                    "## 修改建议\n"
                    "Only base conclusions on provided context and well-known Chinese law. "
                    "Explicitly state when evidence is insufficient."
                ),
            },
            {"role": "user", "content": f"check_type={check_type}\n\n{text[:4000]}{context_block}"},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class _RiskScoringTool(Tool):
    name = "score_risk"
    description = "Score the risk level of a contract clause on a 0-10 scale."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "clause": {"type": "string", "description": "contract clause text"},
                "legal_context": {"type": "string", "description": "applicable legal provisions"},
            },
            "required": ["clause"],
        }

    async def execute(self, clause: str = "", legal_context: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service

        ctx = f"\nLegal context:\n{legal_context}" if legal_context else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "Score the risk level of this contract clause on a 0-10 scale (10=highest risk).\n"
                    "Output format: SCORE: <number>\nREASON: <one sentence>"
                ),
            },
            {"role": "user", "content": f"{clause[:2000]}{ctx}"},
        ]
        result = await llm_service.light_generate(messages)
        return result["content"]


class ComplianceAgent(BaseAgent):
    agent_type = "compliance"
    description = "Specialized in contract compliance risk identification and legal basis matching."

    def __init__(self):
        super().__init__()
        self.register_tool(_ComplianceCheckTool())
        self.register_tool(_RiskScoringTool())

    def _build_system_prompt(self) -> str:
        return (
            "You are a contract compliance review expert.\n"
            "Your job is to identify compliance risks in contract text and provide legally grounded analysis.\n"
            "Rules:\n"
            "1) Always use compliance_check tool for thorough analysis.\n"
            "2) Use score_risk to quantify risk levels when analyzing specific clauses.\n"
            "3) Every finding must cite specific legal provisions.\n"
            "4) Distinguish between mandatory (强制性) and discretionary (任意性) provisions.\n"
            "5) When evidence is insufficient, clearly state '暂无充分法律依据'.\n"
        )
