"""
Simple Memory Cache with TTL
Implements LRU eviction and time-to-live for cached items.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import Any, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import OrderedDict
from loguru import logger


@dataclass
class CacheEntry:
    """Cache entry with value and expiration time."""
    value: Any
    expires_at: datetime


class MemoryCache:
    """Simple in-memory cache with TTL and LRU eviction."""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 10000):
        """
        Initialize memory cache.

        Args:
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
            max_size: Maximum number of entries (default: 10,000)
        """
        if ttl_seconds <= 0:
            raise ValueError("TTL must be positive")
        if max_size <= 0:
            raise ValueError("max_size must be positive")

        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

        logger.info(f"MemoryCache initialized (TTL={ttl_seconds}s, max_size={max_size})")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not isinstance(key, str):
            raise ValueError("Key must be string")

        if key not in self._cache:
            return None

        entry = self._cache[key]

        # Check expiration
        if datetime.now() > entry.expires_at:
            del self._cache[key]
            logger.debug(f"Cache miss (expired): {key}")
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        logger.debug(f"Cache hit: {key}")
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional custom TTL (default: use cache TTL)
        """
        if not isinstance(key, str):
            raise ValueError("Key must be string")

        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        expires_at = datetime.now() + timedelta(seconds=ttl)

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Evicted (LRU): {oldest_key}")

        # Add/update entry
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
        self._cache.move_to_end(key)
        logger.debug(f"Cache set: {key} (TTL={ttl}s)")

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        if not isinstance(key, str):
            raise ValueError("Key must be string")

        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache delete: {key}")
            return True

        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared ({count} entries)")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl_seconds,
            'utilization': len(self._cache) / self.max_size
        }

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry.expires_at
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired entries")

        return len(expired_keys)
