"""
Agent基础框架 - ReAct模式
Thought -> Action -> Observation 循环执行
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

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
        self.latency_ms: float = kwargs.get("latency_ms", 0)
        self.timestamp: float = time.time()


class AgentResult:
    def __init__(self, success: bool, output: str, steps: list[AgentStep],
                 metadata: dict | None = None):
        self.success = success
        self.output = output
        self.steps = steps
        self.metadata = metadata or {}
        self.total_tokens = sum(s.tokens_used for s in steps)
        self.total_latency_ms = sum(s.latency_ms for s in steps)


class Tool(ABC):
    """Agent可调用的工具基类"""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        pass

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters(),
            },
        }

    def get_parameters(self) -> dict:
        return {"type": "object", "properties": {}}


class BaseAgent(ABC):
    """ReAct Agent基类"""

    agent_type: str = "base"
    description: str = ""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.max_iterations = settings.agent.max_iterations
        self.max_execution_time = settings.agent.max_execution_time

    def register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    async def execute(self, query: str, context: dict | None = None) -> AgentResult:
        """ReAct循环执行"""
        steps = []
        start_time = time.perf_counter()
        iteration = 0

        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            context_msg = self._format_context(context)
            messages.append({"role": "user", "content": context_msg})

        messages.append({"role": "user", "content": query})

        while iteration < self.max_iterations:
            elapsed = (time.perf_counter() - start_time)
            if elapsed > self.max_execution_time:
                logger.warning(f"Agent {self.agent_type} 执行超时: {elapsed:.0f}s")
                return AgentResult(
                    success=False, output="执行超时，请缩小问题范围后重试",
                    steps=steps, metadata={"timeout": True},
                )

            iteration += 1
            step_start = time.perf_counter()

            try:
                # 调用大模型进行推理
                tools_schema = [t.to_schema() for t in self.tools.values()] if self.tools else None
                response = await llm_service.generate(
                    messages=messages,
                    tools=tools_schema,
                )

                step_latency = (time.perf_counter() - step_start) * 1000
                content = response.get("content", "")
                tokens = response.get("usage", {}).get("total_tokens", 0)

                # 检查是否有工具调用
                tool_calls = response.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc["function"]["name"]
                        func_args = tc["function"]["arguments"]

                        # 记录Action步骤
                        steps.append(AgentStep(
                            step_type=StepType.ACTION,
                            content=f"调用工具: {func_name}",
                            action=func_name,
                            action_input=func_args if isinstance(func_args, dict) else {},
                            tool_name=func_name,
                            tokens_used=tokens,
                            latency_ms=step_latency,
                        ))

                        # 执行工具
                        if func_name in self.tools:
                            tool_start = time.perf_counter()
                            args = func_args if isinstance(func_args, dict) else {}
                            observation = await self.tools[func_name].execute(**args)
                            tool_latency = (time.perf_counter() - tool_start) * 1000

                            steps.append(AgentStep(
                                step_type=StepType.OBSERVATION,
                                content=observation,
                                observation=observation,
                                tool_name=func_name,
                                latency_ms=tool_latency,
                            ))

                            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                            messages.append({"role": "tool", "content": observation, "tool_call_id": tc.get("id", "")})
                        else:
                            messages.append({
                                "role": "tool",
                                "content": f"未知工具: {func_name}",
                                "tool_call_id": tc.get("id", ""),
                            })
                else:
                    # 无工具调用 = 最终输出
                    steps.append(AgentStep(
                        step_type=StepType.FINAL,
                        content=content,
                        tokens_used=tokens,
                        latency_ms=step_latency,
                    ))

                    return AgentResult(
                        success=True, output=content, steps=steps,
                        metadata={
                            "iterations": iteration,
                            "model": response.get("model", ""),
                        },
                    )

            except Exception as exc:
                logger.error(f"Agent {self.agent_type} 步骤 {iteration} 执行失败: {exc}")
                steps.append(AgentStep(
                    step_type=StepType.THOUGHT,
                    content=f"执行错误: {exc}",
                    latency_ms=(time.perf_counter() - step_start) * 1000,
                ))

                if iteration >= self.max_iterations:
                    return AgentResult(
                        success=False, output=f"执行失败: {exc}",
                        steps=steps, metadata={"error": str(exc)},
                    )

        return AgentResult(
            success=False, output="达到最大迭代次数",
            steps=steps, metadata={"max_iterations_reached": True},
        )

    @abstractmethod
    def _build_system_prompt(self) -> str:
        pass

    def _format_context(self, context: dict) -> str:
        parts = []
        if "retrieval_context" in context:
            parts.append(f"## 检索上下文\n\n{context['retrieval_context']}")
        if "references" in context:
            ref_text = "\n".join(
                f"- [参考{r['ref_id']}] {r['source']} ({r['hierarchy']})"
                for r in context["references"]
            )
            parts.append(f"## 参考来源\n\n{ref_text}")
        if "conversation_history" in context:
            parts.append(f"## 对话历史\n\n{context['conversation_history']}")
        return "\n\n".join(parts)
