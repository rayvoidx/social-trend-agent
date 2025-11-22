"""
LangGraph definition for Viral Video Agent
"""
import os
import uuid
from datetime import datetime
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from src.core.state import ViralAgentState
from src.agents.viral_video.tools import (
    fetch_video_stats,
    detect_spike,
    topic_cluster,
    generate_success_factors
)


def collect_node(state: ViralAgentState) -> Dict[str, Any]:
    """Collect video statistics from platforms"""
    print(f"[collect_node] market={state.market}, platforms={state.platforms}")

    raw_items = []

    for platform in state.platforms:
        stats = fetch_video_stats(
            platform=platform,
            market=state.market,
            time_window=state.time_window or "24h"
        )
        raw_items.extend(stats)

    return {"raw_items": raw_items}


def normalize_node(state: ViralAgentState) -> Dict[str, Any]:
    """Normalize and clean collected data"""
    print(f"[normalize_node] raw_items count={len(state.raw_items)}")

    normalized = []
    for item in state.raw_items:
        normalized.append({
            "video_id": item.get("video_id", ""),
            "title": item.get("title", ""),
            "channel": item.get("channel", ""),
            "views": item.get("views", 0),
            "likes": item.get("likes", 0),
            "comments": item.get("comments", 0),
            "published_at": item.get("published_at", ""),
            "platform": item.get("platform", "youtube"),
            "url": item.get("url", ""),
            "thumbnail": item.get("thumbnail", "")
        })

    return {"normalized": normalized}


def analyze_node(state: ViralAgentState) -> Dict[str, Any]:
    """Detect viral spikes and cluster topics"""
    print(f"[analyze_node] normalized count={len(state.normalized)}")

    # Detect spikes
    spike_results = detect_spike(
        items=state.normalized,
        threshold=state.spike_threshold
    )

    # Cluster topics
    cluster_results = topic_cluster(state.normalized)

    analysis = {
        "spikes": spike_results,
        "clusters": cluster_results,
        "total_items": len(state.normalized)
    }

    return {"analysis": analysis}


def summarize_node(state: ViralAgentState) -> Dict[str, Any]:
    """Generate success factors and insights"""
    print(f"[summarize_node] analysis={state.analysis}")

    success_factors = generate_success_factors(
        query=state.query,
        spike_videos=state.analysis.get("spikes", {}).get("spike_videos", []),
        clusters=state.analysis.get("clusters", {}).get("top_clusters", [])
    )

    return {"analysis": {**state.analysis, "success_factors": success_factors}}


def report_node(state: ViralAgentState) -> Dict[str, Any]:
    """Generate markdown report"""
    print(f"[report_node] Generating report...")

    # Build markdown report
    report_lines = [
        f"# 바이럴 영상 분석 리포트",
        f"",
        f"**검색어**: {state.query}",
        f"**시장**: {state.market}",
        f"**플랫폼**: {', '.join(state.platforms)}",
        f"**기간**: {state.time_window or '24h'}",
        f"**분석 영상 수**: {len(state.normalized)}",
        f"",
        f"---",
        f"",
        f"## 🚀 급상승 영상 (Spike Detection)",
        f"",
    ]

    spikes = state.analysis.get("spikes", {})
    spike_videos = spikes.get("spike_videos", [])

    if spike_videos:
        report_lines.append(f"**급상승 영상 수**: {len(spike_videos)}개")
        report_lines.append("")

        for i, video in enumerate(spike_videos[:10], 1):
            report_lines.extend([
                f"### {i}. {video['title']}",
                f"**채널**: {video['channel']}",
                f"**조회수**: {video['views']:,}",
                f"**좋아요**: {video['likes']:,}",
                f"**URL**: [{video['platform']}]({video['url']})",
                f"**Z-Score**: {video.get('z_score', 0):.2f}",
                f"",
            ])
    else:
        report_lines.append("급상승 영상이 발견되지 않았습니다.")
        report_lines.append("")

    report_lines.extend([
        f"---",
        f"",
        f"## 📊 토픽 클러스터",
        f"",
    ])

    clusters = state.analysis.get("clusters", {}).get("top_clusters", [])
    for i, cluster in enumerate(clusters[:5], 1):
        report_lines.extend([
            f"### {i}. {cluster['topic']}",
            f"**영상 수**: {cluster['count']}개",
            f"**평균 조회수**: {cluster['avg_views']:,}",
            f"",
        ])

    report_lines.extend([
        f"---",
        f"",
        f"## 💡 성공 요인 분석",
        f"",
        state.analysis.get("success_factors", "No success factors available."),
        f"",
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
        "coverage": len(state.normalized) / 100,  # Assume 100 videos target
        "factuality": 1.0 if all(item.get("url") for item in state.normalized) else 0.0,
        "actionability": 1.0 if state.analysis.get("success_factors") else 0.0
    }

    return {"report_md": report_md, "metrics": metrics}


def notify_node(state: ViralAgentState) -> Dict[str, Any]:
    """Send notifications (n8n, Slack, etc)"""
    print(f"[notify_node] Sending notifications...")

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
                "timestamp": datetime.now().isoformat()
            }

            response = requests.post(n8n_webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            notifications_sent.append("n8n")
            print(f"✅ n8n webhook notification sent successfully")

        except Exception as e:
            print(f"⚠️  n8n webhook notification failed: {e}")

    # Slack webhook notification
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_webhook_url:
        try:
            import requests

            # Format Slack message
            analysis = state.analysis or {}
            spikes = analysis.get("spikes", {})
            total_spikes = spikes.get("total_spikes", 0) if isinstance(spikes, dict) else 0

            slack_message = {
                "text": f"🔥 Viral Video Analysis Complete",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🔥 Viral Video Analysis Report"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Query:*\n{state.query}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Market:*\n{state.market}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Spikes Detected:*\n{total_spikes}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Videos Analyzed:*\n{len(state.normalized or [])}"
                            }
                        ]
                    }
                ]
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

                slack_message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Top Videos:*\n" + "\n".join(top_videos)
                    }
                })

            # Add report link if available
            if state.report_md:
                slack_message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Full Report:*\n`{state.report_md}`"
                    }
                })

            response = requests.post(slack_webhook_url, json=slack_message, timeout=10)
            response.raise_for_status()
            notifications_sent.append("slack")
            print(f"✅ Slack webhook notification sent successfully")

        except Exception as e:
            print(f"⚠️  Slack webhook notification failed: {e}")

    if not notifications_sent:
        print(f"ℹ️  No webhook URLs configured (N8N_WEBHOOK_URL, SLACK_WEBHOOK_URL)")

    return {"notifications_sent": notifications_sent}


def build_graph() -> StateGraph:
    """Build LangGraph for Viral Video Agent"""

    graph = StateGraph(ViralAgentState)

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


def run_agent(
    query: str,
    market: str = "KR",
    platforms: list = None,
    time_window: str = "24h",
    spike_threshold: float = 2.0
) -> ViralAgentState:
    """Run the viral video agent"""

    if platforms is None:
        platforms = ["youtube"]

    # Generate run_id
    run_id = str(uuid.uuid4())

    # Create initial state
    initial_state = ViralAgentState(
        query=query,
        time_window=time_window,
        market=market,
        platforms=platforms,
        spike_threshold=spike_threshold,
        run_id=run_id
    )

    # Build and run graph
    graph = build_graph()
    final_state = graph.invoke(initial_state)

    return final_state
