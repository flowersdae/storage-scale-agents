"""AgentStack Server entry point for Scale Agents.

This module initializes and runs the AgentStack server with a single
orchestrator agent that routes to specialized Scale agents internally.

Uses AgentStack MCP Extension for dynamic MCP server configuration,
allowing users to specify the MCP server via the AgentStack UI/connectors.

AgentStack SDK constraint: Only ONE @server.agent() decorator per server.
"""

import os
import signal
import sys
from typing import TYPE_CHECKING, Annotated, NoReturn

from a2a.types import Message, TextPart
from a2a.utils.message import get_message_text
from agentstack_sdk.a2a.extensions import MCPServiceExtensionServer, MCPServiceExtensionSpec
from agentstack_sdk.a2a.types import AgentMessage
from agentstack_sdk.server import Server
from agentstack_sdk.server.context import RunContext
from mcp import ClientSession

from scale_agents.config.settings import get_settings, reload_settings
from scale_agents.core.logging import get_logger, setup_logging

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Create the server instance
server = Server()


def _classify_intent(text: str) -> str:
    """Classify user intent to route to appropriate handler.

    Args:
        text: User message text.

    Returns:
        Handler name to route to.
    """
    text_lower = text.lower()

    # Check for compound intents first (more specific patterns)
    # "filesystem health" should go to health, not storage
    if "filesystem" in text_lower and "health" in text_lower:
        return "filesystem_health"
    
    # Storage related keywords (check before health since "filesystem" is storage)
    storage_keywords = [
        "filesystem", "fileset", "mount", "unmount", "pool",
        "storage pool", "create fs", "delete fs", "link", "unlink",
        "nsd", "disk", "list fs",
    ]
    if any(kw in text_lower for kw in storage_keywords):
        return "storage"

    # Health related keywords
    health_keywords = [
        "health", "status", "node", "event", "diagnostic",
        "monitoring", "alert", "state", "version", "cluster",
    ]
    if any(kw in text_lower for kw in health_keywords):
        return "health"

    # Quota related keywords
    quota_keywords = [
        "quota", "usage", "capacity", "limit", "space",
        "disk usage", "fileset usage",
    ]
    if any(kw in text_lower for kw in quota_keywords):
        return "quota"

    # Performance related keywords
    performance_keywords = [
        "performance", "metric", "throughput", "latency",
        "iops", "bandwidth", "bottleneck", "slow",
    ]
    if any(kw in text_lower for kw in performance_keywords):
        return "performance"

    # Admin related keywords
    admin_keywords = [
        "snapshot", "backup", "config", "admin", "remote cluster",
        "policy", "add node", "remove node", "shutdown", "start node",
        "stop node",
    ]
    if any(kw in text_lower for kw in admin_keywords):
        return "admin"

    # Default to orchestrator for complex or unclear requests
    return "orchestrator"


def _extract_filesystem_name(text: str) -> str | None:
    """Extract filesystem name from user text.
    
    Looks for patterns like:
    - "for fs1"
    - "filesystem fs1"
    - "fs fs1"
    """
    import re
    
    # Pattern: "for <name>" or "filesystem <name>" or "fs <name>"
    patterns = [
        r'\bfor\s+(\w+)',
        r'\bfilesystem\s+(\w+)',
        r'\bfs\s+(\w+)',
        r'\bon\s+(\w+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            name = match.group(1)
            # Filter out common words that aren't filesystem names
            if name not in ["the", "a", "an", "all", "health", "status", "info"]:
                return name
    
    return None


async def _call_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict | None = None,
) -> dict:
    """Call an MCP tool via the session.
    
    Args:
        session: Active MCP ClientSession.
        tool_name: Name of the tool to call.
        arguments: Tool arguments.
        
    Returns:
        Tool result as dictionary.
    """
    result = await session.call_tool(tool_name, arguments or {})
    
    # Extract content from result
    if hasattr(result, "content") and result.content:
        content = result.content[0]
        if hasattr(content, "text"):
            import orjson
            try:
                return orjson.loads(content.text)
            except Exception:
                return {"text": content.text}
    return {"result": str(result)}


async def _handle_filesystem_health_request(
    session: ClientSession,
    user_text: str,
) -> str:
    """Handle filesystem health requests."""
    fs_name = _extract_filesystem_name(user_text)
    
    try:
        if fs_name:
            # Get health states for specific filesystem
            result = await _call_mcp_tool(
                session, 
                "get_filesystem_health_states", 
                {"filesystem": fs_name}
            )
            return f"**Filesystem Health: {fs_name}**\n\n```json\n{_format_result(result)}\n```"
        else:
            # List filesystems first, then get health for each
            fs_result = await _call_mcp_tool(session, "list_filesystems", {})
            return f"**Available Filesystems** (specify one for health check)\n\n```json\n{_format_result(fs_result)}\n```"
            
    except Exception as e:
        return f"**Error**: {e}"


async def _handle_health_request(
    session: ClientSession,
    user_text: str,
) -> str:
    """Handle health-related requests."""
    user_lower = user_text.lower()
    
    try:
        if "node" in user_lower:
            if "status" in user_lower:
                result = await _call_mcp_tool(session, "get_nodes_status", {})
                return f"**Node Status**\n\n```json\n{_format_result(result)}\n```"
            
            if "health" in user_lower or "state" in user_lower:
                result = await _call_mcp_tool(session, "get_node_health_states", {"name": ":all:"})
                return f"**Node Health States**\n\n```json\n{_format_result(result)}\n```"
            
            if "event" in user_lower:
                result = await _call_mcp_tool(session, "get_node_health_events", {"name": ":all:"})
                return f"**Node Health Events**\n\n```json\n{_format_result(result)}\n```"
            
            # Default node info
            result = await _call_mcp_tool(session, "get_nodes_status", {})
            return f"**Node Status**\n\n```json\n{_format_result(result)}\n```"
        
        if "cluster" in user_lower:
            result = await _call_mcp_tool(session, "list_clusters", {})
            return f"**Cluster Information**\n\n```json\n{_format_result(result)}\n```"
        
        if "event" in user_lower:
            result = await _call_mcp_tool(session, "get_node_health_events", {"name": ":all:"})
            return f"**Health Events**\n\n```json\n{_format_result(result)}\n```"
        
        # Default: node health states
        result = await _call_mcp_tool(session, "get_node_health_states", {"name": ":all:"})
        return f"**Health Overview**\n\n```json\n{_format_result(result)}\n```"
        
    except Exception as e:
        return f"**Error**: {e}"


async def _handle_storage_request(
    session: ClientSession,
    user_text: str,
) -> str:
    """Handle storage-related requests."""
    user_lower = user_text.lower()
    fs_name = _extract_filesystem_name(user_text)
    
    try:
        if "fileset" in user_lower:
            if fs_name:
                result = await _call_mcp_tool(session, "list_filesets", {"filesystem": fs_name})
                return f"**Filesets in {fs_name}**\n\n```json\n{_format_result(result)}\n```"
            else:
                # List filesystems first
                result = await _call_mcp_tool(session, "list_filesystems", {})
                return f"**Filesystems** (specify one to list filesets)\n\n```json\n{_format_result(result)}\n```"
        
        if "pool" in user_lower:
            if fs_name:
                result = await _call_mcp_tool(session, "list_storage_pools", {"filesystem": fs_name})
                return f"**Storage Pools in {fs_name}**\n\n```json\n{_format_result(result)}\n```"
            else:
                result = await _call_mcp_tool(session, "list_filesystems", {})
                return f"**Filesystems** (specify one to list pools)\n\n```json\n{_format_result(result)}\n```"
        
        if fs_name:
            # Get specific filesystem info
            result = await _call_mcp_tool(session, "get_filesystem", {"filesystem": fs_name})
            return f"**Filesystem: {fs_name}**\n\n```json\n{_format_result(result)}\n```"
        
        # Default: list filesystems
        result = await _call_mcp_tool(session, "list_filesystems", {})
        return f"**Filesystems**\n\n```json\n{_format_result(result)}\n```"
        
    except Exception as e:
        return f"**Error**: {e}"


async def _handle_quota_request(
    session: ClientSession,
    user_text: str,
) -> str:
    """Handle quota-related requests."""
    fs_name = _extract_filesystem_name(user_text)
    
    try:
        if fs_name:
            result = await _call_mcp_tool(session, "list_quotas", {"filesystem": fs_name})
            return f"**Quotas for {fs_name}**\n\n```json\n{_format_result(result)}\n```"
        
        # List filesystems first
        result = await _call_mcp_tool(session, "list_filesystems", {})
        return f"**Filesystems** (specify one for quota info)\n\n```json\n{_format_result(result)}\n```"
        
    except Exception as e:
        return f"**Error**: {e}"


async def _handle_performance_request(
    session: ClientSession,
    user_text: str,
) -> str:
    """Handle performance-related requests."""
    try:
        result = await _call_mcp_tool(session, "get_nodes_status", {})
        return f"**Node Status** (for performance analysis)\n\n```json\n{_format_result(result)}\n```"
    except Exception as e:
        return f"**Error**: {e}"


async def _handle_admin_request(
    session: ClientSession,
    user_text: str,
) -> str:
    """Handle admin-related requests."""
    user_lower = user_text.lower()
    fs_name = _extract_filesystem_name(user_text)
    
    try:
        if "snapshot" in user_lower:
            if fs_name:
                result = await _call_mcp_tool(session, "list_snapshots", {"filesystem": fs_name})
                return f"**Snapshots for {fs_name}**\n\n```json\n{_format_result(result)}\n```"
            result = await _call_mcp_tool(session, "list_filesystems", {})
            return f"**Filesystems** (specify one for snapshots)\n\n```json\n{_format_result(result)}\n```"
        
        if "remote" in user_lower and "cluster" in user_lower:
            result = await _call_mcp_tool(session, "list_remote_clusters", {})
            return f"**Remote Clusters**\n\n```json\n{_format_result(result)}\n```"
        
        if "config" in user_lower:
            result = await _call_mcp_tool(session, "get_admin_config", {})
            return f"**Admin Configuration**\n\n```json\n{_format_result(result)}\n```"
        
        # Default: cluster info
        result = await _call_mcp_tool(session, "list_clusters", {})
        return f"**Cluster Information**\n\n```json\n{_format_result(result)}\n```"
        
    except Exception as e:
        return f"**Error**: {e}"


def _format_result(result: dict) -> str:
    """Format result as JSON string."""
    import orjson
    return orjson.dumps(result, option=orjson.OPT_INDENT_2).decode()


@server.agent()
async def scale_agent(
    input: Message,
    context: RunContext,
    mcp: Annotated[
        MCPServiceExtensionServer,
        MCPServiceExtensionSpec.single_demand(),
    ],
):
    """IBM Storage Scale Agent for cluster management and monitoring.

    This is the single entry point for all Storage Scale operations.
    Routes requests to specialized handlers based on intent:
    
    - **Health**: Cluster health, node status, events, diagnostics
    - **Storage**: Filesystems, filesets, storage pools, NSDs
    - **Quota**: Quota management, capacity monitoring, usage reports
    - **Performance**: Metrics analysis, bottleneck detection, throughput
    - **Admin**: Snapshots, policies, node management, cluster admin
    
    Requires MCP server connection to scale-mcp-server.
    Configure via AgentStack UI or connectors.
    
    Examples:
        "Show cluster health" -> Health handler
        "List all filesystems" -> Storage handler
        "Check filesystem health for fs1" -> Filesystem health
        "What's the quota for fileset data01?" -> Quota handler
        "Create a snapshot of fs01" -> Admin handler
    """
    # Check MCP availability
    if not mcp:
        yield AgentMessage(parts=[TextPart(
            text="**Error**: No MCP server configured.\n\n"
                 "Please configure the scale-mcp-server connection via AgentStack UI."
        )])
        return
    
    # Get message text
    user_text = get_message_text(input) or ""
    
    if not user_text.strip():
        yield AgentMessage(parts=[TextPart(
            text="Hello! I'm the IBM Storage Scale Agent. I can help you with:\n\n"
                 "- **Cluster health** and node status\n"
                 "- **Filesystems** and filesets\n"
                 "- **Quotas** and capacity\n"
                 "- **Performance** metrics\n"
                 "- **Administration** tasks\n\n"
                 "What would you like to know?"
        )])
        return
    
    # Classify intent
    intent = _classify_intent(user_text)
    
    logger.info(
        "routing_request",
        intent=intent,
        message_preview=user_text[:100] if user_text else "",
    )
    
    try:
        # Create MCP session and handle request
        async with mcp.create_client() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Route to handler based on intent
                if intent == "filesystem_health":
                    result = await _handle_filesystem_health_request(session, user_text)
                elif intent == "health":
                    result = await _handle_health_request(session, user_text)
                elif intent == "storage":
                    result = await _handle_storage_request(session, user_text)
                elif intent == "quota":
                    result = await _handle_quota_request(session, user_text)
                elif intent == "performance":
                    result = await _handle_performance_request(session, user_text)
                elif intent == "admin":
                    result = await _handle_admin_request(session, user_text)
                else:
                    # Default: show cluster info
                    cluster_result = await _call_mcp_tool(session, "list_clusters", {})
                    result = f"**Cluster Overview**\n\n```json\n{_format_result(cluster_result)}\n```"
                
                yield AgentMessage(parts=[TextPart(text=result)])
                
    except Exception as e:
        logger.exception("agent_error", intent=intent, error=str(e))
        yield AgentMessage(parts=[TextPart(
            text=f"**Error**\n\n**Context:** {intent}\n\n**Details:** {e}"
        )])


def handle_shutdown(signum: int, frame: object) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger.info("shutdown_signal_received", signal=signum)
    sys.exit(0)


def run(config_path: str | None = None) -> None:
    """Main entry point for the server.

    Args:
        config_path: Optional path to configuration file.
    """
    # Load settings (will load config.yaml if present)
    if config_path:
        reload_settings(config_path)

    settings = get_settings()

    # Setup logging
    setup_logging()

    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Get host and port from environment (AgentStack standard) or settings
    host = os.getenv("HOST", settings.server.host)
    port = int(os.getenv("PORT", settings.server.port))

    # Log configuration summary
    logger.info(
        "scale_agents_starting",
        version="1.0.0",
        config={
            "host": host,
            "port": port,
            "log_level": settings.logging.level,
            "mcp_mode": "extension",
        },
    )

    # Run server
    try:
        server.run(host=host, port=port)
    except KeyboardInterrupt:
        logger.info("server_stopped_by_user")
    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run()
