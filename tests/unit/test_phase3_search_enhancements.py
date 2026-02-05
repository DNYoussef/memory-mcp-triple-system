"""Tests for Phase 3: Progressive disclosure, timeline, and search filters.

Tests:
  1. Compact formatter produces short single-line output
  2. Full formatter produces multi-line detailed output
  3. KVStore.get_observations respects after/before date filters
  4. observation_timeline handler formats compact and full correctly
  5. Tool registry includes observation_timeline definition
  6. Tool registry includes detail param in vector_search schema
"""

import os
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Module under test
from src.mcp.request_router import (
    _format_result_compact,
    _format_result_full,
    handle_observation_timeline,
)
from src.mcp.tool_registry import get_tool_definitions
from src.stores.kv_store import KVStore


# --- Formatter Tests ---

class TestProgressiveDisclosure:
    """Test compact vs full result formatting."""

    def test_compact_is_single_line(self):
        result = {
            "text": "This is a sample memory chunk about Python patterns",
            "score": 0.8765,
            "file_path": "src/utils.py",
            "tier": "vector",
        }
        formatted = _format_result_compact(1, result)
        assert formatted["type"] == "text"
        # Compact should be a single line
        assert "\n" not in formatted["text"]
        # Should contain score
        assert "0.876" in formatted["text"]
        # Should contain tier tag
        assert "[vector]" in formatted["text"]

    def test_compact_truncates_text(self):
        result = {
            "text": "A" * 200,
            "score": 0.5,
            "file_path": "long.py",
        }
        formatted = _format_result_compact(1, result)
        # Text preview should be at most ~80 chars of the text
        assert len(formatted["text"]) < 200

    def test_full_has_multiline_detail(self):
        result = {
            "text": "Full content of memory chunk with details",
            "score": 0.9123,
            "file_path": "src/models.py",
            "tier": "graph",
        }
        formatted = _format_result_full(1, result)
        assert "Result 1:" in formatted["text"]
        assert "Score: 0.9123" in formatted["text"]
        assert "File: src/models.py" in formatted["text"]
        assert "Tier: graph" in formatted["text"]

    def test_compact_no_tier_if_absent(self):
        result = {"text": "no tier here", "score": 0.5, "file_path": "f.py"}
        formatted = _format_result_compact(1, result)
        assert "[" not in formatted["text"].split("(")[0]  # No tier bracket before score


# --- KVStore Date Filter Tests ---

class TestKVStoreDateFilters:
    """Test after/before filters on get_observations."""

    @pytest.fixture
    def store(self, tmp_path):
        db = str(tmp_path / "test_obs.db")
        s = KVStore(db)
        yield s
        s.close()

    def _insert_obs(self, store, created_at, content="test", project="proj"):
        """Helper to insert an observation with a specific timestamp."""
        obs = {
            "observation_id": f"obs-{created_at}",
            "session_id": "sess-1",
            "obs_type": "tool_use",
            "concept": "implementation",
            "tool_name": "Read",
            "content": content,
            "metadata": "{}",
            "who": "test",
            "project": project,
            "why": "testing",
            "entities": "[]",
            "created_at": created_at,
        }
        store.store_observation(obs)

    def test_after_filter(self, store):
        self._insert_obs(store, "2026-02-04T10:00:00Z", "old")
        self._insert_obs(store, "2026-02-05T10:00:00Z", "new")

        results = store.get_observations(after="2026-02-05T00:00:00Z")
        assert len(results) == 1
        assert results[0]["content"] == "new"

    def test_before_filter(self, store):
        self._insert_obs(store, "2026-02-04T10:00:00Z", "old")
        self._insert_obs(store, "2026-02-05T10:00:00Z", "new")

        results = store.get_observations(before="2026-02-04T23:59:59Z")
        assert len(results) == 1
        assert results[0]["content"] == "old"

    def test_after_and_before_combined(self, store):
        self._insert_obs(store, "2026-02-03T10:00:00Z", "too-old")
        self._insert_obs(store, "2026-02-04T10:00:00Z", "in-range")
        self._insert_obs(store, "2026-02-05T10:00:00Z", "too-new")

        results = store.get_observations(
            after="2026-02-04T00:00:00Z",
            before="2026-02-04T23:59:59Z",
        )
        assert len(results) == 1
        assert results[0]["content"] == "in-range"

    def test_no_filters_returns_all(self, store):
        self._insert_obs(store, "2026-02-03T10:00:00Z", "a")
        self._insert_obs(store, "2026-02-04T10:00:00Z", "b")
        self._insert_obs(store, "2026-02-05T10:00:00Z", "c")

        results = store.get_observations()
        assert len(results) == 3


# --- Tool Registry Tests ---

class TestToolRegistryPhase3:
    """Test that Phase 3 tool definitions are correct."""

    def test_vector_search_has_detail_param(self):
        tools = get_tool_definitions()
        vs = next(t for t in tools if t["name"] == "vector_search")
        props = vs["inputSchema"]["properties"]
        assert "detail" in props
        assert props["detail"]["enum"] == ["compact", "full"]
        assert props["detail"]["default"] == "full"

    def test_unified_search_has_detail_param(self):
        tools = get_tool_definitions()
        us = next(t for t in tools if t["name"] == "unified_search")
        props = us["inputSchema"]["properties"]
        assert "detail" in props

    def test_observation_timeline_tool_exists(self):
        tools = get_tool_definitions()
        names = [t["name"] for t in tools]
        assert "observation_timeline" in names

    def test_observation_timeline_schema(self):
        tools = get_tool_definitions()
        ot = next(t for t in tools if t["name"] == "observation_timeline")
        props = ot["inputSchema"]["properties"]
        assert "project" in props
        assert "obs_type" in props
        assert "session_id" in props
        assert "hours_back" in props
        assert "limit" in props
        assert "detail" in props
        # obs_type should have enum
        assert "enum" in props["obs_type"]
        assert "tool_use" in props["obs_type"]["enum"]


# --- Timeline Handler Tests ---

class TestObservationTimeline:
    """Test the observation_timeline handler."""

    def _make_mock_tool(self, observations):
        """Create a mock NexusSearchTool with kv_store.get_observations."""
        tool = MagicMock()
        tool.kv_store.get_observations.return_value = observations
        return tool

    def test_empty_observations(self):
        tool = self._make_mock_tool([])
        result = handle_observation_timeline({}, tool)
        assert not result["isError"]
        assert "No observations found" in result["content"][0]["text"]

    def test_compact_format(self):
        obs = [
            {
                "observation_id": "obs-1",
                "created_at": "2026-02-05T10:30:00Z",
                "tool_name": "Read",
                "obs_type": "tool_use",
                "content": "Read file src/main.py for analysis",
                "project": "myproj",
                "entities": [],
            }
        ]
        tool = self._make_mock_tool(obs)
        result = handle_observation_timeline({"detail": "compact"}, tool)
        assert not result["isError"]
        # Header + 1 obs line
        assert len(result["content"]) == 2
        line = result["content"][1]["text"]
        assert "tool_use" in line
        assert "Read" in line

    def test_full_format(self):
        obs = [
            {
                "observation_id": "obs-abcdef12",
                "created_at": "2026-02-05T10:30:00Z",
                "tool_name": "Edit",
                "obs_type": "code_change",
                "content": "Modified authentication module",
                "project": "myproj",
                "entities": ["auth", "login"],
            }
        ]
        tool = self._make_mock_tool(obs)
        result = handle_observation_timeline({"detail": "full"}, tool)
        assert not result["isError"]
        body = result["content"][1]["text"]
        assert "Type: code_change" in body
        assert "Tool: Edit" in body
        assert "Entities: auth, login" in body

    def test_passes_filters_to_kv_store(self):
        tool = self._make_mock_tool([])
        handle_observation_timeline(
            {"project": "myproj", "obs_type": "error", "session_id": "s-1", "limit": 10},
            tool,
        )
        call_kwargs = tool.kv_store.get_observations.call_args
        assert call_kwargs.kwargs["project"] == "myproj"
        assert call_kwargs.kwargs["obs_type"] == "error"
        assert call_kwargs.kwargs["session_id"] == "s-1"
        assert call_kwargs.kwargs["limit"] == 10

    def test_hours_back_computes_after(self):
        tool = self._make_mock_tool([])
        handle_observation_timeline({"hours_back": 48}, tool)
        call_kwargs = tool.kv_store.get_observations.call_args
        after_str = call_kwargs.kwargs["after"]
        # Should be ~48h ago
        after_dt = datetime.fromisoformat(after_str.rstrip("Z"))
        expected = datetime.utcnow() - timedelta(hours=48)
        # Allow 5 second tolerance
        assert abs((after_dt - expected).total_seconds()) < 5
