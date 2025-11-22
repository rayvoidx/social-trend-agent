"""
Redis 캐시 및 저장소

기능:
- TTL 기반 캐싱
- 중복 체크 키 관리
- Job 상태 관리
- 실시간 데이터 버퍼
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Redis client (lazy import)
_redis_client = None


def get_redis_client():
    """Get Redis client instance (singleton)."""
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        import redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_db = int(os.getenv("REDIS_DB", "0"))

        _redis_client = redis.from_url(
            redis_url,
            db=redis_db,
            decode_responses=False,  # We'll handle encoding ourselves
            socket_connect_timeout=5,
            socket_timeout=5,
        )

        # Test connection
        _redis_client.ping()
        logger.info(f"Connected to Redis: {redis_url}")

        return _redis_client

    except ImportError:
        logger.warning("redis package not installed. Using in-memory fallback.")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}. Using in-memory fallback.")
        return None


class RedisCache:
    """
    Redis 기반 캐시 클래스.

    Redis 연결 실패 시 인메모리 폴백 사용.
    """

    def __init__(
        self,
        prefix: str = "trend",
        default_ttl: int = 3600,
    ):
        """
        Args:
            prefix: 키 프리픽스
            default_ttl: 기본 TTL (초)
        """
        self.prefix = prefix
        self.default_ttl = default_ttl
        self._client = get_redis_client()

        # In-memory fallback
        self._memory_cache: Dict[str, Any] = {}
        self._memory_expiry: Dict[str, float] = {}

    def _make_key(self, key: str) -> str:
        """Generate prefixed key."""
        return f"{self.prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 값 조회.

        Args:
            key: 캐시 키

        Returns:
            저장된 값 또는 None
        """
        full_key = self._make_key(key)

        if self._client:
            try:
                data = self._client.get(full_key)
                if data:
                    return pickle.loads(data)
                return None
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # Fallback to memory
        import time
        if full_key in self._memory_cache:
            if self._memory_expiry.get(full_key, 0) > time.time():
                return self._memory_cache[full_key]
            else:
                del self._memory_cache[full_key]
                self._memory_expiry.pop(full_key, None)

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        캐시에 값 저장.

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL (초)

        Returns:
            성공 여부
        """
        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl

        if self._client:
            try:
                data = pickle.dumps(value)
                self._client.setex(full_key, ttl, data)
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # Fallback to memory
        import time
        self._memory_cache[full_key] = value
        self._memory_expiry[full_key] = time.time() + ttl
        return True

    def delete(self, key: str) -> bool:
        """캐시에서 키 삭제."""
        full_key = self._make_key(key)

        if self._client:
            try:
                self._client.delete(full_key)
                return True
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        # Fallback
        self._memory_cache.pop(full_key, None)
        self._memory_expiry.pop(full_key, None)
        return True

    def exists(self, key: str) -> bool:
        """키 존재 여부 확인."""
        full_key = self._make_key(key)

        if self._client:
            try:
                return bool(self._client.exists(full_key))
            except Exception as e:
                logger.error(f"Redis exists error: {e}")

        return full_key in self._memory_cache

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """JSON 형식으로 저장된 값 조회."""
        full_key = self._make_key(key)

        if self._client:
            try:
                data = self._client.get(full_key)
                if data:
                    return json.loads(data.decode("utf-8"))
                return None
            except Exception as e:
                logger.error(f"Redis get_json error: {e}")

        return self._memory_cache.get(full_key)

    def set_json(
        self,
        key: str,
        value: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """JSON 형식으로 값 저장."""
        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl

        if self._client:
            try:
                data = json.dumps(value, ensure_ascii=False)
                self._client.setex(full_key, ttl, data.encode("utf-8"))
                return True
            except Exception as e:
                logger.error(f"Redis set_json error: {e}")

        self._memory_cache[full_key] = value
        return True

    # =========================================================================
    # Deduplication
    # =========================================================================

    def check_duplicate(self, content_hash: str) -> bool:
        """
        콘텐츠 중복 여부 확인.

        Args:
            content_hash: 콘텐츠 해시

        Returns:
            중복 여부
        """
        key = f"dedup:{content_hash}"
        return self.exists(key)

    def mark_as_seen(
        self,
        content_hash: str,
        ttl: Optional[int] = None
    ):
        """
        콘텐츠를 처리됨으로 표시.

        Args:
            content_hash: 콘텐츠 해시
            ttl: TTL (기본값: 24시간)
        """
        key = f"dedup:{content_hash}"
        ttl = ttl or int(os.getenv("REDIS_DEDUP_TTL", "86400"))
        self.set(key, 1, ttl=ttl)

    def get_content_hash(self, url: str, content: str = "") -> str:
        """URL과 콘텐츠로 해시 생성."""
        data = f"{url}:{content[:200]}"
        return hashlib.sha256(data.encode()).hexdigest()

    # =========================================================================
    # Job State Management
    # =========================================================================

    def set_job_state(
        self,
        job_id: str,
        state: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Job 상태 저장.

        Args:
            job_id: Job ID
            state: 상태 (pending, running, completed, failed)
            metadata: 추가 메타데이터
        """
        key = f"job:{job_id}"
        data = {
            "state": state,
            "updated_at": __import__("time").time(),
            **(metadata or {}),
        }
        self.set_json(key, data, ttl=86400)  # 24 hours

    def get_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Job 상태 조회."""
        key = f"job:{job_id}"
        return self.get_json(key)

    # =========================================================================
    # List Operations (for buffering)
    # =========================================================================

    def push_to_list(
        self,
        key: str,
        value: Any,
        max_size: int = 1000
    ):
        """
        리스트에 값 추가 (FIFO 버퍼).

        Args:
            key: 리스트 키
            value: 추가할 값
            max_size: 최대 리스트 크기
        """
        full_key = self._make_key(f"list:{key}")

        if self._client:
            try:
                data = pickle.dumps(value)
                self._client.lpush(full_key, data)
                self._client.ltrim(full_key, 0, max_size - 1)
                return
            except Exception as e:
                logger.error(f"Redis push_to_list error: {e}")

        # Fallback
        if full_key not in self._memory_cache:
            self._memory_cache[full_key] = []
        self._memory_cache[full_key].insert(0, value)
        self._memory_cache[full_key] = self._memory_cache[full_key][:max_size]

    def get_list(
        self,
        key: str,
        start: int = 0,
        end: int = -1
    ) -> List[Any]:
        """리스트 조회."""
        full_key = self._make_key(f"list:{key}")

        if self._client:
            try:
                data = self._client.lrange(full_key, start, end)
                return [pickle.loads(item) for item in data]
            except Exception as e:
                logger.error(f"Redis get_list error: {e}")

        # Fallback
        items = self._memory_cache.get(full_key, [])
        if end == -1:
            return items[start:]
        return items[start:end + 1]

    # =========================================================================
    # Set Operations (for unique collections)
    # =========================================================================

    def add_to_set(self, key: str, value: str) -> bool:
        """Set에 값 추가."""
        full_key = self._make_key(f"set:{key}")

        if self._client:
            try:
                self._client.sadd(full_key, value)
                return True
            except Exception as e:
                logger.error(f"Redis add_to_set error: {e}")

        # Fallback
        if full_key not in self._memory_cache:
            self._memory_cache[full_key] = set()
        self._memory_cache[full_key].add(value)
        return True

    def is_in_set(self, key: str, value: str) -> bool:
        """Set에 값 존재 여부 확인."""
        full_key = self._make_key(f"set:{key}")

        if self._client:
            try:
                return bool(self._client.sismember(full_key, value))
            except Exception as e:
                logger.error(f"Redis is_in_set error: {e}")

        # Fallback
        return value in self._memory_cache.get(full_key, set())

    def get_set(self, key: str) -> Set[str]:
        """Set 전체 조회."""
        full_key = self._make_key(f"set:{key}")

        if self._client:
            try:
                return {
                    item.decode("utf-8") if isinstance(item, bytes) else item
                    for item in self._client.smembers(full_key)
                }
            except Exception as e:
                logger.error(f"Redis get_set error: {e}")

        # Fallback
        return self._memory_cache.get(full_key, set())

    # =========================================================================
    # Counter Operations
    # =========================================================================

    def increment(self, key: str, amount: int = 1) -> int:
        """카운터 증가."""
        full_key = self._make_key(f"counter:{key}")

        if self._client:
            try:
                return self._client.incrby(full_key, amount)
            except Exception as e:
                logger.error(f"Redis increment error: {e}")

        # Fallback
        current = self._memory_cache.get(full_key, 0)
        new_value = current + amount
        self._memory_cache[full_key] = new_value
        return new_value

    def get_counter(self, key: str) -> int:
        """카운터 값 조회."""
        full_key = self._make_key(f"counter:{key}")

        if self._client:
            try:
                value = self._client.get(full_key)
                return int(value) if value else 0
            except Exception as e:
                logger.error(f"Redis get_counter error: {e}")

        return self._memory_cache.get(full_key, 0)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def clear_prefix(self, pattern: str):
        """특정 패턴의 키 모두 삭제."""
        full_pattern = self._make_key(pattern)

        if self._client:
            try:
                keys = self._client.keys(f"{full_pattern}*")
                if keys:
                    self._client.delete(*keys)
                return
            except Exception as e:
                logger.error(f"Redis clear_prefix error: {e}")

        # Fallback
        to_delete = [
            k for k in self._memory_cache.keys()
            if k.startswith(full_pattern)
        ]
        for k in to_delete:
            del self._memory_cache[k]

    def health_check(self) -> bool:
        """Redis 연결 상태 확인."""
        if self._client:
            try:
                self._client.ping()
                return True
            except Exception:
                return False
        return False


# Global cache instance
_global_cache: Optional[RedisCache] = None


def get_cache(prefix: str = "trend") -> RedisCache:
    """Get global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = RedisCache(prefix=prefix)
    return _global_cache
