from __future__ import annotations

import os
import json
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from src.core.state import SocialTrendAgentState
from src.core.logging import AgentLogger
from src.core.errors import safe_api_call
from src.core.config import get_config_manager
from src.agents.social_trend.tools import (
    fetch_x_posts,
    fetch_instagram_posts,
    fetch_naver_blog_posts,
    fetch_rss_feeds,
    normalize_items,
    analyze_sentiment_and_keywords,
)
from src.integrations.llm import get_llm_client
from src.integrations.retrieval.vectorstore_pinecone import PineconeVectorStore

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "social_trend_agent"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _get_llm_client():
    """Social Trend 에이전트 전용 LLM 클라이언트를 가져옵니다."""
    try:
        return get_llm_client(agent_name="social_trend_agent")
    except Exception as e:
        logger.warning(f"Failed to initialize LLM client: {e}")
        return None


def _get_vector_store():
    """Social Trend 에이전트 전용 벡터 스토어를 가져옵니다."""
    try:
        cfg = get_config_manager()
        agent_cfg = cfg.get_agent_config("social_trend_agent")
        vs_cfg = agent_cfg.vector_store if agent_cfg and agent_cfg.vector_store else {}
        index_name = vs_cfg.get("index_name", "social-trend-index")
        return PineconeVectorStore(index_name=index_name)
    except Exception as e:
        logger.warning(f"Failed to initialize vector store: {e}")
        return None


def _generate_llm_insights(
    query: str,
    normalized: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    sources: List[str],
    time_window: str
) -> str:
    """LLM을 사용하여 심층 인사이트를 생성합니다"""
    llm_client = _get_llm_client()
    if not llm_client:
        return "LLM을 사용할 수 없어 인사이트를 생성하지 못했습니다."

    try:
        from src.agents.social_trend.prompts import SUMMARIZE_PROMPT_TEMPLATE

        # Prepare data for LLM
        sentiment = analysis.get("sentiment", {})
        keywords_data = analysis.get("keywords", {})
        top_keywords = keywords_data.get("top_keywords", [])

        keywords_str = "\n".join([
            f"- {kw['keyword']}: {kw['count']}회 언급"
            for kw in top_keywords[:10]
        ])

        social_items_str = "\n\n".join([
            f"[{item.get('source', 'Unknown')}] {item.get('title', '')}\n{item.get('content', '')[:200]}..."
            for item in normalized[:15]
        ])

        prompt = SUMMARIZE_PROMPT_TEMPLATE.format(
            query=query,
            time_window=time_window,
            sources=", ".join(sources),
            item_count=len(normalized),
            positive=sentiment.get("positive_pct", 0),
            neutral=sentiment.get("neutral_pct", 0),
            negative=sentiment.get("negative_pct", 0),
            keywords=keywords_str,
            social_items=social_items_str
        )

        return llm_client.invoke(prompt)

    except Exception as e:
        logger.warning(f"LLM insight generation failed: {e}")
        return f"인사이트 생성 중 오류가 발생했습니다: {str(e)}"


# =============================================================================
# LangGraph Node Functions
# =============================================================================

def collect_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """소셜 미디어 데이터 수집 노드"""
    agent_logger = AgentLogger("social_trend_agent", state.run_id)
    agent_logger.node_start("collect")

    all_items = []
    max_per_platform = state.max_results_per_platform // len(state.platforms) if state.platforms else 10

    for platform in state.platforms:
        try:
            if platform == "x":
                items = safe_api_call(
                    fetch_x_posts,
                    state.query,
                    max_results=max_per_platform,
                    default=[]
                )
            elif platform == "instagram":
                items = safe_api_call(
                    fetch_instagram_posts,
                    state.query,
                    max_results=max_per_platform,
                    default=[]
                )
            elif platform == "naver_blog":
                items = safe_api_call(
                    fetch_naver_blog_posts,
                    state.query,
                    max_results=max_per_platform,
                    default=[]
                )
            else:
                items = []

            if items:
                all_items.extend(items)
                logger.info(f"Collected {len(items)} items from {platform}")
            else:
                logger.info(f"No items collected from {platform}")

        except Exception as e:
            logger.error(f"Error collecting from {platform}: {e}")

    # RSS feeds
    if state.include_rss:
        feeds = state.rss_feeds or [
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            "https://www.reddit.com/r/MachineLearning/.rss",
        ]
        rss_items = safe_api_call(
            fetch_rss_feeds,
            feeds,
            max_results=max_per_platform,
            default=[]
        )
        if rss_items:
            all_items.extend(rss_items)

    agent_logger.node_end("collect", {"items_count": len(all_items)})
    return {"raw_items": all_items}


def normalize_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """데이터 정규화 노드"""
    agent_logger = AgentLogger("social_trend_agent", state.run_id)
    agent_logger.node_start("normalize")

    normalized = normalize_items(state.raw_items)

    agent_logger.node_end("normalize", {"normalized_count": len(normalized)})
    return {"normalized": normalized}


def analyze_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """감성 및 키워드 분석 노드 (Pinecone RAG 지원)"""
    agent_logger = AgentLogger("social_trend_agent", state.run_id)
    agent_logger.node_start("analyze")

    texts = [
        it.get("title", "") + "\n" + it.get("content", "")
        for it in state.normalized
    ]
    analysis = analyze_sentiment_and_keywords(texts)

    # Extract engagement stats per platform
    engagement_stats = {}
    for item in state.normalized:
        platform = item.get("source", "unknown")
        if platform not in engagement_stats:
            engagement_stats[platform] = {"count": 0, "total_engagement": 0}
        engagement_stats[platform]["count"] += 1

    # Index items in Pinecone for RAG
    try:
        llm_client = _get_llm_client()
        vector_store = _get_vector_store()

        if llm_client and vector_store and state.normalized:
            import hashlib
            # Build corpus
            ids = [hashlib.md5(t.encode()).hexdigest()[:12] for t in texts]
            vectors = llm_client.get_embeddings_batch(texts)

            # Prepare metadata
            metadatas = []
            for i, item in enumerate(state.normalized):
                meta = {
                    "index": i,
                    "title": item.get("title", "")[:500],
                    "source": item.get("source", ""),
                    "url": item.get("url", "")[:500]
                }
                metadatas.append(meta)

            # Upsert to Pinecone
            vector_store.upsert(ids, vectors, metadatas)
            logger.info(f"Indexed {len(ids)} items to Pinecone for social_trend_agent")

    except Exception as e:
        logger.warning(f"Failed to index items to Pinecone: {e}")

    agent_logger.node_end("analyze", {"sentiment": analysis.get("sentiment", {})})
    return {
        "analysis": analysis,
        "engagement_stats": engagement_stats
    }


def summarize_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """LLM 기반 인사이트 생성 노드"""
    agent_logger = AgentLogger("social_trend_agent", state.run_id)
    agent_logger.node_start("summarize")

    llm_insights = _generate_llm_insights(
        query=state.query,
        normalized=state.normalized,
        analysis=state.analysis,
        sources=state.platforms,
        time_window=state.time_window or "7d"
    )

    summary = _make_summary(state.analysis)
    updated_analysis = {
        **state.analysis,
        "summary": summary,
        "llm_insights": llm_insights
    }

    agent_logger.node_end("summarize")
    return {"analysis": updated_analysis}


def report_node(state: SocialTrendAgentState) -> Dict[str, Any]:
    """리포트 생성 노드"""
    agent_logger = AgentLogger("social_trend_agent", state.run_id)
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
        state.analysis.get("llm_insights", "")
    )

    agent_logger.node_end("report", {"report_path": str(report_path)})
    return {
        "metrics": metrics,
        "report_md": str(report_path)
    }


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph() -> StateGraph:
    """Social Trend Agent 그래프 빌드"""
    graph = StateGraph(SocialTrendAgentState)

    # Add nodes
    graph.add_node("collect", collect_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("report", report_node)

    # Add edges
    graph.set_entry_point("collect")
    graph.add_edge("collect", "normalize")
    graph.add_edge("normalize", "analyze")
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "report")
    graph.add_edge("report", END)

    return graph


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
) -> SocialTrendAgentState:
    """
    Social Trend Agent 실행

    Args:
        query: 검색어
        sources: 수집할 소스 플랫폼 목록
        rss_feeds: RSS 피드 URL 목록
        time_window: 시간 범위
        language: 언어 코드
        max_results: 최대 결과 수

    Returns:
        최종 상태
    """
    if sources is None:
        sources = ["x", "instagram", "naver_blog"]

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
        run_id=run_id
    )

    # Build and compile graph
    graph = build_graph()
    compiled = graph.compile()

    # Execute
    logger.info(f"Starting Social Trend Agent run: {run_id}")
    final_state = compiled.invoke(initial_state)

    logger.info(f"Completed Social Trend Agent run: {run_id}")
    return SocialTrendAgentState(**final_state)


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
    state = run_agent(query, sources, rss_feeds, time_window, language, max_results)
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
    llm_insights: str = ""
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
    lines.append(f"- **Positive**: {sentiment.get('positive', 0)} ({sentiment.get('positive_pct', 0):.1f}%)")
    lines.append(f"- **Neutral**: {sentiment.get('neutral', 0)} ({sentiment.get('neutral_pct', 0):.1f}%)")
    lines.append(f"- **Negative**: {sentiment.get('negative', 0)} ({sentiment.get('negative_pct', 0):.1f}%)")
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
        title = it.get('title', 'No title')
        url = it.get('url', '')
        source = it.get('source', 'Unknown')
        if url:
            lines.append(f"{i}. [{title}]({url}) - *{source}*")
        else:
            lines.append(f"{i}. {title} - *{source}*")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


