"""
Tools for Viral Video Agent
"""

import random
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from src.integrations.mcp.sns_collect import (
    fetch_tiktok_videos_via_mcp,
    fetch_youtube_videos_via_mcp,
)
from src.core.config import get_config_manager
from src.core.refine import RefineEngine
from src.core.prompts import VIRAL_ANALYSIS_PROMPT_TEMPLATE, DEFAULT_SYSTEM_PERSONA
from src.domain.schemas import TrendInsight
from src.integrations.llm.llm_client import get_llm_client
from src.core.routing import ModelRole, get_model_for_role

logger = logging.getLogger(__name__)

# ============================================================================
# Data Collection Tools
# ============================================================================


def fetch_video_stats(
    platform: str, market: str = "KR", time_window: str = "24h"
) -> List[Dict[str, Any]]:
    """
    Fetch video statistics from YouTube/TikTok
    """
    logger.info(
        f"[fetch_video_stats] platform={platform}, market={market}, time_window={time_window}"
    )

    if platform == "youtube":
        return _fetch_youtube_stats(market, time_window)
    elif platform == "tiktok":
        return _fetch_tiktok_stats(market, time_window)
    else:
        logger.warning(f"[fetch_video_stats] Unknown platform: {platform}")
        return []


def _fetch_youtube_stats(market: str, time_window: str) -> List[Dict[str, Any]]:
    """Fetch YouTube trending videos via MCP server only."""
    videos = fetch_youtube_videos_via_mcp(
        market=market,
        time_window=time_window,
        max_results=50,
    )
    if not videos:
        # MCP 서버에서 결과를 얻지 못한 경우 설정에 따라 폴백 결정
        if get_config_manager().should_allow_sample_fallback():
            return _get_sample_youtube_data(market)
        else:
            logger.info("ℹ️  No YouTube videos found and sample fallback disabled.")
            return []
    return videos


def _fetch_tiktok_stats(market: str, time_window: str) -> List[Dict[str, Any]]:
    """
    Fetch TikTok trending videos
    """
    # MCP 서버를 통해서만 TikTok 데이터를 가져옵니다.
    videos = fetch_tiktok_videos_via_mcp(query="trending", max_count=50)
    if not videos:
        # MCP 서버에서 결과를 얻지 못한 경우 설정에 따라 폴백 결정
        if get_config_manager().should_allow_sample_fallback():
            logger.info("ℹ️  Using sample TikTok data (MCP server returned no results)")
            return _get_sample_tiktok_data(market)
        else:
            logger.info("ℹ️  No TikTok videos found and sample fallback disabled.")
            return []
    return videos


def _get_sample_youtube_data(market: str) -> List[Dict[str, Any]]:
    """Generate sample YouTube data"""
    sample_videos = []
    base_views = [100000, 500000, 1000000, 5000000, 10000000]

    for i in range(20):
        views = random.choice(base_views) + random.randint(-50000, 50000)
        likes = int(views * random.uniform(0.03, 0.08))
        comments = int(views * random.uniform(0.001, 0.005))

        sample_videos.append(
            {
                "video_id": f"YT_{i:03d}",
                "title": f"Sample YouTube Video {i+1}",
                "channel": f"Channel {i % 5 + 1}",
                "views": views,
                "likes": likes,
                "comments": comments,
                "published_at": (
                    datetime.now() - timedelta(hours=random.randint(1, 48))
                ).isoformat(),
                "platform": "youtube",
                "url": f"https://youtube.com/watch?v=YT_{i:03d}",
                "thumbnail": f"https://i.ytimg.com/vi/YT_{i:03d}/default.jpg",
            }
        )

    return sample_videos


def _get_sample_tiktok_data(market: str) -> List[Dict[str, Any]]:
    """Generate sample TikTok data"""
    sample_videos = []
    base_views = [50000, 200000, 500000, 1000000, 5000000]

    for i in range(20):
        views = random.choice(base_views) + random.randint(-20000, 20000)
        likes = int(views * random.uniform(0.05, 0.12))
        comments = int(views * random.uniform(0.002, 0.008))

        sample_videos.append(
            {
                "video_id": f"TT_{i:03d}",
                "title": f"Sample TikTok Video {i+1}",
                "channel": f"@creator{i % 5 + 1}",
                "views": views,
                "likes": likes,
                "comments": comments,
                "published_at": (
                    datetime.now() - timedelta(hours=random.randint(1, 48))
                ).isoformat(),
                "platform": "tiktok",
                "url": f"https://tiktok.com/@creator/video/TT_{i:03d}",
                "thumbnail": f"https://tiktok.com/thumbnail/TT_{i:03d}.jpg",
            }
        )

    return sample_videos


# ============================================================================
# Analysis Tools
# ============================================================================


def detect_spike(items: List[Dict[str, Any]], threshold: float = 2.0) -> Dict[str, Any]:
    """
    Detect viral spikes using Z-score
    """
    logger.info(f"[detect_spike] Analyzing {len(items)} videos with threshold={threshold}...")

    if not items:
        return {"spike_videos": [], "mean_views": 0, "std_views": 0}

    # Calculate mean and std of views
    views_list = [item.get("views", 0) for item in items]
    mean_views = sum(views_list) / len(views_list)

    # Calculate standard deviation
    variance = sum((x - mean_views) ** 2 for x in views_list) / len(views_list)
    std_views = variance**0.5

    # Detect spikes
    spike_videos = []
    for item in items:
        views = item.get("views", 0)
        if std_views > 0:
            z_score = (views - mean_views) / std_views
            if z_score >= threshold:
                spike_videos.append({**item, "z_score": z_score})

    # Sort by z_score
    spike_videos.sort(key=lambda x: x.get("z_score", 0), reverse=True)

    return {
        "spike_videos": spike_videos,
        "mean_views": mean_views,
        "std_views": std_views,
        "total_spikes": len(spike_videos),
    }


def topic_cluster(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Cluster videos by topic (simple keyword-based clustering)
    """
    logger.info(f"[topic_cluster] Clustering {len(items)} videos...")

    # Simple keyword-based clustering (production: use embeddings + KMeans)
    topic_keywords = {
        "음식/요리": ["recipe", "cooking", "food", "요리", "음식", "레시피"],
        "게임": ["game", "gaming", "gameplay", "게임", "플레이"],
        "뷰티/패션": ["beauty", "makeup", "fashion", "뷰티", "메이크업", "패션"],
        "여행": ["travel", "trip", "tour", "여행", "관광"],
        "교육": ["tutorial", "education", "learn", "튜토리얼", "교육", "배우기"],
        "엔터테인먼트": ["entertainment", "funny", "comedy", "엔터", "웃긴", "코미디"],
        "기술": ["tech", "technology", "review", "기술", "리뷰"],
        "일상": ["vlog", "daily", "life", "브이로그", "일상"],
    }

    clusters: Dict[str, List[Dict[str, Any]]] = {}

    for item in items:
        title = item.get("title", "").lower()
        matched_topic = "기타"

        for topic, keywords in topic_keywords.items():
            if any(kw in title for kw in keywords):
                matched_topic = topic
                break

        if matched_topic not in clusters:
            clusters[matched_topic] = []
        clusters[matched_topic].append(item)

    # Calculate cluster statistics
    cluster_stats = []
    for topic, videos in clusters.items():
        avg_views = sum(v.get("views", 0) for v in videos) / len(videos)
        cluster_stats.append({"topic": topic, "count": len(videos), "avg_views": avg_views})

    # Sort by count
    cluster_stats.sort(key=lambda x: x["count"], reverse=True)

    return {"top_clusters": cluster_stats, "total_clusters": len(clusters)}


def generate_success_factors(
    query: str,
    spike_videos: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    use_llm: bool = True,
    strategy: str = "auto",
) -> str:
    """
    Generate success factors and recommendations (RefineEngine + gpt-5.2)
    """
    logger.info(f"[generate_success_factors] Analyzing {len(spike_videos)} spike videos...")

    # LLM 기반 분석
    if use_llm:
        try:
            return _generate_success_factors_llm(query, spike_videos, clusters, strategy=strategy)
        except Exception as e:
            logger.error(
                f"[generate_success_factors] LLM analysis failed, falling back to template: {e}"
            )

    # 템플릿 기반 폴백
    return _generate_success_factors_template(query, spike_videos, clusters)


def _generate_success_factors_llm(
    query: str,
    spike_videos: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    strategy: str = "auto",
) -> str:
    """LLM 기반 성공 요인 분석 (RefineEngine 적용)"""
    client = get_llm_client()
    engine = RefineEngine(client)
    writer_model = get_model_for_role("viral_video_agent", ModelRole.WRITER)
    synthesizer_model = get_model_for_role("viral_video_agent", ModelRole.SYNTHESIZER)

    # Prepare video data
    video_summaries = []
    for i, video in enumerate(spike_videos[:10]):
        summary = f"""
Video {i+1}:
- Title: {video.get('title', 'N/A')}
- Views: {video.get('views', 0):,}
- Likes: {video.get('likes', 0):,}
- Z-Score: {video.get('z_score', 0):.2f}
"""
        video_summaries.append(summary.strip())

    # Prepare cluster data
    cluster_summaries = []
    for cluster in clusters[:5]:
        summary = f"- {cluster.get('topic', 'N/A')}: {cluster.get('count', 0)} videos, avg {cluster.get('avg_views', 0):,} views"
        cluster_summaries.append(summary)

    prompt = VIRAL_ANALYSIS_PROMPT_TEMPLATE.format(
        system_persona=DEFAULT_SYSTEM_PERSONA,
        query=query,
        video_summaries="\n".join(video_summaries),
        cluster_summaries=(
            "\n".join(cluster_summaries) if cluster_summaries else "No clusters available"
        ),
    )

    if str(strategy).lower() == "cheap":
        cheap_prompt = (
            "Write a compact Korean brief about viral video success factors.\n"
            "Requirements:\n"
            "- 6~10 bullets\n"
            "- Use the provided spike/cluster evidence only\n"
            "- No speculation; if uncertain, say '불확실'\n\n"
            f"Query: {query}\n\n"
            f"Spike evidence:\n{chr(10).join(video_summaries)}\n\n"
            f"Clusters:\n{chr(10).join(cluster_summaries) if cluster_summaries else 'None'}\n"
        )
        return client.chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are a cheap gateway summarizer. Be concise and grounded.",
                },
                {"role": "user", "content": cheap_prompt},
            ],
            temperature=0.3,
            max_tokens=900,
            model=synthesizer_model,
        ).strip()

    insight: TrendInsight = engine.refine_loop(
        prompt=prompt,
        initial_schema=TrendInsight,
        criteria="데이터(조회수, Z-Score)에 기반한 구체적인 성공 요인 분석 및 콘텐츠 제작자를 위한 실행 가능한 팁 포함",
        max_iterations=1,
        model=writer_model,  # Model Routing
    )

    return f"""
## 바이럴 영상 분석 요약
{insight.summary}

## 핵심 성공 요인
{chr(10).join([f"- {item}" for item in insight.key_findings])}

## 콘텐츠 제작 가이드
{chr(10).join([f"- {item}" for item in insight.recommendations])}

## 추천 키워드/해시태그
{", ".join(insight.keywords)}

---
*분석 영향력 점수: {insight.impact_score}/10*
"""


def _generate_success_factors_template(
    query: str, spike_videos: List[Dict[str, Any]], clusters: List[Dict[str, Any]]
) -> str:
    """템플릿 기반 성공 요인 분석 (폴백)"""
    summary_lines = []

    if spike_videos:
        top_video = spike_videos[0]
        summary_lines.append(f"**최고 성과 영상**: {top_video['title']}")
        summary_lines.append(f"- 조회수: {top_video['views']:,}")
        summary_lines.append(f"- Z-Score: {top_video.get('z_score', 0):.2f}")
        if top_video.get("engagement_rate"):
            summary_lines.append(f"- 참여율: {top_video['engagement_rate']:.2%}")
        summary_lines.append("")

    if clusters:
        top_cluster = clusters[0]
        summary_lines.append(f"**가장 인기 있는 토픽**: {top_cluster['topic']}")
        summary_lines.append(f"- 영상 수: {top_cluster['count']}개")
        summary_lines.append(f"- 평균 조회수: {top_cluster['avg_views']:,}")
        summary_lines.append("")

    # 분석 기반 성공 요인
    summary_lines.append("**성공 요인:**")

    if spike_videos:
        avg_views = sum(v.get("views", 0) for v in spike_videos) / len(spike_videos)
        avg_likes = sum(v.get("likes", 0) for v in spike_videos) / len(spike_videos)
        avg_engagement = avg_likes / avg_views if avg_views > 0 else 0

        summary_lines.append(f"1. **높은 참여도**: 평균 참여율 {avg_engagement:.2%}")
        summary_lines.append(
            f"2. **바이럴 잠재력**: 평균 Z-Score {sum(v.get('z_score', 0) for v in spike_videos) / len(spike_videos):.2f}"
        )

    summary_lines.append("3. **타이밍**: 트렌드를 빠르게 포착하여 초기에 콘텐츠 발행")
    summary_lines.append("4. **주제**: 대중의 관심사와 일치하는 토픽 선택")
    summary_lines.append("5. **참여도**: 좋아요/댓글 비율이 높은 콘텐츠")
    summary_lines.append("")

    summary_lines.append("**실행 권고안:**")
    summary_lines.append("- 급상승 영상의 포맷과 스타일 참고")
    summary_lines.append("- 인기 토픽 클러스터를 중심으로 콘텐츠 기획")
    summary_lines.append("- 시청자 참여를 유도하는 요소 강화 (질문, 투표 등)")
    summary_lines.append("- 초반 10초 내에 핵심 메시지 전달")
    summary_lines.append("- 트렌드 키워드를 제목과 설명에 활용")

    return "\n".join(summary_lines)
