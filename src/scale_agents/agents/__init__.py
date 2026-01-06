"""Agent implementations for Scale Agents."""

from scale_agents.agents.base import BaseScaleAgent
from scale_agents.agents.health import HealthAgent, register_health_agent
from scale_agents.agents.storage import StorageAgent, register_storage_agent
from scale_agents.agents.quota import QuotaAgent, register_quota_agent
from scale_agents.agents.performance import PerformanceAgent, register_performance_agent
from scale_agents.agents.admin import AdminAgent, register_admin_agent
from scale_agents.agents.orchestrator import Orchestrator, register_orchestrator

__all__ = [
    "BaseScaleAgent",
    "HealthAgent",
    "StorageAgent",
    "QuotaAgent",
    "PerformanceAgent",
    "AdminAgent",
    "Orchestrator",
    "register_health_agent",
    "register_storage_agent",
    "register_quota_agent",
    "register_performance_agent",
    "register_admin_agent",
    "register_orchestrator",
]

# Optional LLM-powered agent
try:
    from scale_agents.agents.llm_agent import LLMPoweredAgent
    __all__.append("LLMPoweredAgent")
except ImportError:
    pass
