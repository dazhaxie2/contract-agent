"""Drafting sub-agent: specialized in contract drafting and clause optimization."""

from __future__ import annotations

from app.agents.base import BaseAgent, Tool


class _DraftClauseTool(Tool):
    name = "draft_clause"
    description = "Draft or optimize a contract clause based on requirements and legal constraints."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "clause_type": {
                    "type": "string",
                    "description": "Type: payment, liability, termination, confidentiality, warranty, indemnity, force_majeure, dispute, general",
                },
                "requirements": {"type": "string", "description": "specific requirements or constraints for the clause"},
                "context": {"type": "string", "description": "surrounding contract context"},
            },
            "required": ["clause_type"],
        }

    async def execute(self, clause_type: str = "", requirements: str = "", context: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service

        req_block = f"\nRequirements: {requirements}" if requirements else ""
        ctx_block = f"\nContext: {context}" if context else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior contract drafting lawyer. Draft a legally sound contract clause.\n"
                    "Requirements:\n"
                    "1) Use precise Chinese legal language.\n"
                    "2) Ensure compliance with 《民法典》, 《合同法》relevant provisions.\n"
                    "3) Include appropriate safeguards and remedies.\n"
                    "4) Output the clause in ready-to-use format.\n"
                    "5) Briefly note the legal basis for key provisions."
                ),
            },
            {"role": "user", "content": f"Clause type: {clause_type}{req_block}{ctx_block}"},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class _OptimizeClauseTool(Tool):
    name = "optimize_clause"
    description = "Optimize an existing contract clause for better legal protection and compliance."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "original_clause": {"type": "string", "description": "the original clause to optimize"},
                "optimization_goal": {
                    "type": "string",
                    "description": "Goal: risk_reduction, compliance, clarity, balance",
                    "default": "balance",
                },
            },
            "required": ["original_clause"],
        }

    async def execute(self, original_clause: str = "", optimization_goal: str = "balance", **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "Optimize this contract clause. Goals:\n"
                    "1) Strengthen legal protection.\n"
                    "2) Ensure regulatory compliance.\n"
                    "3) Improve clarity and reduce ambiguity.\n"
                    f"Optimization focus: {optimization_goal}\n"
                    "Output: ORIGINAL → OPTIMIZED → CHANGES_EXPLAINED"
                ),
            },
            {"role": "user", "content": original_clause[:3000]},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class DraftingAgent(BaseAgent):
    agent_type = "drafting"
    description = "Specialized in contract drafting and clause optimization."

    def __init__(self):
        super().__init__()
        self.register_tool(_DraftClauseTool())
        self.register_tool(_OptimizeClauseTool())

    def _build_system_prompt(self) -> str:
        return (
            "You are a contract drafting specialist.\n"
            "Your job is to draft and optimize contract clauses that are legally sound and compliant.\n"
            "Rules:\n"
            "1) Use draft_clause to create new clauses based on type and requirements.\n"
            "2) Use optimize_clause to improve existing clauses.\n"
            "3) All drafted content must cite applicable legal provisions.\n"
            "4) Balance between legal protection and commercial feasibility.\n"
        )
