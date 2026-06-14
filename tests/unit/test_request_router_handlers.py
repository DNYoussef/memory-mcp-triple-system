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
    out = _format_result_full(2, {"text": "t", "score": 0.5, "file_path": "/a.md", "tier": "vector"})
    assert "Score: 0.5000" in out["text"]
    assert "/a.md" in out["text"]
    assert "Tier: vector" in out["text"]


# ---- G9 ----

def _tool_with_engine():
    tool = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = "rain"
    return tool


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
    tool.nexus_processor.probabilistic_query_engine.query_conditional.return_value = None

    result = handle_bayesian_inference({"query": "x"}, tool)

    assert result["isError"] is False
    assert "No Bayesian inference" in result["content"][0]["text"]
    assert result["content"][0]["text"] != "null"


def test_bayesian_inference_empty_entity_is_handled():
    """An empty extracted entity returns a clear error, not a bad query."""
    tool = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = ""

    result = handle_bayesian_inference({"query": "???"}, tool)

    assert result["isError"] is True
    assert "entity" in result["content"][0]["text"].lower()
