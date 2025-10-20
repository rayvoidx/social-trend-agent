"""
Tools for Viral Video Agent
"""
import os
import random
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests


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
    """Fetch YouTube trending videos"""
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")

    if youtube_api_key:
        # TODO: Implement real YouTube Data API call
        # url = "https://www.googleapis.com/youtube/v3/videos"
        # params = {
        #     "part": "snippet,statistics",
        #     "chart": "mostPopular",
        #     "regionCode": market,
        #     "maxResults": 50,
        #     "key": youtube_api_key
        # }
        pass

    # Fallback to sample data
    return _get_sample_youtube_data(market)


def _fetch_tiktok_stats(market: str, time_window: str) -> List[Dict[str, Any]]:
    """Fetch TikTok trending videos"""
    tiktok_token = os.getenv("TIKTOK_CONNECTOR_TOKEN")

    if tiktok_token:
        # TODO: Implement TikTok API call (requires official connector)
        pass

    # Fallback to sample data
    return _get_sample_tiktok_data(market)


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


def topic_cluster(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Cluster videos by topic (simple keyword-based clustering)

    Args:
        items: List of video statistics

    Returns:
        Topic clustering results
    """
    print(f"[topic_cluster] Clustering {len(items)} videos...")

    # Simple keyword-based clustering (production: use embeddings + KMeans)
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

    clusters = {}

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
    clusters: List[Dict[str, Any]]
) -> str:
    """
    Generate success factors and recommendations

    Args:
        query: Original search query
        spike_videos: List of spike videos
        clusters: Topic cluster results

    Returns:
        Success factors analysis text
    """
    print(f"[generate_success_factors] Analyzing {len(spike_videos)} spike videos...")

    # TODO: Use Azure OpenAI for real analysis

    summary_lines = []

    if spike_videos:
        top_video = spike_videos[0]
        summary_lines.append(f"**최고 성과 영상**: {top_video['title']}")
        summary_lines.append(f"- 조회수: {top_video['views']:,}")
        summary_lines.append(f"- Z-Score: {top_video.get('z_score', 0):.2f}")
        summary_lines.append("")

    if clusters:
        top_cluster = clusters[0]
        summary_lines.append(f"**가장 인기 있는 토픽**: {top_cluster['topic']}")
        summary_lines.append(f"- 영상 수: {top_cluster['count']}개")
        summary_lines.append(f"- 평균 조회수: {top_cluster['avg_views']:,}")
        summary_lines.append("")

    summary_lines.append("**성공 요인:**")
    summary_lines.append("1. **타이밍**: 트렌드를 빠르게 포착하여 초기에 콘텐츠 발행")
    summary_lines.append("2. **주제**: 대중의 관심사와 일치하는 토픽 선택")
    summary_lines.append("3. **참여도**: 좋아요/댓글 비율이 높은 콘텐츠")
    summary_lines.append("")

    summary_lines.append("**실행 권고안:**")
    summary_lines.append("- 급상승 영상의 포맷과 스타일 참고")
    summary_lines.append("- 인기 토픽 클러스터를 중심으로 콘텐츠 기획")
    summary_lines.append("- 시청자 참여를 유도하는 요소 강화 (질문, 투표 등)")

    return "\n".join(summary_lines)
