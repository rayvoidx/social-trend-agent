"""
Tools for Viral Video Agent
"""
import os
import logging
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from src.integrations.mcp.sns_collect import (
    fetch_tiktok_videos_via_mcp,
    fetch_youtube_videos_via_mcp,
)
from src.integrations.llm import get_llm_client
from src.integrations.retrieval.vectorstore_pinecone import PineconeVectorStore
from src.core.config import get_config_manager

logger = logging.getLogger(__name__)


# ============================================================================
# Data Collection Tools
# ============================================================================

def fetch_video_stats(
    platform: str,
    market: str = "KR",
    time_window: str = "24h"
) -> List[Dict[str, Any]]:
    """
    Fetch video statistics from YouTube/TikTok

    Args:
        platform: Platform name ("youtube", "tiktok")
        market: Market code ("KR", "US", etc)
        time_window: Time window (e.g., "24h", "7d")

    Returns:
        List of video statistics
    """
    print(f"[fetch_video_stats] platform={platform}, market={market}, time_window={time_window}")

    if platform == "youtube":
        return _fetch_youtube_stats(market, time_window)
    elif platform == "tiktok":
        return _fetch_tiktok_stats(market, time_window)
    else:
        print(f"[fetch_video_stats] Unknown platform: {platform}")
        return []


def _fetch_youtube_stats(market: str, time_window: str) -> List[Dict[str, Any]]:
    """Fetch YouTube trending videos via MCP server only."""
    videos = fetch_youtube_videos_via_mcp(
        market=market,
        time_window=time_window,
        max_results=50,
    )
    if not videos:
        # MCP 서버에서 결과를 얻지 못한 경우에만 샘플 데이터 사용
        return _get_sample_youtube_data(market)
    return videos


def _fetch_tiktok_stats(market: str, time_window: str) -> List[Dict[str, Any]]:
    """
    Fetch TikTok trending videos

    Note: TikTok API는 공식 비즈니스 파트너십이 필요합니다.
    현재는 샘플 데이터를 반환하지만, 실제 API 연동을 위해서는:
    1. TikTok for Business API 액세스 신청
    2. 또는 서드파티 데이터 제공자 사용 (예: Apify, RapidAPI)
    """
    # MCP 서버를 통해서만 TikTok 데이터를 가져옵니다.
    videos = fetch_tiktok_videos_via_mcp(query="trending", max_count=50)
    if not videos:
        # MCP 서버에서 결과를 얻지 못한 경우에만 샘플 데이터 사용
        print("ℹ️  Using sample TikTok data (MCP server returned no results)")
        return _get_sample_tiktok_data(market)
    return videos


def _get_sample_youtube_data(market: str) -> List[Dict[str, Any]]:
    """Generate sample YouTube data"""
    sample_videos = []
    base_views = [100000, 500000, 1000000, 5000000, 10000000]

    for i in range(20):
        views = random.choice(base_views) + random.randint(-50000, 50000)
        likes = int(views * random.uniform(0.03, 0.08))
        comments = int(views * random.uniform(0.001, 0.005))

        sample_videos.append({
            "video_id": f"YT_{i:03d}",
            "title": f"Sample YouTube Video {i+1}",
            "channel": f"Channel {i % 5 + 1}",
            "views": views,
            "likes": likes,
            "comments": comments,
            "published_at": (datetime.now() - timedelta(hours=random.randint(1, 48))).isoformat(),
            "platform": "youtube",
            "url": f"https://youtube.com/watch?v=YT_{i:03d}",
            "thumbnail": f"https://i.ytimg.com/vi/YT_{i:03d}/default.jpg"
        })

    return sample_videos


def _get_sample_tiktok_data(market: str) -> List[Dict[str, Any]]:
    """Generate sample TikTok data"""
    sample_videos = []
    base_views = [50000, 200000, 500000, 1000000, 5000000]

    for i in range(20):
        views = random.choice(base_views) + random.randint(-20000, 20000)
        likes = int(views * random.uniform(0.05, 0.12))
        comments = int(views * random.uniform(0.002, 0.008))

        sample_videos.append({
            "video_id": f"TT_{i:03d}",
            "title": f"Sample TikTok Video {i+1}",
            "channel": f"@creator{i % 5 + 1}",
            "views": views,
            "likes": likes,
            "comments": comments,
            "published_at": (datetime.now() - timedelta(hours=random.randint(1, 48))).isoformat(),
            "platform": "tiktok",
            "url": f"https://tiktok.com/@creator/video/TT_{i:03d}",
            "thumbnail": f"https://tiktok.com/thumbnail/TT_{i:03d}.jpg"
        })

    return sample_videos


# ============================================================================
# Analysis Tools
# ============================================================================

def detect_spike(items: List[Dict[str, Any]], threshold: float = 2.0) -> Dict[str, Any]:
    """
    Detect viral spikes using Z-score

    Args:
        items: List of video statistics
        threshold: Z-score threshold for spike detection (default: 2.0)

    Returns:
        Spike detection results with spike_videos list
    """
    print(f"[detect_spike] Analyzing {len(items)} videos with threshold={threshold}...")

    if not items:
        return {"spike_videos": [], "mean_views": 0, "std_views": 0}

    # Calculate mean and std of views
    views_list = [item.get("views", 0) for item in items]
    mean_views = sum(views_list) / len(views_list)

    # Calculate standard deviation
    variance = sum((x - mean_views) ** 2 for x in views_list) / len(views_list)
    std_views = variance ** 0.5

    # Detect spikes
    spike_videos = []
    for item in items:
        views = item.get("views", 0)
        if std_views > 0:
            z_score = (views - mean_views) / std_views
            if z_score >= threshold:
                spike_videos.append({
                    **item,
                    "z_score": z_score
                })

    # Sort by z_score
    spike_videos.sort(key=lambda x: x.get("z_score", 0), reverse=True)

    return {
        "spike_videos": spike_videos,
        "mean_views": mean_views,
        "std_views": std_views,
        "total_spikes": len(spike_videos)
    }


def topic_cluster(items: List[Dict[str, Any]], use_embeddings: bool = True) -> Dict[str, Any]:
    """
    Cluster videos by topic using embeddings or keyword-based clustering

    Args:
        items: List of video statistics
        use_embeddings: Use Pinecone + embeddings for clustering (default: True)

    Returns:
        Topic clustering results
    """
    logger.info(f"[topic_cluster] Clustering {len(items)} videos...")

    if use_embeddings:
        try:
            return _topic_cluster_embeddings(items)
        except Exception as e:
            logger.warning(f"Embedding clustering failed, falling back to keyword: {e}")

    return _topic_cluster_keywords(items)


def _topic_cluster_embeddings(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cluster videos using Pinecone embeddings."""
    cfg = get_config_manager()
    agent_cfg = cfg.get_agent_config("viral_video_agent")

    vs_cfg = agent_cfg.vector_store if agent_cfg and agent_cfg.vector_store else {}
    index_name = vs_cfg.get("index_name", "viral-video-index")

    # Get LLM client for embeddings
    llm_client = get_llm_client(agent_name="viral_video_agent")
    vector_store = PineconeVectorStore(index_name=index_name)

    # Build corpus from video titles
    texts = [item.get("title", "") for item in items]
    ids = [item.get("video_id", f"vid_{i}") for i, item in enumerate(items)]

    # Get embeddings
    vectors = llm_client.get_embeddings_batch(texts)

    # Prepare metadata
    metadatas = []
    for i, item in enumerate(items):
        meta = {
            "index": i,
            "title": item.get("title", "")[:500],
            "views": item.get("views", 0),
            "platform": item.get("platform", "")
        }
        metadatas.append(meta)

    # Upsert to Pinecone
    vector_store.upsert(ids, vectors, metadatas)

    # Use LLM to identify clusters
    cluster_prompt = f"""Analyze these video titles and group them into 5-8 topic categories.
Return a JSON object where keys are topic names (in Korean) and values are arrays of video indices.

Video titles:
{chr(10).join([f'{i}: {t}' for i, t in enumerate(texts[:50])])}

Return only valid JSON."""

    import json
    response = llm_client.invoke(cluster_prompt)

    try:
        cluster_map = json.loads(response)
    except json.JSONDecodeError:
        return _topic_cluster_keywords(items)

    # Calculate cluster statistics
    cluster_stats = []
    for topic, indices in cluster_map.items():
        videos_in_cluster = [items[i] for i in indices if i < len(items)]
        if videos_in_cluster:
            avg_views = sum(v.get("views", 0) for v in videos_in_cluster) / len(videos_in_cluster)
            cluster_stats.append({
                "topic": topic,
                "count": len(videos_in_cluster),
                "avg_views": avg_views
            })

    cluster_stats.sort(key=lambda x: x["count"], reverse=True)

    return {
        "top_clusters": cluster_stats,
        "total_clusters": len(cluster_stats)
    }


def _topic_cluster_keywords(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Keyword-based clustering fallback."""
    # Simple keyword-based clustering
    topic_keywords = {
        "음식/요리": ["recipe", "cooking", "food", "요리", "음식", "레시피"],
        "게임": ["game", "gaming", "gameplay", "게임", "플레이"],
        "뷰티/패션": ["beauty", "makeup", "fashion", "뷰티", "메이크업", "패션"],
        "여행": ["travel", "trip", "tour", "여행", "관광"],
        "교육": ["tutorial", "education", "learn", "튜토리얼", "교육", "배우기"],
        "엔터테인먼트": ["entertainment", "funny", "comedy", "엔터", "웃긴", "코미디"],
        "기술": ["tech", "technology", "review", "기술", "리뷰"],
        "일상": ["vlog", "daily", "life", "브이로그", "일상"]
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
        cluster_stats.append({
            "topic": topic,
            "count": len(videos),
            "avg_views": avg_views
        })

    # Sort by count
    cluster_stats.sort(key=lambda x: x["count"], reverse=True)

    return {
        "top_clusters": cluster_stats,
        "total_clusters": len(clusters)
    }


def generate_success_factors(
    query: str,
    spike_videos: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    use_llm: bool = True
) -> str:
    """
    Generate success factors and recommendations

    Args:
        query: Original search query
        spike_videos: List of spike videos
        clusters: Topic cluster results
        use_llm: Use LLM for analysis (default: True)

    Returns:
        Success factors analysis text
    """
    print(f"[generate_success_factors] Analyzing {len(spike_videos)} spike videos...")

    # LLM 기반 분석
    if use_llm:
        try:
            return _generate_success_factors_llm(query, spike_videos, clusters)
        except Exception as e:
            print(f"[generate_success_factors] LLM analysis failed, falling back to template: {e}")

    # 템플릿 기반 폴백
    return _generate_success_factors_template(query, spike_videos, clusters)


def _generate_success_factors_llm(
    query: str,
    spike_videos: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]]
) -> str:
    """LLM 기반 성공 요인 분석"""
    client = get_llm_client(agent_name="viral_video_agent")

    # Prepare video data
    video_summaries = []
    for i, video in enumerate(spike_videos[:10]):
        summary = f"""
Video {i+1}:
- Title: {video.get('title', 'N/A')}
- Views: {video.get('views', 0):,}
- Likes: {video.get('likes', 0):,}
- Comments: {video.get('comments', 0):,}
- Z-Score: {video.get('z_score', 0):.2f}
- Engagement Rate: {video.get('engagement_rate', 0):.2%}
"""
        video_summaries.append(summary)

    # Prepare cluster data
    cluster_summaries = []
    for cluster in clusters[:5]:
        summary = f"- {cluster.get('topic', 'N/A')}: {cluster.get('count', 0)} videos, avg {cluster.get('avg_views', 0):,} views"
        cluster_summaries.append(summary)

    prompt = f"""Analyze these viral videos about "{query}" and provide detailed success factors.

## Viral Videos Data:
{chr(10).join(video_summaries)}

## Topic Clusters:
{chr(10).join(cluster_summaries) if cluster_summaries else "No clusters available"}

Please provide a comprehensive analysis in Korean with the following structure:

## 최고 성과 영상 분석
(Analyze the top performing video)

## 핵심 성공 요인
(5-7 specific factors with data-backed explanations)
1. **요인명**: 설명
2. ...

## 콘텐츠 패턴 분석
(Common patterns in viral content)

## 실행 권고안
(5-7 actionable recommendations for content creators)
- 구체적인 실행 항목

## 예상 KPI
(Expected metrics if recommendations are followed)

Be specific, data-driven, and provide actionable insights."""

    full_prompt = f"""You are a viral video analyst expert. Provide specific, data-driven insights in Korean.

{prompt}"""

    return client.invoke(full_prompt)


def _generate_success_factors_template(
    query: str,
    spike_videos: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]]
) -> str:
    """템플릿 기반 성공 요인 분석 (폴백)"""
    summary_lines = []

    if spike_videos:
        top_video = spike_videos[0]
        summary_lines.append(f"**최고 성과 영상**: {top_video['title']}")
        summary_lines.append(f"- 조회수: {top_video['views']:,}")
        summary_lines.append(f"- Z-Score: {top_video.get('z_score', 0):.2f}")
        if top_video.get('engagement_rate'):
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
        avg_views = sum(v.get('views', 0) for v in spike_videos) / len(spike_videos)
        avg_likes = sum(v.get('likes', 0) for v in spike_videos) / len(spike_videos)
        avg_engagement = avg_likes / avg_views if avg_views > 0 else 0

        summary_lines.append(f"1. **높은 참여도**: 평균 참여율 {avg_engagement:.2%}")
        summary_lines.append(f"2. **바이럴 잠재력**: 평균 Z-Score {sum(v.get('z_score', 0) for v in spike_videos) / len(spike_videos):.2f}")

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
