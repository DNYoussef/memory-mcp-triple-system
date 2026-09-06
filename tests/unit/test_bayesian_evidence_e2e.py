"""Evidence validation through the REAL NetworkBuilder + pgmpy engine + handler.

No mocks on the inference path: a bogus evidence key or a bool value used to
raise inside pgmpy, be swallowed by execute_with_timeout, and surface as
"inference returned no result". The handler must now filter/coerce evidence
and still return probabilities.
"""
import json
import threading
import types

import networkx as nx
import pytest


def _graph():
    g = nx.DiGraph()
    g.add_edge("guardspine", "reactor", confidence=0.8, weight=2.0)
    g.add_edge("wilhelmina", "reactor", confidence=0.7, weight=1.5)
    g.add_edge("wilhelmina", "guardspine", confidence=0.6, weight=1.0)
    return g


def _real_tool():
    pytest.importorskip("pgmpy")
    from src.bayesian import NetworkBuilder, ProbabilisticQueryEngine

    builder = NetworkBuilder(max_nodes=1000)
    gs = types.SimpleNamespace(graph=_graph())
    return types.SimpleNamespace(
        graph_service=gs,
        _build_bayesian_network=lambda g: builder.build_network(g.graph),
        nexus_processor=types.SimpleNamespace(
            _extract_query_entity=lambda q: "guardspine",
            probabilistic_query_engine=ProbabilisticQueryEngine(timeout_seconds=5.0),
        ),
    )


def test_bogus_key_and_bool_evidence_still_yield_probabilities():
    from src.mcp.request_router import handle_bayesian_inference

    tool = _real_tool()
    r = handle_bayesian_inference(
        {"query": "guardspine", "evidence": {"not_a_node": True, "reactor": True}},
        tool,
    )
    text = r["content"][0]["text"]
    assert r["isError"] is False, text
    payload = json.loads(text)
    probs = payload["results"]["guardspine"]["probabilities"]
    assert set(probs) == {"true", "false"}
    assert abs(sum(probs.values()) - 1.0) < 1e-6
    assert payload["evidence"] == {"reactor": "true"}
    assert payload["ignored_evidence"] == ["not_a_node"]


def test_raw_bogus_evidence_still_breaks_the_engine():
    """Positive control: the engine itself still rejects unknown evidence, so
    the handler's filter is load-bearing, not decorative."""
    tool = _real_tool()
    net = tool._build_bayesian_network(tool.graph_service)
    r = tool.nexus_processor.probabilistic_query_engine.query_conditional(
        network=net, query_vars=["guardspine"], evidence={"not_a_node": "true"}
    )
    assert r is None
