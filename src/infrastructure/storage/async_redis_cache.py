"""
Async Redis cache for FastAPI endpoints

Features:
- Async/await support for FastAPI
- Response caching with TTL
- Cache invalidation
- Prometheus metrics integration
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
from typing import Any, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Async Redis client (lazy import)
_async_redis_client = None


async def get_async_redis_client():
    """Get async Redis client instance (singleton)."""
    global _async_redis_client

    if _async_redis_client is not None:
        return _async_redis_client

    try:
        import redis.asyncio as aioredis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_db = int(os.getenv("REDIS_DB", "0"))

        _async_redis_client = await aioredis.from_url(
            redis_url,
            db=redis_db,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

        # Test connection
        await _async_redis_client.ping()
        logger.info(f"Connected to async Redis: {redis_url}")

        return _async_redis_client

    except ImportError:
        logger.warning("redis[asyncio] package not installed. Caching disabled.")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to async Redis: {e}. Caching disabled.")
        return None


class AsyncRedisCache:
    """
    Async Redis cache for FastAPI endpoints.

    Optimized for:
    - High-throughput API responses
    - Concurrent requests
    - Automatic serialization
    """

    def __init__(
        self,
        prefix: str = "api",
        default_ttl: int = 300,  # 5 minutes default for API responses
    ):
        """
        Args:
            prefix: Key prefix for namespace isolation
            default_ttl: Default TTL in seconds
        """
        self.prefix = prefix
        self.default_ttl = default_ttl
        self._client = None
        self._initialized = False

    async def _ensure_client(self):
        """Ensure Redis client is initialized."""
        if not self._initialized:
            self._client = await get_async_redis_client()
            self._initialized = True

    def _make_key(self, key: str) -> str:
        """Generate prefixed key."""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        await self._ensure_client()

        if not self._client:
            return None

        full_key = self._make_key(key)

        try:
            data = await self._client.get(full_key)
            if data:
                logger.debug(f"Cache HIT: {key}")
                return pickle.loads(data)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (default: self.default_ttl)

        Returns:
            Success status
        """
        await self._ensure_client()

        if not self._client:
            return False

        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl

        try:
            data = pickle.dumps(value)
            await self._client.setex(full_key, ttl, data)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        await self._ensure_client()

        if not self._client:
            return False

        full_key = self._make_key(key)

        try:
            await self._client.delete(full_key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        await self._ensure_client()

        if not self._client:
            return False

        full_key = self._make_key(key)

        try:
            return bool(await self._client.exists(full_key))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON value from cache."""
        await self._ensure_client()

        if not self._client:
            return None

        full_key = self._make_key(key)

        try:
            data = await self._client.get(full_key)
            if data:
                return json.loads(data.decode("utf-8"))
            return None
        except Exception as e:
            logger.error(f"Redis get_json error: {e}")
            return None

    async def set_json(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set JSON value in cache."""
        await self._ensure_client()

        if not self._client:
            return False

        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl

        try:
            data = json.dumps(value, ensure_ascii=False)
            await self._client.setex(full_key, ttl, data.encode("utf-8"))
            logger.debug(f"Cache SET_JSON: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Redis set_json error: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "insights:*")

        Returns:
            Number of keys deleted
        """
        await self._ensure_client()

        if not self._client:
            return 0

        full_pattern = self._make_key(pattern)

        try:
            keys = []
            async for key in self._client.scan_iter(match=f"{full_pattern}*"):
                keys.append(key)

            if keys:
                deleted = await self._client.delete(*keys)
                logger.info(f"Cache INVALIDATE: {pattern} ({deleted} keys)")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Redis invalidate_pattern error: {e}")
            return 0

    async def health_check(self) -> bool:
        """Check Redis connection health."""
        await self._ensure_client()

        if not self._client:
            return False

        try:
            await self._client.ping()
            return True
        except Exception:
            return False


# Global cache instance
_global_async_cache: Optional[AsyncRedisCache] = None


def get_async_cache(prefix: str = "api") -> AsyncRedisCache:
    """Get global async cache instance."""
    global _global_async_cache
    if _global_async_cache is None:
        _global_async_cache = AsyncRedisCache(prefix=prefix)
    return _global_async_cache


def cache_key_from_request(
    path: str,
    query_params: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> str:
    """
    Generate cache key from request parameters.

    Args:
        path: Request path (e.g., "/api/insights")
        query_params: Query parameters dict
        user_id: Optional user ID for user-specific caching

    Returns:
        MD5 hash of request components
    """
    parts = [path]

    if query_params:
        # Sort to ensure consistent keys
        sorted_params = json.dumps(query_params, sort_keys=True)
        parts.append(sorted_params)

    if user_id:
        parts.append(user_id)

    combined = ":".join(parts)
    return hashlib.md5(combined.encode()).hexdigest()


# ============================================================================
# FastAPI Dependency for caching
# ============================================================================


def cached_endpoint(
    ttl: int = 300,
    key_func: Optional[callable] = None,
    prefix: str = "endpoint",
):
    """
    Decorator for caching FastAPI endpoint responses.

    Args:
        ttl: Cache TTL in seconds
        key_func: Optional function to generate cache key from args
        prefix: Cache key prefix

    Example:
        @app.get("/api/insights")
        @cached_endpoint(ttl=600, prefix="insights")
        async def list_insights(source: Optional[str] = None):
            # ... expensive operation ...
            return result
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_async_cache(prefix=prefix)

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: function name + args
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            # Try cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator
