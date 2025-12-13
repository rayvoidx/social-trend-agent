"""
Planning / Plan-runner core package.

Canonical location for:
- plan utilities (DAG normalization, policy extraction)
- plan-driven LangGraph runner

Legacy shims:
- src/core/plan.py
- src/core/plan_graph.py
"""

from src.core.planning.plan import *  # noqa: F401,F403
from src.core.planning.graph import *  # noqa: F401,F403
