"""
Tool execution helper (2025).

Problem:
- Tool calling is error-prone when using general chat models.
Solution:
- Provide a single helper that forces ModelRole.TOOL by default.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.routing import ModelRole, get_model_for_role
from src.integrations.llm.llm_client import get_llm_client


def tool_chat(
    agent_name: str,
    messages: List[Dict[str, str]],
    *,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
    model: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Call an OpenAI-compatible chat endpoint with tools using a tool-specialized model.
    """
    client = get_llm_client()
    tool_model = model or get_model_for_role(agent_name, ModelRole.TOOL)
    return client.chat(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model=tool_model,
        tools=tools,
        tool_choice=tool_choice,
        **kwargs,
    )
