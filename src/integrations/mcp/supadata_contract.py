from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.integrations.mcp.schemas.supadata import (
    SupadataToolResponse,
    SupadataTikTokVideo,
    SupadataXPost,
    SupadataYouTubeVideo,
)

logger = logging.getLogger(__name__)


def _pick_list(resp: Dict[str, Any], keys: Sequence[str]) -> List[Dict[str, Any]]:
    for k in keys:
        v = resp.get(k)
        if isinstance(v, list):
            out: List[Dict[str, Any]] = []
            for item in v:
                if isinstance(item, dict):
                    out.append(item)
            return out
    return []


def parse_supadata_x_posts(
    resp: Dict[str, Any],
) -> Tuple[SupadataToolResponse, List[SupadataXPost]]:
    parsed = SupadataToolResponse(
        tweets=resp.get("tweets") if isinstance(resp.get("tweets"), list) else None,
        items=resp.get("items") if isinstance(resp.get("items"), list) else None,
        results=resp.get("results") if isinstance(resp.get("results"), list) else None,
        raw=resp,
    )

    rows = _pick_list(resp, ["tweets", "items", "results"])
    posts: List[SupadataXPost] = []
    for r in rows:
        posts.append(
            SupadataXPost(
                id=_first_str(r, ["id", "tweet_id"]),
                url=_first_str(r, ["url"]),
                text=_first_str(r, ["text", "content"]),
                created_at=_first_str(r, ["created_at", "timestamp", "createdAt"]),
            )
        )
    return parsed, posts


def parse_supadata_tiktok_videos(
    resp: Dict[str, Any],
) -> Tuple[SupadataToolResponse, List[SupadataTikTokVideo]]:
    parsed = SupadataToolResponse(
        videos=resp.get("videos") if isinstance(resp.get("videos"), list) else None,
        items=resp.get("items") if isinstance(resp.get("items"), list) else None,
        results=resp.get("results") if isinstance(resp.get("results"), list) else None,
        raw=resp,
    )

    rows = _pick_list(resp, ["videos", "items", "results"])
    vids: List[SupadataTikTokVideo] = []
    for r in rows:
        vids.append(
            SupadataTikTokVideo(
                id=_first_str(r, ["id", "video_id"]),
                url=_first_str(r, ["url", "webVideoUrl"]),
                title=_first_str(r, ["title", "desc"]),
                author=_first_str(r, ["author", "channel"]),
                views=_first_int(r, ["views", "playCount"]),
                likes=_first_int(r, ["likes", "diggCount"]),
                comments=_first_int(r, ["comments", "commentCount"]),
                published_at=_first_str(r, ["published_at", "createTime"]),
                thumbnail=_first_str(r, ["thumbnail"]),
            )
        )
    return parsed, vids


def parse_supadata_youtube_videos(
    resp: Dict[str, Any],
) -> Tuple[SupadataToolResponse, List[SupadataYouTubeVideo]]:
    parsed = SupadataToolResponse(
        videos=resp.get("videos") if isinstance(resp.get("videos"), list) else None,
        items=resp.get("items") if isinstance(resp.get("items"), list) else None,
        results=resp.get("results") if isinstance(resp.get("results"), list) else None,
        raw=resp,
    )

    rows = _pick_list(resp, ["videos", "items", "results"])
    vids: List[SupadataYouTubeVideo] = []
    for r in rows:
        stats = r.get("statistics") if isinstance(r.get("statistics"), dict) else {}
        snippet = r.get("snippet") if isinstance(r.get("snippet"), dict) else {}

        vids.append(
            SupadataYouTubeVideo(
                id=_first_str(r, ["id", "video_id"]),
                url=_first_str(r, ["url"]),
                title=_first_str(r, ["title"]) or _first_str(snippet, ["title"]),
                channel=_first_str(r, ["channel"]) or _first_str(snippet, ["channelTitle"]),
                views=_first_int(r, ["views"]) or _first_int(stats, ["viewCount"]),
                likes=_first_int(r, ["likes"]) or _first_int(stats, ["likeCount"]),
                comments=_first_int(r, ["comments"]) or _first_int(stats, ["commentCount"]),
                published_at=_first_str(r, ["published_at"])
                or _first_str(snippet, ["publishedAt"]),
                description=_first_str(r, ["description"]) or _first_str(snippet, ["description"]),
                thumbnail=_first_str(r, ["thumbnail"])
                or _first_str(
                    (
                        snippet.get("thumbnails", {}).get("default", {})
                        if isinstance(snippet.get("thumbnails"), dict)
                        else {}
                    ),
                    ["url"],
                ),
            )
        )
    return parsed, vids


def _first_str(d: Dict[str, Any], keys: Sequence[str]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str):
            return v
    return ""


def _first_int(d: Dict[str, Any], keys: Sequence[str]) -> Optional[int]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except Exception:
                continue
    return None
