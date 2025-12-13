"""
MCP (Model Context Protocol) Manager

OpenAI API와 MCP Server를 통합하여 도구 호출을 관리합니다.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MCPManager:
    """
    MCP 도구 관리자

    OpenAI Function Calling과 MCP Server를 통합하여
    에이전트가 외부 도구를 사용할 수 있도록 합니다.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: MCP 설정 파일 경로 (기본: automation/mcp/mcp_config.json)
        """
        self.config_path = config_path or str(
            Path(__file__).parent.parent.parent / "automation" / "mcp" / "mcp_config.json"
        )
        self.tools = []
        self.mcp_servers = {}
        self._load_config()

    def _load_config(self):
        """MCP 설정 파일 로드"""
        import json

        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"MCP config not found: {self.config_path}")
                logger.info("Using built-in tools only")
                return

            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            self.mcp_servers = config.get("mcpServers", {})
            logger.info(f"Loaded {len(self.mcp_servers)} MCP servers")

            # MCP 서버별 도구 등록
            for server_name, server_config in self.mcp_servers.items():
                logger.info(f"Registering MCP server: {server_name}")
                self._register_server_tools(server_name, server_config)

        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            logger.info("Continuing with built-in tools only")

    def _register_server_tools(self, server_name: str, server_config: Dict[str, Any]):
        """
        MCP 서버의 도구를 등록

        Args:
            server_name: 서버 이름 (예: "brave-search", "filesystem")
            server_config: 서버 설정 (command, args, env)
        """
        # Brave Search MCP
        if server_name == "brave-search":
            brave_api_key = os.getenv("BRAVE_API_KEY")
            if brave_api_key:
                self.tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": "brave_web_search",
                            "description": "Search the web using Brave Search API. Returns recent and relevant web results.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "The search query"},
                                    "count": {
                                        "type": "integer",
                                        "description": "Number of results to return (default: 10)",
                                        "default": 10,
                                    },
                                },
                                "required": ["query"],
                            },
                        },
                    }
                )
                logger.info(f"✅ Registered Brave Search tool")
            else:
                logger.warning(f"⚠️  BRAVE_API_KEY not set, skipping {server_name}")

        # Filesystem MCP
        elif server_name == "filesystem":
            self.tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "Read contents of a file from the filesystem",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Path to the file to read",
                                }
                            },
                            "required": ["path"],
                        },
                    },
                }
            )
            self.tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "description": "Write contents to a file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Path to the file to write",
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Content to write to the file",
                                },
                            },
                            "required": ["path", "content"],
                        },
                    },
                }
            )
            logger.info(f"✅ Registered Filesystem tools")

        # PostgreSQL MCP
        elif server_name == "postgres":
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                self.tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": "execute_sql_query",
                            "description": "Execute a SQL query on the PostgreSQL database",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "SQL query to execute",
                                    }
                                },
                                "required": ["query"],
                            },
                        },
                    }
                )
                logger.info(f"✅ Registered PostgreSQL tool")
            else:
                logger.warning(f"⚠️  DATABASE_URL not set, skipping {server_name}")

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        OpenAI Function Calling 형식의 도구 목록 반환

        Returns:
            OpenAI tools 형식의 리스트
        """
        return self.tools

    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        MCP 도구 호출

        Args:
            tool_name: 호출할 도구 이름
            **kwargs: 도구에 전달할 인자

        Returns:
            도구 실행 결과
        """
        logger.info(f"Calling MCP tool: {tool_name} with args: {kwargs}")

        try:
            # Brave Search
            if tool_name == "brave_web_search":
                return await self._brave_search(**kwargs)

            # Filesystem
            elif tool_name == "read_file":
                return self._read_file(**kwargs)
            elif tool_name == "write_file":
                return self._write_file(**kwargs)

            # PostgreSQL
            elif tool_name == "execute_sql_query":
                return await self._execute_sql(**kwargs)

            else:
                logger.error(f"Unknown tool: {tool_name}")
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
            return {"error": str(e)}

    async def _brave_search(self, query: str, count: int = 10) -> Dict[str, Any]:
        """Brave Search 실행"""
        import aiohttp

        brave_api_key = os.getenv("BRAVE_API_KEY")
        if not brave_api_key:
            return {"error": "BRAVE_API_KEY not configured"}

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": brave_api_key}
        params = {"q": query, "count": count}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    for item in data.get("web", {}).get("results", [])[:count]:
                        results.append(
                            {
                                "title": item.get("title"),
                                "url": item.get("url"),
                                "description": item.get("description"),
                            }
                        )
                    return {"results": results, "count": len(results)}
                else:
                    return {"error": f"Brave API error: {response.status}"}

    def _read_file(self, path: str) -> Dict[str, Any]:
        """파일 읽기"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"content": content, "path": path}
        except Exception as e:
            return {"error": str(e)}

    def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        """파일 쓰기"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"error": str(e)}

    async def _execute_sql(self, query: str) -> Dict[str, Any]:
        """SQL 쿼리 실행"""
        try:
            import asyncpg

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                return {"error": "DATABASE_URL not configured"}

            conn = await asyncpg.connect(database_url)
            try:
                # SELECT 쿼리
                if query.strip().upper().startswith("SELECT"):
                    rows = await conn.fetch(query)
                    return {"rows": [dict(row) for row in rows], "count": len(rows)}
                # INSERT/UPDATE/DELETE
                else:
                    result = await conn.execute(query)
                    return {"result": result}
            finally:
                await conn.close()

        except Exception as e:
            return {"error": str(e)}


# 싱글톤 인스턴스
_mcp_manager = None


def get_mcp_manager() -> MCPManager:
    """MCP Manager 싱글톤 인스턴스 반환"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
