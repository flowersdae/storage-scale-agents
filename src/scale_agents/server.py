"""AgentStack Server entry point for Scale Agents.

This module initializes and runs the AgentStack server with all
registered Scale agents.

Configuration is loaded from:
1. config.yaml (if present in current directory)
2. Environment variables (override YAML)
3. Default values
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import NoReturn

from agentstack_sdk.server import Server

from scale_agents.agents import (
    register_admin_agent,
    register_health_agent,
    register_orchestrator,
    register_performance_agent,
    register_quota_agent,
    register_storage_agent,
)
from scale_agents.config.settings import get_settings, reload_settings
from scale_agents.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def create_server() -> Server:
    """Create and configure the AgentStack server.

    Returns:
        Configured Server instance with all agents registered.
    """
    settings = get_settings()
    use_llm = settings.llm.enabled

    server = Server(
        name="scale-agents",
        description=(
            "IBM Storage Scale AI Agents for cluster management, "
            "health monitoring, storage operations, and administration."
        ),
        version="1.0.0",
    )

    # Register orchestrator with optional LLM support
    register_orchestrator(server, use_llm=use_llm)

    # Register specialized agents based on config
    agents_config = settings.agents

    if agents_config.health.enabled:
        register_health_agent(server)

    if agents_config.storage.enabled:
        register_storage_agent(server)

    if agents_config.quota.enabled:
        register_quota_agent(server)

    if agents_config.performance.enabled:
        register_performance_agent(server)

    if agents_config.admin.enabled:
        register_admin_agent(server)

    registered_agents = [
        "scale_orchestrator",
    ]
    if agents_config.health.enabled:
        registered_agents.append("health_agent")
    if agents_config.storage.enabled:
        registered_agents.append("storage_agent")
    if agents_config.quota.enabled:
        registered_agents.append("quota_agent")
    if agents_config.performance.enabled:
        registered_agents.append("performance_agent")
    if agents_config.admin.enabled:
        registered_agents.append("admin_agent")

    logger.info(
        "agents_registered",
        agents=registered_agents,
        llm_enabled=use_llm,
    )

    return server


async def run_server() -> None:
    """Run the AgentStack server."""
    settings = get_settings()
    server = create_server()

    logger.info(
        "starting_server",
        host=settings.server.host,
        port=settings.server.port,
        mcp_server=settings.mcp.server_url,
        llm_enabled=settings.llm.enabled,
        llm_provider=settings.llm.provider,
        llm_model=settings.llm.model,
    )

    try:
        await server.serve(
            host=settings.server.host,
            port=settings.server.port,
        )
    except Exception as e:
        logger.error("server_error", error=str(e))
        raise


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

    # Log configuration summary
    logger.info(
        "scale_agents_starting",
        version="1.0.0",
        config={
            "mcp_server": settings.mcp.server_url,
            "host": settings.server.host,
            "port": settings.server.port,
            "llm_enabled": settings.llm.enabled,
            "llm_provider": settings.llm.provider,
            "llm_model": settings.llm.model,
            "require_confirmation": settings.security.require_confirmation,
            "log_level": settings.logging.level,
        },
    )

    # Check LLM availability if enabled
    if settings.llm.enabled:
        try:
            import beeai_framework  # noqa: F401
            logger.info(
                "llm_available",
                provider=settings.llm.provider,
                model=settings.llm.model,
            )
        except ImportError:
            logger.warning(
                "beeai_not_installed",
                message="Install with: uv pip install -e '.[llm]'",
            )

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("server_stopped_by_user")
    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run()
