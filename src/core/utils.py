"""
Core Utilities
"""

from __future__ import annotations

import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def parse_timestamp(value: Any) -> Optional[float]:
    """
    다양한 형식의 타임스탬프를 Unix timestamp(float)로 변환합니다.

    지원 형식:
    - Unix timestamp (int/float/str)
    - ISO 8601 (e.g., "2023-01-01T12:00:00Z")
    - RFC 2822 (e.g., "Sun, 01 Jan 2023 12:00:00 +0000")
    - YYYY-MM-DD HH:MM:SS

    Returns:
        Unix timestamp (float) or None if parsing fails
    """
    if value is None:
        return None

    # 이미 숫자형인 경우
    if isinstance(value, (int, float)):
        # 밀리초 단위인 경우 (예: 13자리 정수) 초 단위로 변환
        if value > 1e11:
            return float(value) / 1000.0
        return float(value)

    if not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    # 숫자 문자열인 경우
    try:
        float_val = float(value)
        if float_val > 1e11:
            return float_val / 1000.0
        return float_val
    except ValueError:
        pass

    # 날짜 문자열 파싱 시도
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601 with timezone
        "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO 8601 with ms & timezone
        "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601 UTC
        "%Y-%m-%dT%H:%M:%S",  # ISO 8601 no timezone
        "%Y-%m-%d %H:%M:%S",  # Generic
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
        "%a, %d %b %Y %H:%M:%S %Z",  # RFC 2822 with zone name
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            # 타임존 정보가 없으면 UTC로 가정
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue

    # dateutil이 설치되어 있다면 최후의 수단으로 사용
    try:
        from dateutil import parser

        dt = parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ImportError:
        pass
    except Exception:
        pass

    logger.debug(f"Failed to parse timestamp: {value}")
    return None


def deduplicate_items(
    items: List[Dict[str, Any]], unique_keys: List[str] = ["url", "id"]
) -> List[Dict[str, Any]]:
    """
    리스트 내 딕셔너리 중복 제거.

    우선순위:
    1. unique_keys에 지정된 필드 값이 같으면 중복으로 간주.
    2. 키가 없으면 본문(content/description) 해시로 중복 체크.

    Args:
        items: 아이템 리스트
        unique_keys: 고유 식별자로 사용할 필드명 목록 (우선순위 순)

    Returns:
        중복 제거된 리스트
    """
    seen = set()
    unique_items = []

    for item in items:
        identifier = None

        # 1. 지정된 키로 식별 시도
        for key in unique_keys:
            val = item.get(key)
            if val:
                identifier = f"{key}:{val}"
                break

        # 2. 실패 시 내용 해시 사용
        if not identifier:
            content = item.get("content") or item.get("description") or item.get("title") or ""
            if content:
                # 짧은 내용은 해시 충돌 가능성이 있으나 트렌드 분석용으로는 허용
                identifier = f"hash:{hashlib.md5(str(content).encode()).hexdigest()}"
            else:
                # 식별 불가한 아이템은 그냥 추가 (또는 제외?) -> 일단 추가
                unique_items.append(item)
                continue

        if identifier not in seen:
            seen.add(identifier)
            unique_items.append(item)

    return unique_items


def filter_by_time_window(
    items: List[Dict[str, Any]], time_window_hours: int = 24, timestamp_key: str = "published_at"
) -> List[Dict[str, Any]]:
    """
    지정된 시간 범위 내의 아이템만 필터링합니다.

    Args:
        items: 아이템 리스트 (timestamp_key 필드는 Unix timestamp float여야 함)
        time_window_hours: 최근 N시간
        timestamp_key: 타임스탬프 필드명

    Returns:
        필터링된 리스트
    """
    if time_window_hours <= 0:
        return items

    now = time.time()
    cutoff = now - (time_window_hours * 3600)

    filtered = []
    for item in items:
        ts = item.get(timestamp_key)
        if ts is None:
            # 타임스탬프가 없으면 보수적으로 포함 (또는 정책에 따라 제외)
            filtered.append(item)
            continue

        if isinstance(ts, (int, float)) and ts >= cutoff:
            filtered.append(item)

    return filtered
