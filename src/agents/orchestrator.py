"""
Orchestrator (Manager) for Compound AI Systems (2025).

Purpose:
- Select the most appropriate agent (worker) for a given query with a cheap router.
- Optional: For complex tasks, call a System-2 planner model to produce a JSON plan.
- Keep the API backwards-compatible: existing callers can still specify agent_name explicitly.

This is intentionally lightweight: it's a "manager" that routes, not a new heavy agent.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from src.core.gateway import route_request
from src.core.routing import ModelRole, get_model_for_role
from src.integrations.llm.llm_client import get_llm_client


SUPPORTED_AGENTS = ("news_trend_agent", "social_trend_agent", "viral_video_agent")


def select_agent(
    query: str,
    hint: Optional[str] = None,
    time_window: Optional[str] = None,
    language: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Pick an agent for the query.

    Returns:
      (agent_name, routing_dict)
    """
    # Respect explicit hint if valid.
    if hint in SUPPORTED_AGENTS:
        return hint, {"notes": "explicit_hint", "hint": hint}

    # Use the cheap router to infer intent and complexity.
    r = route_request("orchestrator", query=query, time_window=time_window, language=language)

    # Simple heuristic mapping based on query content (robust even if router is heuristic).
    q = (query or "").lower()
    if any(k in q for k in ["유튜브", "youtube", "tiktok", "틱톡", "viral", "바이럴", "조회수", "shorts", "릴스"]):
        return "viral_video_agent", r
    if any(k in q for k in ["트위터", "twitter", "x ", "인스타", "instagram", "블로그", "sns", "소셜", "커뮤니티"]):
        return "social_trend_agent", r

    # Default to news_trend_agent for general market/news queries.
    return "news_trend_agent", r


def _planner_enabled() -> bool:
    return os.getenv("ORCHESTRATOR_ENABLE_PLANNER", "1").strip().lower() in ("1", "true", "yes", "on")


def _multi_agent_enabled() -> bool:
    return os.getenv("ORCHESTRATOR_MULTI_AGENT", "1").strip().lower() in ("1", "true", "yes", "on")


def plan_workflow(
    query: str,
    routing: Dict[str, Any],
    *,
    hint: Optional[str] = None,
    time_window: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    System-2 planning step (JSON only).

    Returns a plan dict:
      {
        "primary_agent": "news_trend_agent",
        "agents": [{"agent_name": "...", "params": {...}}],
        "combine": "single"|"merge",
        "notes": "...",
      }
    """
    # Always safe fallback plan (single-agent)
    primary, _ = select_agent(query=query, hint=hint, time_window=time_window, language=language)
    # Structured DAG fallback (single agent)
    fallback_steps = [
        {
            "id": "s1",
            "op": "collect",
            "inputs": [],
            "outputs": ["raw_items"],
            "depends_on": [],
            "retry_policy": {"max_retries": 2, "backoff_seconds": 1.0, "jitter": True},
            "timeout_seconds": 30,
            "circuit_breaker": {"failure_threshold": 2, "reset_seconds": 60},
            "params": {},
        },
        {
            "id": "s2",
            "op": "normalize",
            "inputs": ["raw_items"],
            "outputs": ["normalized"],
            "depends_on": ["s1"],
            "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
            "timeout_seconds": 10,
            "circuit_breaker": {"failure_threshold": 0, "reset_seconds": 0},
            "params": {},
        },
        {
            "id": "s3",
            "op": "analyze",
            "inputs": ["normalized"],
            "outputs": ["analysis"],
            "depends_on": ["s2"],
            "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
            "timeout_seconds": 30,
            "circuit_breaker": {"failure_threshold": 1, "reset_seconds": 120},
            "params": {},
        },
        {
            "id": "s4",
            "op": "rag",
            "inputs": ["normalized"],
            "outputs": ["normalized_filtered"],
            "depends_on": ["s2"],
            "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
            "timeout_seconds": 30,
            "circuit_breaker": {"failure_threshold": 1, "reset_seconds": 120},
            "params": {"rag_mode": "graph", "rag_top_k": 10},
        },
        {
            "id": "s5",
            "op": "summarize",
            "inputs": ["analysis", "normalized_filtered"],
            "outputs": ["summary"],
            "depends_on": ["s3", "s4"],
            "retry_policy": {"max_retries": 1, "backoff_seconds": 1.0, "jitter": True},
            "timeout_seconds": 60,
            "circuit_breaker": {"failure_threshold": 1, "reset_seconds": 180},
            "params": {"summary_strategy": "compound"},
        },
        {
            "id": "s6",
            "op": "report",
            "inputs": ["summary"],
            "outputs": ["report_md"],
            "depends_on": ["s5"],
            "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
            "timeout_seconds": 15,
            "circuit_breaker": {"failure_threshold": 0, "reset_seconds": 0},
            "params": {},
        },
    ]

    fallback_plan: Dict[str, Any] = {
        "primary_agent": primary,
        "agents": [{"agent_name": primary, "params": {"rag_mode": "graph", "rag_top_k": 10, "summary_strategy": "compound"}, "steps": fallback_steps}],
        "combine": "single",
        "notes": "planner_fallback",
    }

    if not _planner_enabled():
        fallback_plan["notes"] = "planner_disabled"
        return fallback_plan

    try:
        client = get_llm_client()
        planner_model = get_model_for_role("orchestrator", ModelRole.PLANNER)
        schema = {
            "type": "object",
            "properties": {
                "primary_agent": {"type": "string", "enum": list(SUPPORTED_AGENTS)},
                "agents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_name": {"type": "string", "enum": list(SUPPORTED_AGENTS)},
                            "params": {"type": "object"},
                            "steps": {
                                "type": "array",
                                "minItems": 2,
                                "maxItems": 14,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "op": {"type": "string"},
                                        "inputs": {"type": "array", "items": {"type": "string"}},
                                        "outputs": {"type": "array", "items": {"type": "string"}},
                                        "depends_on": {"type": "array", "items": {"type": "string"}},
                                        "retry_policy": {
                                            "type": "object",
                                            "properties": {
                                                "max_retries": {"type": "integer", "minimum": 0, "maximum": 5},
                                                "backoff_seconds": {"type": "number", "minimum": 0, "maximum": 30},
                                                "jitter": {"type": "boolean"},
                                            },
                                            "required": ["max_retries", "backoff_seconds", "jitter"],
                                        },
                                        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 600},
                                        "circuit_breaker": {
                                            "type": "object",
                                            "properties": {
                                                "failure_threshold": {"type": "integer", "minimum": 0, "maximum": 10},
                                                "reset_seconds": {"type": "integer", "minimum": 0, "maximum": 3600},
                                            },
                                            "required": ["failure_threshold", "reset_seconds"],
                                        },
                                        "params": {"type": "object"},
                                    },
                                    "required": ["id", "op", "inputs", "outputs", "depends_on", "retry_policy", "timeout_seconds", "circuit_breaker", "params"],
                                },
                            },
                            # legacy support: allow old tool_plan too
                            "tool_plan": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["agent_name", "params"],
                    },
                    "minItems": 1,
                    "maxItems": 3,
                },
                "combine": {"type": "string", "enum": ["single", "merge"]},
                "notes": {"type": "string"},
            },
            "required": ["primary_agent", "agents", "combine", "notes"],
        }

        prompt = (
            "You are a System-2 planner (manager) for a multi-agent trend analysis system.\n"
            "Create the cheapest plan that meets the user intent.\n"
            "Rules:\n"
            "- Prefer a SINGLE agent unless multi-agent adds clear value.\n"
            "- If multi-agent, use at most 2-3 agents.\n"
            "- Return a structured DAG under agents[].steps.\n"
            "- Each step must include: id, op, inputs, outputs, depends_on, retry_policy, timeout_seconds, circuit_breaker, params.\n"
            "- circuit_breaker: failure_threshold N (0 disables), reset_seconds.\n"
            "- Use ops from this set as much as possible:\n"
            "  - common: collect, normalize, analyze, rag, summarize, report, notify\n"
            "  - viral: detect_spike, cluster (instead of analyze if you want)\n"
            "- Put rag settings inside the rag step params: rag_mode (graph|vector|none), rag_top_k.\n"
            "- Put summary strategy inside summarize step params: summary_strategy (cheap|compound).\n"
            "- In params, include only json-serializable knobs that affect execution, e.g.:\n"
            "  - summary_strategy: 'cheap'|'compound'\n"
            "  - rag_mode: 'graph'|'vector'|'none'\n"
            "  - rag_top_k: integer\n"
            "- 'params' must only include simple scalars/lists (json-serializable).\n"
            "- If query is simple, set combine='single'.\n\n"
            f"Query: {query}\n"
            f"Hint: {hint or ''}\n"
            f"time_window: {time_window or ''}\n"
            f"language: {language or ''}\n"
            f"Router output: {routing}\n"
        )

        planned = client.chat_json(
            messages=[
                {"role": "system", "content": "Return JSON only. Be conservative on cost."},
                {"role": "user", "content": prompt},
            ],
            schema=schema,
            temperature=0.1,
            model=planner_model,
            max_tokens=500,
        )

        if not isinstance(planned, dict):
            return fallback_plan

        # If multi-agent is disabled, force single.
        if not _multi_agent_enabled():
            pa = str(planned.get("primary_agent") or primary)
            return {
                "primary_agent": pa if pa in SUPPORTED_AGENTS else primary,
                "agents": [{"agent_name": pa if pa in SUPPORTED_AGENTS else primary, "params": {}, "steps": fallback_steps}],
                "combine": "single",
                "notes": "multi_disabled",
            }

        return planned
    except Exception:
        return fallback_plan


def orchestrate_request(
    query: str,
    *,
    agent_hint: Optional[str] = None,
    time_window: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    3-gear orchestration:
    1) cheap route_request
    2) optional planner plan (complexity=high)
    3) worker agent list + params
    """
    routing = route_request("orchestrator", query=query, time_window=time_window, language=language)
    complexity = str(routing.get("complexity") or "medium").lower()

    if complexity == "high":
        plan = plan_workflow(
            query=query,
            routing=routing,
            hint=agent_hint,
            time_window=time_window,
            language=language,
        )
    else:
        primary, _ = select_agent(query=query, hint=agent_hint, time_window=time_window, language=language)
        plan = {
            "primary_agent": primary,
            "agents": [{
                "agent_name": primary,
                "params": {"rag_mode": "graph", "rag_top_k": 10, "summary_strategy": "cheap"},
                "steps": [
                    {
                        "id": "s1",
                        "op": "collect",
                        "inputs": [],
                        "outputs": ["raw_items"],
                        "depends_on": [],
                        "retry_policy": {"max_retries": 1, "backoff_seconds": 0.5, "jitter": True},
                        "params": {},
                    },
                    {
                        "id": "s2",
                        "op": "normalize",
                        "inputs": ["raw_items"],
                        "outputs": ["normalized"],
                        "depends_on": ["s1"],
                        "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
                        "params": {},
                    },
                    {
                        "id": "s3",
                        "op": "rag",
                        "inputs": ["normalized"],
                        "outputs": ["normalized_filtered"],
                        "depends_on": ["s2"],
                        "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
                        "params": {"rag_mode": "graph", "rag_top_k": 10},
                    },
                    {
                        "id": "s4",
                        "op": "summarize",
                        "inputs": ["analysis", "normalized_filtered"],
                        "outputs": ["summary"],
                        "depends_on": ["s3"],
                        "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
                        "params": {"summary_strategy": "cheap"},
                    },
                    {
                        "id": "s5",
                        "op": "report",
                        "inputs": ["summary"],
                        "outputs": ["report_md"],
                        "depends_on": ["s4"],
                        "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
                        "params": {},
                    },
                ],
            }],
            "combine": "single",
            "notes": "router_only",
        }

    return {"routing": routing, "plan": plan}


