"""
Tests for QueryTrace (Week 7)

Tests query logging for context debugger foundation.
"""

import pytest
from pathlib import Path
from uuid import UUID
from datetime import datetime
from src.debug.query_trace import QueryTrace


@pytest.fixture
def temp_db(tmp_path):
    """Temporary database path."""
    db_path = tmp_path / "test_traces.db"

    # Apply migration
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    with open("migrations/007_query_traces_table.sql", "r") as f:
        conn.executescript(f.read())
    conn.close()

    return str(db_path)


def test_query_trace_creation():
    """Test creating query trace."""
    trace = QueryTrace.create(
        query="What is NASA Rule 10?",
        user_context={"session_id": "abc123", "user_id": "user1"}
    )

    assert isinstance(trace.query_id, UUID)
    assert trace.query == "What is NASA Rule 10?"
    assert trace.user_context == {"session_id": "abc123", "user_id": "user1"}
    assert isinstance(trace.timestamp, datetime)
    assert trace.mode_detected == ""
    assert trace.stores_queried == []


def test_query_trace_logging(temp_db):
    """Test logging query trace to SQLite."""
    trace = QueryTrace.create(
        query="What is NASA Rule 10?",
        user_context={"session_id": "abc123"}
    )
    trace.mode_detected = "execution"
    trace.mode_confidence = 0.92
    trace.stores_queried = ["vector", "relational"]
    trace.output = "NASA Rule 10: All functions ≤60 LOC"
    trace.total_latency_ms = 195

    success = trace.log(db_path=temp_db)
    assert success is True

    # Verify saved to DB
    retrieved = QueryTrace.get_trace(trace.query_id, db_path=temp_db)
    assert retrieved is not None
    assert retrieved.query_id == trace.query_id
    assert retrieved.mode_detected == "execution"
    assert retrieved.mode_confidence == 0.92
    assert retrieved.stores_queried == ["vector", "relational"]


def test_query_trace_error_attribution(temp_db):
    """Test error attribution classification."""
    trace = QueryTrace.create(
        query="What's my coding style?",
        user_context={"session_id": "abc123"}
    )
    trace.error = "Wrong output returned"
    trace.error_type = "context_bug"  # Wrong store queried

    success = trace.log(db_path=temp_db)
    assert success is True

    # Verify error fields
    retrieved = QueryTrace.get_trace(trace.query_id, db_path=temp_db)
    assert retrieved.error == "Wrong output returned"
    assert retrieved.error_type == "context_bug"


def test_query_trace_get_nonexistent(temp_db):
    """Test retrieving non-existent trace."""
    from uuid import uuid4

    trace = QueryTrace.get_trace(uuid4(), db_path=temp_db)
    assert trace is None


def test_query_trace_to_dict():
    """Test converting trace to dictionary."""
    trace = QueryTrace.create(
        query="Test query",
        user_context={"session_id": "xyz"}
    )
    trace.mode_detected = "planning"
    trace.total_latency_ms = 150

    trace_dict = trace.to_dict()

    assert isinstance(trace_dict["query_id"], str)
    assert isinstance(trace_dict["timestamp"], str)
    assert trace_dict["query"] == "Test query"
    assert trace_dict["mode_detected"] == "planning"
    assert trace_dict["total_latency_ms"] == 150
