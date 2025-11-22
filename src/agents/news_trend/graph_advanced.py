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
from src.agents.news_trend.tools import (
    search_news,
    analyze_sentiment,
    extract_keywords,
    summarize_trend
)

# Initialize module-level logger (without run_id for module-level logging)
_module_logger = logging.getLogger("news_trend_agent_advanced")


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

    result = PartialResult(status=CompletionStatus.FULL)

    raw_items = safe_api_call(
        operation_name="search_news",
        func=search_news,
        query=state.query,
        time_window=state.time_window or "7d",
        language=state.language,
        max_results=state.max_results,
        fallback_value=[],
        result_container=result
    )

    # Determine retry count
    retry_count = getattr(state, 'retry_count', 0)

    logger.node_end("collect", output_size=len(raw_items), status=result.status.value)

    return {
        "raw_items": raw_items,
        "error": result.error if result.status == CompletionStatus.FAILED else None,
        "retry_count": retry_count + 1 if result.status == CompletionStatus.FAILED else 0
    }


def normalize_node(state: NewsAgentState) -> Dict[str, Any]:
    """Normalize and clean collected data"""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("normalize", raw_count=len(state.raw_items))

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

    # Define async wrappers
    async def analyze_sentiment_async():
        """Async wrapper for sentiment analysis"""
        return safe_api_call(
            "analyze_sentiment",
            analyze_sentiment,
            items=state.normalized,
            fallback_value={"positive": 0, "neutral": 0, "negative": 0}
        )

    async def extract_keywords_async():
        """Async wrapper for keyword extraction"""
        return safe_api_call(
            "extract_keywords",
            extract_keywords,
            items=state.normalized,
            fallback_value={"top_keywords": [], "total_unique_keywords": 0}
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


def summarize_node(state: NewsAgentState) -> Dict[str, Any]:
    """Summarize trend insights using LLM"""
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("summarize")

    result = PartialResult(status=CompletionStatus.FULL)
    summary = safe_api_call(
        operation_name="summarize_trend",
        func=summarize_trend,
        query=state.query,
        normalized_items=state.normalized,
        analysis=state.analysis,
        fallback_value="트렌드 요약을 생성할 수 없습니다.",
        result_container=result
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
        f"- ���립: {sentiment.get('neutral', 0)}건 ({sentiment.get('neutral_pct', 0):.1f}%)",
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
    graph.add_node("collect", collect_node_with_retry)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analyze", parallel_analyze_node)  # Async parallel execution
    graph.add_node("summarize", summarize_node)
    graph.add_node("report", report_node)
    graph.add_node("notify", notify_node)

    # Set entry point
    graph.set_entry_point("collect")

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
        final_state = graph.invoke(initial_state)
        logger.info("Advanced agent completed successfully")
    except Exception as e:
        logger.error("Advanced agent failed", error=str(e))
        raise

    return final_state
