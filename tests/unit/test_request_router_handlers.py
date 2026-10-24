"""Regression tests for MCP request-router handler robustness (MECE G9, G10).

G10: _format_result_full() direct-indexed result['text']/['score']/['file_path'],
so a vector-search fallback result missing any key raised KeyError -> the most-used
tool returned isError. Now uses .get() defaults like the compact formatter.

G9: handle_bayesian_inference() had no try/except, so any extraction/inference
error propagated to the generic wrapper (opaque isError), and a None result (no
network / timeout) became a useless "null". Now it guards and reports clearly.
"""

from unittest.mock import MagicMock

from src.mcp.request_router import _format_result_full, handle_bayesian_inference


# ---- G10 ----


def test_format_result_full_tolerates_missing_keys():
    """A result missing score/file_path must format without KeyError."""
    out = _format_result_full(1, {"text": "hello world"})  # no score, no file_path
    assert out["type"] == "text"
    assert "hello world" in out["text"]
    assert "Score: 0.0000" in out["text"]  # default applied


def test_format_result_full_full_result_unchanged():
    """A complete result still formats with its values."""
    out = _format_result_full(
        2, {"text": "t", "score": 0.5, "file_path": "/a.md", "tier": "vector"}
    )
    assert "Score: 0.5000" in out["text"]
    assert "/a.md" in out["text"]
    assert "Tier: vector" in out["text"]


# ---- G9 ----


def _tool_with_engine():
    tool = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = "rain"
    # P4: the handler rebuilds the network from the current graph and only
    # queries entities that are nodes in it. Give it a net containing "rain".
    net = MagicMock()
    net.nodes.return_value = ["rain"]
    tool._build_bayesian_network.return_value = net
    return tool


def test_bayesian_inference_resolves_multiword_entity_to_single_token_node():
    """NER stores "Wilhelmina Ashgrove" as the node "wilhelmina"; the handler
    must resolve the multi-word query to that single-token node."""
    tool = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = "Wilhelmina Ashgrove"
    net = MagicMock()
    net.nodes.return_value = ["wilhelmina", "guardspine"]
    tool._build_bayesian_network.return_value = net
    tool.nexus_processor.probabilistic_query_engine.query_conditional.return_value = {
        "p": 0.7
    }

    result = handle_bayesian_inference(
        {"query": "tell me about Wilhelmina Ashgrove"}, tool
    )

    assert result["isError"] is False
    assert "is not a node" not in result["content"][0]["text"]
    # resolved to the single-token node
    (
        _,
        kwargs,
    ) = tool.nexus_processor.probabilistic_query_engine.query_conditional.call_args
    assert kwargs["query_vars"] == ["wilhelmina"]


def test_bayesian_inference_rejects_empty_query():
    """An empty/whitespace query is rejected before any build."""
    tool = MagicMock()
    result = handle_bayesian_inference({"query": "   "}, tool)
    assert result["isError"] is True
    assert "No query provided" in result["content"][0]["text"]


def test_bayesian_inference_per_word_skips_stopwords():
    """The per-word fallback must not match a common node like "the"."""
    tool = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = "the report"
    net = MagicMock()
    net.nodes.return_value = ["the", "report"]  # both present
    tool._build_bayesian_network.return_value = net
    tool.nexus_processor.probabilistic_query_engine.query_conditional.return_value = {
        "p": 0.5
    }

    handle_bayesian_inference({"query": "show me the report"}, tool)

    # "the" is a stopword and skipped; "report" (>3 chars) is the match
    (
        _,
        kwargs,
    ) = tool.nexus_processor.probabilistic_query_engine.query_conditional.call_args
    assert kwargs["query_vars"] == ["report"]


def test_bayesian_inference_returns_error_not_raises_on_exception():
    """An inference exception must become an isError result, not propagate."""
    tool = _tool_with_engine()
    tool.nexus_processor.probabilistic_query_engine.query_conditional.side_effect = (
        RuntimeError("infer boom")
    )

    result = handle_bayesian_inference({"query": "will it rain"}, tool)

    assert result["isError"] is True
    assert "infer boom" in result["content"][0]["text"]


def test_bayesian_inference_handles_none_result_clearly():
    """A None result (no network / timeout) returns a clear message, not 'null'."""
    tool = _tool_with_engine()
    tool.nexus_processor.probabilistic_query_engine.query_conditional.return_value = (
        None
    )

    result = handle_bayesian_inference({"query": "x"}, tool)

    assert result["isError"] is True
    assert "No Bayesian inference" in result["content"][0]["text"]
    assert result["content"][0]["text"] != "null"


def test_bayesian_inference_empty_entity_is_handled():
    """An empty extracted entity returns a clear error, not a bad query."""
    tool = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = ""

    result = handle_bayesian_inference({"query": "???"}, tool)

    assert result["isError"] is True
    assert "entity" in result["content"][0]["text"].lower()


# ---- A5: beads priority P0 ----


def _beads_tool():
    from src.integrations.beads_bridge import BeadTask

    tasks = [
        BeadTask("mem-vrn", "GuardSpine: ship", "open", 0, "task"),
        BeadTask("mem-x", "other", "open", 2, "task"),
    ]

    async def _tasks(**_kw):
        return tasks

    tool = MagicMock()
    tool.beads_bridge.get_ready_tasks = _tasks
    tool.beads_bridge.query_tasks = _tasks
    return tool


def test_beads_handlers_print_p0_priority():
    from src.mcp.request_router import (
        handle_beads_query_tasks,
        handle_beads_ready_tasks,
    )

    for handler in (handle_beads_ready_tasks, handle_beads_query_tasks):
        text = handler({}, _beads_tool())["content"][0]["text"]
        assert "[mem-vrn] P0 " in text
        assert "[mem-x] P2 " in text


# ---- A2: entity_extraction without spaCy ----


def test_entity_extraction_without_spacy_uses_regex_fallback():
    from types import SimpleNamespace

    from src.mcp.request_router import handle_entity_extraction
    from src.services.entity_service import EntityService

    svc = EntityService.__new__(EntityService)
    svc.nlp = None
    out = handle_entity_extraction(
        {"text": "Apple hired Tim Cook in California"},
        SimpleNamespace(entity_service=svc),
    )
    assert out["isError"] is False
    assert "Tim Cook" in out["content"][0]["text"]


# ---- evidence validation (2026-09-06) ----


def _tool_with_net(nodes):
    tool = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = "guardspine"
    net = MagicMock()
    net.nodes.return_value = nodes
    tool._build_bayesian_network.return_value = net
    tool.nexus_processor.probabilistic_query_engine.query_conditional.return_value = {
        "results": {"guardspine": {"probabilities": {"true": 0.5, "false": 0.5}}}
    }
    return tool


def test_bayesian_inference_filters_unknown_evidence_and_coerces_bools():
    """Evidence keys that are not network nodes must be dropped (pgmpy raises
    on them and the handler used to report 'no result'); bool values must be
    coerced to the 'true'/'false' state names the builder uses."""
    tool = _tool_with_net(["guardspine", "igor"])
    result = handle_bayesian_inference(
        {"query": "GuardSpine", "evidence": {"not_a_node": True, "igor": True}}, tool
    )
    assert result["isError"] is False, result["content"][0]["text"]
    (
        _,
        kwargs,
    ) = tool.nexus_processor.probabilistic_query_engine.query_conditional.call_args
    assert kwargs["evidence"] == {"igor": "true"}
    assert '"ignored_evidence": ["not_a_node"]' in result["content"][0]["text"]


def test_bayesian_inference_keeps_valid_string_evidence():
    """Positive control: the filter must not drop evidence that IS a node."""
    tool = _tool_with_net(["guardspine", "igor"])
    result = handle_bayesian_inference(
        {"query": "GuardSpine", "evidence": {"igor": "false"}}, tool
    )
    assert result["isError"] is False
    (
        _,
        kwargs,
    ) = tool.nexus_processor.probabilistic_query_engine.query_conditional.call_args
    assert kwargs["evidence"] == {"igor": "false"}
    assert "ignored_evidence" not in result["content"][0]["text"]
