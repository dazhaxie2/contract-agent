"""Orchestrator agent: routes tasks to specialized sub-agents."""

from __future__ import annotations

import json

from app.agents.base import BaseAgent, Tool
from app.agents.contracts import build_sub_agent_input, build_sub_agent_output
from app.agents.sub_agents import SUB_AGENTS
from app.core.config import settings


class _IntentRoutingTool(Tool):
    name = "route_to_agent"
    description = (
        "Route the current task to a specialized sub-agent. "
        "Use this when the task requires specialized expertise."
    )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["retrieval", "compliance", "comparison", "drafting", "legal_search", "validation"],
                    "description": "The specialized agent to delegate to",
                },
                "task_description": {
                    "type": "string",
                    "description": "Clear description of the sub-task for the specialized agent",
                },
                "context_payload": {
                    "type": "string",
                    "description": "JSON string of additional context to pass to the sub-agent",
                },
            },
            "required": ["agent_type", "task_description"],
        }

    async def execute(
        self, agent_type: str = "", task_description: str = "", context_payload: str = "", **kwargs
    ) -> str:
        agent_cls = SUB_AGENTS.get(agent_type)
        if not agent_cls:
            return f"Unknown agent type: {agent_type}. Available: {list(SUB_AGENTS.keys())}"

        sub_context = {}
        if context_payload:
            try:
                sub_context = json.loads(context_payload)
            except (json.JSONDecodeError, TypeError):
                sub_context = {"extra_context": context_payload}

        if "tenant_id" not in sub_context and "tenant_id" in kwargs:
            sub_context["tenant_id"] = kwargs["tenant_id"]

        contract_input = build_sub_agent_input(
            agent_type=agent_type,
            task_description=task_description,
            context_payload=sub_context,
            fallback_tenant_id=str(kwargs.get("tenant_id") or "default"),
        )
        sub_context["agent_contract"] = contract_input.model_dump(mode="json")

        agent = agent_cls()
        result = await agent.execute(query=task_description, context=sub_context)
        contract_output = build_sub_agent_output(contract_input, result)

        return json.dumps(contract_output.model_dump(mode="json"), ensure_ascii=False)
        sub_context["agent_contract"] = contract_input.model_dump(mode="json")

        agent = agent_cls()
        result = await agent.execute(query=task_description, context=sub_context)
        contract_output = build_sub_agent_output(contract_input, result)

        return json.dumps(contract_output.model_dump(mode="json"), ensure_ascii=False)


class _DirectSearchTool(Tool):
    name = "direct_search"
    description = "Quick knowledge base search without delegating to the retrieval agent. Use for simple lookups."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "search query"},
                "top_k": {"type": "integer", "description": "result size", "default": 5},
                "tenant_id": {"type": "string", "description": "tenant scope"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", top_k: int = 5, tenant_id: str = "default", **kwargs) -> str:
        from app.rag.retriever import hybrid_retriever

        results = await hybrid_retriever.retrieve(query=query, tenant_id=tenant_id, top_k=top_k)
        if not results:
            return "No relevant references found."
        lines = []
        for i, item in enumerate(results, start=1):
            title = item.metadata.get("doc_title", "Untitled")
            lines.append(f"[{i}] {title}: {item.content[:300]}")
        return "\n\n".join(lines)


class _DirectCalcTool(Tool):
    name = "direct_calculation"
    description = "Quick legal calculation without delegating to legal_search agent."

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "calculation_type": {"type": "string"},
                "parameters": {"type": "object"},
            },
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


class OrchestratorAgent(BaseAgent):
    agent_type = "orchestrator"
    description = (
        "Top-level orchestrator that analyzes user intent and routes to specialized sub-agents. "
        "Handles multi-step tasks by coordinating retrieval, compliance, comparison, drafting, "
        "legal search, and validation agents."
    )

    def __init__(self):
        super().__init__()
        self.register_tool(_IntentRoutingTool())
        self.register_tool(_DirectSearchTool())
        self.register_tool(_DirectCalcTool())

    def _build_system_prompt(self) -> str:
        enabled = []
        for key in SUB_AGENTS:
            flag = f"enable_{key}_agent"
            if getattr(settings.agent, flag, True):
                enabled.append(key)
        agent_list = ", ".join(enabled) if enabled else "none"

        return (
            "You are the master orchestrator for a contract compliance legal AI system.\n"
            "You analyze user requests and delegate to specialized sub-agents when needed.\n\n"
            f"Available sub-agents: {agent_list}\n"
            "- retrieval: document search and query expansion\n"
            "- compliance: contract compliance risk analysis\n"
            "- comparison: contract version comparison\n"
            "- drafting: contract clause drafting and optimization\n"
            "- legal_search: specific law provision search and legal calculations\n"
            "- validation: factuality and compliance verification of generated content\n\n"
            "Rules:\n"
            "1) For simple lookups or calculations, use direct_search or direct_calculation directly.\n"
            "2) For complex tasks (compliance review, contract comparison, drafting), delegate to the appropriate sub-agent via route_to_agent.\n"
            "3) For multi-step tasks, break them down and route each step to the appropriate agent.\n"
            "4) After receiving results from sub-agents, synthesize and present a coherent answer.\n"
            "5) All conclusions must be grounded in retrieval context. State uncertainty explicitly.\n"
            "6) For compliance reviews, always route to the compliance agent, then optionally to the validation agent.\n"
            "7) Sub-agent calls are wrapped with the shared agent_contract input/output schema; preserve that structure when synthesizing.\n"
        )


orchestrator_agent = OrchestratorAgent()
