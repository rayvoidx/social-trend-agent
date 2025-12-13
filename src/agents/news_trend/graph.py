"""
뉴스 트렌드 에이전트를 위한 LangGraph 정의

LangGraph 공식 패턴과 에러 핸들링, 로깅 기능을 적용했습니다.
Human-in-the-loop (검토/승인) 워크플로우가 포함되어 있습니다.
"""
import os
import uuid
import logging
from typing import Dict, Any, Optional
import sys
from langgraph.graph import StateGraph, END

from src.core.state import NewsAgentState
from src.core.logging import AgentLogger
from src.core.errors import PartialResult, CompletionStatus, safe_api_call
from src.core.checkpoint import get_checkpointer
from src.core.config import get_config_manager
from src.agents.news_trend.tools import (
    search_news,
    analyze_sentiment,
    extract_keywords,
    summarize_trend,
    retrieve_relevant_items,
    redact_pii,
    check_safety,
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

# Initialize module-level logger (without run_id for module-level logging)
_module_logger = logging.getLogger("news_trend_agent")


def router_node(state: NewsAgentState) -> Dict[str, Any]:
    """Cheap gateway/router node (Compound AI 2025)."""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
    logger.node_start("router")

    route = route_request(
        agent_name="news_trend_agent",
        query=state.query,
        time_window=state.time_window,
        language=state.language,
    )

    # Orchestrator structured DAG overrides (strong binding, backward compatible)
    agent_entry = get_agent_entry(state.orchestrator, "news_trend_agent")
    overrides = derive_execution_overrides(agent_entry)
    if overrides:
        route = {**route, **overrides}

    # Apply small, safe knobs for cost/latency
    suggested_max = route.get("suggested_max_results")
    max_results = state.max_results
    if isinstance(suggested_max, int) and suggested_max > 0:
        max_results = min(max(5, suggested_max), 50)
    # Allow planner to set max_results directly (strong binding)
    if isinstance(route.get("max_results"), int) and route.get("max_results") > 0:
        max_results = min(max(5, int(route["max_results"])), 50)

    suggested_tw = route.get("suggested_time_window")
    time_window = state.time_window
    if isinstance(suggested_tw, str) and suggested_tw.strip():
        time_window = suggested_tw.strip()
    if isinstance(route.get("time_window"), str) and str(route.get("time_window")).strip():
        time_window = str(route.get("time_window")).strip()

    logger.node_end("router")
    return {
        "time_window": time_window,
        "max_results": max_results,
        "analysis": {**(state.analysis or {}), "_routing": route},
        "plan": {"steps": normalize_steps(agent_entry) if agent_entry else []},
    }


def collect_node(state: NewsAgentState) -> Dict[str, Any]:
    # If plan explicitly omits collect, skip it (plan==DAG strong binding)
    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "collect"):
        logger.node_end("collect", output_size=0)
        return {}

    """
    다양한 소스에서 뉴스 데이터 수집
    """
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
    logger.node_start("collect")
    logger.info(f"Collecting news: query={state.query}, time_window={state.time_window}")

    # Use safe_api_call for error handling
    result = PartialResult(status=CompletionStatus.FULL)

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    current_step_id = (state.plan_execution or {}).get("current_step_id") if isinstance(state.plan_execution, dict) else None
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(steps, "collect")
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "collect")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = isinstance(cb, dict) and isinstance(cb.get("failure_threshold"), int) and cb.get("failure_threshold", 0) > 0

    raw_items = safe_api_call(
        "search_news",
        search_news,
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

    logger.node_end("collect", output_size=len(raw_items))

    return {
        "raw_items": raw_items,
        "error": result.errors[0] if result.errors else None
    }


def normalize_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    수집된 데이터 정규화 및 정제
    """
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
    logger.node_start("normalize", input_size=len(state.raw_items))

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "normalize"):
        logger.node_end("normalize", output_size=len(state.normalized))
        return {}

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
    """
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
    logger.node_start("analyze", input_size=len(state.normalized))

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "analyze"):
        logger.node_end("analyze", output_size=len(state.normalized))
        return {}

    current_step_id = (state.plan_execution or {}).get("current_step_id") if isinstance(state.plan_execution, dict) else None
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(steps, "analyze")
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "analyze")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = isinstance(cb, dict) and isinstance(cb.get("failure_threshold"), int) and cb.get("failure_threshold", 0) > 0

    # Analyze sentiment with error handling
    result_sentiment = PartialResult(status=CompletionStatus.FULL)
    sentiment_results = safe_api_call(
        "analyze_sentiment",
        analyze_sentiment,
        items=state.normalized,
        fallback_value={"positive": 0, "neutral": 0, "negative": 0},
        result_container=result_sentiment,
        retry_policy=rp,
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
    )

    # Extract keywords with error handling
    result_keywords = PartialResult(status=CompletionStatus.FULL)
    keyword_results = safe_api_call(
        "extract_keywords",
        extract_keywords,
        items=state.normalized,
        fallback_value={"top_keywords": [], "total_unique_keywords": 0},
        result_container=result_keywords,
        retry_policy=rp,
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
    )

    analysis = {
        "sentiment": sentiment_results,
        "keywords": keyword_results,
        "total_items": len(state.normalized)
    }

    logger.node_end("analyze", output_size=len(state.normalized))

    return {"analysis": analysis}


def rag_node(state: NewsAgentState) -> Dict[str, Any]:
    """
    Optional explicit RAG step for plan runner.
    Stores selected relevant items into analysis['_rag_relevant'].
    """
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
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
    """
    LLM을 활용한 트렌드 인사이트 요약
    """
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
    logger.node_start("summarize")

    # Use LLM to summarize trend with error handling
    result = PartialResult(status=CompletionStatus.FULL)
    # Retrieve relevant subset (RAG) - controlled by tool plan (rag_mode/top_k)
    routed = (state.analysis or {}).get("_routing", {}) if isinstance(state.analysis, dict) else {}
    rag_mode = str(routed.get("rag_mode") or "graph").lower()
    rag_top_k = routed.get("rag_top_k")
    top_k = int(rag_top_k) if isinstance(rag_top_k, int) and rag_top_k > 0 else min(10, len(state.normalized))

    # If plan has no rag step, force no-rag (strong binding)
    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    if isinstance(steps, list) and steps and not has_step(steps, "rag"):
        rag_mode = "none"

    # If rag_node already computed a subset, reuse it
    cached = (state.analysis or {}).get("_rag_relevant") if isinstance(state.analysis, dict) else None
    if isinstance(cached, list) and cached:
        relevant = cached
    else:
        if rag_mode == "none":
            relevant = state.normalized[: max(1, top_k)]
        else:
            use_graph = rag_mode != "vector"
            relevant = retrieve_relevant_items(state.query, state.normalized, top_k, use_graph=use_graph)

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    current_step_id = (state.plan_execution or {}).get("current_step_id") if isinstance(state.plan_execution, dict) else None
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(steps, "summarize")
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "summarize")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = isinstance(cb, dict) and isinstance(cb.get("failure_threshold"), int) and cb.get("failure_threshold", 0) > 0

    # summarize_trend is @backoff_retry-decorated; pass plan policy through to decorator to avoid double-retry
    raw_summary = safe_api_call(
        "summarize_trend",
        summarize_trend,
        query=state.query,
        normalized_items=relevant,
        analysis=state.analysis,
        strategy=str((state.analysis or {}).get("_routing", {}).get("summary_strategy", "auto")),
        fallback_value="트렌드 요약을 생성할 수 없습니다. LLM 서비스를 확인하세요.",
        result_container=result,
        retry_policy={"max_retries": 0, "backoff_seconds": 0.0, "jitter": False},
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
        __plan_retry_policy=rp,
        __plan_timeout_seconds=timeout_s,
        __plan_step_id=current_step_id,
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
    """
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
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
                f"",
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
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
    logger.node_start("plan")
    # plan must be a Dict (AgentState.plan is Dict[str, Any])
    plan_steps = [
        "Collect",
        "Normalize",
        "Analyze",
        "RAG",
        "Summarize+Guard",
        "Report+Notify",
    ]
    logger.node_end("plan")
    return {"plan": {"steps": plan_steps, "display": plan_steps}}


def critic_node(state: NewsAgentState) -> Dict[str, Any]:
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
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
    """
    run_id = state.run_id or "unknown"
    logger = AgentLogger("news_trend_agent", run_id)
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


def build_graph(checkpointer: Optional[Any] = None):
    """
    뉴스 트렌드 에이전트용 LangGraph 구축
    
    Args:
        checkpointer: 상태 저장을 위한 체크포인터 (선택 사항)
    """
    _module_logger.info("Building LangGraph for News Trend Agent")

    # Create StateGraph with NewsAgentState
    graph = StateGraph(NewsAgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("collect", collect_node)
    graph.add_node("plan", plan_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("critic", critic_node)
    graph.add_node("report", report_node)
    graph.add_node("notify", notify_node)

    # Set entry point
    graph.set_entry_point("router")

    # Add edges
    graph.add_edge("router", "collect")
    graph.add_edge("collect", "plan")
    graph.add_edge("plan", "normalize")
    graph.add_edge("normalize", "analyze")
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "critic")
    graph.add_edge("critic", "report")
    graph.add_edge("report", "notify")
    graph.add_edge("notify", END)

    # Compile graph with checkpointer and interrupt logic
    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["report"] if checkpointer else None
    )

    _module_logger.info(f"LangGraph compiled (HITL: {bool(checkpointer)})")

    return compiled_graph


def run_agent(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20,
    run_id: Optional[str] = None,
    require_approval: bool = True,
    orchestrator: Optional[Dict[str, Any]] = None,
) -> NewsAgentState:
    """
    뉴스 트렌드 에이전트 실행 (HITL 지원)
    """
    # Generate run_id if not provided
    if not run_id:
        run_id = str(uuid.uuid4())

    logger = AgentLogger("news_trend_agent", run_id)
    logger.info("Starting news trend agent", query=query, time_window=time_window, language=language)

    # Create initial state
    initial_state = NewsAgentState(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results,
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
    agent_entry = get_agent_entry(orchestrator, "news_trend_agent")
    steps = normalize_steps(agent_entry) if agent_entry else []
    if steps:
        graph = build_plan_runner_graph(
            agent_name="news_trend_agent",
            state_cls=NewsAgentState,
            router_node=router_node,
            op_nodes={
                "collect": collect_node,
                "normalize": normalize_node,
                "analyze": analyze_node,
                "rag": rag_node,
                "summarize": summarize_node,
                "report": report_node,
                "notify": notify_node,
            },
            steps=steps,
            checkpointer=checkpointer,
        )
        config = {"configurable": {"thread_id": run_id}}
        try:
            logger.info("Running workflow...")
            current_state = graph.invoke(initial_state, config=config)

            if require_approval:
                snapshot = graph.get_state(config)
                if snapshot.next and "report" in snapshot.next:
                    logger.info("⏸️  Workflow paused for approval before report generation.")
                    print("\n" + "="*50)
                    print("✋  APPROVAL REQUIRED")
                    print("="*50)
                    print(f"Analysis complete for query: '{query}'")
                    print("Summary: " + str(current_state.get("analysis", {}).get("summary", "")[:100]) + "...")
                    print("-" * 50)
                    while True:
                        choice = input("Proceed to generate report? (y/n): ").strip().lower()
                        if choice == 'y':
                            logger.info("✅ Approved. Resuming...")
                            current_state = graph.invoke(None, config=config)
                            break
                        elif choice == 'n':
                            logger.info("🛑 Aborted by user.")
                            return NewsAgentState(**current_state)
                        else:
                            print("Please enter 'y' or 'n'.")

            logger.info("News trend agent completed successfully", run_id=run_id)
            if isinstance(current_state, dict):
                return NewsAgentState(**current_state)
            return current_state
        except Exception as e:
            logger.error("News trend agent failed", error=str(e), run_id=run_id)
            raise
    # Optional: use advanced graph (loop/parallel/conditional edges) for 2025-style execution
    use_advanced = os.getenv("NEWS_TREND_ADVANCED_GRAPH", "").strip().lower() in ("1", "true", "yes", "on")
    if not use_advanced:
        try:
            cfg = get_config_manager()
            agent_cfg = cfg.get_agent_config("news_trend_agent")
            d = agent_cfg.model_dump() if agent_cfg else {}
            use_advanced = bool(d.get("advanced_graph_enabled", False))
        except Exception:
            use_advanced = False

    if use_advanced:
        from src.agents.news_trend.graph_advanced import build_advanced_graph
        graph = build_advanced_graph()
    else:
        graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id}}

    try:
        # 1. Start execution (runs until 'report' interrupt)
        logger.info("Running workflow...")
        current_state = graph.invoke(initial_state, config=config)
        
        # 2. Check for interrupt
        if require_approval:
            snapshot = graph.get_state(config)
            if snapshot.next and "report" in snapshot.next:
                logger.info("⏸️  Workflow paused for approval before report generation.")
                
                # Simple CLI interaction
                print("\n" + "="*50)
                print("✋  APPROVAL REQUIRED")
                print("="*50)
                print(f"Analysis complete for query: '{query}'")
                print("Summary: " + str(current_state.get("analysis", {}).get("summary", "")[:100]) + "...")
                print("-" * 50)
                
                while True:
                    choice = input("Proceed to generate report? (y/n): ").strip().lower()
                    if choice == 'y':
                        logger.info("✅ Approved. Resuming...")
                        current_state = graph.invoke(None, config=config)
                        break
                    elif choice == 'n':
                        logger.info("🛑 Aborted by user.")
                        return NewsAgentState(**current_state) # Return partial state
                    else:
                        print("Please enter 'y' or 'n'.")
        
        logger.info("News trend agent completed successfully", run_id=run_id)
        
        # Ensure result is NewsAgentState
        if isinstance(current_state, dict):
            return NewsAgentState(**current_state)
        return current_state

    except Exception as e:
        logger.error("News trend agent failed", error=str(e), run_id=run_id)
        raise
