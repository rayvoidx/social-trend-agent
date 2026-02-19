"""
LangGraph 스트리밍 유틸리티

graph.stream()을 활용하여 노드별 진행 이벤트를 발행합니다.
graph.stream()은 동기 함수이므로 ThreadPoolExecutor에서 실행하고,
asyncio.run_coroutine_threadsafe()로 이벤트를 발행합니다.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional

from src.api.streaming import stream_manager, StreamEvent

logger = logging.getLogger(__name__)

# 에이전트별 노드 순서 (progress 계산용)
AGENT_NODE_ORDER: Dict[str, list] = {
    "news_trend_agent": [
        "router", "collect", "plan", "normalize",
        "analyze", "summarize", "critic", "report", "notify",
    ],
    "viral_video_agent": [
        "router", "collect", "plan", "normalize",
        "analyze", "summarize", "critic", "report", "notify",
    ],
    "social_trend_agent": [
        "router", "collect", "plan", "normalize",
        "analyze", "summarize", "critic", "report", "notify",
    ],
}

# 노드별 한국어 라벨
NODE_LABELS: Dict[str, str] = {
    "router": "라우팅",
    "collect": "데이터 수집",
    "plan": "실행 계획",
    "normalize": "데이터 정규화",
    "analyze": "감성/키워드 분석",
    "rag": "RAG 검색",
    "summarize": "인사이트 요약",
    "critic": "품질 검토",
    "report": "리포트 생성",
    "notify": "알림 전송",
}

# Thread pool for blocking graph.stream() calls
_executor = ThreadPoolExecutor(max_workers=4)


def _extract_preview(node_name: str, output: Any) -> Dict[str, Any]:
    """노드별 미리보기 데이터 추출"""
    preview: Dict[str, Any] = {}

    if not isinstance(output, dict):
        return preview

    if node_name == "collect":
        items = output.get("raw_items", [])
        preview["items_collected"] = len(items) if isinstance(items, list) else 0

    elif node_name == "normalize":
        items = output.get("normalized", [])
        preview["items_normalized"] = len(items) if isinstance(items, list) else 0

    elif node_name == "analyze":
        analysis = output.get("analysis", {})
        if isinstance(analysis, dict):
            sentiment = analysis.get("sentiment", {})
            if isinstance(sentiment, dict):
                preview["sentiment"] = {
                    k: sentiment.get(k, 0) for k in ("positive", "neutral", "negative")
                }
            keywords = analysis.get("keywords", {})
            if isinstance(keywords, dict):
                top_kw = keywords.get("top_keywords", [])
                if isinstance(top_kw, list):
                    preview["keyword_count"] = len(top_kw)

    elif node_name == "summarize":
        analysis = output.get("analysis", {})
        if isinstance(analysis, dict):
            summary = analysis.get("summary", "")
            if isinstance(summary, str) and summary:
                preview["summary_length"] = len(summary)
                preview["summary_preview"] = summary[:100]

    elif node_name == "report":
        report = output.get("report_md", "")
        if isinstance(report, str):
            preview["report_length"] = len(report)

    return preview


def _run_graph_stream_sync(
    task_id: str,
    agent_name: str,
    graph: Any,
    initial_state: Any,
    config: Dict[str, Any],
    loop: asyncio.AbstractEventLoop,
) -> Dict[str, Any]:
    """
    동기 함수: graph.stream()을 실행하며 노드별 이벤트 발행

    ThreadPoolExecutor에서 실행됩니다.
    """
    node_order = AGENT_NODE_ORDER.get(agent_name, [])
    total_nodes = len(node_order)
    completed_count = 0
    final_state = {}

    try:
        for event in graph.stream(initial_state, config=config):
            # event is a dict: {node_name: output_dict}
            if not isinstance(event, dict):
                continue

            for node_name, output in event.items():
                if node_name == "__end__":
                    continue

                completed_count += 1
                index = completed_count
                if node_name in node_order:
                    index = node_order.index(node_name) + 1

                preview = _extract_preview(node_name, output)
                label = NODE_LABELS.get(node_name, node_name)

                se = StreamEvent(
                    event="node_complete",
                    data={
                        "node": node_name,
                        "label": label,
                        "index": index,
                        "total": total_nodes,
                        "progress": round(index / total_nodes * 100),
                        "preview": preview,
                    },
                )

                # Emit event to async stream manager from sync thread
                asyncio.run_coroutine_threadsafe(
                    stream_manager.emit(task_id, se), loop
                )

                # Track final state
                if isinstance(output, dict):
                    final_state.update(output)

    except Exception as e:
        se = StreamEvent(
            event="error",
            data={"error": str(e)},
        )
        asyncio.run_coroutine_threadsafe(
            stream_manager.emit(task_id, se), loop
        )
        raise

    return final_state


async def run_agent_with_streaming(
    task_id: str,
    agent_name: str,
    run_fn: Any,
    query: str,
    params: Dict[str, Any],
) -> Any:
    """
    스트리밍 래퍼: 에이전트를 실행하면서 노드별 이벤트를 발행

    기존 run_agent()를 graph.stream()으로 대체하여 실시간 이벤트를 발행합니다.
    run_fn이 graph.stream()을 지원하면 스트리밍, 아니면 기존 invoke 방식 사용.

    Args:
        task_id: 태스크 ID
        agent_name: 에이전트 이름
        run_fn: 에이전트의 run_agent 함수
        query: 검색 쿼리
        params: 추가 파라미터
    """
    loop = asyncio.get_event_loop()

    # Emit start event
    await stream_manager.emit(task_id, StreamEvent(
        event="started",
        data={"agent_name": agent_name, "query": query},
    ))

    try:
        # Try streaming approach: build graph and use stream()
        if agent_name == "news_trend_agent":
            from src.agents.news_trend.graph import build_graph
            from src.core.state import NewsAgentState
            import uuid

            run_id = params.get("run_id") or str(uuid.uuid4())
            initial_state = NewsAgentState(
                query=query,
                time_window=params.get("time_window", "7d"),
                language=params.get("language", "ko"),
                max_results=params.get("max_results", 20),
                orchestrator=params.get("orchestrator"),
                run_id=run_id,
                report_md=None,
                error=None,
            )

            graph = build_graph(checkpointer=None)
            config = {"configurable": {"thread_id": run_id}}

            # Run graph.stream() in thread pool
            final_state = await loop.run_in_executor(
                _executor,
                _run_graph_stream_sync,
                task_id, agent_name, graph, initial_state, config, loop,
            )

            # Reconstruct state
            if isinstance(final_state, dict):
                result_state = NewsAgentState(**{**initial_state.model_dump(), **final_state})
            else:
                result_state = final_state

            return result_state

        else:
            # Fallback: run normally without streaming for other agents
            result = run_fn(query=query, **params)
            return result

    except Exception as e:
        await stream_manager.emit(task_id, StreamEvent(
            event="error",
            data={"error": str(e)},
        ))
        raise
