"""
Model routing for Compound AI Systems.

Goal (2025): Use the smallest/cheapest model that is sufficient for each role.

Roles:
- router: classify/route requests (fast, cheap)
- planner: produce JSON plan only (high reasoning, but short output)
- synthesizer: summarize/merge retrieved context (long context, cheaper if possible)
- writer: generate final report/structured output (high quality)
- sentiment: sentiment-only (cheap/fast)
- tool: tool-calling oriented (reliable function calling)
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Optional

from src.core.config import get_config_manager


class ModelRole(str, Enum):
    ROUTER = "router"
    PLANNER = "planner"
    SYNTHESIZER = "synthesizer"
    WRITER = "writer"
    SENTIMENT = "sentiment"
    TOOL = "tool"


def _env_key(agent_name: str, role: ModelRole) -> str:
    # e.g., NEWS_TREND_AGENT__MODEL__PLANNER
    return f"{agent_name.upper()}__MODEL__{role.value.upper()}"


def get_model_for_role(agent_name: str, role: ModelRole) -> Optional[str]:
    """
    Return model name for a given agent+role.

    Priority:
    1) Per-agent env override: {AGENT}__MODEL__{ROLE}
    2) Generic env override: MODEL__{ROLE}
    3) ConfigManager agent config: agents.{agent}.model_roles.{role}
    4) Reasonable defaults
    """
    # 1) per-agent env
    v = os.getenv(_env_key(agent_name, role))
    if v:
        return v

    # 2) generic env
    v = os.getenv(f"MODEL__{role.value.upper()}")
    if v:
        return v

    # 3) config
    cfg = get_config_manager()
    agent_cfg = cfg.get_agent_config(agent_name)
    model_roles = None
    if agent_cfg is not None:
        # agent_cfg is Pydantic model; allow extra keys via model_dump for forward-compat
        d = agent_cfg.model_dump()
        model_roles = d.get("model_roles")
    if isinstance(model_roles, dict):
        mv = model_roles.get(role.value)
        if isinstance(mv, str) and mv.strip():
            return mv.strip()

    # 4) defaults tuned for cost-efficiency
    # NOTE: these are "best effort" defaults. Actual access is enforced by the provider key.
    defaults = {
        # Ref: https://platform.openai.com/docs/models
        ModelRole.ROUTER: os.getenv("OPENAI_MODEL_NAME", "gpt-5-mini"),
        # System-2 planner default: o-series reasoning model (fallback handled by LLMClient if unavailable)
        ModelRole.PLANNER: os.getenv("OPENAI_MODEL_NAME", "o3"),
        ModelRole.SYNTHESIZER: os.getenv("OPENAI_MODEL_NAME", "gpt-5-mini"),
        ModelRole.WRITER: os.getenv("OPENAI_MODEL_NAME", "gpt-5.2"),
        ModelRole.SENTIMENT: os.getenv("OPENAI_MODEL_NAME", "gpt-5-mini"),
        ModelRole.TOOL: os.getenv("OPENAI_MODEL_NAME", "gpt-5-mini"),
    }
    return defaults.get(role)
