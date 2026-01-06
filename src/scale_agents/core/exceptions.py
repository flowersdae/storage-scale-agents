"""Custom exceptions for Scale Agents."""

from __future__ import annotations

from typing import Any


class ScaleAgentError(Exception):
    """Base exception for all Scale Agent errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class MCPConnectionError(ScaleAgentError):
    """Raised when connection to MCP server fails."""

    def __init__(
        self,
        message: str = "Failed to connect to MCP server",
        url: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = {}
        if url:
            details["url"] = url
        if cause:
            details["cause"] = str(cause)
        super().__init__(message, details)
        self.url = url
        self.cause = cause


class MCPToolError(ScaleAgentError):
    """Raised when an MCP tool call fails."""

    def __init__(
        self,
        message: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        error_code: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = {"tool_name": tool_name}
        if arguments:
            details["arguments"] = arguments
        if error_code:
            details["error_code"] = error_code
        if cause:
            details["cause"] = str(cause)
        super().__init__(message, details)
        self.tool_name = tool_name
        self.arguments = arguments
        self.error_code = error_code
        self.cause = cause


class ConfirmationRequiredError(ScaleAgentError):
    """Raised when an operation requires user confirmation."""

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        risk_level: str = "MEDIUM",
        summary: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        self.risk_level = risk_level
        self.summary = summary or f"Operation '{tool_name}' requires confirmation"

        message = f"Confirmation required for {tool_name}"
        details = {
            "tool_name": tool_name,
            "arguments": arguments,
            "risk_level": risk_level,
            "summary": self.summary,
        }
        super().__init__(message, details)

    def format_confirmation_prompt(self) -> str:
        """Format a user-friendly confirmation prompt."""
        risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
            self.risk_level, "⚪"
        )

        lines = [
            f"**{risk_emoji} Confirmation Required**",
            "",
            f"**Operation:** `{self.tool_name}`",
            f"**Risk Level:** {self.risk_level}",
            "",
            "**Parameters:**",
        ]

        for key, value in self.arguments.items():
            if isinstance(value, dict):
                lines.append(f"  - {key}:")
                for k, v in value.items():
                    lines.append(f"    - {k}: `{v}`")
            else:
                lines.append(f"  - {key}: `{value}`")

        lines.extend([
            "",
            "Reply **'confirm'** to proceed or **'cancel'** to abort.",
        ])

        return "\n".join(lines)


class AgentRoutingError(ScaleAgentError):
    """Raised when agent routing fails."""

    def __init__(
        self,
        message: str = "Failed to route request to appropriate agent",
        intent: str | None = None,
        available_agents: list[str] | None = None,
    ) -> None:
        details = {}
        if intent:
            details["detected_intent"] = intent
        if available_agents:
            details["available_agents"] = available_agents
        super().__init__(message, details)
        self.intent = intent
        self.available_agents = available_agents


class ValidationError(ScaleAgentError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        constraint: str | None = None,
    ) -> None:
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        if constraint:
            details["constraint"] = constraint
        super().__init__(message, details)
        self.field = field
        self.value = value
        self.constraint = constraint


class ToolNotAllowedError(ScaleAgentError):
    """Raised when an agent attempts to use a tool outside its whitelist."""

    def __init__(
        self,
        tool_name: str,
        agent_name: str,
        allowed_tools: frozenset[str] | None = None,
    ) -> None:
        message = f"Agent '{agent_name}' is not authorized to use tool '{tool_name}'"
        details = {
            "tool_name": tool_name,
            "agent_name": agent_name,
        }
        if allowed_tools:
            details["allowed_tools"] = list(allowed_tools)
        super().__init__(message, details)
        self.tool_name = tool_name
        self.agent_name = agent_name
        self.allowed_tools = allowed_tools
