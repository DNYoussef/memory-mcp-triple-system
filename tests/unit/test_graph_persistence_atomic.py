"""A7a/A7b: graph.json is replaced atomically and save failures are surfaced.

T7a partial write, T7b replace failure, T7c overlapping writers,
T7d failed save reported by ingest (stdio and HTTP) and retried on the next store.
"""

import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import networkx as nx
import numpy as np
import pytest

from src.services import graph_persistence
from src.services.graph_persistence import GraphPersistence
from src.services.graph_service import GraphService
from src.services.memory_ingestion_service import MemoryIngestionService


def _graph(n, prefix="n"):
    g = nx.DiGraph()
    for i in range(n):
        g.add_node(f"{prefix}{i}", type="entity")
    return g


def _saved(tmp_path):
    p = GraphPersistence(_graph(3), tmp_path)
    assert p.save(force=True)
    return p, (tmp_path / "graph.json").read_bytes()


def test_partial_write_keeps_original(tmp_path, monkeypatch):
    p, before = _saved(tmp_path)
    p.graph.add_node("new")

    def half_dump(obj, f, **kw):
        f.write(json.dumps(obj, **kw)[:50])
        raise OSError("disk full")

    monkeypatch.setattr(graph_persistence.json, "dump", half_dump)
    assert p.save(force=True) is False
    assert (tmp_path / "graph.json").read_bytes() == before
    assert list(tmp_path.glob("graph.*.tmp")) == []


def test_replace_failure_keeps_original_and_dirty(tmp_path, monkeypatch):
    p, before = _saved(tmp_path)
    p.graph.add_node("new")
    p.mark_dirty()

    def deny(*_a, **_kw):
        raise PermissionError("file in use")

    monkeypatch.setattr(graph_persistence.os, "replace", deny)
    assert p.save() is False
    assert (tmp_path / "graph.json").read_bytes() == before
    assert list(tmp_path.glob("graph.*.tmp")) == []
    assert p._dirty is True


def test_overlapping_writers_publish_one_complete_graph(tmp_path):
    small, big = _graph(20, "s"), _graph(200, "b")
    writers = [GraphPersistence(small, tmp_path), GraphPersistence(big, tmp_path)]

    def loop(w):
        for _ in range(50):
            w.save(force=True)

    threads = [threading.Thread(target=loop, args=(w,)) for w in writers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with open(tmp_path / "graph.json", encoding="utf-8") as f:
        nodes = {n["id"] for n in json.load(f)["nodes"]}
    assert nodes in (set(small.nodes), set(big.nodes))
    assert list(tmp_path.glob("graph.*.tmp")) == []


def _ingestion(gs):
    embedder = MagicMock()
    embedder.encode.return_value = [np.zeros(4)]
    entity_service = MagicMock()
    entity_service.add_entities_to_graph.return_value = {
        "entities_added": 0,
        "relationships_created": 0,
        "entity_types": [],
    }
    return MemoryIngestionService(
        embedder=embedder,
        indexer=MagicMock(),
        graph_service=gs,
        entity_service=entity_service,
        classifier=None,
        lifecycle_manager=None,
        event_log=None,
    )


def _fail_replace_once(monkeypatch):
    real = graph_persistence.os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError("file in use")
        return real(src, dst)

    monkeypatch.setattr(graph_persistence.os, "replace", flaky)


def test_failed_save_is_reported_then_retried(tmp_path, monkeypatch):
    gs = GraphService(data_dir=tmp_path)
    svc = _ingestion(gs)
    _fail_replace_once(monkeypatch)

    first = svc.ingest("first memory", {})
    assert first["graph_persisted"] is False
    assert first["warnings"] == ["graph not persisted; will retry on next store"]
    svc._indexer.index_chunks.assert_called_once()

    second = svc.ingest("second memory", {})
    assert second["graph_persisted"] is True
    assert second["warnings"] == []
    with open(tmp_path / "graph.json", encoding="utf-8") as f:
        ids = {n["id"] for n in json.load(f)["nodes"]}
    assert {first["chunk_id"], second["chunk_id"]} <= ids


def test_failed_save_warning_reaches_stdio_text(tmp_path, monkeypatch):
    from src.mcp.request_router import handle_memory_store

    tool = SimpleNamespace(
        config={}, _ingestion_service=_ingestion(GraphService(tmp_path))
    )
    _fail_replace_once(monkeypatch)
    text = handle_memory_store({"text": "first memory"}, tool)["content"][0]["text"]
    assert text.startswith("Stored memory: ")
    assert "Warning: graph not persisted; will retry on next store" in text


@pytest.mark.asyncio
async def test_failed_save_fields_reach_http(tmp_path, monkeypatch):
    from src.mcp import http_server

    svc = _ingestion(GraphService(tmp_path))
    monkeypatch.setattr(http_server, "get_ingestion_service", lambda: svc)
    _fail_replace_once(monkeypatch)
    body = await http_server.memory_store(
        http_server.MemoryStoreRequest(text="first memory")
    )
    assert body["graph_persisted"] is False
    assert body["warnings"] == ["graph not persisted; will retry on next store"]
