"""
Unit tests for MemoryCache
Following TDD (London School) with proper test structure.
"""

import pytest
import time
from datetime import datetime, timedelta
from src.cache.memory_cache import MemoryCache


class TestMemoryCacheInitialization:
    """Test suite for MemoryCache initialization."""

    def test_default_initialization(self):
        """Test cache initializes with default values."""
        cache = MemoryCache()

        assert cache.ttl_seconds == 3600
        assert cache.max_size == 10000
        assert len(cache._cache) == 0

    def test_custom_initialization(self):
        """Test cache initializes with custom values."""
        cache = MemoryCache(ttl_seconds=300, max_size=100)

        assert cache.ttl_seconds == 300
        assert cache.max_size == 100

    def test_initialization_invalid_ttl(self):
        """Test initialization fails with invalid TTL."""
        with pytest.raises(AssertionError):
            MemoryCache(ttl_seconds=0)

        with pytest.raises(AssertionError):
            MemoryCache(ttl_seconds=-1)

    def test_initialization_invalid_max_size(self):
        """Test initialization fails with invalid max_size."""
        with pytest.raises(AssertionError):
            MemoryCache(max_size=0)

        with pytest.raises(AssertionError):
            MemoryCache(max_size=-1)


class TestMemoryCacheBasicOperations:
    """Test suite for basic cache operations."""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return MemoryCache(ttl_seconds=10, max_size=5)

    def test_set_and_get(self, cache):
        """Test setting and getting values."""
        cache.set('key1', 'value1')

        assert cache.get('key1') == 'value1'

    def test_get_nonexistent_key(self, cache):
        """Test getting nonexistent key returns None."""
        assert cache.get('nonexistent') is None

    def test_set_updates_existing_key(self, cache):
        """Test setting updates existing key."""
        cache.set('key1', 'value1')
        cache.set('key1', 'value2')

        assert cache.get('key1') == 'value2'

    def test_delete_existing_key(self, cache):
        """Test deleting existing key."""
        cache.set('key1', 'value1')

        result = cache.delete('key1')

        assert result is True
        assert cache.get('key1') is None

    def test_delete_nonexistent_key(self, cache):
        """Test deleting nonexistent key."""
        result = cache.delete('nonexistent')

        assert result is False

    def test_clear(self, cache):
        """Test clearing all entries."""
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')

        cache.clear()

        assert len(cache._cache) == 0
        assert cache.get('key1') is None


class TestMemoryCacheTTL:
    """Test suite for TTL functionality."""

    @pytest.fixture
    def cache(self):
        """Create cache with short TTL for testing."""
        return MemoryCache(ttl_seconds=1, max_size=10)

    def test_entry_expires_after_ttl(self, cache):
        """Test entry expires after TTL."""
        cache.set('key1', 'value1')

        # Wait for expiration
        time.sleep(1.5)

        assert cache.get('key1') is None

    def test_custom_ttl_overrides_default(self, cache):
        """Test custom TTL overrides default."""
        cache.set('key1', 'value1', ttl_seconds=5)

        # After 1.5s (default TTL would expire), should still be valid
        time.sleep(1.5)

        assert cache.get('key1') == 'value1'

    def test_cleanup_expired_entries(self, cache):
        """Test cleanup removes expired entries."""
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        # Wait for expiration
        time.sleep(1.5)

        removed = cache.cleanup_expired()

        assert removed == 2
        assert len(cache._cache) == 0


class TestMemoryCacheLRU:
    """Test suite for LRU eviction."""

    @pytest.fixture
    def cache(self):
        """Create cache with small max_size."""
        return MemoryCache(ttl_seconds=60, max_size=3)

    def test_lru_eviction_when_full(self, cache):
        """Test LRU eviction when cache is full."""
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')

        # This should evict key1 (oldest)
        cache.set('key4', 'value4')

        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert cache.get('key3') == 'value3'
        assert cache.get('key4') == 'value4'

    def test_get_moves_to_end(self, cache):
        """Test get moves entry to end (most recently used)."""
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')

        # Access key1 (moves to end)
        cache.get('key1')

        # This should evict key2 (now oldest)
        cache.set('key4', 'value4')

        assert cache.get('key1') == 'value1'
        assert cache.get('key2') is None
        assert cache.get('key3') == 'value3'
        assert cache.get('key4') == 'value4'


class TestMemoryCacheStats:
    """Test suite for cache statistics."""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return MemoryCache(ttl_seconds=10, max_size=100)

    def test_get_stats_structure(self, cache):
        """Test get_stats returns correct structure."""
        stats = cache.get_stats()

        assert 'size' in stats
        assert 'max_size' in stats
        assert 'ttl_seconds' in stats
        assert 'utilization' in stats

    def test_get_stats_values(self, cache):
        """Test get_stats returns correct values."""
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        stats = cache.get_stats()

        assert stats['size'] == 2
        assert stats['max_size'] == 100
        assert stats['ttl_seconds'] == 10
        assert stats['utilization'] == 0.02


class TestMemoryCacheValidation:
    """Test suite for input validation."""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return MemoryCache()

    def test_get_requires_string_key(self, cache):
        """Test get requires string key."""
        with pytest.raises(AssertionError):
            cache.get(123)

    def test_set_requires_string_key(self, cache):
        """Test set requires string key."""
        with pytest.raises(AssertionError):
            cache.set(123, 'value')

    def test_delete_requires_string_key(self, cache):
        """Test delete requires string key."""
        with pytest.raises(AssertionError):
            cache.delete(123)
