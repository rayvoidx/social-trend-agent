"""
Unit tests for MCP Client Manager

Tests for MCP client manager that connects to external MCP servers
defined in mcp_config.json.
"""
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from src.integrations.mcp.servers.mcp_client import (
    MCPClient,
    MCPClientManager,
    get_mcp_manager,
    call_mcp_tool
)


class TestMCPClient:
    """Test MCP Client"""

    def test_client_initialization(self):
        """Test client initializes correctly"""
        client = MCPClient(
            name="test-server",
            command="npx",
            args=["-y", "test-mcp"],
            env={"API_KEY": "${TEST_API_KEY}"},
            description="Test MCP server"
        )

        assert client.name == "test-server"
        assert client.command == "npx"
        assert client.args == ["-y", "test-mcp"]
        assert client.env == {"API_KEY": "${TEST_API_KEY}"}
        assert client.description == "Test MCP server"
        assert client._process is None
        assert client._initialized is False

    def test_is_running_false_when_not_started(self):
        """Test is_running returns False when not started"""
        client = MCPClient(
            name="test",
            command="npx",
            args=[]
        )
        assert client.is_running is False

    @pytest.mark.asyncio
    async def test_start_creates_process(self):
        """Test start creates subprocess"""
        client = MCPClient(
            name="test",
            command="echo",
            args=["hello"]
        )

        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        # Mock readline to return valid JSON responses
        init_response = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "test", "version": "1.0"}
            }
        }).encode() + b"\n"
        mock_process.stdout.readline = AsyncMock(return_value=init_response)

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.start()

        assert client._process is not None
        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_stop_terminates_process(self):
        """Test stop terminates the process"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[]
        )

        mock_process = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        client._process = mock_process
        client._initialized = True

        await client.stop()

        mock_process.terminate.assert_called_once()
        assert client._process is None
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_env_variable_substitution(self):
        """Test environment variable substitution"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[],
            env={"API_KEY": "${MY_API_KEY}"}
        )

        with patch.dict('os.environ', {'MY_API_KEY': 'secret123'}):
            mock_process = AsyncMock()
            mock_process.returncode = None
            mock_process.stdin = AsyncMock()
            mock_process.stdout = AsyncMock()

            init_response = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "result": {}
            }).encode() + b"\n"
            mock_process.stdout.readline = AsyncMock(return_value=init_response)

            with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
                await client.start()

                # Check that env was passed with substitution
                call_kwargs = mock_exec.call_args
                passed_env = call_kwargs.kwargs.get('env', {})
                assert passed_env.get('API_KEY') == 'secret123'

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing tools from server"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[]
        )

        # Setup mock process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        # First call is for initialize, second for list_tools
        responses = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode() + b"\n",
            json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "tools": [
                        {
                            "name": "search",
                            "description": "Search for items",
                            "inputSchema": {"type": "object"}
                        }
                    ]
                }
            }).encode() + b"\n"
        ]
        mock_process.stdout.readline = AsyncMock(side_effect=responses)
        client._process = mock_process
        client._initialized = False

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            tools = await client.list_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "search"

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test calling a tool"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[]
        )

        # Setup initialized client
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        tool_response = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"data": [{"id": "1", "text": "Hello"}]})
                    }
                ]
            }
        }).encode() + b"\n"
        mock_process.stdout.readline = AsyncMock(return_value=tool_response)

        client._process = mock_process
        client._initialized = True

        result = await client.call_tool("search", {"query": "test"})

        assert "data" in result
        assert result["data"][0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self):
        """Test error handling when calling tool"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[]
        )

        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        error_response = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32000,
                "message": "Tool not found"
            }
        }).encode() + b"\n"
        mock_process.stdout.readline = AsyncMock(return_value=error_response)

        client._process = mock_process
        client._initialized = True

        result = await client.call_tool("unknown_tool", {})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout when waiting for response"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[]
        )

        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        # Simulate timeout
        async def slow_readline():
            await asyncio.sleep(100)

        mock_process.stdout.readline = slow_readline

        client._process = mock_process
        client._initialized = True

        # This should timeout
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
            result = await client._send_request("test", {})
            assert result is None


class TestMCPClientManager:
    """Test MCP Client Manager"""

    @pytest.fixture
    def sample_config(self, tmp_path):
        """Create a sample config file"""
        config = {
            "mcpServers": {
                "test-server": {
                    "command": "npx",
                    "args": ["-y", "test-mcp"],
                    "env": {"API_KEY": "${TEST_KEY}"},
                    "description": "Test server"
                },
                "another-server": {
                    "command": "python",
                    "args": ["server.py"],
                    "env": {},
                    "description": "Another server"
                }
            },
            "defaults": {
                "timeout": 30000
            }
        }

        config_path = tmp_path / "mcp_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)

        return config_path

    def test_manager_initialization(self, sample_config):
        """Test manager initializes correctly"""
        manager = MCPClientManager(sample_config)
        assert manager.config_path == sample_config
        assert manager._clients == {}
        assert not manager._loaded

    def test_load_config(self, sample_config):
        """Test loading configuration"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        assert manager._loaded
        assert len(manager._clients) == 2
        assert "test-server" in manager._clients
        assert "another-server" in manager._clients

    def test_load_config_missing_file(self, tmp_path):
        """Test handling missing config file"""
        missing_path = tmp_path / "missing.json"
        manager = MCPClientManager(missing_path)
        manager.load_config()

        assert len(manager._clients) == 0

    def test_get_client(self, sample_config):
        """Test getting a specific client"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        client = manager.get_client("test-server")
        assert client is not None
        assert client.name == "test-server"
        assert client.command == "npx"

    def test_get_client_not_found(self, sample_config):
        """Test getting non-existent client"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        client = manager.get_client("nonexistent")
        assert client is None

    def test_list_servers(self, sample_config):
        """Test listing all servers"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        servers = manager.list_servers()
        assert len(servers) == 2

        server_names = [s["name"] for s in servers]
        assert "test-server" in server_names
        assert "another-server" in server_names

    @pytest.mark.asyncio
    async def test_start_server(self, sample_config):
        """Test starting a specific server"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        client = manager.get_client("test-server")

        with patch.object(client, 'start', new_callable=AsyncMock) as mock_start:
            result = await manager.start_server("test-server")
            assert result is True
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_server_not_found(self, sample_config):
        """Test starting non-existent server"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        result = await manager.start_server("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_all(self, sample_config):
        """Test stopping all servers"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        # Mock all clients as running
        for client in manager._clients.values():
            client._process = AsyncMock()
            client._process.returncode = None

        with patch.object(MCPClient, 'stop', new_callable=AsyncMock) as mock_stop:
            await manager.stop_all()
            assert mock_stop.call_count == 2

    @pytest.mark.asyncio
    async def test_call_tool(self, sample_config):
        """Test calling tool through manager"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        client = manager.get_client("test-server")

        with patch.object(client, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"result": "success"}

            result = await manager.call_tool(
                "test-server",
                "search",
                {"query": "test"}
            )

            assert result == {"result": "success"}
            mock_call.assert_called_once_with("search", {"query": "test"})

    @pytest.mark.asyncio
    async def test_call_tool_server_not_found(self, sample_config):
        """Test calling tool on non-existent server"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        result = await manager.call_tool("nonexistent", "tool", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_session_context_manager(self, sample_config):
        """Test session context manager"""
        manager = MCPClientManager(sample_config)
        manager.load_config()

        with patch.object(MCPClient, 'start', new_callable=AsyncMock):
            with patch.object(MCPClient, 'stop', new_callable=AsyncMock) as mock_stop:
                async with manager.session("test-server") as clients:
                    assert "test-server" in clients
                    assert isinstance(clients["test-server"], MCPClient)

                # Verify stop was called after context exit
                mock_stop.assert_called()


class TestMCPConvenienceFunctions:
    """Test convenience functions"""

    def test_get_mcp_manager(self, tmp_path):
        """Test get_mcp_manager function"""
        config = {"mcpServers": {}}
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)

        manager = get_mcp_manager(config_path)
        assert isinstance(manager, MCPClientManager)
        assert manager._loaded

    @pytest.mark.asyncio
    async def test_call_mcp_tool(self, tmp_path):
        """Test call_mcp_tool convenience function"""
        config = {
            "mcpServers": {
                "test": {
                    "command": "echo",
                    "args": [],
                    "env": {},
                    "description": "Test"
                }
            }
        }
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)

        with patch.object(MCPClient, 'start', new_callable=AsyncMock):
            with patch.object(MCPClient, 'stop', new_callable=AsyncMock):
                with patch.object(MCPClient, 'call_tool', new_callable=AsyncMock) as mock_call:
                    mock_call.return_value = {"data": "result"}

                    result = await call_mcp_tool(
                        "test",
                        "my_tool",
                        {"arg": "value"},
                        config_path
                    )

                    assert result == {"data": "result"}


class TestMCPConfigIntegration:
    """Test integration with actual mcp_config.json"""

    def test_load_actual_config(self):
        """Test loading the actual project config"""
        from src.integrations.mcp.servers.mcp_client import DEFAULT_CONFIG_PATH

        if DEFAULT_CONFIG_PATH.exists():
            manager = MCPClientManager(DEFAULT_CONFIG_PATH)
            manager.load_config()

            servers = manager.list_servers()
            assert len(servers) > 0

            # Check expected servers are present
            server_names = [s["name"] for s in servers]
            # These should be in mcp_config.json
            expected = ["x-mcp", "youtube-mcp", "tiktok-mcp"]
            for name in expected:
                if name in server_names:
                    client = manager.get_client(name)
                    assert client is not None
                    assert client.command == "npx"


class TestJSONRPCProtocol:
    """Test JSON-RPC 2.0 protocol compliance"""

    @pytest.mark.asyncio
    async def test_request_format(self):
        """Test request message format"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[]
        )

        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline = AsyncMock(
            return_value=json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode() + b"\n"
        )

        client._process = mock_process

        await client._send_request("test/method", {"key": "value"})

        # Verify the request format
        written_data = mock_process.stdin.write.call_args[0][0]
        request = json.loads(written_data.decode().strip())

        assert request["jsonrpc"] == "2.0"
        assert "id" in request
        assert request["method"] == "test/method"
        assert request["params"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_notification_format(self):
        """Test notification message format (no id)"""
        client = MCPClient(
            name="test",
            command="echo",
            args=[]
        )

        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()

        client._process = mock_process

        await client._send_notification("notifications/test", {"data": "value"})

        # Verify the notification format
        written_data = mock_process.stdin.write.call_args[0][0]
        notification = json.loads(written_data.decode().strip())

        assert notification["jsonrpc"] == "2.0"
        assert "id" not in notification  # Notifications have no id
        assert notification["method"] == "notifications/test"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
