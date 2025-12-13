"""
Gateway/Router utilities for Compound AI Systems (2025).

Goal:
- Put a cheap "front door" in front of expensive reasoning/long-horizon steps.
- Decide whether to run a full compound pipeline (planner->synthesizer->writer) or a cheap path.

Design:
- Uses ModelRole.ROUTER (small/cheap) when available.
- Falls back to deterministic heuristics if LLM routing fails.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from src.core.routing import ModelRole, get_model_for_role
from src.integrations.llm.llm_client import get_llm_client


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s-]?\d{3,4}[\s-]?\d{4}\b")


def precheck_query(query: str) -> Dict[str, Any]:
    """Lightweight precheck (no extra dependencies)."""
    q = query or ""
    pii_found = bool(_EMAIL_RE.search(q) or _PHONE_RE.search(q))
    # Very light "unsafe" check (kept conservative)
    unsafe_keywords = {"폭탄", "테러", "자살", "살인", "weapon", "terror", "suicide", "murder"}
    lowered = q.lower()
    unsafe = any(k.lower() in lowered for k in unsafe_keywords)
    return {"pii_found": pii_found, "unsafe": unsafe}


def route_request(
    agent_name: str,
    query: str,
    time_window: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return routing decisions for an agent.

    Output keys (best effort):
    - complexity: low|medium|high
    - summary_strategy: cheap|compound
    - should_use_rag: bool
    - suggested_time_window: str | None
    - suggested_max_results: int | None
    - notes: str
    - precheck: { pii_found, unsafe }
    """
    pre = precheck_query(query)

    # Heuristic defaults (always valid even if LLM fails)
    heuristic: Dict[str, Any] = {
        "complexity": "medium",
        "summary_strategy": "compound",
        "should_use_rag": True,
        "suggested_time_window": time_window,
        "suggested_max_results": None,
        "notes": "heuristic_fallback",
        "precheck": pre,
    }

    # Simple heuristics for cost control
    q = (query or "").strip()
    if len(q) <= 8 and len(q.split()) <= 2:
        heuristic["complexity"] = "low"
        heuristic["summary_strategy"] = "cheap"
        heuristic["suggested_max_results"] = 10
    if any(k in q for k in ["전략", "원인", "비교", "시장", "분석", "roadmap", "strategy"]):
        heuristic["complexity"] = "high"
        heuristic["summary_strategy"] = "compound"
        heuristic["suggested_max_results"] = 30

    # If obviously unsafe/PII, keep it cheap + conservative
    if pre.get("pii_found") or pre.get("unsafe"):
        heuristic["summary_strategy"] = "cheap"
        heuristic["notes"] = "precheck_triggered"

    # Try LLM routing (cheap model)
    try:
        client = get_llm_client()
        router_model = get_model_for_role(agent_name, ModelRole.ROUTER)
        schema = {
            "type": "object",
            "properties": {
                "complexity": {"type": "string", "enum": ["low", "medium", "high"]},
                "summary_strategy": {"type": "string", "enum": ["cheap", "compound"]},
                "should_use_rag": {"type": "boolean"},
                "suggested_time_window": {"type": ["string", "null"]},
                "suggested_max_results": {"type": ["integer", "null"]},
                "notes": {"type": "string"},
            },
            "required": ["complexity", "summary_strategy", "should_use_rag", "notes"],
        }
        prompt = (
            "You are a routing gateway for a Compound AI system.\n"
            "Decide the cheapest safe strategy.\n"
            "Rules:\n"
            "- Use 'cheap' for simple queries or when unsafe/pii is detected.\n"
            "- Use 'compound' only for complex reasoning.\n"
            "- Keep suggested_max_results small unless necessary.\n\n"
            f"agent_name: {agent_name}\n"
            f"query: {query}\n"
            f"time_window: {time_window or ''}\n"
            f"language: {language or ''}\n"
            f"precheck: {pre}\n"
        )
        routed = client.chat_json(
            messages=[
                {"role": "system", "content": "Return JSON only. Be conservative on cost."},
                {"role": "user", "content": prompt},
            ],
            schema=schema,
            temperature=0.1,
            model=router_model,
            max_tokens=250,
        )
        if isinstance(routed, dict):
            # Merge with heuristic to ensure required keys exist
            merged = {**heuristic, **routed}
            merged["precheck"] = pre
            return merged
    except Exception:
        pass

    return heuristic
