"""
Tests for KVStore (Week 7)

Tests O(1) key-value operations with SQLite backend.
"""

import pytest
from pathlib import Path
import json
from src.stores.kv_store import KVStore


@pytest.fixture
def kv_store(tmp_path):
    """KV store instance with temporary database."""
    db_path = tmp_path / "test_kv.db"
    store = KVStore(str(db_path))
    yield store
    store.close()


def test_kv_store_initialization(tmp_path):
    """Test KV store initializes correctly."""
    db_path = tmp_path / "test.db"
    store = KVStore(str(db_path))

    assert store.db_path == db_path
    assert db_path.exists()
    store.close()


def test_kv_set_and_get(kv_store):
    """Test setting and getting values."""
    kv_store.set("key1", "value1")
    value = kv_store.get("key1")

    assert value == "value1"


def test_kv_get_nonexistent_key(kv_store):
    """Test getting non-existent key returns None."""
    value = kv_store.get("nonexistent")
    assert value is None


def test_kv_set_overwrites_existing(kv_store):
    """Test setting existing key overwrites value."""
    kv_store.set("key1", "value1")
    kv_store.set("key1", "value2")

    value = kv_store.get("key1")
    assert value == "value2"


def test_kv_delete(kv_store):
    """Test deleting keys."""
    kv_store.set("key1", "value1")
    assert kv_store.get("key1") == "value1"

    deleted = kv_store.delete("key1")
    assert deleted is True
    assert kv_store.get("key1") is None


def test_kv_delete_nonexistent(kv_store):
    """Test deleting non-existent key."""
    deleted = kv_store.delete("nonexistent")
    assert deleted is False


def test_kv_list_keys_empty(kv_store):
    """Test listing keys when store is empty."""
    keys = kv_store.list_keys()
    assert keys == []


def test_kv_list_keys_with_data(kv_store):
    """Test listing all keys."""
    kv_store.set("key1", "value1")
    kv_store.set("key2", "value2")
    kv_store.set("key3", "value3")

    keys = kv_store.list_keys()
    assert sorted(keys) == ["key1", "key2", "key3"]


def test_kv_list_keys_with_prefix(kv_store):
    """Test listing keys with prefix filter."""
    kv_store.set("user:1", "alice")
    kv_store.set("user:2", "bob")
    kv_store.set("session:1", "active")

    user_keys = kv_store.list_keys(prefix="user:")
    assert sorted(user_keys) == ["user:1", "user:2"]

    session_keys = kv_store.list_keys(prefix="session:")
    assert session_keys == ["session:1"]


def test_kv_get_json(kv_store):
    """Test getting value as JSON dict."""
    data = {"name": "Alice", "age": 30}
    kv_store.set("user", json.dumps(data))

    result = kv_store.get_json("user")
    assert result == data


def test_kv_set_json(kv_store):
    """Test setting value as JSON dict."""
    data = {"name": "Bob", "active": True}
    kv_store.set_json("config", data)

    value = kv_store.get("config")
    assert json.loads(value) == data


def test_kv_exists(kv_store):
    """Test checking key existence."""
    assert kv_store.exists("key1") is False

    kv_store.set("key1", "value1")
    assert kv_store.exists("key1") is True


def test_kv_count(kv_store):
    """Test counting total keys."""
    assert kv_store.count() == 0

    kv_store.set("key1", "value1")
    kv_store.set("key2", "value2")
    assert kv_store.count() == 2

    kv_store.delete("key1")
    assert kv_store.count() == 1


def test_kv_context_manager(tmp_path):
    """Test KV store as context manager."""
    db_path = tmp_path / "test.db"

    with KVStore(str(db_path)) as store:
        store.set("key1", "value1")
        assert store.get("key1") == "value1"

    # Connection should be closed after context (thread-local)
    assert getattr(store._local, "conn", None) is None
