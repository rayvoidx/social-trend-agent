"""
날짜 파싱 및 타임 윈도우 유틸리티

다양한 소스의 날짜 형식을 통합 처리하고,
타임 윈도우 기반 필터링을 지원합니다.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Date Parsing
# =============================================================================

def parse_datetime(date_str: Union[str, int, float, None]) -> Optional[float]:
    """
    다양한 형식의 날짜를 Unix timestamp로 변환.

    지원 형식:
    - ISO 8601 (2023-11-21T09:00:00Z)
    - RFC 2822 (Tue, 21 Nov 2023 09:00:00 +0900)
    - Twitter/X format
    - Instagram format
    - TikTok timestamp
    - Naver format (YYYYMMDD)
    - Unix timestamp (int/float)

    Args:
        date_str: 파싱할 날짜 문자열 또는 타임스탬프

    Returns:
        Unix timestamp (float) 또는 None
    """
    if date_str is None:
        return None

    # Already a timestamp
    if isinstance(date_str, (int, float)):
        # TikTok sometimes uses milliseconds
        if date_str > 1e12:
            return date_str / 1000
        return float(date_str)

    if not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    if not date_str:
        return None

    # Try different parsers
    parsers = [
        _parse_iso8601,
        _parse_rfc2822,
        _parse_naver_date,
        _parse_korean_date,
        _parse_relative_date,
        _parse_numeric_date,
    ]

    for parser in parsers:
        try:
            result = parser(date_str)
            if result is not None:
                return result
        except Exception:
            continue

    logger.warning(f"Failed to parse date: {date_str}")
    return None


def _parse_iso8601(date_str: str) -> Optional[float]:
    """Parse ISO 8601 format."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue

    return None


def _parse_rfc2822(date_str: str) -> Optional[float]:
    """Parse RFC 2822 format (email/RSS)."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.timestamp()
    except Exception:
        return None


def _parse_naver_date(date_str: str) -> Optional[float]:
    """Parse Naver date format (YYYYMMDD)."""
    if len(date_str) == 8 and date_str.isdigit():
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.timestamp()
        except ValueError:
            pass
    return None


def _parse_korean_date(date_str: str) -> Optional[float]:
    """Parse Korean date format."""
    # Example: "2023년 11월 21일", "2023.11.21"
    patterns = [
        (r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", "%Y-%m-%d"),
        (r"(\d{4})\.(\d{1,2})\.(\d{1,2})", "%Y-%m-%d"),
    ]

    for pattern, fmt in patterns:
        match = re.match(pattern, date_str)
        if match:
            normalized = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
            try:
                dt = datetime.strptime(normalized, fmt)
                return dt.timestamp()
            except ValueError:
                continue

    return None


def _parse_relative_date(date_str: str) -> Optional[float]:
    """Parse relative date format (e.g., '3일 전', '2 hours ago')."""
    now = datetime.utcnow()

    # Korean patterns
    korean_patterns = [
        (r"(\d+)\s*초\s*전", "seconds"),
        (r"(\d+)\s*분\s*전", "minutes"),
        (r"(\d+)\s*시간\s*전", "hours"),
        (r"(\d+)\s*일\s*전", "days"),
        (r"(\d+)\s*주\s*전", "weeks"),
        (r"(\d+)\s*개월\s*전", "months"),
    ]

    # English patterns
    english_patterns = [
        (r"(\d+)\s*seconds?\s*ago", "seconds"),
        (r"(\d+)\s*minutes?\s*ago", "minutes"),
        (r"(\d+)\s*hours?\s*ago", "hours"),
        (r"(\d+)\s*days?\s*ago", "days"),
        (r"(\d+)\s*weeks?\s*ago", "weeks"),
        (r"(\d+)\s*months?\s*ago", "months"),
    ]

    all_patterns = korean_patterns + english_patterns

    for pattern, unit in all_patterns:
        match = re.match(pattern, date_str, re.IGNORECASE)
        if match:
            value = int(match.group(1))

            if unit == "seconds":
                delta = timedelta(seconds=value)
            elif unit == "minutes":
                delta = timedelta(minutes=value)
            elif unit == "hours":
                delta = timedelta(hours=value)
            elif unit == "days":
                delta = timedelta(days=value)
            elif unit == "weeks":
                delta = timedelta(weeks=value)
            elif unit == "months":
                delta = timedelta(days=value * 30)  # Approximate
            else:
                continue

            result_dt = now - delta
            return result_dt.timestamp()

    return None


def _parse_numeric_date(date_str: str) -> Optional[float]:
    """Parse numeric timestamp."""
    try:
        ts = float(date_str)
        # Milliseconds to seconds
        if ts > 1e12:
            ts = ts / 1000
        # Validate range (1970-2100)
        if 0 < ts < 4102444800:
            return ts
    except (ValueError, TypeError):
        pass
    return None


# =============================================================================
# Time Window Utilities
# =============================================================================

def parse_time_window(time_window: str) -> Tuple[float, float]:
    """
    타임 윈도우 문자열을 시작/종료 타임스탬프로 변환.

    Args:
        time_window: 타임 윈도우 (예: "24h", "7d", "30d", "1w", "1m")

    Returns:
        (start_timestamp, end_timestamp) 튜플

    Examples:
        >>> start, end = parse_time_window("24h")
        >>> start, end = parse_time_window("7d")
    """
    now = time.time()
    end_time = now

    # Parse the time window
    match = re.match(r"(\d+)\s*([hdwmHDWM])", time_window)
    if not match:
        # Default to 24 hours
        logger.warning(f"Invalid time window: {time_window}. Using default 24h.")
        return (now - 86400, now)

    value = int(match.group(1))
    unit = match.group(2).lower()

    if unit == "h":
        delta_seconds = value * 3600
    elif unit == "d":
        delta_seconds = value * 86400
    elif unit == "w":
        delta_seconds = value * 604800
    elif unit == "m":
        delta_seconds = value * 2592000  # 30 days
    else:
        delta_seconds = 86400

    start_time = now - delta_seconds
    return (start_time, end_time)


def get_time_window_bounds(
    time_window: str,
    reference_time: Optional[float] = None
) -> Tuple[datetime, datetime]:
    """
    타임 윈도우의 시작/종료 datetime 객체 반환.

    Args:
        time_window: 타임 윈도우 문자열
        reference_time: 기준 시간 (기본값: 현재 시간)

    Returns:
        (start_datetime, end_datetime) 튜플
    """
    if reference_time is None:
        reference_time = time.time()

    start_ts, end_ts = parse_time_window(time_window)

    # Adjust to reference time
    delta = reference_time - end_ts
    start_ts += delta
    end_ts = reference_time

    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

    return (start_dt, end_dt)


def filter_by_time_window(
    items: List[dict],
    time_window: str,
    timestamp_field: str = "published_at"
) -> List[dict]:
    """
    타임 윈도우로 아이템 필터링.

    Args:
        items: 필터링할 아이템 리스트
        time_window: 타임 윈도우 (예: "24h", "7d")
        timestamp_field: 타임스탬프 필드 이름

    Returns:
        필터링된 아이템 리스트
    """
    start_time, end_time = parse_time_window(time_window)

    filtered = []
    for item in items:
        ts = item.get(timestamp_field)
        if ts is None:
            continue

        # Parse if string
        if isinstance(ts, str):
            ts = parse_datetime(ts)

        if ts and start_time <= ts <= end_time:
            filtered.append(item)

    logger.info(
        f"Filtered {len(items)} items to {len(filtered)} "
        f"within {time_window} window"
    )
    return filtered


def sort_by_time(
    items: List[dict],
    timestamp_field: str = "published_at",
    descending: bool = True
) -> List[dict]:
    """
    시간순으로 아이템 정렬.

    Args:
        items: 정렬할 아이템 리스트
        timestamp_field: 타임스탬프 필드 이름
        descending: 내림차순 정렬 여부 (최신순)

    Returns:
        정렬된 아이템 리스트
    """
    def get_timestamp(item: dict) -> float:
        ts = item.get(timestamp_field)
        if ts is None:
            return 0.0
        if isinstance(ts, str):
            parsed = parse_datetime(ts)
            return parsed if parsed else 0.0
        return float(ts)

    return sorted(items, key=get_timestamp, reverse=descending)


# =============================================================================
# Utility Functions
# =============================================================================

def timestamp_to_iso(timestamp: float) -> str:
    """Unix timestamp를 ISO 8601 문자열로 변환."""
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def timestamp_to_korean(timestamp: float) -> str:
    """Unix timestamp를 한국어 날짜 문자열로 변환."""
    # KST (UTC+9)
    kst = timezone(timedelta(hours=9))
    dt = datetime.fromtimestamp(timestamp, tz=kst)
    return dt.strftime("%Y년 %m월 %d일 %H:%M")


def get_date_range_str(start_ts: float, end_ts: float) -> str:
    """시작/종료 타임스탬프를 날짜 범위 문자열로 변환."""
    start_str = timestamp_to_iso(start_ts)[:10]
    end_str = timestamp_to_iso(end_ts)[:10]

    if start_str == end_str:
        return start_str
    return f"{start_str} ~ {end_str}"


def calculate_time_ago(timestamp: float) -> str:
    """타임스탬프를 '~전' 형식으로 변환."""
    now = time.time()
    diff = now - timestamp

    if diff < 60:
        return "방금 전"
    elif diff < 3600:
        return f"{int(diff / 60)}분 전"
    elif diff < 86400:
        return f"{int(diff / 3600)}시간 전"
    elif diff < 604800:
        return f"{int(diff / 86400)}일 전"
    elif diff < 2592000:
        return f"{int(diff / 604800)}주 전"
    else:
        return f"{int(diff / 2592000)}개월 전"


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test date parsing
    test_dates = [
        "2023-11-21T09:00:00Z",
        "2023-11-21T09:00:00.000Z",
        "Tue, 21 Nov 2023 09:00:00 +0900",
        "20231121",
        "2023년 11월 21일",
        "3시간 전",
        "2 days ago",
        1700550000,
        1700550000000,  # Milliseconds
    ]

    print("=== Date Parsing Tests ===")
    for date in test_dates:
        result = parse_datetime(date)
        if result:
            iso_str = timestamp_to_iso(result)
            print(f"{date} -> {iso_str}")
        else:
            print(f"{date} -> Failed")

    # Test time window
    print("\n=== Time Window Tests ===")
    for window in ["24h", "7d", "30d", "1w", "1m"]:
        start, end = parse_time_window(window)
        print(f"{window}: {get_date_range_str(start, end)}")

    # Test filtering
    print("\n=== Filtering Test ===")
    items = [
        {"title": "Item 1", "published_at": time.time() - 3600},      # 1 hour ago
        {"title": "Item 2", "published_at": time.time() - 86400},     # 1 day ago
        {"title": "Item 3", "published_at": time.time() - 604800},    # 1 week ago
        {"title": "Item 4", "published_at": time.time() - 2592000},   # 30 days ago
    ]

    filtered = filter_by_time_window(items, "7d")
    print(f"Items within 7d: {[item['title'] for item in filtered]}")
