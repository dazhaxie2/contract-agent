"""Sub-agents for specialized contract compliance tasks."""

from collections.abc import Callable

from app.agents.base import BaseAgent
from app.agents.sub_agents.retrieval_agent import RetrievalAgent
from app.agents.sub_agents.compliance_agent import ComplianceAgent
from app.agents.sub_agents.comparison_agent import ComparisonAgent
from app.agents.sub_agents.drafting_agent import DraftingAgent
from app.agents.sub_agents.validation_agent import ValidationAgent
from app.agents.sub_agents.legal_search_agent import LegalSearchAgent

# 注册表只保存「具体」子代理类（均实现了 _build_system_prompt）。
# 标注为零参工厂 Callable[[], BaseAgent] 而非 type[BaseAgent]，
# 这样在 orchestrator 中按 key 取出后可直接实例化，且不会触发
# mypy 对「实例化抽象基类」的误报（具体类对工厂类型是型变兼容的）。
SUB_AGENTS: dict[str, Callable[[], BaseAgent]] = {
    "retrieval": RetrievalAgent,
    "compliance": ComplianceAgent,
    "comparison": ComparisonAgent,
    "drafting": DraftingAgent,
    "legal_search": LegalSearchAgent,
    "validation": ValidationAgent,
}

__all__ = ["SUB_AGENTS"]
