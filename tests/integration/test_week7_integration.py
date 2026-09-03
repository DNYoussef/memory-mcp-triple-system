"""Integration tests for live Week 7 storage and tracing."""

from src.debug.query_trace import QueryTrace
from src.stores.kv_store import KVStore


def test_kv_store_with_json_preferences(tmp_path):
    """Test KV store handles JSON preferences (use case from schema)."""
    db_path = tmp_path / "prefs.db"
    store = KVStore(str(db_path))

    # Store user preferences as JSON
    prefs = {"coding_style": "functional", "theme": "dark", "notifications": True}

    store.set_json("user:preferences", prefs)

    # Retrieve and verify
    retrieved = store.get_json("user:preferences")
    assert retrieved == prefs

    store.close()


def test_query_logging_end_to_end(tmp_path):
    """Test full query logging workflow."""
    db_path = tmp_path / "traces.db"

    # Apply migration
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    with open("migrations/007_query_traces_table.sql", "r") as f:
        conn.executescript(f.read())
    conn.close()

    # Create and log query trace
    trace = QueryTrace.create(
        query="What is NASA Rule 10?", user_context={"session_id": "test123"}
    )
    trace.mode_detected = "execution"
    trace.stores_queried = ["vector", "relational"]
    trace.output = "NASA Rule 10: <=60 LOC per function"
    trace.total_latency_ms = 195

    success = trace.log(db_path=str(db_path))
    assert success is True

    # Retrieve and verify
    retrieved = QueryTrace.get_trace(trace.query_id, db_path=str(db_path))
    assert retrieved is not None
    assert retrieved.query == "What is NASA Rule 10?"
    assert retrieved.mode_detected == "execution"
