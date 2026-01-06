"""Core module for Scale Agents."""

from scale_agents.core.logging import get_logger, setup_logging
from scale_agents.core.exceptions import (
    ScaleAgentError,
    MCPConnectionError,
    MCPToolError,
    ConfirmationRequiredError,
    AgentRoutingError,
    ValidationError,
    ToolNotAllowedError,
)

__all__ = [
    "get_logger",
    "setup_logging",
    "ScaleAgentError",
    "MCPConnectionError",
    "MCPToolError",
    "ConfirmationRequiredError",
    "AgentRoutingError",
    "ValidationError",
    "ToolNotAllowedError",
]

# Optional LLM reasoning exports
try:
    from scale_agents.core.reasoning import (
        LLMReasoner,
        ReasoningResult,
        get_reasoner,
        classify_with_llm,
        select_tools_with_llm,
    )

    __all__.extend([
        "LLMReasoner",
        "ReasoningResult",
        "get_reasoner",
        "classify_with_llm",
        "select_tools_with_llm",
    ])
except ImportError:
    pass
