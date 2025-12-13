"""
Structured execution plan utilities (2025).

Canonical module (moved from `src/core/plan.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_agent_entry(orchestrator: Optional[Dict[str, Any]], agent_name: str) -> Optional[Dict[str, Any]]:
    if not isinstance(orchestrator, dict):
        return None
    plan = orchestrator.get("plan")
    if not isinstance(plan, dict):
        return None
    agents = plan.get("agents")
    if not isinstance(agents, list):
        return None
    for a in agents:
        if isinstance(a, dict) and a.get("agent_name") == agent_name:
            return a
    return None


def normalize_steps(agent_entry: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a normalized list of step dicts.

    Priority:
    1) steps (structured)
    2) tool_plan (legacy list[str]) -> converted to linear steps
    """
    if not isinstance(agent_entry, dict):
        return []

    steps = agent_entry.get("steps")
    if isinstance(steps, list) and all(isinstance(s, dict) for s in steps):
        return [dict(s) for s in steps]

    tool_plan = agent_entry.get("tool_plan")
    if isinstance(tool_plan, list) and all(isinstance(x, str) for x in tool_plan):
        out: List[Dict[str, Any]] = []
        prev_id: Optional[str] = None
        for i, op in enumerate(tool_plan, 1):
            sid = f"tp{i}"
            out.append(
                {
                    "id": sid,
                    "op": op.strip(),
                    "inputs": [],
                    "outputs": [],
                    "depends_on": [prev_id] if prev_id else [],
                    "retry_policy": {"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
                    "params": {},
                }
            )
            prev_id = sid
        return out

    return []


def find_step_by_id(steps: List[Dict[str, Any]], step_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not step_id:
        return None
    for s in steps:
        if isinstance(s, dict) and s.get("id") == step_id:
            return s
    return None


def get_retry_policy_for_step(steps: List[Dict[str, Any]], step_id: Optional[str]) -> Dict[str, Any]:
    s = find_step_by_id(steps, step_id)
    if not isinstance(s, dict):
        return {}
    rp = s.get("retry_policy")
    return dict(rp) if isinstance(rp, dict) else {}


def get_retry_policy_for_op(steps: List[Dict[str, Any]], op_prefix: str) -> Dict[str, Any]:
    p = (op_prefix or "").strip().lower()
    if not p:
        return {}
    for s in steps:
        op = s.get("op")
        if isinstance(op, str) and op.strip().lower().startswith(p):
            rp = s.get("retry_policy")
            return dict(rp) if isinstance(rp, dict) else {}
    return {}


def get_timeout_for_step(steps: List[Dict[str, Any]], step_id: Optional[str]) -> Optional[int]:
    s = find_step_by_id(steps, step_id)
    if not isinstance(s, dict):
        return None
    v = s.get("timeout_seconds")
    return int(v) if isinstance(v, int) and v > 0 else None


def get_timeout_for_op(steps: List[Dict[str, Any]], op_prefix: str) -> Optional[int]:
    p = (op_prefix or "").strip().lower()
    if not p:
        return None
    for s in steps:
        op = s.get("op")
        if isinstance(op, str) and op.strip().lower().startswith(p):
            v = s.get("timeout_seconds")
            return int(v) if isinstance(v, int) and v > 0 else None
    return None


def get_circuit_breaker_for_step(steps: List[Dict[str, Any]], step_id: Optional[str]) -> Dict[str, Any]:
    s = find_step_by_id(steps, step_id)
    if not isinstance(s, dict):
        return {}
    cb = s.get("circuit_breaker")
    return dict(cb) if isinstance(cb, dict) else {}


def step_ops(steps: List[Dict[str, Any]]) -> List[str]:
    ops: List[str] = []
    for s in steps:
        op = s.get("op")
        if isinstance(op, str) and op.strip():
            ops.append(op.strip())
    return ops


def has_step(steps: List[Dict[str, Any]], op_prefix: str) -> bool:
    p = (op_prefix or "").strip().lower()
    if not p:
        return False
    for op in step_ops(steps):
        if op.lower().startswith(p):
            return True
    return False


def get_first_step_params(steps: List[Dict[str, Any]], op_prefix: str) -> Dict[str, Any]:
    p = (op_prefix or "").strip().lower()
    if not p:
        return {}
    for s in steps:
        op = s.get("op")
        if isinstance(op, str) and op.strip().lower().startswith(p):
            params = s.get("params")
            return dict(params) if isinstance(params, dict) else {}
    return {}


def derive_execution_overrides(agent_entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Derive actual execution knobs from structured steps + top-level params.
    This is how we make "plan == executable DAG" influence runtime.
    """
    if not isinstance(agent_entry, dict):
        return {}

    overrides: Dict[str, Any] = {}

    # 1) Top-level params (planner knobs)
    params = agent_entry.get("params")
    if isinstance(params, dict):
        overrides.update(params)

    # 2) Step-derived knobs (if steps explicitly include/omit operations)
    steps = normalize_steps(agent_entry)
    if steps:
        overrides["steps"] = steps  # keep full DAG for observability
        overrides["step_ops"] = step_ops(steps)

        # If there is no rag step, force rag_mode=none (strong binding)
        if not has_step(steps, "rag"):
            overrides.setdefault("rag_mode", "none")

        # Summarize step can specify strategy
        sparams = get_first_step_params(steps, "summarize")
        if "summary_strategy" in sparams and isinstance(sparams.get("summary_strategy"), str):
            overrides["summary_strategy"] = sparams["summary_strategy"]

        # RAG step can specify rag_mode/top_k
        rparams = get_first_step_params(steps, "rag")
        if "rag_mode" in rparams and isinstance(rparams.get("rag_mode"), str):
            overrides["rag_mode"] = rparams["rag_mode"]
        if "rag_top_k" in rparams and isinstance(rparams.get("rag_top_k"), int):
            overrides["rag_top_k"] = rparams["rag_top_k"]

    return overrides


