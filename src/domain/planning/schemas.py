from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AgentPlan(BaseModel):
    """
    Planner-only JSON output for compound pipelines.

    Keep it short; the goal is fast "System-2" decomposition,
    not full report generation.
    """

    intent: str = Field(..., description="User intent interpreted from the query.")
    key_questions: List[str] = Field(default_factory=list, description="Key questions to answer.")
    assumptions: List[str] = Field(default_factory=list, description="Explicit assumptions/constraints.")
    tool_strategy: List[str] = Field(
        default_factory=list,
        description="What tools/data sources to use and why (high-level).",
    )
    output_outline: List[str] = Field(default_factory=list, description="Outline for final report.")
    risk_flags: List[str] = Field(default_factory=list, description="Potential risks: hallucination, bias, data gaps.")
    language: Optional[str] = Field(None, description="Preferred response language.")


