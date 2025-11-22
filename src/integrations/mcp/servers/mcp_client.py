"""
MCP Client Manager

Manages connections to external MCP servers defined in mcp_config.json.
Uses the Model Context Protocol to communicate with servers via stdio.
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "mcp_config.json"


class MCPClient:
    """
    Client for communicating with a single MCP server.

    Handles JSON-RPC 2.0 communication over stdio.
    """

    def __init__(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        description: str = ""
    ):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.description = description
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._initialized = False

    @property
    def is_running(self) -> bool:
        """Check if the server process is running."""
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        """Start the MCP server process."""
        if self.is_running:
            return

        # Prepare environment with substitutions
        process_env = os.environ.copy()
        for key, value in self.env.items():
            # Handle ${VAR} substitution
            if value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                process_env[key] = os.getenv(env_var, "")
            else:
                process_env[key] = value

        try:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env
            )
            logger.info(f"Started MCP server: {self.name}")

            # Initialize the server
            await self._initialize()

        except Exception as e:
            logger.error(f"Failed to start MCP server {self.name}: {e}")
            raise

    async def stop(self) -> None:
        """Stop the MCP server process."""
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
            finally:
                self._process = None
                self._initialized = False
                logger.info(f"Stopped MCP server: {self.name}")

    async def _initialize(self) -> None:
        """Send initialize request to the server."""
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "social-trend-agent",
                "version": "1.0.0"
            }
        })

        if response:
            # Send initialized notification
            await self._send_notification("notifications/initialized", {})
            self._initialized = True
            logger.info(f"Initialized MCP server: {self.name}")

    async def _send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and wait for response."""
        if not self.is_running:
            raise RuntimeError(f"MCP server {self.name} is not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        # Send request
        request_bytes = (json.dumps(request) + "\n").encode()
        self._process.stdin.write(request_bytes)
        await self._process.stdin.drain()

        # Read response
        try:
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=30.0
            )
            if response_line:
                response = json.loads(response_line.decode())
                if "error" in response:
                    logger.error(f"MCP error from {self.name}: {response['error']}")
                    return None
                return response.get("result")
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for response from {self.name}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {self.name}: {e}")
            return None

        return None

    async def _send_notification(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self.is_running:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            notification["params"] = params

        notification_bytes = (json.dumps(notification) + "\n").encode()
        self._process.stdin.write(notification_bytes)
        await self._process.stdin.drain()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        if not self._initialized:
            await self.start()

        response = await self._send_request("tools/list", {})
        if response and "tools" in response:
            return response["tools"]
        return []

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call a tool on the server."""
        if not self._initialized:
            await self.start()

        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments or {}
        })

        if response:
            # Extract content from response
            content = response.get("content", [])
            if content and len(content) > 0:
                # Return the text content
                result = {}
                for item in content:
                    if item.get("type") == "text":
                        try:
                            # Try to parse as JSON
                            result = json.loads(item.get("text", "{}"))
                        except json.JSONDecodeError:
                            result = {"text": item.get("text", "")}
                return result

        return {"error": f"Failed to call tool {name} on {self.name}"}

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources from the server."""
        if not self._initialized:
            await self.start()

        response = await self._send_request("resources/list", {})
        if response and "resources" in response:
            return response["resources"]
        return []

    async def read_resource(self, uri: str) -> Optional[str]:
        """Read a resource from the server."""
        if not self._initialized:
            await self.start()

        response = await self._send_request("resources/read", {"uri": uri})
        if response and "contents" in response:
            contents = response["contents"]
            if contents and len(contents) > 0:
                return contents[0].get("text")
        return None


class MCPClientManager:
    """
    Manager for multiple MCP server connections.

    Loads configuration from mcp_config.json and manages
    lifecycle of MCP server connections.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._clients: Dict[str, MCPClient] = {}
        self._config: Dict[str, Any] = {}
        self._loaded = False

    def load_config(self) -> None:
        """Load MCP configuration from file."""
        if not self.config_path.exists():
            logger.warning(f"MCP config not found: {self.config_path}")
            return

        try:
            with open(self.config_path) as f:
                self._config = json.load(f)

            # Create clients for each server
            servers = self._config.get("mcpServers", {})
            for name, config in servers.items():
                self._clients[name] = MCPClient(
                    name=name,
                    command=config.get("command", ""),
                    args=config.get("args", []),
                    env=config.get("env", {}),
                    description=config.get("description", "")
                )

            self._loaded = True
            logger.info(f"Loaded {len(self._clients)} MCP servers from config")

        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            raise

    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get a specific MCP client by name."""
        if not self._loaded:
            self.load_config()
        return self._clients.get(name)

    def list_servers(self) -> List[Dict[str, str]]:
        """List all configured MCP servers."""
        if not self._loaded:
            self.load_config()

        return [
            {
                "name": name,
                "description": client.description,
                "command": client.command
            }
            for name, client in self._clients.items()
        ]

    async def start_server(self, name: str) -> bool:
        """Start a specific MCP server."""
        client = self.get_client(name)
        if not client:
            logger.error(f"MCP server not found: {name}")
            return False

        try:
            await client.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")
            return False

    async def stop_server(self, name: str) -> None:
        """Stop a specific MCP server."""
        client = self.get_client(name)
        if client:
            await client.stop()

    async def stop_all(self) -> None:
        """Stop all running MCP servers."""
        for name, client in self._clients.items():
            if client.is_running:
                await client.stop()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call a tool on a specific server."""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"MCP server not found: {server_name}"}

        return await client.call_tool(tool_name, arguments)

    async def list_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """List tools from all configured servers."""
        all_tools = {}

        for name, client in self._clients.items():
            try:
                tools = await client.list_tools()
                all_tools[name] = tools
            except Exception as e:
                logger.error(f"Failed to list tools from {name}: {e}")
                all_tools[name] = []

        return all_tools

    @asynccontextmanager
    async def session(self, *server_names: str):
        """
        Context manager for using specific MCP servers.

        Usage:
            async with manager.session("x-mcp", "youtube-mcp") as clients:
                result = await clients["x-mcp"].call_tool("search_tweets", {...})
        """
        if not server_names:
            server_names = tuple(self._clients.keys())

        started_clients = {}
        try:
            for name in server_names:
                client = self.get_client(name)
                if client:
                    await client.start()
                    started_clients[name] = client

            yield started_clients

        finally:
            for client in started_clients.values():
                await client.stop()


# Convenience functions
def get_mcp_manager(config_path: Optional[Path] = None) -> MCPClientManager:
    """Get MCP client manager instance."""
    manager = MCPClientManager(config_path)
    manager.load_config()
    return manager


async def call_mcp_tool(
    server_name: str,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    config_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Convenience function to call an MCP tool.

    Example:
        result = await call_mcp_tool(
            "x-mcp",
            "search_tweets",
            {"query": "AI trends", "max_results": 10}
        )
    """
    manager = get_mcp_manager(config_path)
    client = manager.get_client(server_name)

    if not client:
        return {"error": f"MCP server not found: {server_name}"}

    try:
        await client.start()
        result = await client.call_tool(tool_name, arguments)
        return result
    finally:
        await client.stop()
