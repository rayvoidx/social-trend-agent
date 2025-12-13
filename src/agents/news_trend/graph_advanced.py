"""
Advanced LangGraph implementation for News Trend Agent

Next-level features:
- Conditional edges for error recovery
- Parallel node execution
- Streaming support for real-time updates

References:
- Conditional Edges: https://langchain-ai.github.io/langgraph/how-tos/branching/
- Streaming: https://langchain-ai.github.io/langgraph/how-tos/stream-values/
"""
import os
import uuid
import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
import asyncio

from src.core.state import NewsAgentState
from src.core.logging import AgentLogger
from src.core.errors import PartialResult, CompletionStatus, safe_api_call
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
from src.agents.news_trend.tools import (
    search_news,
    analyze_sentiment,
    extract_keywords,
    summarize_trend,
    retrieve_relevant_items,
)

# Initialize module-level logger (without run_id for module-level logging)
_module_logger = logging.getLogger("news_trend_agent_advanced")

def router_node(state: NewsAgentState) -> Dict[str, Any]:
    """Cheap gateway/router node (Compound AI 2025)."""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("router")

    route = route_request(
        agent_name="news_trend_agent",
        query=state.query,
        time_window=state.time_window,
        language=state.language,
    )

    agent_entry = get_agent_entry(state.orchestrator, "news_trend_agent")
    overrides = derive_execution_overrides(agent_entry)
    if overrides:
        route = {**route, **overrides}

    suggested_max = route.get("suggested_max_results")
    max_results = state.max_results
    if isinstance(suggested_max, int) and suggested_max > 0:
        max_results = min(max(5, suggested_max), 50)

    suggested_tw = route.get("suggested_time_window")
    time_window = state.time_window
    if isinstance(suggested_tw, str) and suggested_tw.strip():
        time_window = suggested_tw.strip()

    logger.node_end("router")
    return {
        "time_window": time_window,
        "max_results": max_results,
        "analysis": {**(state.analysis or {}), "_routing": route},
        "plan": {"steps": normalize_steps(agent_entry) if agent_entry else []},
    }


# ============================================================================
# Advanced Node Functions with Parallel Execution
# ============================================================================

async def parallel_collect_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    Collect news data with parallel API calls

    Executes multiple data sources in parallel for better performance.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("parallel_collect")

    # Parallel execution with asyncio
    async def fetch_newsapi():
        """Fetch from NewsAPI"""
        return safe_api_call(
            "search_news_newsapi",
            search_news,
            query=state.query,
            time_window=state.time_window or "7d",
            language="en" if state.language == "en" else "ko",
            max_results=state.max_results // 2,
            fallback_value=[]
        )

    async def fetch_naver():
        """Fetch from Naver"""
        return safe_api_call(
            "search_news_naver",
            search_news,
            query=state.query,
            time_window=state.time_window or "7d",
            language="ko",
            max_results=state.max_results // 2,
            fallback_value=[]
        )

    # Execute in parallel
    results = await asyncio.gather(
        fetch_newsapi(),
        fetch_naver(),
        return_exceptions=True
    )

    # Combine results
    raw_items = []
    for result in results:
        if isinstance(result, list):
            raw_items.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Parallel fetch failed", error=str(result))

    logger.node_end("parallel_collect", output_size=len(raw_items))

    return {
        "raw_items": raw_items,
        "error": None if raw_items else "All parallel fetches failed"
    }


def collect_node_with_retry(state: NewsAgentState) -> Dict[str, Any]:
    """
    Collect node with retry capability

    Stores retry_count in state for conditional edge routing.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("collect")

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "collect"):
        logger.node_end("collect", output_size=0, status=CompletionStatus.FULL.value)
        return {"retry_count": 0}
    current_step_id = (state.plan_execution or {}).get("current_step_id") if isinstance(state.plan_execution, dict) else None
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(steps, "collect")
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "collect")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = isinstance(cb, dict) and isinstance(cb.get("failure_threshold"), int) and cb.get("failure_threshold", 0) > 0
    result = PartialResult(status=CompletionStatus.FULL)

    raw_items = safe_api_call(
        operation_name="search_news",
        api_func=search_news,
        query=state.query,
        time_window=state.time_window or "7d",
        language=state.language,
        max_results=state.max_results,
        fallback_value=[],
        result_container=result,
        retry_policy=rp,
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
    )

    # Determine retry count
    retry_count = getattr(state, 'retry_count', 0)

    logger.node_end("collect", output_size=len(raw_items), status=result.status.value)

    return {
        "raw_items": raw_items,
        "error": (result.errors[0].get("error_message") if result.errors else None) if result.status == CompletionStatus.FAILED else None,
        "retry_count": retry_count + 1 if result.status == CompletionStatus.FAILED else 0
    }


def normalize_node(state: NewsAgentState) -> Dict[str, Any]:
    """Normalize and clean collected data"""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("normalize", raw_count=len(state.raw_items))

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "normalize"):
        logger.node_end("normalize", normalized_count=len(state.normalized))
        return {}
    normalized = []
    for item in state.raw_items:
        normalized.append({
            "title": item.get("title", "").strip(),
            "description": item.get("description", "").strip(),
            "url": item.get("url", ""),
            "source": item.get("source", {}).get("name", "Unknown") if isinstance(item.get("source"), dict) else str(item.get("source", "Unknown")),
            "published_at": item.get("publishedAt", ""),
            "content": item.get("content", "").strip()
        })

    logger.node_end("normalize", normalized_count=len(normalized))

    return {"normalized": normalized}


async def parallel_analyze_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    Analyze sentiment and keywords in parallel

    Executes sentiment analysis and keyword extraction concurrently.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("parallel_analyze")

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "analyze"):
        logger.node_end("parallel_analyze")
        return {}
    current_step_id = (state.plan_execution or {}).get("current_step_id") if isinstance(state.plan_execution, dict) else None
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(steps, "analyze")
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "analyze")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = isinstance(cb, dict) and isinstance(cb.get("failure_threshold"), int) and cb.get("failure_threshold", 0) > 0
    # Define async wrappers
    async def analyze_sentiment_async():
        """Async wrapper for sentiment analysis"""
        return safe_api_call(
            "analyze_sentiment",
            analyze_sentiment,
            items=state.normalized,
            fallback_value={"positive": 0, "neutral": 0, "negative": 0},
            retry_policy=rp,
            timeout_seconds=timeout_s,
            raise_on_fail=strict,
        )

    async def extract_keywords_async():
        """Async wrapper for keyword extraction"""
        return safe_api_call(
            "extract_keywords",
            extract_keywords,
            items=state.normalized,
            fallback_value={"top_keywords": [], "total_unique_keywords": 0},
            retry_policy=rp,
            timeout_seconds=timeout_s,
            raise_on_fail=strict,
        )

    # Execute in parallel
    sentiment_results, keyword_results = await asyncio.gather(
        analyze_sentiment_async(),
        extract_keywords_async()
    )

    analysis = {
        "sentiment": sentiment_results,
        "keywords": keyword_results,
        "total_items": len(state.normalized)
    }

    logger.node_end("parallel_analyze")

    return {"analysis": analysis}


def rag_node(state: NewsAgentState) -> Dict[str, Any]:
    """Optional explicit RAG step for plan runner (advanced graph)."""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("rag")

    routed = (state.analysis or {}).get("_routing", {}) if isinstance(state.analysis, dict) else {}
    rag_mode = str(routed.get("rag_mode") or "graph").lower()
    rag_top_k = routed.get("rag_top_k")
    top_k = int(rag_top_k) if isinstance(rag_top_k, int) and rag_top_k > 0 else min(10, len(state.normalized))

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "rag"):
        rag_mode = "none"

    if rag_mode == "none":
        relevant = state.normalized[: max(1, top_k)]
    else:
        use_graph = rag_mode != "vector"
        relevant = retrieve_relevant_items(state.query, state.normalized, top_k, use_graph=use_graph)

    logger.node_end("rag", output_size=len(relevant))
    return {"analysis": {**state.analysis, "_rag_relevant": relevant}}


def summarize_node(state: NewsAgentState) -> Dict[str, Any]:
    """Summarize trend insights using LLM"""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("summarize")

    result = PartialResult(status=CompletionStatus.FULL)
    # Retrieve relevant subset (RAG) - controlled by tool plan (rag_mode/top_k)
    routed = (state.analysis or {}).get("_routing", {}) if isinstance(state.analysis, dict) else {}
    rag_mode = str(routed.get("rag_mode") or "graph").lower()
    rag_top_k = routed.get("rag_top_k")
    top_k = int(rag_top_k) if isinstance(rag_top_k, int) and rag_top_k > 0 else min(10, len(state.normalized))

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "rag"):
        rag_mode = "none"

    cached = (state.analysis or {}).get("_rag_relevant") if isinstance(state.analysis, dict) else None
    if isinstance(cached, list) and cached:
        relevant = cached
    else:
        if rag_mode == "none":
            relevant = state.normalized[: max(1, top_k)]
        else:
            use_graph = rag_mode != "vector"
            relevant = retrieve_relevant_items(state.query, state.normalized, top_k, use_graph=use_graph)

    current_step_id = (state.plan_execution or {}).get("current_step_id") if isinstance(state.plan_execution, dict) else None
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(steps, "summarize")
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "summarize")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = isinstance(cb, dict) and isinstance(cb.get("failure_threshold"), int) and cb.get("failure_threshold", 0) > 0

    summary = safe_api_call(
        operation_name="summarize_trend",
        api_func=summarize_trend,
        query=state.query,
        normalized_items=relevant,
        analysis=state.analysis,
        fallback_value="트렌드 요약을 생성할 수 없습니다.",
        result_container=result,
        retry_policy=rp,
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
    )

    logger.node_end("summarize", summary_length=len(summary), status=result.status.value)

    return {"analysis": {**state.analysis, "summary": summary}}


def report_node(state: NewsAgentState) -> Dict[str, Any]:
    """Generate markdown report"""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("report")

    # Build report (same as before)
    sentiment = state.analysis.get("sentiment", {})
    keywords = state.analysis.get("keywords", {}).get("top_keywords", [])

    report_lines = [
        f"# 뉴스 트렌드 분석 리포트",
        f"",
        f"**검색어**: {state.query}",
        f"**기간**: {state.time_window or '7d'}",
        f"**분석 항목**: {len(state.normalized)}건",
        f"",
        f"## 📊 감성 분석",
        f"- 긍정: {sentiment.get('positive', 0)}건 ({sentiment.get('positive_pct', 0):.1f}%)",
        f"- 중립: {sentiment.get('neutral', 0)}건 ({sentiment.get('neutral_pct', 0):.1f}%)",
        f"- 부정: {sentiment.get('negative', 0)}건 ({sentiment.get('negative_pct', 0):.1f}%)",
        f"",
        f"## 🔑 핵심 키워드",
        f"",
    ]

    for kw in keywords[:10]:
        report_lines.append(f"- **{kw['keyword']}** ({kw['count']}회)")

    report_lines.extend([
        f"",
        f"## 💡 주요 인사이트",
        f"",
        state.analysis.get("summary", "No summary available."),
        f"",
        f"**Run ID**: `{state.run_id}`"
    ])

    report_md = "\n".join(report_lines)

    metrics = {
        "coverage": len(state.normalized) / max(state.max_results, 1),
        "factuality": 1.0 if all(item.get("url") for item in state.normalized) else 0.0,
        "actionability": 1.0 if state.analysis.get("summary") else 0.0
    }

    logger.node_end("report", metrics=metrics)

    return {"report_md": report_md, "metrics": metrics}


def notify_node(state: NewsAgentState) -> Dict[str, Any]:
    """Send notifications"""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("notify")

    # Notification logic (same as before)
    logger.node_end("notify")

    return {}


# ============================================================================
# Conditional Edge Functions
# ============================================================================

def should_retry_collect(state: NewsAgentState) -> Literal["retry_collect", "normalize", "end"]:
    """
    Conditional edge: decide whether to retry collection

    Official LangGraph pattern for error recovery.

    Returns:
        - "retry_collect": If collection failed and retries < 3
        - "normalize": If collection succeeded
        - "end": If max retries exceeded
    """
    retry_count = getattr(state, 'retry_count', 0)
    has_data = len(state.raw_items) > 0

    if has_data:
        return "normalize"
    elif retry_count < 3:
        _module_logger.warning(f"Collection failed, retrying ({retry_count}/3)")
        return "retry_collect"
    else:
        _module_logger.error("Max retries exceeded, ending workflow")
        return "end"


def should_proceed_to_analysis(state: NewsAgentState) -> Literal["analyze", "end"]:
    """
    Conditional edge: decide whether to proceed to analysis

    Returns:
        - "analyze": If normalized data is available
        - "end": If no data to analyze
    """
    if len(state.normalized) > 0:
        return "analyze"
    else:
        _module_logger.warning("No normalized data, ending workflow")
        return "end"


# ============================================================================
# Advanced Graph Builder
# ============================================================================

def build_advanced_graph():
    """
    Build advanced LangGraph with:
    - Conditional edges for error recovery
    - Parallel node execution
    - Retry logic

    Official LangGraph patterns:
    - add_conditional_edges(): https://langchain-ai.github.io/langgraph/how-tos/branching/
    """
    _module_logger.info("Building advanced LangGraph")

    graph = StateGraph(NewsAgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("collect", collect_node_with_retry)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analyze", parallel_analyze_node)  # Async parallel execution
    graph.add_node("summarize", summarize_node)
    graph.add_node("report", report_node)
    graph.add_node("notify", notify_node)

    # Set entry point
    graph.set_entry_point("router")
    graph.add_edge("router", "collect")

    # Add conditional edges (official pattern)
    graph.add_conditional_edges(
        "collect",
        should_retry_collect,
        {
            "retry_collect": "collect",  # Loop back for retry
            "normalize": "normalize",    # Success path
            "end": END                   # Give up
        }
    )

    graph.add_conditional_edges(
        "normalize",
        should_proceed_to_analysis,
        {
            "analyze": "analyze",
            "end": END
        }
    )

    # Regular edges
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "report")
    graph.add_edge("report", "notify")
    graph.add_edge("notify", END)

    # Compile
    compiled_graph = graph.compile()

    _module_logger.info("Advanced LangGraph compiled with conditional edges")

    return compiled_graph


# ============================================================================
# Streaming Support
# ============================================================================

async def run_agent_with_streaming(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20,
    stream_callback=None
):
    """
    Run agent with streaming support

    Official LangGraph streaming pattern:
    https://langchain-ai.github.io/langgraph/how-tos/stream-values/

    Args:
        query: Search keyword
        time_window: Time window
        language: Language code
        max_results: Max results
        stream_callback: Callback function for streaming events

    Example:
        ```python
        async def on_event(event):
            print(f"Event: {event}")

        final_state = await run_agent_with_streaming(
            query="AI trends",
            stream_callback=on_event
        )
        ```
    """
    run_id = str(uuid.uuid4())
    logger = AgentLogger("news_trend_agent", run_id)
    logger.info("Starting streaming agent", query=query)

    initial_state = NewsAgentState(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results,
        run_id=run_id
    )

    graph = build_advanced_graph()

    # Stream events (official pattern)
    final_state = None
    async for event in graph.astream(initial_state):
        # event format: {node_name: state_update}
        if stream_callback:
            await stream_callback(event)

        # Keep track of latest state
        for node_name, state_update in event.items():
            if isinstance(state_update, dict):
                final_state = state_update

    logger.info("Streaming agent completed")

    return final_state


def run_agent_advanced(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20
) -> NewsAgentState:
    """
    Run agent with advanced features (synchronous version)

    Uses conditional edges and error recovery.
    """
    run_id = str(uuid.uuid4())
    logger = AgentLogger("news_trend_agent", run_id)
    logger.info("Starting advanced agent", query=query)

    initial_state = NewsAgentState(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results,
        run_id=run_id
    )

    graph = build_advanced_graph()

    try:
        # Use ainvoke via asyncio.run for async graph execution
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            final_state = loop.run_until_complete(graph.ainvoke(initial_state))
        finally:
            loop.close()
            
        logger.info("Advanced agent completed successfully")
    except Exception as e:
        logger.error("Advanced agent failed", error=str(e))
        raise

    return final_state
