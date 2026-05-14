"""Sub-agents for specialized contract compliance tasks."""

from app.agents.sub_agents.retrieval_agent import RetrievalAgent
from app.agents.sub_agents.compliance_agent import ComplianceAgent
from app.agents.sub_agents.comparison_agent import ComparisonAgent
from app.agents.sub_agents.drafting_agent import DraftingAgent
from app.agents.sub_agents.validation_agent import ValidationAgent
from app.agents.sub_agents.legal_search_agent import LegalSearchAgent

SUB_AGENTS = {
    "retrieval": RetrievalAgent,
    "compliance": ComplianceAgent,
    "comparison": ComparisonAgent,
    "drafting": DraftingAgent,
    "legal_search": LegalSearchAgent,
    "validation": ValidationAgent,
}

__all__ = ["SUB_AGENTS"]
