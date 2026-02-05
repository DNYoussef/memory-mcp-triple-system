"""
P3-2: Concurrent write tests for KV and vector stores.

Validates thread safety of:
1. KVStore concurrent set/get operations
2. GraphService concurrent node/edge mutations
3. GraphPersistence thread-safe save/load
"""

import threading
import time
import pytest
from src.stores.kv_store import KVStore
from src.services.graph_service import GraphService


class TestKVStoreConcurrency:
    """Concurrent access to KVStore."""

    @pytest.fixture
    def store(self, tmp_path):
        db_path = tmp_path / "concurrent_kv.db"
        s = KVStore(str(db_path))
        yield s
        s.close()

    def test_concurrent_writes_no_corruption(self, store):
        """Multiple threads writing different keys simultaneously."""
        errors = []

        def writer(thread_id):
            try:
                for i in range(50):
                    store.set(f"thread{thread_id}_key{i}", f"value_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        # Verify all values written
        for t in range(5):
            for i in range(50):
                val = store.get(f"thread{t}_key{i}")
                assert val == f"value_{t}_{i}", f"Missing thread{t}_key{i}"

    def test_concurrent_read_write(self, store):
        """Reads and writes happening simultaneously."""
        store.set("shared", "initial")
        errors = []

        def writer():
            try:
                for i in range(100):
                    store.set("shared", f"v{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    val = store.get("shared")
                    assert val is not None
            except Exception as e:
                errors.append(e)

        w = threading.Thread(target=writer)
        r = threading.Thread(target=reader)
        w.start()
        r.start()
        w.join(timeout=30)
        r.join(timeout=30)

        assert len(errors) == 0, f"Errors during concurrent R/W: {errors}"

    def test_concurrent_deletes(self, store):
        """Delete operations are safe under concurrency."""
        for i in range(100):
            store.set(f"del_key_{i}", f"val_{i}")

        errors = []

        def deleter(start, end):
            try:
                for i in range(start, end):
                    store.delete(f"del_key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=deleter, args=(0, 50)),
            threading.Thread(target=deleter, args=(50, 100)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0


class TestGraphServiceConcurrency:
    """Concurrent access to GraphService."""

    @pytest.fixture
    def graph(self, tmp_path):
        return GraphService(data_dir=str(tmp_path / "graph_data"))

    def test_concurrent_node_additions(self, graph):
        """Multiple threads adding nodes simultaneously."""
        errors = []

        def add_nodes(thread_id):
            try:
                for i in range(50):
                    graph.add_chunk_node(f"t{thread_id}_chunk_{i}", {"text": f"content {i}"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_nodes, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0
        assert graph.get_node_count() == 200  # 4 threads * 50 nodes

    def test_concurrent_edge_additions(self, graph):
        """Adding edges from multiple threads."""
        # Pre-create nodes
        for i in range(20):
            graph.add_chunk_node(f"node_{i}")

        errors = []

        def add_edges(thread_id):
            try:
                for i in range(10):
                    src = f"node_{thread_id}"
                    tgt = f"node_{(thread_id + i + 1) % 20}"
                    graph.add_relationship(src, "references", tgt)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_edges, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0
        assert graph.get_edge_count() > 0

    def test_dirty_flag_under_concurrency(self, graph):
        """Dirty flag is set correctly under concurrent mutations."""
        def mutate(thread_id):
            for i in range(20):
                graph.add_chunk_node(f"mt{thread_id}_{i}")

        threads = [threading.Thread(target=mutate, args=(t,)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Dirty flag should be set
        assert graph._persistence._dirty is True

        # Save should work
        result = graph.save_graph()
        assert result is True

        # After save, not dirty
        assert graph._persistence._dirty is False
