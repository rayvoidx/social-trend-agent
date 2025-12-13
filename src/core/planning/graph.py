"""
Dynamic plan-driven LangGraph builder (2025).

Canonical module (moved from `src/core/plan_graph.py`).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type
import time

from langgraph.graph import StateGraph, END


def build_plan_runner_graph(
    *,
    agent_name: str,
    state_cls: Type[Any],
    router_node: Callable[[Any], Dict[str, Any]],
    op_nodes: Dict[str, Callable[[Any], Dict[str, Any]]],
    steps: List[Dict[str, Any]],
    checkpointer: Optional[Any] = None,
) -> Any:
    """
    Build a plan-driven runner graph.

    - op_nodes key is op name prefix (e.g., "collect", "normalize", "analyze", "rag", "summarize", "report", "notify")
    - steps are structured plan steps (id/op/depends_on/...)
    """
    graph = StateGraph(state_cls)

    def _match_op_key(op: str) -> Optional[str]:
        o = (op or "").lower()
        for k in op_nodes.keys():
            if o.startswith(str(k).lower()):
                return str(k)
        return None

    def _router_wrapper(state: Any) -> Dict[str, Any]:
        out = router_node(state)
        plan = dict(getattr(state, "plan", {}) or {})
        plan.setdefault("steps", steps)
        out["plan"] = plan
        pe = dict(getattr(state, "plan_execution", {}) or {})
        pe.setdefault("completed_ids", [])
        pe.setdefault("skipped_ids", [])
        pe.setdefault("failure_counts", {})
        pe.setdefault("failure_counts_op", {})
        pe.setdefault("circuit_open_until", {})
        pe.setdefault("circuit_open_until_op", {})
        out["plan_execution"] = pe
        return out

    graph.add_node("router", _router_wrapper)

    def dispatch_node(state: Any) -> Dict[str, Any]:
        plan = getattr(state, "plan", {}) or {}
        steps_local = plan.get("steps") if isinstance(plan, dict) else None
        steps_list: List[Dict[str, Any]] = steps_local if isinstance(steps_local, list) else steps

        pe = getattr(state, "plan_execution", {}) or {}
        completed = pe.get("completed_ids")
        completed_ids: List[str] = [x for x in completed if isinstance(x, str)] if isinstance(completed, list) else []
        open_until = pe.get("circuit_open_until")
        open_until_map: Dict[str, float] = dict(open_until) if isinstance(open_until, dict) else {}
        open_until_op = pe.get("circuit_open_until_op")
        open_until_op_map: Dict[str, float] = dict(open_until_op) if isinstance(open_until_op, dict) else {}
        skipped = pe.get("skipped_ids")
        skipped_ids: List[str] = [x for x in skipped if isinstance(x, str)] if isinstance(skipped, list) else []

        next_step: Optional[Dict[str, Any]] = None
        for s in steps_list:
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if not isinstance(sid, str) or sid in completed_ids:
                continue
            ou = open_until_map.get(sid)
            if isinstance(ou, (int, float)) and float(ou) > time.time():
                if sid not in skipped_ids:
                    skipped_ids.append(sid)
                if sid not in completed_ids:
                    completed_ids.append(sid)
                continue
            op = str(s.get("op") or "")
            op_key = _match_op_key(op) or op.split(".", 1)[0].strip().lower()
            ou2 = open_until_op_map.get(op_key)
            if isinstance(ou2, (int, float)) and float(ou2) > time.time():
                if sid not in skipped_ids:
                    skipped_ids.append(sid)
                if sid not in completed_ids:
                    completed_ids.append(sid)
                continue
            deps = s.get("depends_on")
            deps_list = [d for d in deps if isinstance(d, str)] if isinstance(deps, list) else []
            if all(d in completed_ids for d in deps_list):
                next_step = s
                break

        if next_step is None:
            pe["current_step_id"] = None
            pe["current_op"] = "__end__"
            pe["current_op_key"] = None
            pe["completed_ids"] = completed_ids
            pe["skipped_ids"] = skipped_ids
            pe["circuit_open_until"] = open_until_map
            pe["circuit_open_until_op"] = open_until_op_map
            return {"plan_execution": pe}

        pe["current_step_id"] = str(next_step.get("id"))
        op = str(next_step.get("op") or "")
        pe["current_op_key"] = _match_op_key(op) or op.split(".", 1)[0].strip().lower()
        pe["current_op"] = op
        pe["completed_ids"] = completed_ids
        pe["skipped_ids"] = skipped_ids
        pe["circuit_open_until"] = open_until_map
        pe["circuit_open_until_op"] = open_until_op_map
        return {"plan_execution": pe}

    graph.add_node("dispatch", dispatch_node)

    op_key_to_node_name: Dict[str, str] = {}
    for op_key, fn in op_nodes.items():
        node_name = f"op_{op_key}"
        op_key_to_node_name[op_key] = node_name

        def _make_wrapper(opk: str, f: Callable[[Any], Dict[str, Any]]):
            def _wrapped(state: Any) -> Dict[str, Any]:
                pe = dict(getattr(state, "plan_execution", {}) or {})
                completed = pe.get("completed_ids")
                completed_ids: List[str] = [x for x in completed if isinstance(x, str)] if isinstance(completed, list) else []
                fail_counts = pe.get("failure_counts")
                failure_counts: Dict[str, int] = dict(fail_counts) if isinstance(fail_counts, dict) else {}
                fail_counts_op = pe.get("failure_counts_op")
                failure_counts_op: Dict[str, int] = dict(fail_counts_op) if isinstance(fail_counts_op, dict) else {}
                open_until = pe.get("circuit_open_until")
                open_until_map: Dict[str, float] = dict(open_until) if isinstance(open_until, dict) else {}
                open_until_op = pe.get("circuit_open_until_op")
                open_until_op_map: Dict[str, float] = dict(open_until_op) if isinstance(open_until_op, dict) else {}

                sid = pe.get("current_step_id")
                op_key_local = pe.get("current_op_key")
                try:
                    out = f(state)
                except Exception:
                    if isinstance(sid, str):
                        failure_counts[sid] = int(failure_counts.get(sid, 0)) + 1
                        plan = getattr(state, "plan", {}) or {}
                        steps_local = plan.get("steps") if isinstance(plan, dict) else None
                        steps_list2: List[Dict[str, Any]] = steps_local if isinstance(steps_local, list) else steps
                        for st in steps_list2:
                            if isinstance(st, dict) and st.get("id") == sid:
                                cb = st.get("circuit_breaker")
                                if isinstance(cb, dict):
                                    thr = cb.get("failure_threshold", 0)
                                    reset = cb.get("reset_seconds", 0)
                                    if isinstance(thr, int) and thr > 0 and failure_counts[sid] >= thr:
                                        if isinstance(reset, int) and reset > 0:
                                            open_until_map[sid] = time.time() + float(reset)
                                            if isinstance(op_key_local, str) and op_key_local:
                                                failure_counts_op[op_key_local] = int(failure_counts_op.get(op_key_local, 0)) + 1
                                                open_until_op_map[op_key_local] = time.time() + float(reset)
                                break
                    if isinstance(sid, str) and sid not in completed_ids:
                        completed_ids.append(sid)
                    pe["completed_ids"] = completed_ids
                    pe["failure_counts"] = failure_counts
                    pe["failure_counts_op"] = failure_counts_op
                    pe["circuit_open_until"] = open_until_map
                    pe["circuit_open_until_op"] = open_until_op_map
                    return {"plan_execution": pe}

                if isinstance(sid, str) and sid not in completed_ids:
                    completed_ids.append(sid)
                pe["completed_ids"] = completed_ids
                pe["failure_counts"] = failure_counts
                pe["failure_counts_op"] = failure_counts_op
                pe["circuit_open_until"] = open_until_map
                pe["circuit_open_until_op"] = open_until_op_map
                return {**(out or {}), "plan_execution": pe}

            return _wrapped

        graph.add_node(node_name, _make_wrapper(op_key, fn))
        graph.add_edge(node_name, "dispatch")

    def _route_to_op(state: Any) -> str:
        pe = getattr(state, "plan_execution", {}) or {}
        op = str(pe.get("current_op") or "").lower()
        if not op or op == "__end__":
            return "__end__"
        for op_key in op_key_to_node_name.keys():
            if op.startswith(op_key):
                return op_key
        return "__unknown__"

    def op_unknown(state: Any) -> Dict[str, Any]:
        pe = dict(getattr(state, "plan_execution", {}) or {})
        completed = pe.get("completed_ids")
        completed_ids: List[str] = [x for x in completed if isinstance(x, str)] if isinstance(completed, list) else []
        sid = pe.get("current_step_id")
        if isinstance(sid, str) and sid not in completed_ids:
            completed_ids.append(sid)
        pe["completed_ids"] = completed_ids
        return {"plan_execution": pe}

    graph.add_node("op_unknown", op_unknown)
    graph.add_edge("op_unknown", "dispatch")

    graph.set_entry_point("router")
    graph.add_edge("router", "dispatch")

    path_map: Dict[str, Any] = {k: v for k, v in op_key_to_node_name.items()}
    path_map["__unknown__"] = "op_unknown"
    path_map["__end__"] = END
    graph.add_conditional_edges("dispatch", _route_to_op, path_map)

    interrupt_before = None
    if checkpointer:
        if "report" in op_nodes:
            interrupt_before = ["op_report"]
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)


