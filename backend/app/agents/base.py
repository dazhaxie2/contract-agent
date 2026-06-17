"""Base ReAct-style agent runtime."""

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.llm_service import llm_service


class StepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    VALIDATION = "validation"
    FINAL = "final"


class AgentStep:
    def __init__(self, step_type: StepType, content: str, **kwargs):
        self.id = str(uuid.uuid4())
        self.step_type = step_type
        self.content = content
        self.action: str | None = kwargs.get("action")
        self.action_input: dict = kwargs.get("action_input", {})
        self.observation: str | None = kwargs.get("observation")
        self.tool_name: str | None = kwargs.get("tool_name")
        self.tokens_used: int = kwargs.get("tokens_used", 0)
        self.latency_ms: float = kwargs.get("latency_ms", 0.0)
        self.timestamp: float = time.time()


class AgentResult:
    def __init__(self, success: bool, output: str, steps: list[AgentStep], metadata: dict | None = None):
        self.success = success
        self.output = output
        self.steps = steps
        self.metadata = metadata or {}
        self.total_tokens = sum(step.tokens_used for step in steps)
        self.total_latency_ms = sum(step.latency_ms for step in steps)


class Tool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        raise NotImplementedError

    def get_parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters(),
            },
        }


class BaseAgent(ABC):
    agent_type: str = "base"
    description: str = ""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.max_iterations = settings.agent.max_iterations
        self.max_execution_time = settings.agent.max_execution_time

    def register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    async def execute(self, query: str, context: dict | None = None) -> AgentResult:
        started = time.perf_counter()
        steps: list[AgentStep] = []
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._build_system_prompt()}]

        if context:
            context_text = self._format_context(context)
            if context_text:
                messages.append({"role": "user", "content": context_text})
        messages.append({"role": "user", "content": query})

        for iteration in range(1, self.max_iterations + 1):
            elapsed = time.perf_counter() - started
            if elapsed > self.max_execution_time:
                return AgentResult(
                    success=False,
                    output="Agent execution timeout",
                    steps=steps,
                    metadata={"timeout": True, "iterations": iteration - 1},
                )

            step_started = time.perf_counter()
            try:
                response = await llm_service.generate(
                    messages=messages,
                    tools=[tool.to_schema() for tool in self.tools.values()] or None,
                )
                step_latency = (time.perf_counter() - step_started) * 1000
                content = str(response.get("content", ""))
                tokens = int((response.get("usage") or {}).get("total_tokens", 0))
                tool_calls = response.get("tool_calls") or []

                if not tool_calls:
                    steps.append(
                        AgentStep(
                            step_type=StepType.FINAL,
                            content=content,
                            tokens_used=tokens,
                            latency_ms=step_latency,
                        )
                    )
                    return AgentResult(
                        success=True,
                        output=content,
                        steps=steps,
                        metadata={"iterations": iteration, "model": response.get("model", "")},
                    )

                for tool_call in tool_calls:
                    fn = (tool_call.get("function") or {}).get("name", "")
                    raw_args = (tool_call.get("function") or {}).get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            raw_args = json.loads(raw_args) if raw_args.strip() else {}
                        except Exception:
                            raw_args = {}
                    args = dict(raw_args) if isinstance(raw_args, dict) else {}
                    if context and "tenant_id" in context and "tenant_id" not in args:
                        args["tenant_id"] = context["tenant_id"]

                    steps.append(
                        AgentStep(
                            step_type=StepType.ACTION,
                            content=f"Invoke tool: {fn}",
                            action=fn,
                            action_input=args,
                            tool_name=fn,
                            tokens_used=tokens,
                            latency_ms=step_latency,
                        )
                    )

                    if fn not in self.tools:
                        observation = f"Unknown tool: {fn}"
                    else:
                        tool_started = time.perf_counter()
                        observation = await self.tools[fn].execute(**args)
                        tool_latency = (time.perf_counter() - tool_started) * 1000
                        steps.append(
                            AgentStep(
                                step_type=StepType.OBSERVATION,
                                content=observation,
                                observation=observation,
                                tool_name=fn,
                                latency_ms=tool_latency,
                            )
                        )

                    messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                    messages.append(
                        {
                            "role": "tool",
                            "content": observation,
                            "tool_call_id": tool_call.get("id", ""),
                        }
                    )
            except Exception as exc:
                logger.error(f"Agent {self.agent_type} iteration {iteration} failed: {exc}")
                steps.append(
                    AgentStep(
                        step_type=StepType.THOUGHT,
                        content=f"Agent error: {exc}",
                        latency_ms=(time.perf_counter() - step_started) * 1000,
                    )
                )
                if iteration >= self.max_iterations:
                    return AgentResult(success=False, output=f"Agent failed: {exc}", steps=steps, metadata={"error": str(exc)})

        return AgentResult(
            success=False,
            output="Agent stopped after reaching max iterations",
            steps=steps,
            metadata={"max_iterations_reached": True},
        )

    @abstractmethod
    def _build_system_prompt(self) -> str:
        raise NotImplementedError

    def _format_context(self, context: dict) -> str:
        parts: list[str] = []
        if context.get("retrieval_context"):
            parts.append(f"## Retrieval Context\n{context['retrieval_context']}")
        if context.get("references"):
            refs = "\n".join(
                f"- [REF-{r.get('ref_id')}] {r.get('source', '')} ({r.get('hierarchy', '')})"
                for r in context["references"]
            )
            parts.append(f"## References\n{refs}")
        if context.get("conversation_history"):
            parts.append(f"## Conversation\n{context['conversation_history']}")
        if context.get("session_summary"):
            parts.append(f"## Session Summary\n{context['session_summary']}")
        if context.get("memory_facts"):
            facts = "\n".join(f"- {item['key']}: {item['value']}" for item in context["memory_facts"][:10])
            if facts:
                parts.append(f"## Facts\n{facts}")
        if context.get("user_profile"):
            parts.append(f"## User Profile\n{context['user_profile']}")
        return "\n\n".join(parts)
