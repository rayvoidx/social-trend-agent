"""
Caching utilities for API responses and expensive operations
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
    Simple in-memory cache with TTL (Time To Live)
    """

    def __init__(self, default_ttl: int = 3600):
        """
        Args:
            default_ttl: Default time to live in seconds (default: 1 hour)
        """
        self._cache = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
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
        """Set value in cache with TTL"""
        if ttl is None:
            ttl = self.default_ttl

        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def clear(self):
        """Clear all cache"""
        self._cache.clear()
        logger.debug("Cache cleared")

    def size(self) -> int:
        """Get number of items in cache"""
        return len(self._cache)


class DiskCache:
    """
    Disk-based cache for persistent storage
    """

    def __init__(self, cache_dir: str = ".cache", default_ttl: int = 86400):
        """
        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time to live in seconds (default: 24 hours)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key"""
        # Hash the key to create a valid filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.pkl"

    def get(self, key: str) -> Optional[Any]:
        """Get value from disk cache if not expired"""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)

            value, expiry = data['value'], data['expiry']

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
        """Set value in disk cache with TTL"""
        if ttl is None:
            ttl = self.default_ttl

        cache_path = self._get_cache_path(key)
        expiry = time.time() + ttl

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump({'value': value, 'expiry': expiry}, f)

            logger.debug(f"Disk cache set: {key} (TTL: {ttl}s)")

        except Exception as e:
            logger.error(f"Error writing cache: {e}")

    def clear(self):
        """Clear all disk cache"""
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        logger.debug("Disk cache cleared")


# Global cache instances
_memory_cache = SimpleCache(default_ttl=3600)  # 1 hour
_disk_cache = DiskCache(cache_dir=".cache/agents", default_ttl=86400)  # 24 hours


def cached(
    ttl: int = 3600,
    use_disk: bool = False,
    key_func: Optional[Callable] = None
):
    """
    Decorator for caching function results

    Args:
        ttl: Time to live in seconds
        use_disk: Use disk cache instead of memory cache
        key_func: Optional function to generate cache key from args/kwargs

    Example:
        @cached(ttl=3600)
        def expensive_operation(param1, param2):
            # ... expensive computation ...
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
        wrapper.cache_size = cache.size if hasattr(cache, 'size') else lambda: 0

        return wrapper
    return decorator


def cache_key_from_query(query: str, **params) -> str:
    """
    Generate cache key from query and parameters

    Useful for API calls with consistent parameter structure
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
