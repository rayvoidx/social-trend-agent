"""
Unit tests for AsyncRedisCache

Tests async Redis cache functionality with mocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pickle


@pytest.mark.asyncio
class TestAsyncRedisCache:
    """Test AsyncRedisCache class."""

    @pytest.fixture
    async def mock_redis(self):
        """Create mock Redis client."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.setex = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.exists = AsyncMock(return_value=False)
        mock_client.scan_iter = AsyncMock(return_value=[])
        return mock_client

    @pytest.fixture
    async def cache(self, mock_redis):
        """Create AsyncRedisCache instance with mocked Redis."""
        with patch(
            "src.infrastructure.storage.async_redis_cache.get_async_redis_client",
            return_value=mock_redis,
        ):
            from src.infrastructure.storage.async_redis_cache import AsyncRedisCache

            cache = AsyncRedisCache(prefix="test", default_ttl=60)
            await cache._ensure_client()
            return cache

    async def test_get_miss(self, cache, mock_redis):
        """Test cache miss returns None."""
        mock_redis.get.return_value = None

        result = await cache.get("missing_key")

        assert result is None
        mock_redis.get.assert_called_once_with("test:missing_key")

    async def test_get_hit(self, cache, mock_redis):
        """Test cache hit returns value."""
        test_value = {"data": "test"}
        mock_redis.get.return_value = pickle.dumps(test_value)

        result = await cache.get("existing_key")

        assert result == test_value
        mock_redis.get.assert_called_once_with("test:existing_key")

    async def test_set(self, cache, mock_redis):
        """Test setting value in cache."""
        test_value = {"data": "test"}

        success = await cache.set("test_key", test_value, ttl=120)

        assert success is True
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == "test:test_key"
        assert args[0][1] == 120
        assert pickle.loads(args[0][2]) == test_value

    async def test_delete(self, cache, mock_redis):
        """Test deleting key from cache."""
        success = await cache.delete("test_key")

        assert success is True
        mock_redis.delete.assert_called_once_with("test:test_key")

    async def test_exists_false(self, cache, mock_redis):
        """Test key doesn't exist."""
        mock_redis.exists.return_value = 0

        result = await cache.exists("missing_key")

        assert result is False
        mock_redis.exists.assert_called_once_with("test:missing_key")

    async def test_exists_true(self, cache, mock_redis):
        """Test key exists."""
        mock_redis.exists.return_value = 1

        result = await cache.exists("existing_key")

        assert result is True
        mock_redis.exists.assert_called_once_with("test:existing_key")

    async def test_get_json(self, cache, mock_redis):
        """Test getting JSON value."""
        test_data = {"key": "value", "number": 42}
        import json

        mock_redis.get.return_value = json.dumps(test_data).encode("utf-8")

        result = await cache.get_json("json_key")

        assert result == test_data

    async def test_set_json(self, cache, mock_redis):
        """Test setting JSON value."""
        test_data = {"key": "value", "number": 42}

        success = await cache.set_json("json_key", test_data, ttl=180)

        assert success is True
        mock_redis.setex.assert_called_once()

    async def test_health_check_healthy(self, cache, mock_redis):
        """Test health check when Redis is healthy."""
        mock_redis.ping.return_value = True

        result = await cache.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    async def test_health_check_unhealthy(self, cache, mock_redis):
        """Test health check when Redis is unhealthy."""
        mock_redis.ping.side_effect = Exception("Connection failed")

        result = await cache.health_check()

        assert result is False

    async def test_invalidate_pattern(self, cache, mock_redis):
        """Test invalidating keys by pattern."""

        async def mock_scan():
            """Mock scan iterator."""
            for key in [b"test:key1", b"test:key2", b"test:key3"]:
                yield key

        mock_redis.scan_iter.return_value = mock_scan()
        mock_redis.delete.return_value = 3

        deleted = await cache.invalidate_pattern("key*")

        assert deleted == 3
        mock_redis.delete.assert_called_once()


@pytest.mark.asyncio
class TestCacheKeyGeneration:
    """Test cache key generation utilities."""

    def test_cache_key_from_request_basic(self):
        """Test basic cache key generation."""
        from src.infrastructure.storage.async_redis_cache import cache_key_from_request

        key = cache_key_from_request("/api/insights", {"limit": 10})

        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length

    def test_cache_key_from_request_with_user(self):
        """Test cache key generation with user ID."""
        from src.infrastructure.storage.async_redis_cache import cache_key_from_request

        key1 = cache_key_from_request("/api/insights", {"limit": 10}, user_id="user1")
        key2 = cache_key_from_request("/api/insights", {"limit": 10}, user_id="user2")

        assert key1 != key2

    def test_cache_key_from_request_consistency(self):
        """Test cache key is consistent for same inputs."""
        from src.infrastructure.storage.async_redis_cache import cache_key_from_request

        key1 = cache_key_from_request("/api/tasks", {"status": "completed", "limit": 50})
        key2 = cache_key_from_request("/api/tasks", {"status": "completed", "limit": 50})

        assert key1 == key2

    def test_cache_key_from_request_param_order(self):
        """Test cache key is same regardless of param order."""
        from src.infrastructure.storage.async_redis_cache import cache_key_from_request

        # JSON dumps sorts keys, so order shouldn't matter
        key1 = cache_key_from_request("/api/test", {"a": 1, "b": 2})
        key2 = cache_key_from_request("/api/test", {"b": 2, "a": 1})

        assert key1 == key2
