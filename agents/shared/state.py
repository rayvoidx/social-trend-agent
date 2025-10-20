"""
Common State Schema for all agents
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Base state for all agents following LangGraph pattern"""

    # Input
    query: str = Field(..., description="User query or search term")
    time_window: Optional[str] = Field(None, description="Time window (e.g., last_24h, 7d, 30d)")

    # Data pipeline
    raw_items: List[Dict[str, Any]] = Field(default_factory=list, description="Raw collected items")
    normalized: List[Dict[str, Any]] = Field(default_factory=list, description="Normalized/cleaned items")

    # Analysis results
    analysis: Dict[str, Any] = Field(default_factory=dict, description="Analysis results (sentiment, keywords, etc)")

    # Output
    report_md: Optional[str] = Field(None, description="Final markdown report")

    # Metrics
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Quality metrics (coverage, factuality, actionability)"
    )

    # Metadata
    run_id: Optional[str] = Field(None, description="Unique run identifier")
    error: Optional[str] = Field(None, description="Error message if failed")


class NewsAgentState(AgentState):
    """Extended state for news trend agent"""
    language: Optional[str] = Field("ko", description="Language code (ko, en)")
    max_results: int = Field(20, description="Maximum number of results")


class ViralAgentState(AgentState):
    """Extended state for viral video agent"""
    market: str = Field("KR", description="Market code (KR, US, etc)")
    platforms: List[str] = Field(default_factory=lambda: ["youtube"], description="Platforms to analyze")
    spike_threshold: float = Field(2.0, description="Z-score threshold for spike detection")
