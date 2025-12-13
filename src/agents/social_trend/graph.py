from __future__ import annotations

import os
import json
import uuid
import logging
from pathlib import Path
from dataclasses import asdict
from typing import Any, Dict, List, Optional, cast
import sys

from langgraph.graph import StateGraph, END

from src.core.state import SocialTrendAgentState
from src.core.logging import AgentLogger
from src.core.errors import safe_api_call
from src.core.config import get_config_manager
from src.core.checkpoint import get_checkpointer
from src.agents.social_trend.tools import (
    fetch_x_posts,
    fetch_instagram_posts,
    fetch_naver_blog_posts,
    fetch_rss_feeds,
    normalize_items,
    retrieve_relevant_posts,
    analyze_sentiment_and_keywords,
    generate_trend_report,
)
from src.core.gateway import route_request
from src.core.planning.plan import (
    get_agent_entry,
    derive_execution_overrides,
    normalize_steps,
    has_step,
    get_retry_policy_for_step,
    get_retry_policy_for_op,
    get_timeout_for_step,
    get_timeout_for_op,
    get_circuit_breaker_for_step,
)
from src.core.planning.graph import build_plan_runner_graph

try:
    # Check LangChain availability
    import langchain

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)

# Write artifacts to project-level /artifacts (not inside the Python package)
ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "social_trend_agent"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# LangGraph Node Functions
# =============================================================================


def router_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """Cheap gateway/router node (Compound AI 2025)."""
    run_id = state.run_id or "unknown"
    agent_logger = AgentLogger("social_trend_agent", run_id)
    agent_logger.node_start("router")

    route = route_request(
        agent_name="social_trend_agent",
        query=state.query,
        time_window=state.time_window,
        language=state.language,
    )

    agent_entry = get_agent_entry(state.orchestrator, "social_trend_agent")
    overrides = derive_execution_overrides(agent_entry)
    if overrides:
        route = {**route, **overrides}

    # Apply small, safe knobs for cost/latency
    suggested_tw = route.get("suggested_time_window")
    time_window = state.time_window
    if isinstance(suggested_tw, str) and suggested_tw.strip():
        time_window = suggested_tw.strip()

    suggested_max = route.get("suggested_max_results")
    max_results_per_platform = state.max_results_per_platform
    if isinstance(suggested_max, int) and suggested_max > 0:
        # this is per-platform cap; keep conservative
        max_results_per_platform = min(max(10, suggested_max), 80)

    agent_logger.node_end("router")
    return {
        "time_window": time_window,
        "max_results_per_platform": max_results_per_platform,
        "analysis": {**(state.analysis or {}), "_routing": route},
        "plan": {"steps": normalize_steps(agent_entry) if agent_entry else []},
    }


def rag_filter_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """Optional RAG filter step controlled by tool plan (rag_mode/top_k)."""
    run_id = state.run_id or "unknown"
    agent_logger = AgentLogger("social_trend_agent", run_id)
    agent_logger.node_start("rag_filter")

    routed = (state.analysis or {}).get("_routing", {}) if isinstance(state.analysis, dict) else {}
    rag_mode = str(routed.get("rag_mode") or "graph").lower()
    rag_top_k = routed.get("rag_top_k")
    top_k = (
        int(rag_top_k)
        if isinstance(rag_top_k, int) and rag_top_k > 0
        else min(30, len(state.normalized))
    )

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "rag"):
        rag_mode = "none"

    if rag_mode == "none" or not state.normalized:
        agent_logger.node_end("rag_filter", output_size=len(state.normalized))
        return {}

    use_graph = rag_mode != "vector"
    filtered = retrieve_relevant_posts(
        state.query, state.normalized, top_k=top_k, use_graph=use_graph
    )
    agent_logger.node_end("rag_filter", output_size=len(filtered))
    return {
        "normalized": filtered,
        "analysis": {**(state.analysis or {}), "rag_selected": len(filtered)},
    }


def collect_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """소셜 미디어 데이터 수집 노드"""
    run_id = state.run_id or "unknown"
    agent_logger = AgentLogger("social_trend_agent", run_id)
    agent_logger.node_start("collect")

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    current_step_id = (
        (state.plan_execution or {}).get("current_step_id")
        if isinstance(state.plan_execution, dict)
        else None
    )
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(
        steps, "collect"
    )
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "collect")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = (
        isinstance(cb, dict)
        and isinstance(cb.get("failure_threshold"), int)
        and cb.get("failure_threshold", 0) > 0
    )

    all_items = []
    max_per_platform = (
        state.max_results_per_platform // len(state.platforms) if state.platforms else 10
    )

    for platform in state.platforms:
        try:
            if platform == "x":
                items = safe_api_call(
                    "fetch_x_posts",
                    fetch_x_posts,
                    state.query,
                    max_results=max_per_platform,
                    fallback_value=[],
                    retry_policy=rp,
                    timeout_seconds=timeout_s,
                    raise_on_fail=strict,
                )
            elif platform == "instagram":
                items = safe_api_call(
                    "fetch_instagram_posts",
                    fetch_instagram_posts,
                    state.query,
                    max_results=max_per_platform,
                    fallback_value=[],
                    retry_policy=rp,
                    timeout_seconds=timeout_s,
                    raise_on_fail=strict,
                )
            elif platform == "naver_blog":
                items = safe_api_call(
                    "fetch_naver_blog_posts",
                    fetch_naver_blog_posts,
                    state.query,
                    max_results=max_per_platform,
                    fallback_value=[],
                    retry_policy=rp,
                    timeout_seconds=timeout_s,
                    raise_on_fail=strict,
                )
            else:
                items = []

            all_items.extend(items)
            logger.info(f"Collected {len(items)} items from {platform}")

        except Exception as e:
            logger.error(f"Error collecting from {platform}: {e}")

    # RSS feeds
    if state.include_rss:
        feeds = state.rss_feeds or [
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            "https://www.reddit.com/r/MachineLearning/.rss",
        ]
        rss_items = safe_api_call(
            "fetch_rss_feeds",
            fetch_rss_feeds,
            feeds,
            max_results=max_per_platform,
            fallback_value=[],
            retry_policy=rp,
            timeout_seconds=timeout_s,
            raise_on_fail=strict,
        )
        all_items.extend(rss_items)

    # Convert CollectedItem objects to dicts
    all_items_dict = [
        asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in all_items
    ]

    agent_logger.node_end(
        "collect", output_size=len(all_items_dict), items_count=len(all_items_dict)
    )
    return {"raw_items": all_items_dict}


def normalize_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """데이터 정규화 노드"""
    run_id = state.run_id or "unknown"
    agent_logger = AgentLogger("social_trend_agent", run_id)
    agent_logger.node_start("normalize")

    normalized = normalize_items(state.raw_items)

    agent_logger.node_end(
        "normalize", output_size=len(normalized), normalized_count=len(normalized)
    )
    return {"normalized": normalized}


def analyze_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """감성 및 키워드 분석 노드"""
    run_id = state.run_id or "unknown"
    agent_logger = AgentLogger("social_trend_agent", run_id)
    agent_logger.node_start("analyze")

    texts = [it.get("title", "") + "\n" + it.get("content", "") for it in state.normalized]
    analysis = analyze_sentiment_and_keywords(texts)

    # Extract engagement stats per platform
    engagement_stats = {}
    for item in state.normalized:
        platform = item.get("source", "unknown")
        if platform not in engagement_stats:
            engagement_stats[platform] = {"count": 0, "total_engagement": 0}
        engagement_stats[platform]["count"] += 1

    agent_logger.node_end(
        "analyze", output_size=len(state.normalized), sentiment=analysis.get("sentiment", {})
    )
    return {"analysis": analysis, "engagement_stats": engagement_stats}


def summarize_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """LLM 기반 인사이트 생성 노드"""
    run_id = state.run_id or "unknown"
    agent_logger = AgentLogger("social_trend_agent", run_id)
    agent_logger.node_start("summarize")

    llm_insights = generate_trend_report(
        query=state.query,
        normalized=state.normalized,
        analysis=state.analysis,
        sources=state.platforms,
        time_window=state.time_window or "7d",
        strategy=str((state.analysis or {}).get("_routing", {}).get("summary_strategy", "auto")),
    )

    summary = _make_summary(state.analysis)
    updated_analysis = {**state.analysis, "summary": summary, "llm_insights": llm_insights}

    agent_logger.node_end("summarize")
    return {"analysis": updated_analysis}


def report_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """리포트 생성 노드"""
    run_id = state.run_id or "unknown"
    agent_logger = AgentLogger("social_trend_agent", run_id)
    agent_logger.node_start("report")

    metrics = _make_metrics(state.normalized, state.analysis)

    report_path = ARTIFACTS_DIR / f"{state.run_id}.md"
    _write_report(
        report_path,
        state.query,
        state.time_window or "7d",
        state.language,
        state.normalized,
        state.analysis,
        state.analysis.get("summary", ""),
        metrics,
        state.analysis.get("llm_insights", ""),
    )

    agent_logger.node_end("report", output_size=len(state.normalized), report_path=str(report_path))
    return {"metrics": metrics, "report_md": str(report_path)}


# =============================================================================
# Graph Builder
# =============================================================================


def build_graph(checkpointer: Optional[Any] = None) -> Any:
    """Social Trend Agent 그래프 빌드"""
    graph = StateGraph(SocialTrendAgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("collect", collect_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("rag_filter", rag_filter_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("report", report_node)

    # Add edges
    graph.set_entry_point("router")
    graph.add_edge("router", "collect")
    graph.add_edge("collect", "normalize")
    graph.add_edge("normalize", "rag_filter")
    graph.add_edge("rag_filter", "analyze")
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "report")
    graph.add_edge("report", END)

    return graph.compile(
        checkpointer=checkpointer, interrupt_before=["report"] if checkpointer else None
    )


# =============================================================================
# Main Entry Point
# =============================================================================


def run_agent(
    query: str,
    sources: Optional[List[str]] = None,
    rss_feeds: Optional[List[str]] = None,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 50,
    run_id: Optional[str] = None,
    require_approval: bool = True,
    orchestrator: Optional[Dict[str, Any]] = None,
) -> SocialTrendAgentState:
    """
    Social Trend Agent 실행
    """
    if sources is None:
        sources = ["x", "instagram", "naver_blog"]

    if not run_id:
        run_id = str(uuid.uuid4())[:8]

    # Initialize state
    initial_state = SocialTrendAgentState(
        query=query,
        time_window=time_window,
        language=language,
        platforms=sources,
        rss_feeds=rss_feeds or [],
        max_results_per_platform=max_results,
        include_rss=True,
        orchestrator=orchestrator,
        run_id=run_id,
        report_md=None,
        error=None,
    )

    # Auto-disable HITL when running in non-interactive environments (e.g., Docker/API/UI)
    if require_approval and not sys.stdin.isatty():
        logger.warning("require_approval=True but stdin is not a TTY. Disabling HITL to avoid EOF.")
        require_approval = False

    # Setup HITL
    checkpointer = get_checkpointer() if require_approval else None
    # 2025: Plan-driven dynamic graph compilation (plan == graph structure)
    agent_entry = get_agent_entry(orchestrator, "social_trend_agent")
    steps = normalize_steps(agent_entry) if agent_entry else []
    if steps:
        graph = build_plan_runner_graph(
            agent_name="social_trend_agent",
            state_cls=SocialTrendAgentState,
            router_node=router_node,
            op_nodes={
                "collect": collect_node,
                "normalize": normalize_node,
                "rag": rag_filter_node,
                "analyze": analyze_node,
                "summarize": summarize_node,
                "report": report_node,
            },
            steps=steps,
            checkpointer=checkpointer,
        )
    else:
        graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id}}

    logger.info(f"Starting Social Trend Agent run: {run_id}")

    try:
        # 1. Start execution
        current_state = graph.invoke(initial_state, config=config)

        # 2. Check for interrupt
        if require_approval:
            snapshot = graph.get_state(config)
            if snapshot.next and "report" in snapshot.next:
                # CLI Interaction
                print("\n" + "=" * 50)
                print("✋  APPROVAL REQUIRED")
                print("=" * 50)
                print(f"Social analysis complete for: '{query}'")
                print("-" * 50)

                while True:
                    choice = input("Proceed to generate report? (y/n): ").strip().lower()
                    if choice == "y":
                        logger.info("✅ Approved. Resuming...")
                        current_state = graph.invoke(None, config=config)
                        break
                    elif choice == "n":
                        logger.info("🛑 Aborted by user.")
                        return SocialTrendAgentState(**cast(Dict[str, Any], current_state))
                    else:
                        print("Please enter 'y' or 'n'.")

        logger.info(f"Completed Social Trend Agent run: {run_id}")

        if isinstance(current_state, dict):
            return SocialTrendAgentState(**cast(Dict[str, Any], current_state))
        return current_state

    except Exception as e:
        logger.error(f"Error running social trend agent: {e}")
        raise


# Legacy compatibility function
def run_agent_legacy(
    query: str,
    sources: Optional[List[str]] = None,
    rss_feeds: Optional[List[str]] = None,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 50,
) -> Dict[str, Any]:
    """Legacy run_agent that returns Dict for backwards compatibility"""
    state = run_agent(
        query, sources, rss_feeds, time_window, language, max_results, require_approval=False
    )
    return {
        "query": state.query,
        "time_window": state.time_window,
        "language": state.language,
        "normalized": state.normalized,
        "analysis": state.analysis,
        "metrics": state.metrics,
        "run_id": state.run_id,
        "report_md": state.report_md,
    }


def _make_summary(analysis: Dict[str, Any]) -> str:
    s = analysis.get("sentiment", {})
    k = analysis.get("keywords", {})
    top_kw = ", ".join([kw["keyword"] for kw in k.get("top_keywords", [])[:5]])
    return (
        f"긍정 {s.get('positive_pct', 0):.1f}% / 중립 {s.get('neutral_pct', 0):.1f}% / "
        f"부정 {s.get('negative_pct', 0):.1f}% | 주요 키워드: {top_kw}"
    )


def _make_metrics(normalized: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "coverage": min(1.0, len(normalized) / 100.0),
        "factuality": 0.7,  # placeholder
        "actionability": 0.6,  # placeholder
    }


def _write_report(
    path: Path,
    query: str,
    time_window: str,
    language: str,
    normalized: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    summary: str,
    metrics: Dict[str, Any],
    llm_insights: str = "",
) -> None:
    lines = []
    lines.append(f"# Social Trend Report")
    lines.append("")
    lines.append(f"- **Query**: {query}")
    lines.append(f"- **Time Window**: {time_window}")
    lines.append(f"- **Language**: {language}")
    lines.append(f"- **Items Analyzed**: {len(normalized)}")
    lines.append("")

    lines.append("## 📊 Quick Summary")
    lines.append(summary)
    lines.append("")

    # Sentiment breakdown
    sentiment = analysis.get("sentiment", {})
    lines.append("## 💭 Sentiment Analysis")
    lines.append(
        f"- **Positive**: {sentiment.get('positive', 0)} ({sentiment.get('positive_pct', 0):.1f}%)"
    )
    lines.append(
        f"- **Neutral**: {sentiment.get('neutral', 0)} ({sentiment.get('neutral_pct', 0):.1f}%)"
    )
    lines.append(
        f"- **Negative**: {sentiment.get('negative', 0)} ({sentiment.get('negative_pct', 0):.1f}%)"
    )
    lines.append("")

    # Keywords
    keywords_data = analysis.get("keywords", {})
    top_keywords = keywords_data.get("top_keywords", [])
    if top_keywords:
        lines.append("## 🔑 Top Keywords")
        for i, kw in enumerate(top_keywords[:10], 1):
            lines.append(f"{i}. **{kw['keyword']}** - {kw['count']} mentions")
        lines.append("")

    # LLM Insights
    if llm_insights and llm_insights != "LLM을 사용할 수 없어 인사이트를 생성하지 못했습니다.":
        lines.append("## 💡 AI-Generated Insights")
        lines.append(llm_insights)
        lines.append("")

    # Metrics
    lines.append("## 📈 Quality Metrics")
    lines.append(f"- **Coverage**: {metrics.get('coverage', 0):.2f}")
    lines.append(f"- **Factuality**: {metrics.get('factuality', 0):.2f}")
    lines.append(f"- **Actionability**: {metrics.get('actionability', 0):.2f}")
    lines.append("")

    # Top items
    lines.append("## 📱 Top Social Posts")
    for i, it in enumerate(normalized[:10], 1):
        title = it.get("title", "No title")
        url = it.get("url", "")
        source = it.get("source", "Unknown")
        if url:
            lines.append(f"{i}. [{title}]({url}) - *{source}*")
        else:
            lines.append(f"{i}. {title} - *{source}*")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
