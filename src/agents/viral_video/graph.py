"""
LangGraph definition for Viral Video Agent
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, cast
import sys
from langgraph.graph import StateGraph, END

from src.core.state import ViralAgentState
from src.core.logging import AgentLogger
from src.core.checkpoint import get_checkpointer
from src.core.errors import safe_api_call, PartialResult, CompletionStatus
from src.agents.viral_video.tools import (
    fetch_video_stats,
    detect_spike,
    topic_cluster,
    generate_success_factors,
)
from src.core.gateway import route_request
from src.core.planning.plan import (
    get_agent_entry,
    derive_execution_overrides,
    normalize_steps,
    get_retry_policy_for_step,
    get_retry_policy_for_op,
    get_timeout_for_step,
    get_timeout_for_op,
    get_circuit_breaker_for_step,
)
from src.core.planning.graph import build_plan_runner_graph


def collect_node(state: ViralAgentState) -> Dict[str, Any]:
    """Collect video statistics from platforms"""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("viral_video_agent", run_id)
    logger.node_start("collect", input_size=len(state.platforms))
    logger.info("Collecting video stats", market=state.market, platforms=state.platforms)

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

    raw_items = []

    for platform in state.platforms:
        stats = safe_api_call(
            f"fetch_video_stats_{platform}",
            fetch_video_stats,
            platform=platform,
            market=state.market,
            time_window=state.time_window or "24h",
            fallback_value=[],
            retry_policy=rp,
            timeout_seconds=timeout_s,
            raise_on_fail=strict,
        )
        if isinstance(stats, list):
            raw_items.extend(stats)
        logger.info(
            f"Collected {len(stats) if isinstance(stats, list) else 0} items from {platform}"
        )

    logger.node_end("collect", output_size=len(raw_items))
    return {"raw_items": raw_items}


def router_node(state: ViralAgentState) -> Dict[str, Any]:
    """Cheap gateway/router node (Compound AI 2025)."""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("viral_video_agent", run_id)
    logger.node_start("router")

    route = route_request(
        agent_name="viral_video_agent",
        query=state.query,
        time_window=state.time_window,
        language=None,
    )

    agent_entry = get_agent_entry(state.orchestrator, "viral_video_agent")
    overrides = derive_execution_overrides(agent_entry)
    if overrides:
        route = {**route, **overrides}

    suggested_tw = route.get("suggested_time_window")
    time_window = state.time_window
    if isinstance(suggested_tw, str) and suggested_tw.strip():
        time_window = suggested_tw.strip()
    if isinstance(route.get("time_window"), str) and str(route.get("time_window")).strip():
        time_window = str(route.get("time_window")).strip()

    logger.node_end("router")
    return {
        "time_window": time_window,
        "analysis": {**(state.analysis or {}), "_routing": route},
        "plan": {"steps": normalize_steps(agent_entry) if agent_entry else []},
    }


def normalize_node(state: ViralAgentState) -> Dict[str, Any]:
    """Normalize and clean collected data"""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("viral_video_agent", run_id)
    logger.node_start("normalize", input_size=len(state.raw_items))

    normalized = []
    for item in state.raw_items:
        normalized.append(
            {
                "video_id": item.get("video_id", ""),
                "title": item.get("title", ""),
                "channel": item.get("channel", ""),
                "views": item.get("views", 0),
                "likes": item.get("likes", 0),
                "comments": item.get("comments", 0),
                "published_at": item.get("published_at", ""),
                "platform": item.get("platform", "youtube"),
                "url": item.get("url", ""),
                "thumbnail": item.get("thumbnail", ""),
            }
        )

    logger.node_end("normalize", output_size=len(normalized))
    return {"normalized": normalized}


def analyze_node(state: ViralAgentState) -> Dict[str, Any]:
    """Detect viral spikes and cluster topics"""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("viral_video_agent", run_id)
    logger.node_start("analyze", input_size=len(state.normalized))

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    current_step_id = (
        (state.plan_execution or {}).get("current_step_id")
        if isinstance(state.plan_execution, dict)
        else None
    )
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(
        steps, "analyze"
    )
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(steps, "analyze")
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = (
        isinstance(cb, dict)
        and isinstance(cb.get("failure_threshold"), int)
        and cb.get("failure_threshold", 0) > 0
    )

    result_container = PartialResult(status=CompletionStatus.FULL)

    spike_results = safe_api_call(
        "detect_spike",
        detect_spike,
        items=state.normalized,
        threshold=state.spike_threshold,
        fallback_value={"spike_videos": [], "threshold": state.spike_threshold},
        result_container=result_container,
        retry_policy=rp,
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
    )

    cluster_results = safe_api_call(
        "topic_cluster",
        topic_cluster,
        state.normalized,
        fallback_value={"top_clusters": [], "total_clusters": 0},
        result_container=result_container,
        retry_policy=rp,
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
    )

    analysis = {
        "spikes": spike_results,
        "clusters": cluster_results,
        "total_items": len(state.normalized),
    }

    logger.node_end("analyze")
    return {"analysis": analysis}


def summarize_node(state: ViralAgentState) -> Dict[str, Any]:
    """Generate success factors and insights"""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("viral_video_agent", run_id)
    logger.node_start("summarize")

    steps = state.plan.get("steps") if isinstance(state.plan, dict) else []
    current_step_id = (
        (state.plan_execution or {}).get("current_step_id")
        if isinstance(state.plan_execution, dict)
        else None
    )
    rp = get_retry_policy_for_step(steps, current_step_id) or get_retry_policy_for_op(
        steps, "summarize"
    )
    timeout_s = get_timeout_for_step(steps, current_step_id) or get_timeout_for_op(
        steps, "summarize"
    )
    cb = get_circuit_breaker_for_step(steps, current_step_id)
    strict = (
        isinstance(cb, dict)
        and isinstance(cb.get("failure_threshold"), int)
        and cb.get("failure_threshold", 0) > 0
    )

    success_factors = safe_api_call(
        "generate_success_factors",
        generate_success_factors,
        query=state.query,
        spike_videos=state.analysis.get("spikes", {}).get("spike_videos", []),
        clusters=state.analysis.get("clusters", {}).get("top_clusters", []),
        strategy=str((state.analysis or {}).get("_routing", {}).get("summary_strategy", "auto")),
        fallback_value="성공 요인 분석을 생성할 수 없습니다.",
        retry_policy=rp,
        timeout_seconds=timeout_s,
        raise_on_fail=strict,
    )

    logger.node_end("summarize")
    return {"analysis": {**state.analysis, "success_factors": success_factors}}


def report_node(state: ViralAgentState) -> Dict[str, Any]:
    """Generate markdown report"""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("viral_video_agent", run_id)
    logger.node_start("report")

    # Build markdown report
    report_lines = [
        "# 바이럴 영상 분석 리포트",
        "",
        f"**검색어**: {state.query}",
        f"**시장**: {state.market}",
        f"**플랫폼**: {', '.join(state.platforms)}",
        f"**기간**: {state.time_window or '24h'}",
        f"**분석 영상 수**: {len(state.normalized)}",
        "",
        "---",
        "",
        "## 🚀 급상승 영상 (Spike Detection)",
        "",
    ]

    spikes = state.analysis.get("spikes", {})
    spike_videos = spikes.get("spike_videos", [])

    if spike_videos:
        report_lines.append(f"**급상승 영상 수**: {len(spike_videos)}개")
        report_lines.append("")

        for i, video in enumerate(spike_videos[:10], 1):
            report_lines.extend(
                [
                    f"### {i}. {video['title']}",
                    f"**채널**: {video['channel']}",
                    f"**조회수**: {video['views']:,}",
                    f"**좋아요**: {video['likes']:,}",
                    f"**URL**: [{video['platform']}]({video['url']})",
                    f"**Z-Score**: {video.get('z_score', 0):.2f}",
                    "",
                ]
            )
    else:
        report_lines.append("급상승 영상이 발견되지 않았습니다.")
        report_lines.append("")

    report_lines.extend(
        [
            "---",
            "",
            "## 📊 토픽 클러스터",
            "",
        ]
    )

    clusters = state.analysis.get("clusters", {}).get("top_clusters", [])
    for i, cluster in enumerate(clusters[:5], 1):
        report_lines.extend(
            [
                f"### {i}. {cluster['topic']}",
                f"**영상 수**: {cluster['count']}개",
                f"**평균 조회수**: {cluster['avg_views']:,}",
                "",
            ]
        )

    report_lines.extend(
        [
            "---",
            "",
            "## 💡 성공 요인 분석",
            "",
            state.analysis.get("success_factors", "No success factors available."),
            "",
            "---",
            "",
            "**⚠️ 주의**: 본 리포트는 AI가 생성한 분석으로, 사실 확인이 필요합니다.",
            "출처 링크를 반드시 확인하세요.",
            "",
            f"**Run ID**: `{state.run_id}`",
            "",
        ]
    )

    report_md = "\n".join(report_lines)

    # Calculate metrics
    metrics = {
        "coverage": len(state.normalized) / 100,  # Assume 100 videos target
        "factuality": 1.0 if all(item.get("url") for item in state.normalized) else 0.0,
        "actionability": 1.0 if state.analysis.get("success_factors") else 0.0,
    }

    logger.node_end("report", output_size=len(report_md))
    return {"report_md": report_md, "metrics": metrics}


def notify_node(state: ViralAgentState) -> Dict[str, Any]:
    """Send notifications (n8n, Slack, etc)"""
    run_id = state.run_id or "unknown"
    logger = AgentLogger("viral_video_agent", run_id)
    logger.node_start("notify")

    notifications_sent = []

    # n8n webhook notification
    n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if n8n_webhook_url:
        try:
            import requests

            payload = {
                "agent": "viral_video_agent",
                "query": state.query,
                "market": state.market,
                "run_id": state.run_id,
                "analysis": state.analysis,
                "metrics": state.metrics,
                "report_url": state.report_md,
                "timestamp": datetime.now().isoformat(),
            }

            response = requests.post(n8n_webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            notifications_sent.append("n8n")
            logger.info("n8n webhook notification sent successfully")

        except Exception as e:
            logger.warning(f"n8n webhook notification failed: {e}")

    # Slack webhook notification
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_webhook_url:
        try:
            import requests

            # Format Slack message
            analysis = state.analysis or {}
            spikes = analysis.get("spikes", {})
            total_spikes = spikes.get("total_spikes", 0) if isinstance(spikes, dict) else 0

            blocks: List[Dict[str, Any]] = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🔥 Viral Video Analysis Report"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Query:*\n{state.query}"},
                        {"type": "mrkdwn", "text": f"*Market:*\n{state.market}"},
                        {"type": "mrkdwn", "text": f"*Spikes Detected:*\n{total_spikes}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Videos Analyzed:*\n{len(state.normalized or [])}",
                        },
                    ],
                },
            ]

            slack_message: Dict[str, Any] = {
                "text": "🔥 Viral Video Analysis Complete",
                "blocks": blocks,
            }

            # Add top videos if available
            if state.normalized and len(state.normalized) > 0:
                top_videos = []
                for i, video in enumerate(state.normalized[:3], 1):
                    title = video.get("title", "N/A")
                    views = video.get("views", 0)
                    url = video.get("url", "")
                    if url:
                        top_videos.append(f"{i}. <{url}|{title}> - {views:,} views")
                    else:
                        top_videos.append(f"{i}. {title} - {views:,} views")

                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Top Videos:*\n" + "\n".join(top_videos),
                        },
                    }
                )

            # Add report link if available
            if state.report_md:
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*Full Report:*\n`{state.report_md}`"},
                    }
                )

            response = requests.post(slack_webhook_url, json=slack_message, timeout=10)
            response.raise_for_status()
            notifications_sent.append("slack")
            logger.info("Slack webhook notification sent successfully")

        except Exception as e:
            logger.warning(f"Slack webhook notification failed: {e}")

    if not notifications_sent:
        logger.info("No webhook URLs configured (N8N_WEBHOOK_URL, SLACK_WEBHOOK_URL)")

    logger.node_end("notify")
    return {"notifications_sent": notifications_sent}


def build_graph(checkpointer: Optional[Any] = None) -> Any:
    """Build LangGraph for Viral Video Agent"""

    graph = StateGraph(ViralAgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("collect", collect_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("report", report_node)
    graph.add_node("notify", notify_node)

    # Set entry point
    graph.set_entry_point("router")

    # Add edges
    graph.add_edge("router", "collect")
    graph.add_edge("collect", "normalize")
    graph.add_edge("normalize", "analyze")
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "report")
    graph.add_edge("report", "notify")
    graph.add_edge("notify", END)

    return graph.compile(
        checkpointer=checkpointer, interrupt_before=["report"] if checkpointer else None
    )


def run_agent(
    query: str,
    market: str = "KR",
    platforms: Optional[List[str]] = None,
    time_window: str = "24h",
    spike_threshold: float = 2.0,
    run_id: Optional[str] = None,
    require_approval: bool = True,
    orchestrator: Optional[Dict[str, Any]] = None,
) -> ViralAgentState:
    """Run the viral video agent"""

    if platforms is None:
        platforms = ["youtube"]

    # Generate run_id if not provided
    if not run_id:
        run_id = str(uuid.uuid4())

    logger = AgentLogger("viral_video_agent", run_id)

    # Create initial state
    initial_state = ViralAgentState(
        query=query,
        time_window=time_window,
        market=market,
        platforms=platforms,
        spike_threshold=spike_threshold,
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
    agent_entry = get_agent_entry(orchestrator, "viral_video_agent")
    steps = normalize_steps(agent_entry) if agent_entry else []
    if steps:
        graph = build_plan_runner_graph(
            agent_name="viral_video_agent",
            state_cls=ViralAgentState,
            router_node=router_node,
            op_nodes={
                "collect": collect_node,
                "normalize": normalize_node,
                "analyze": analyze_node,
                "summarize": summarize_node,
                "report": report_node,
                "notify": notify_node,
            },
            steps=steps,
            checkpointer=checkpointer,
        )
    else:
        graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id}}

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
                print(f"Viral analysis complete for: '{query}'")
                print("-" * 50)

                while True:
                    choice = input("Proceed to generate report? (y/n): ").strip().lower()
                    if choice == "y":
                        logger.info("✅ Approved. Resuming...")
                        current_state = graph.invoke(None, config=config)
                        break
                    elif choice == "n":
                        logger.info("🛑 Aborted by user.")
                        return ViralAgentState(**cast(Dict[str, Any], current_state))
                    else:
                        print("Please enter 'y' or 'n'.")

        # Ensure result is ViralAgentState
        if isinstance(current_state, dict):
            return ViralAgentState(**cast(Dict[str, Any], current_state))
        return current_state

    except Exception as e:
        logger.error(f"Error running viral video agent: {e}")
        raise
