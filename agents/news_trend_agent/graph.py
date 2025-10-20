"""
LangGraph definition for News Trend Agent
"""
import os
import uuid
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI

from agents.shared.state import NewsAgentState
from agents.news_trend_agent.tools import (
    search_news,
    analyze_sentiment,
    extract_keywords,
    summarize_trend
)


def collect_node(state: NewsAgentState) -> Dict[str, Any]:
    """Collect news data from various sources"""
    print(f"[collect_node] query={state.query}, time_window={state.time_window}")

    # Search news using the tool
    raw_items = search_news(
        query=state.query,
        time_window=state.time_window or "7d",
        language=state.language,
        max_results=state.max_results
    )

    return {"raw_items": raw_items}


def normalize_node(state: NewsAgentState) -> Dict[str, Any]:
    """Normalize and clean collected data"""
    print(f"[normalize_node] raw_items count={len(state.raw_items)}")

    normalized = []
    for item in state.raw_items:
        normalized.append({
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": item.get("source", {}).get("name", "Unknown"),
            "published_at": item.get("publishedAt", ""),
            "content": item.get("content", "")
        })

    return {"normalized": normalized}


def analyze_node(state: NewsAgentState) -> Dict[str, Any]:
    """Analyze sentiment and extract keywords"""
    print(f"[analyze_node] normalized count={len(state.normalized)}")

    # Analyze sentiment
    sentiment_results = analyze_sentiment(state.normalized)

    # Extract keywords
    keyword_results = extract_keywords(state.normalized)

    analysis = {
        "sentiment": sentiment_results,
        "keywords": keyword_results,
        "total_items": len(state.normalized)
    }

    return {"analysis": analysis}


def summarize_node(state: NewsAgentState) -> Dict[str, Any]:
    """Summarize trend insights"""
    print(f"[summarize_node] analysis={state.analysis}")

    # Use LLM to summarize trend
    summary = summarize_trend(
        query=state.query,
        normalized_items=state.normalized,
        analysis=state.analysis
    )

    return {"analysis": {**state.analysis, "summary": summary}}


def report_node(state: NewsAgentState) -> Dict[str, Any]:
    """Generate markdown report"""
    print(f"[report_node] Generating report...")

    # Build markdown report
    report_lines = [
        f"# 뉴스 트렌드 분석 리포트",
        f"",
        f"**검색어**: {state.query}",
        f"**기간**: {state.time_window or '7d'}",
        f"**언어**: {state.language}",
        f"**분석 항목 수**: {len(state.normalized)}",
        f"",
        f"---",
        f"",
        f"## 📊 감성 분석",
        f"",
    ]

    sentiment = state.analysis.get("sentiment", {})
    report_lines.extend([
        f"- 긍정: {sentiment.get('positive', 0)}개 ({sentiment.get('positive_pct', 0):.1f}%)",
        f"- 중립: {sentiment.get('neutral', 0)}개 ({sentiment.get('neutral_pct', 0):.1f}%)",
        f"- 부정: {sentiment.get('negative', 0)}개 ({sentiment.get('negative_pct', 0):.1f}%)",
        f"",
        f"---",
        f"",
        f"## 🔑 핵심 키워드",
        f"",
    ])

    keywords = state.analysis.get("keywords", {}).get("top_keywords", [])
    for kw in keywords[:10]:
        report_lines.append(f"- **{kw['keyword']}** ({kw['count']}회)")

    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 💡 주요 인사이트",
        f"",
        state.analysis.get("summary", "No summary available."),
        f"",
        f"---",
        f"",
        f"## 📰 주요 뉴스 (Top 5)",
        f"",
    ])

    for i, item in enumerate(state.normalized[:5], 1):
        report_lines.extend([
            f"### {i}. {item['title']}",
            f"**출처**: [{item['source']}]({item['url']})",
            f"**발행일**: {item['published_at']}",
            f"",
            f"{item['description']}",
            f"",
        ])

    report_lines.extend([
        f"---",
        f"",
        f"**⚠️ 주의**: 본 리포트는 AI가 생성한 분석으로, 사실 확인이 필요합니다.",
        f"출처 링크를 반드시 확인하세요.",
        f"",
        f"**Run ID**: `{state.run_id}`",
        f""
    ])

    report_md = "\n".join(report_lines)

    # Calculate metrics
    metrics = {
        "coverage": len(state.normalized) / max(state.max_results, 1),
        "factuality": 1.0 if all(item.get("url") for item in state.normalized) else 0.0,
        "actionability": 1.0 if state.analysis.get("summary") else 0.0
    }

    return {"report_md": report_md, "metrics": metrics}


def notify_node(state: NewsAgentState) -> Dict[str, Any]:
    """Send notifications (n8n, Slack, etc)"""
    print(f"[notify_node] Sending notifications...")

    # TODO: Implement n8n webhook call
    # TODO: Implement Slack webhook call

    return {}


def build_graph() -> StateGraph:
    """Build LangGraph for News Trend Agent"""

    graph = StateGraph(NewsAgentState)

    # Add nodes
    graph.add_node("collect", collect_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("report", report_node)
    graph.add_node("notify", notify_node)

    # Set entry point
    graph.set_entry_point("collect")

    # Add edges
    graph.add_edge("collect", "normalize")
    graph.add_edge("normalize", "analyze")
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "report")
    graph.add_edge("report", "notify")
    graph.add_edge("notify", END)

    return graph.compile()


def run_agent(query: str, time_window: str = "7d", language: str = "ko", max_results: int = 20) -> NewsAgentState:
    """Run the news trend agent"""

    # Generate run_id
    run_id = str(uuid.uuid4())

    # Create initial state
    initial_state = NewsAgentState(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results,
        run_id=run_id
    )

    # Build and run graph
    graph = build_graph()
    final_state = graph.invoke(initial_state)

    return final_state
