import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import networkx as nx
import pytest

from src.bayesian.network_builder import NetworkBuilder
from src.lifecycle.hotcold_classifier import HotColdClassifier
from src.mcp import request_router, service_wiring
from src.mcp.request_router import (
    handle_beads_ready_tasks,
    handle_detect_mode,
    handle_observation_timeline,
)
from src.services.graph_service import GraphService
from src.services.ppr_algorithms import PPRAlgorithmsMixin


def test_graph_service_node_aging_delegates_are_real(tmp_path):
    service = GraphService(data_dir=str(tmp_path))
    assert service.add_chunk_node("chunk-1", {"text": "hello"})

    assert service.increment_node_frequency("chunk-1") is True
    assert service.update_node_decay_score("chunk-1") is True
    assert service.update_node_importance("chunk-1", explicit_weight=0.8) is True

    node = service.get_node("chunk-1")
    assert node["frequency"] == 1
    assert 0.0 <= node["decay_score"] <= 1.0
    assert 0.0 <= node["importance"] <= 1.0
    assert service.get_nodes_by_importance(0.0, 1.0)[0][0] == "chunk-1"


def test_detect_mode_uses_real_mode_detector_patterns():
    result = handle_detect_mode({"query": "List all possible designs for a memory router"}, SimpleNamespace())
    text = result["content"][0]["text"].lower()

    assert result["isError"] is False
    assert "detected mode: brainstorming" in text


def test_beads_handler_runs_inside_existing_event_loop():
    class Bridge:
        async def get_ready_tasks(self, limit, brief):
            return [SimpleNamespace(id="mem-1", priority=2, title="Wire bridge", status="open")]

    async def call_inside_loop():
        return handle_beads_ready_tasks({"limit": 1}, SimpleNamespace(beads_bridge=Bridge()))

    result = asyncio.run(call_inside_loop())

    assert result["isError"] is False
    assert "[mem-1]" in result["content"][0]["text"]
    assert "asyncio.run() cannot be called" not in result["content"][0]["text"]


def test_observation_timeline_uses_local_iso_cutoff_without_z_suffix():
    captured = {}

    class Store:
        def get_observations(self, **kwargs):
            captured.update(kwargs)
            return [{"created_at": "2026-06-03T12:00:00", "tool_name": "Read", "obs_type": "tool", "content": "ok"}]

    result = handle_observation_timeline(
        {"hours_back": 2, "detail": "compact"},
        SimpleNamespace(kv_store=Store()),
    )

    assert result["isError"] is False
    assert captured["after"].endswith("Z") is False
    assert datetime.fromisoformat(captured["after"])


def test_bayesian_child_probability_depends_on_sampled_parent_state():
    builder = NetworkBuilder()
    graph = nx.DiGraph()
    graph.add_edge("parent", "child", weight=0.9, confidence=1.0)

    active = builder._calculate_child_probability(graph, ["parent"], "child", {"parent": "true"})
    inactive = builder._calculate_child_probability(graph, ["parent"], "child", {"parent": "false"})

    assert active > inactive
    assert active == pytest.approx(0.9)
    assert inactive == pytest.approx(0.1)


def test_bayesian_cpds_are_labeled_synthetic_not_observed():
    builder = NetworkBuilder()
    graph = nx.DiGraph()
    graph.add_edge("parent", "child", weight=0.8, confidence=1.0)

    network = builder.build_network(graph, use_cache=False)

    assert network.graph["cpd_evidence_type"] == "synthetic_topology_prior"
    assert network.graph["independent_observations"] is False


class PPRHarness(PPRAlgorithmsMixin):
    def __init__(self, graph):
        self.graph = graph


def test_ppr_cache_invalidation_uses_structure_not_counts():
    graph = nx.DiGraph()
    graph.add_edge("a", "b")
    graph.add_node("c")
    harness = PPRHarness(graph)
    personalization = {"a": 1.0, "b": 0.0, "c": 0.0}

    first = harness._execute_pagerank(personalization, alpha=0.85, max_iter=100, tol=1e-6)
    graph.remove_edge("a", "b")
    graph.add_edge("a", "c")
    second = harness._execute_pagerank(personalization, alpha=0.85, max_iter=100, tol=1e-6)

    assert first != second
    assert second["c"] > first["c"]


def test_module_docstrings_survive_import_order_fix():
    assert request_router.__doc__.strip().startswith("Request Router Module")
    assert service_wiring.__doc__.strip().startswith("Service Wiring Module")


def test_lifecycle_decay_score_uses_exponential_age():
    classifier = HotColdClassifier()
    timestamp = (datetime.now() - timedelta(days=30)).isoformat()

    result = classifier.classify("aged content", {"timestamp": timestamp})

    assert result["decay_score"] == pytest.approx(0.367879, rel=1e-2)
    assert 0.0 <= result["decay_score"] <= 1.0
