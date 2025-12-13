"""
API 응답 및 비용이 큰 연산을 위한 캐싱 유틸리티
"""

import time
import hashlib
import json
import pickle
from pathlib import Path
from typing import Callable, Any, Optional
import functools
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    TTL(Time To Live)을 지원하는 간단한 인메모리 캐시
    """

    def __init__(self, default_ttl: int = 3600):
        """
        Args:
            default_ttl: 기본 TTL 시간(초) (기본값: 1시간)
        """
        self._cache = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """만료되지 않은 경우 캐시에서 값 조회"""
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]

        if time.time() > expiry:
            # Expired, remove from cache
            del self._cache[key]
            logger.debug(f"Cache expired: {key}")
            return None

        logger.debug(f"Cache hit: {key}")
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """TTL과 함께 캐시에 값 설정"""
        if ttl is None:
            ttl = self.default_ttl

        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def clear(self):
        """모든 캐시 삭제"""
        self._cache.clear()
        logger.debug("Cache cleared")

    def size(self) -> int:
        """캐시 내 항목 수 조회"""
        return len(self._cache)


class DiskCache:
    """
    영구 저장을 위한 디스크 기반 캐시
    """

    def __init__(self, cache_dir: str = ".cache", default_ttl: int = 86400):
        """
        Args:
            cache_dir: 캐시 파일을 저장할 디렉토리
            default_ttl: 기본 TTL 시간(초) (기본값: 24시간)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    def _get_cache_path(self, key: str) -> Path:
        """캐시 키에 대한 파일 경로 반환"""
        # Hash the key to create a valid filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.pkl"

    def get(self, key: str) -> Optional[Any]:
        """만료되지 않은 경우 디스크 캐시에서 값 조회"""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)

            value, expiry = data["value"], data["expiry"]

            if time.time() > expiry:
                # Expired, remove file
                cache_path.unlink()
                logger.debug(f"Disk cache expired: {key}")
                return None

            logger.debug(f"Disk cache hit: {key}")
            return value

        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """TTL과 함께 디스크 캐시에 값 설정"""
        if ttl is None:
            ttl = self.default_ttl

        cache_path = self._get_cache_path(key)
        expiry = time.time() + ttl

        try:
            with open(cache_path, "wb") as f:
                pickle.dump({"value": value, "expiry": expiry}, f)

            logger.debug(f"Disk cache set: {key} (TTL: {ttl}s)")

        except Exception as e:
            logger.error(f"Error writing cache: {e}")

    def clear(self):
        """모든 디스크 캐시 삭제"""
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        logger.debug("Disk cache cleared")


# Global cache instances
_memory_cache = SimpleCache(default_ttl=3600)  # 1 hour
_disk_cache = DiskCache(cache_dir=".cache/agents", default_ttl=86400)  # 24 hours


def cached(ttl: int = 3600, use_disk: bool = False, key_func: Optional[Callable] = None):
    """
    함수 결과를 캐싱하는 데코레이터

    Args:
        ttl: TTL 시간(초)
        use_disk: 메모리 캐시 대신 디스크 캐시 사용
        key_func: args/kwargs로부터 캐시 키를 생성하는 선택적 함수

    Example:
        @cached(ttl=3600)
        def expensive_operation(param1, param2):
            # ... 비용이 큰 연산 ...
            return result
    """

    def decorator(func: Callable) -> Callable:
        cache = _disk_cache if use_disk else _memory_cache

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name + args + kwargs
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl=ttl)

            return result

        # Add cache management methods
        wrapper.cache_clear = cache.clear
        wrapper.cache_size = cache.size if hasattr(cache, "size") else lambda: 0

        return wrapper

    return decorator


def cache_key_from_query(query: str, **params) -> str:
    """
    쿼리와 파라미터로부터 캐시 키 생성

    일관된 파라미터 구조를 가진 API 호출에 유용합니다.
    """
    params_str = json.dumps(params, sort_keys=True)
    combined = f"{query}:{params_str}"
    return hashlib.md5(combined.encode()).hexdigest()


# Example usage:
if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.DEBUG)

    @cached(ttl=5)  # Cache for 5 seconds
    def slow_function(x):
        """Simulates a slow function"""
        print(f"Computing {x}...")
        time.sleep(2)
        return x * 2

    # First call - should take 2 seconds
    print(f"Result 1: {slow_function(5)}")

    # Second call - should be instant (cached)
    print(f"Result 2: {slow_function(5)}")

    # Wait for cache to expire
    time.sleep(6)

    # Third call - should take 2 seconds again
    print(f"Result 3: {slow_function(5)}")
