"""
뉴스 트렌드 에이전트를 위한 LangGraph 정의

LangGraph 공식 패턴과 에러 핸들링, 로깅 기능을 적용했습니다.
"""
import os
import uuid
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from src.core.state import NewsAgentState
from src.core.logging import AgentLogger
from src.core.errors import PartialResult, CompletionStatus, safe_api_call
from src.agents.news_trend.tools import (
    search_news,
    analyze_sentiment,
    extract_keywords,
    summarize_trend,
    retrieve_relevant_items,
    redact_pii,
    check_safety,
)

# Initialize module-level logger (without run_id for module-level logging)
_module_logger = logging.getLogger("news_trend_agent")


def collect_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    다양한 소스에서 뉴스 데이터 수집

    에러 핸들링을 통해 API 실패를 우아하게 처리합니다.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("collect")
    logger.info(f"Collecting news: query={state.query}, time_window={state.time_window}")

    # Use safe_api_call for error handling
    result = PartialResult(status=CompletionStatus.FULL)

    raw_items = safe_api_call(
        "search_news",
        search_news,
        query=state.query,
        time_window=state.time_window or "7d",
        language=state.language,
        max_results=state.max_results,
        fallback_value=[],
        result_container=result
    )

    logger.node_end("collect", output_size=len(raw_items))

    return {
        "raw_items": raw_items,
        "error": result.errors[0] if result.errors else None
    }


def normalize_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    수집된 데이터 정규화 및 정제

    다운스트림 노드를 위한 일관된 데이터 구조를 보장합니다.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("normalize", input_size=len(state.raw_items))

    normalized = []
    for item in state.raw_items:
        # Clean HTML tags and normalize fields
        normalized.append({
            "title": item.get("title", "").strip(),
            "description": item.get("description", "").strip(),
            "url": item.get("url", ""),
            "source": item.get("source", {}).get("name", "Unknown") if isinstance(item.get("source"), dict) else str(item.get("source", "Unknown")),
            "published_at": item.get("publishedAt", ""),
            "content": item.get("content", "").strip()
        })

    logger.node_end("normalize", output_size=len(normalized))

    return {"normalized": normalized}


def analyze_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    감성 분석 및 키워드 추출

    감성 분석과 키워드 추출을 개념적으로 병렬 실행합니다.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("analyze", input_size=len(state.normalized))

    # Analyze sentiment with error handling
    result_sentiment = PartialResult(status=CompletionStatus.FULL)
    sentiment_results = safe_api_call(
        "analyze_sentiment",
        analyze_sentiment,
        items=state.normalized,
        fallback_value={"positive": 0, "neutral": 0, "negative": 0},
        result_container=result_sentiment
    )

    # Extract keywords with error handling
    result_keywords = PartialResult(status=CompletionStatus.FULL)
    keyword_results = safe_api_call(
        "extract_keywords",
        extract_keywords,
        items=state.normalized,
        fallback_value={"top_keywords": [], "total_unique_keywords": 0},
        result_container=result_keywords
    )

    analysis = {
        "sentiment": sentiment_results,
        "keywords": keyword_results,
        "total_items": len(state.normalized)
    }

    logger.node_end("analyze", output_size=len(state.normalized))

    return {"analysis": analysis}


def summarize_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    LLM을 활용한 트렌드 인사이트 요약

    견고한 LLM 호출을 위해 LangChain과 재시도 로직을 사용합니다.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("summarize")

    # Use LLM to summarize trend with error handling
    result = PartialResult(status=CompletionStatus.FULL)
    # Retrieve relevant subset (RAG)
    relevant = retrieve_relevant_items(state.query, state.normalized, min(10, len(state.normalized)))

    raw_summary = safe_api_call(
        "summarize_trend",
        summarize_trend,
        query=state.query,
        normalized_items=relevant,
        analysis=state.analysis,
        fallback_value="트렌드 요약을 생성할 수 없습니다. LLM 서비스를 확인하세요.",
        result_container=result
    )

    # Guardrails
    pii = redact_pii(raw_summary)
    safety = check_safety(pii["redacted"]) if isinstance(pii, dict) else {"unsafe": False, "categories": []}
    summary = pii["redacted"] if isinstance(pii, dict) else raw_summary

    logger.node_end("summarize", output_size=len(summary))

    return {"analysis": {**state.analysis, "summary": summary, "safety": safety}}


def report_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    마크다운 리포트 생성

    마크다운 형식의 종합 분석 리포트를 생성합니다.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("report")

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
    ])

    analysis = state.analysis if isinstance(state.analysis, dict) else {}
    safety = analysis.get("safety", {})
    if safety:  # dict가 비어있지 않으면
        if safety.get("pii_found") or safety.get("unsafe"):
            report_lines.extend([
                f"---",
                f"",
                f"## 🔒 안전 및 프라이버시",
                f"- 일부 PII 정보가 마스킹되었습니다." if safety.get("pii_found") else "",
                f"- 안전 카테고리 감지: {', '.join(safety.get('categories', []))}" if safety.get("unsafe") else "",
                f"",
            ])

    report_lines.extend([
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

    logger.node_end("report", output_size=len(report_md))

    return {"report_md": report_md, "metrics": metrics}


def plan_node(state: NewsAgentState) -> Dict[str, Any]:
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("plan")
    plan = [
        "Collect",
        "Normalize",
        "Analyze",
        "RAG",
        "Summarize+Guard",
        "Report+Notify",
    ]
    logger.node_end("plan")
    return {"plan": plan}


def critic_node(state: NewsAgentState) -> Dict[str, Any]:
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("critic")
    analysis = state.analysis or {}
    review = {
        "has_sentiment": "sentiment" in analysis,
        "has_keywords": "keywords" in analysis,
        "has_summary": bool(analysis.get("summary")),
    }
    logger.node_end("critic")
    return {"review": review}


def notify_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    알림 전송 (n8n, Slack 등)

    설정된 웹훅 엔드포인트로 분석 결과를 전송합니다.
    """
    logger = AgentLogger("news_trend_agent", state.run_id)
    logger.node_start("notify")

    notifications_sent = []

    # n8n webhook
    n8n_webhook = os.getenv("N8N_WEBHOOK_URL")
    if n8n_webhook:
        try:
            import requests
            payload = {
                "query": state.query,
                "metrics": state.metrics,
                "run_id": state.run_id,
                "summary": state.analysis.get("summary", "")[:500]  # First 500 chars
            }
            response = requests.post(n8n_webhook, json=payload, timeout=10)
            if response.status_code == 200:
                notifications_sent.append("n8n")
                logger.info("n8n notification sent successfully")
        except Exception as e:
            logger.warning("Failed to send n8n notification", error=str(e))

    # Slack webhook
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    if slack_webhook:
        try:
            import requests
            payload = {
                "text": f"📊 트렌드 분석 완료: {state.query}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*검색어*: {state.query}\n*분석 항목*: {len(state.normalized)}건"
                        }
                    }
                ]
            }
            response = requests.post(slack_webhook, json=payload, timeout=10)
            if response.status_code == 200:
                notifications_sent.append("slack")
                logger.info("Slack notification sent successfully")
        except Exception as e:
            logger.warning("Failed to send Slack notification", error=str(e))

    logger.node_end("notify", output_size=len(notifications_sent))

    return {}


def build_graph():
    """
    뉴스 트렌드 에이전트용 LangGraph 구축

    LangGraph 공식 패턴을 따릅니다:
    - Pydantic 상태 모델을 사용하는 StateGraph
    - 에러 핸들링을 포함한 순차적 파이프라인
    - 에러 복구를 위한 조건부 엣지 (향후 개선 예정)

    Returns:
        실행 준비가 완료된 컴파일된 StateGraph
    """
    _module_logger.info("Building LangGraph for News Trend Agent")

    # Create StateGraph with NewsAgentState (official pattern)
    graph = StateGraph(NewsAgentState)

    # Add nodes (official pattern: node_name, node_function)
    graph.add_node("collect", collect_node)
    graph.add_node("plan", plan_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("critic", critic_node)
    graph.add_node("report", report_node)
    graph.add_node("notify", notify_node)

    # Set entry point (official pattern)
    graph.set_entry_point("collect")

    # Add edges for sequential pipeline (official pattern)
    graph.add_edge("collect", "plan")
    graph.add_edge("plan", "normalize")
    graph.add_edge("normalize", "analyze")
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "critic")
    graph.add_edge("critic", "report")
    graph.add_edge("report", "notify")
    graph.add_edge("notify", END)

    # Compile graph (official pattern - required before execution)
    compiled_graph = graph.compile()

    _module_logger.info("LangGraph built and compiled successfully")

    return compiled_graph


def run_agent(query: str, time_window: str = "7d", language: str = "ko", max_results: int = 20) -> NewsAgentState:
    """
    뉴스 트렌드 에이전트 실행

    LangGraph 공식 패턴을 따르는 메인 진입점입니다.

    Args:
        query: 검색 키워드
        time_window: 시간 범위 (예: "24h", "7d", "30d")
        language: 언어 코드 ("ko", "en")
        max_results: 최대 결과 수

    Returns:
        리포트와 메트릭을 포함한 최종 상태
    """
    # Generate run_id
    run_id = str(uuid.uuid4())

    logger = AgentLogger("news_trend_agent", run_id)
    logger.info("Starting news trend agent", query=query, time_window=time_window, language=language)

    # Create initial state (official pattern: Pydantic model)
    initial_state = NewsAgentState(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results,
        run_id=run_id
    )

    # Build and compile graph
    graph = build_graph()

    # Invoke graph (official pattern: invoke() for synchronous execution)
    try:
        final_state = graph.invoke(initial_state)
        logger.info("News trend agent completed successfully", run_id=run_id)
    except Exception as e:
        logger.error("News trend agent failed", error=str(e), run_id=run_id)
        raise

    return final_state
