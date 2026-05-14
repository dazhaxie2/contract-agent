"""Validation sub-agent: post-generation factuality and compliance verification."""

from __future__ import annotations

from app.agents.base import BaseAgent, Tool


class _FactualityCheckTool(Tool):
    name = "factuality_check"
    description = "Verify that generated content is factually grounded in the provided retrieval context."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "generated_text": {"type": "string", "description": "the generated text to verify"},
                "source_context": {"type": "string", "description": "the retrieval context that should ground the output"},
            },
            "required": ["generated_text", "source_context"],
        }

    async def execute(self, generated_text: str = "", source_context: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a factuality verification assistant for legal content.\n"
                    "Check if the generated text is accurately grounded in the source context.\n"
                    "Output format:\n"
                    "VERDICT: PASS|FAIL|PARTIAL\n"
                    "ISSUES: <list of factual inconsistencies, if any>\n"
                    "MISSING_CITATIONS: <claims without source backing>\n"
                    "CORRECTED_TEXT: <suggested correction if FAIL or PARTIAL>\n"
                    "Be strict — legal content must be 100% grounded in sources."
                ),
            },
            {
                "role": "user",
                "content": f"Generated text:\n{generated_text[:3000]}\n\nSource context:\n{source_context[:4000]}",
            },
        ]
        result = await llm_service.light_generate(messages)
        return result["content"]


class _ComplianceValidationTool(Tool):
    name = "compliance_validation"
    description = "Validate that generated legal content does not contain prohibited or misleading advice."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "content to validate"},
            },
            "required": ["content"],
        }

    async def execute(self, content: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "Validate this legal content for compliance:\n"
                    "1) No fabricated law articles or citations.\n"
                    "2) No misleading legal advice.\n"
                    "3) Clear distinction between mandatory and discretionary provisions.\n"
                    "4) Proper uncertainty markers when evidence is insufficient.\n"
                    "Output: PASS|FAIL followed by specific issues found."
                ),
            },
            {"role": "user", "content": content[:4000]},
        ]
        result = await llm_service.light_generate(messages)
        return result["content"]


class ValidationAgent(BaseAgent):
    agent_type = "validation"
    description = "Post-generation factuality and compliance verification specialist."

    def __init__(self):
        super().__init__()
        self.register_tool(_FactualityCheckTool())
        self.register_tool(_ComplianceValidationTool())

    def _build_system_prompt(self) -> str:
        return (
            "You are a legal content validation specialist.\n"
            "Your job is to verify that generated legal content is factual, compliant, and properly sourced.\n"
            "Rules:\n"
            "1) Use factuality_check to verify claims against source context.\n"
            "2) Use compliance_validation to check for prohibited or misleading content.\n"
            "3) If validation fails, clearly describe the issues and suggest corrections.\n"
            "4) Never approve content with unverified legal claims.\n"
        )
