"""
Unit tests for cache module (SimpleCache and DiskCache)
"""

import pytest
import time
import tempfile
import shutil
from pathlib import Path


class TestSimpleCache:
    """Test SimpleCache class."""

    @pytest.fixture
    def cache(self):
        """Create SimpleCache instance."""
        from src.infrastructure.cache import SimpleCache

        return SimpleCache(default_ttl=60)

    def test_set_and_get(self, cache):
        """Test setting and getting a value."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self, cache):
        """Test getting a non-existent key returns None."""
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self, cache):
        """Test that values expire after TTL."""
        cache.set("key1", "value1", ttl=1)
        assert cache.get("key1") == "value1"

        # Wait for expiry
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_custom_ttl(self, cache):
        """Test custom TTL."""
        cache.set("key1", "value1", ttl=2)
        time.sleep(1)
        assert cache.get("key1") == "value1"

    def test_clear(self, cache):
        """Test clearing cache."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_size(self, cache):
        """Test cache size."""
        assert cache.size() == 0

        cache.set("key1", "value1")
        assert cache.size() == 1

        cache.set("key2", "value2")
        assert cache.size() == 2

        cache.clear()
        assert cache.size() == 0

    def test_complex_values(self, cache):
        """Test caching complex Python objects."""
        complex_value = {"list": [1, 2, 3], "dict": {"nested": True}, "tuple": (1, 2)}

        cache.set("complex", complex_value)
        assert cache.get("complex") == complex_value


class TestDiskCache:
    """Test DiskCache class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for disk cache."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def cache(self, temp_dir):
        """Create DiskCache instance."""
        from src.infrastructure.cache import DiskCache

        return DiskCache(cache_dir=temp_dir, default_ttl=60)

    def test_set_and_get(self, cache):
        """Test setting and getting a value from disk."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_persistence(self, cache, temp_dir):
        """Test that values persist across cache instances."""
        from src.infrastructure.cache import DiskCache

        cache.set("persistent", "data")

        # Create new cache instance with same directory
        new_cache = DiskCache(cache_dir=temp_dir)
        assert new_cache.get("persistent") == "data"

    def test_ttl_expiry(self, cache):
        """Test that disk cache values expire."""
        cache.set("key1", "value1", ttl=1)
        assert cache.get("key1") == "value1"

        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_clear(self, cache, temp_dir):
        """Test clearing disk cache."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

        # Check that files are deleted
        cache_files = list(Path(temp_dir).glob("*.pkl"))
        assert len(cache_files) == 0


class TestCachedDecorator:
    """Test @cached decorator."""

    def test_basic_caching(self):
        """Test that function results are cached."""
        from src.infrastructure.cache import cached

        call_count = 0

        @cached(ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - executes function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - returns cached result
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

        # Different argument - executes function
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    def test_cache_clear(self):
        """Test clearing function cache."""
        from src.infrastructure.cache import cached

        @cached(ttl=60)
        def func(x):
            return x * 2

        func(5)
        func.cache_clear()

        # After clear, function should execute again
        func(5)


class TestCacheKeyGeneration:
    """Test cache key generation utilities."""

    def test_cache_key_from_query(self):
        """Test cache key generation from query."""
        from src.infrastructure.cache import cache_key_from_query

        key1 = cache_key_from_query("test query", param1="value1", param2="value2")
        key2 = cache_key_from_query("test query", param1="value1", param2="value2")

        # Same inputs should produce same key
        assert key1 == key2

        # Different inputs should produce different keys
        key3 = cache_key_from_query("different query", param1="value1")
        assert key1 != key3

    def test_cache_key_consistency(self):
        """Test that cache keys are consistent."""
        from src.infrastructure.cache import cache_key_from_query

        # Same params in different order should produce same key
        # (because JSON dumps sorts keys)
        key1 = cache_key_from_query("query", a=1, b=2)
        key2 = cache_key_from_query("query", b=2, a=1)

        assert key1 == key2
