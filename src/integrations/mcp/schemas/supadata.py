from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SupadataXPost(BaseModel):
    id: Optional[str] = None
    url: Optional[str] = None
    text: str = ""
    created_at: Optional[str] = None


class SupadataTikTokVideo(BaseModel):
    id: Optional[str] = None
    url: Optional[str] = None
    title: str = ""
    author: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    published_at: Optional[str] = None
    thumbnail: Optional[str] = None


class SupadataYouTubeVideo(BaseModel):
    id: Optional[str] = None
    url: Optional[str] = None
    title: str = ""
    channel: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    published_at: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None


class SupadataToolResponse(BaseModel):
    """
    Supadata MCP tool 응답의 최소 공통 형태.

    실제 응답은 툴마다 다를 수 있어, 아래처럼 items/tweets/videos 등
    주요 후보 키를 받아서 파서가 우선순위로 해석합니다.
    """

    tweets: Optional[List[Dict[str, Any]]] = None
    videos: Optional[List[Dict[str, Any]]] = None
    items: Optional[List[Dict[str, Any]]] = None
    results: Optional[List[Dict[str, Any]]] = None

    raw: Dict[str, Any] = Field(default_factory=dict, description="원본 응답 전체(디버깅용)")


