from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List


@asynccontextmanager
async def open_mcp_session(
    *, command: str, args: List[str], env: Dict[str, str] | None = None
) -> AsyncIterator[tuple[Any, Any]]:
    """
    Open an MCP stdio client session.
    Yields (session, close_ctx) where session is mcp.ClientSession.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=command, args=args, env=(env or os.environ.copy()))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session, None


async def load_tools(session: Any) -> List[Any]:
    from langchain_mcp_adapters.tools import load_mcp_tools

    return await load_mcp_tools(session)


