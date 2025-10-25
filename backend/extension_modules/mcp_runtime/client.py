"""
MCP (Model Context Protocol) Runtime Client

Follows official MCP patterns for stdio-based server communication.

References:
- MCP Specification: https://spec.modelcontextprotocol.io/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
"""
from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)


def load_mcp_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load MCP configuration from JSON file

    Args:
        config_path: Path to MCP configuration file. If None, uses MCP_CONFIG_PATH env var.

    Returns:
        MCP configuration dictionary
    """
    if config_path is None:
        config_path = os.getenv("MCP_CONFIG_PATH", "automation/mcp/mcp_config.json")

    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"MCP config file not found: {config_path}")
        return {"mcpServers": {}}

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        logger.info(f"Loaded MCP config from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load MCP config: {e}")
        return {"mcpServers": {}}


@asynccontextmanager
async def open_mcp_session(
    *,
    command: str,
    args: List[str],
    env: Optional[Dict[str, str]] = None,
    timeout: int = 30
) -> AsyncIterator[tuple[Any, Any]]:
    """
    Open an MCP stdio client session

    Follows official MCP pattern for stdio-based server communication.

    Args:
        command: Command to start MCP server (e.g., "npx", "python")
        args: Arguments for the command
        env: Environment variables (defaults to current environment)
        timeout: Timeout in seconds for initialization

    Yields:
        tuple: (session, None) where session is mcp.ClientSession

    Example:
        ```python
        async with open_mcp_session(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        ) as (session, _):
            tools = await load_tools(session)
        ```

    Reference:
        https://spec.modelcontextprotocol.io/specification/basic/lifecycle/
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # Use current environment if not specified (official pattern)
    server_env = env or os.environ.copy()

    # Create server parameters (official pattern)
    params = StdioServerParameters(
        command=command,
        args=args,
        env=server_env
    )

    logger.info(f"Starting MCP server: {command} {' '.join(args)}")

    try:
        # Open stdio client (official pattern)
        async with stdio_client(params) as (read, write):
            # Create client session (official pattern)
            async with ClientSession(read, write) as session:
                # Initialize session (official pattern - required)
                await session.initialize()
                logger.info("MCP session initialized successfully")

                yield session, None
    except Exception as e:
        logger.error(f"MCP session error: {e}")
        raise


async def load_tools(session: Any) -> List[Any]:
    """
    Load tools from MCP session into LangChain format

    Uses official langchain-mcp adapter for tool conversion.

    Args:
        session: MCP ClientSession

    Returns:
        List of LangChain tool objects

    Reference:
        https://github.com/rectalogic/langchain-mcp
    """
    try:
        from langchain_mcp_adapters.tools import load_mcp_tools

        tools = await load_mcp_tools(session)
        logger.info(f"Loaded {len(tools)} tools from MCP session")
        return tools
    except ImportError:
        logger.error("langchain-mcp-adapters not installed. Install with: pip install langchain-mcp-adapters")
        return []
    except Exception as e:
        logger.error(f"Failed to load MCP tools: {e}")
        return []


async def list_available_tools(session: Any) -> List[Dict[str, Any]]:
    """
    List available tools from MCP server

    Args:
        session: MCP ClientSession

    Returns:
        List of tool definitions
    """
    try:
        # Call list_tools RPC (official MCP pattern)
        result = await session.list_tools()
        tools = result.tools if hasattr(result, 'tools') else []

        logger.info(f"Available MCP tools: {len(tools)}")
        for tool in tools:
            logger.debug(f"  - {tool.name}: {tool.description}")

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            for tool in tools
        ]
    except Exception as e:
        logger.error(f"Failed to list MCP tools: {e}")
        return []


async def create_mcp_session_from_config(server_name: str, config_path: Optional[str] = None):
    """
    Create MCP session from configuration file

    Args:
        server_name: Name of the MCP server in config (e.g., "filesystem", "fetch")
        config_path: Path to MCP configuration file

    Returns:
        Context manager for MCP session

    Example:
        ```python
        async with create_mcp_session_from_config("filesystem") as (session, _):
            tools = await load_tools(session)
        ```
    """
    config = load_mcp_config(config_path)
    servers = config.get("mcpServers", {})

    if server_name not in servers:
        raise ValueError(f"MCP server '{server_name}' not found in config. Available: {list(servers.keys())}")

    server_config = servers[server_name]
    return open_mcp_session(
        command=server_config["command"],
        args=server_config["args"],
        env=server_config.get("env", {})
    )


