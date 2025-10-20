"""
Unit tests for caching utilities
"""
import pytest
import time
import tempfile
import shutil
from pathlib import Path
from agents.shared.cache import (
    SimpleCache,
    DiskCache,
    cached,
    disk_cached
)


class TestSimpleCache:
    """Tests for SimpleCache (in-memory)"""

    def test_basic_get_set(self):
        """Test basic cache get/set operations"""
        cache = SimpleCache()

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        cache.set("key2", {"data": "complex"})
        assert cache.get("key2") == {"data": "complex"}

    def test_missing_key(self):
        """Test getting non-existent key returns None"""
        cache = SimpleCache()
        assert cache.get("missing") is None

    def test_ttl_expiry(self):
        """Test TTL expiration"""
        cache = SimpleCache(default_ttl=0.1)  # 100ms TTL

        cache.set("temp", "value")
        assert cache.get("temp") == "value"

        time.sleep(0.15)  # Wait for expiry
        assert cache.get("temp") is None

    def test_custom_ttl(self):
        """Test custom TTL per key"""
        cache = SimpleCache(default_ttl=10.0)

        cache.set("short", "value1", ttl=0.1)
        cache.set("long", "value2", ttl=10.0)

        time.sleep(0.15)

        assert cache.get("short") is None  # Expired
        assert cache.get("long") == "value2"  # Still valid

    def test_clear(self):
        """Test cache clearing"""
        cache = SimpleCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.size() == 2

        cache.clear()

        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_size(self):
        """Test cache size tracking"""
        cache = SimpleCache()

        assert cache.size() == 0

        cache.set("key1", "value1")
        assert cache.size() == 1

        cache.set("key2", "value2")
        assert cache.size() == 2

        # Expired entries not counted
        cache.set("temp", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.size() == 2  # temp expired


class TestDiskCache:
    """Tests for DiskCache (persistent)"""

    def setup_method(self):
        """Create temporary cache directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"

    def teardown_method(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic_get_set(self):
        """Test basic disk cache operations"""
        cache = DiskCache(cache_dir=str(self.cache_dir))

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        cache.set("key2", {"data": [1, 2, 3]})
        assert cache.get("key2") == {"data": [1, 2, 3]}

    def test_persistence(self):
        """Test cache persists across instances"""
        cache1 = DiskCache(cache_dir=str(self.cache_dir))
        cache1.set("persistent", "data")

        # Create new cache instance with same directory
        cache2 = DiskCache(cache_dir=str(self.cache_dir))
        assert cache2.get("persistent") == "data"

    def test_ttl_expiry(self):
        """Test TTL expiration on disk"""
        cache = DiskCache(cache_dir=str(self.cache_dir), default_ttl=0.1)

        cache.set("temp", "value")
        assert cache.get("temp") == "value"

        time.sleep(0.15)
        assert cache.get("temp") is None

    def test_clear(self):
        """Test clearing disk cache"""
        cache = DiskCache(cache_dir=str(self.cache_dir))

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_complex_objects(self):
        """Test caching complex Python objects"""
        cache = DiskCache(cache_dir=str(self.cache_dir))

        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "tuple": (4, 5, 6),
            "set": {7, 8, 9}
        }

        cache.set("complex", complex_data)
        result = cache.get("complex")

        assert result["list"] == [1, 2, 3]
        assert result["dict"] == {"nested": "value"}
        assert result["tuple"] == (4, 5, 6)


class TestCachedDecorator:
    """Tests for @cached decorator"""

    def test_basic_caching(self):
        """Test function result is cached"""
        call_count = [0]

        @cached(ttl=10.0, use_disk=False)
        def expensive_func(x):
            call_count[0] += 1
            return x * 2

        result1 = expensive_func(5)
        result2 = expensive_func(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count[0] == 1  # Called only once

    def test_different_args(self):
        """Test different arguments create different cache entries"""
        call_count = [0]

        @cached(ttl=10.0, use_disk=False)
        def add(a, b):
            call_count[0] += 1
            return a + b

        result1 = add(1, 2)
        result2 = add(3, 4)
        result3 = add(1, 2)

        assert result1 == 3
        assert result2 == 7
        assert result3 == 3
        assert call_count[0] == 2  # Called twice (different args)

    def test_kwargs_caching(self):
        """Test caching with keyword arguments"""
        call_count = [0]

        @cached(ttl=10.0, use_disk=False)
        def func(a, b=10):
            call_count[0] += 1
            return a + b

        result1 = func(5, b=10)
        result2 = func(5, b=10)
        result3 = func(5, b=20)

        assert result1 == 15
        assert result2 == 15
        assert result3 == 25
        assert call_count[0] == 2  # Different kwargs = different cache

    def test_ttl_expiry_decorator(self):
        """Test TTL expiry with decorator"""
        call_count = [0]

        @cached(ttl=0.1, use_disk=False)
        def func(x):
            call_count[0] += 1
            return x * 2

        result1 = func(5)
        assert result1 == 10
        assert call_count[0] == 1

        time.sleep(0.15)

        result2 = func(5)
        assert result2 == 10
        assert call_count[0] == 2  # Called again after expiry


class TestDiskCachedDecorator:
    """Tests for @disk_cached decorator"""

    def setup_method(self):
        """Create temporary cache directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"

    def teardown_method(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_persistent_caching(self):
        """Test disk cache persists across function calls"""
        call_count = [0]

        @disk_cached(ttl=10.0, cache_dir=str(self.cache_dir))
        def expensive_func(x):
            call_count[0] += 1
            return x * 2

        result1 = expensive_func(5)
        result2 = expensive_func(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count[0] == 1

    def test_complex_return_values(self):
        """Test caching complex objects with disk cache"""
        @disk_cached(ttl=10.0, cache_dir=str(self.cache_dir))
        def get_data():
            return {
                "items": [1, 2, 3],
                "metadata": {"count": 3}
            }

        result1 = get_data()
        result2 = get_data()

        assert result1 == result2
        assert result1["items"] == [1, 2, 3]


def test_cache_key_generation():
    """Test consistent cache key generation"""
    @cached(ttl=10.0, use_disk=False)
    def func(a, b, c=None):
        return a + b + (c or 0)

    # Same arguments should generate same key
    result1 = func(1, 2, c=3)
    result2 = func(1, 2, c=3)

    assert result1 == result2
    assert result1 == 6


def test_cache_with_none_result():
    """Test caching None results"""
    call_count = [0]

    @cached(ttl=10.0, use_disk=False)
    def returns_none():
        call_count[0] += 1
        return None

    result1 = returns_none()
    result2 = returns_none()

    assert result1 is None
    assert result2 is None
    assert call_count[0] == 1  # Should cache None
