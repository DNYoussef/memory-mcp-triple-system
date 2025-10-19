"""
Week 7 Integration Tests

Tests integration of all Week 7 components:
- Schema validation with KV store
- Query logging with storage tiers
- Obsidian sync with memory system
"""

import pytest
from pathlib import Path
import json
from src.validation.schema_validator import SchemaValidator
from src.stores.kv_store import KVStore
from src.debug.query_trace import QueryTrace
from src.mcp.obsidian_client import ObsidianMCPClient


def test_schema_validation_with_kv_store(tmp_path):
    """Test schema validator works with KV store configuration."""
    # Validate schema
    validator = SchemaValidator()
    result = validator.validate("config/memory-schema.yaml")

    assert result.valid is True
    assert "storage_tiers" in result.schema
    assert "kv" in result.schema["storage_tiers"]

    # Verify KV config matches implementation
    kv_config = result.schema["storage_tiers"]["kv"]
    assert kv_config["type"] == "key-value"
    assert kv_config["backend"] == "sqlite"


def test_kv_store_with_json_preferences(tmp_path):
    """Test KV store handles JSON preferences (use case from schema)."""
    db_path = tmp_path / "prefs.db"
    store = KVStore(str(db_path))

    # Store user preferences as JSON
    prefs = {
        "coding_style": "functional",
        "theme": "dark",
        "notifications": True
    }

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
        query="What is NASA Rule 10?",
        user_context={"session_id": "test123"}
    )
    trace.mode_detected = "execution"
    trace.stores_queried = ["vector", "relational"]
    trace.output = "NASA Rule 10: ≤60 LOC per function"
    trace.total_latency_ms = 195

    success = trace.log(db_path=str(db_path))
    assert success is True

    # Retrieve and verify
    retrieved = QueryTrace.get_trace(trace.query_id, db_path=str(db_path))
    assert retrieved is not None
    assert retrieved.query == "What is NASA Rule 10?"
    assert retrieved.mode_detected == "execution"


def test_obsidian_sync_with_schema_validation(tmp_path):
    """Test Obsidian client validates against memory schema."""
    # Create mock vault
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Test\nContent")

    # Sync vault
    client = ObsidianMCPClient(vault_path=str(vault))
    result = client.sync_vault()

    assert result["success"] is True
    assert result["files_synced"] >= 1

    # Verify schema defines Obsidian as canonical source
    validator = SchemaValidator()
    schema_result = validator.validate("config/memory-schema.yaml")

    assert schema_result.valid is True
    portability = schema_result.schema.get("portability", {})
    canonical = portability.get("canonical_source", {})
    assert canonical.get("type") == "obsidian_vault"


def test_5_tier_storage_query_routing():
    """Test query router pattern matching from schema."""
    validator = SchemaValidator()
    result = validator.validate("config/memory-schema.yaml")

    assert result.valid is True

    # Get routing patterns
    routing = result.schema["query_processing"]["routing"]
    patterns = routing["patterns"]

    # Verify all 5 tiers have routing patterns
    tier_patterns = {p["tier"] for p in patterns}
    assert "kv" in tier_patterns
    assert "relational" in tier_patterns
    assert "vector" in tier_patterns
    assert "graph" in tier_patterns
    assert "event_log" in tier_patterns


def test_memory_lifecycle_stages():
    """Test lifecycle stages defined in schema."""
    validator = SchemaValidator()
    result = validator.validate("config/memory-schema.yaml")

    assert result.valid is True

    lifecycle = result.schema["lifecycle"]
    stages = lifecycle["stages"]
    stage_names = [s["name"] for s in stages]

    # Verify 4-stage lifecycle
    assert "active" in stage_names
    assert "demoted" in stage_names
    assert "archived" in stage_names
    assert "rehydratable" in stage_names

    # Verify rekindling enabled
    assert lifecycle["rekindling"]["enabled"] is True


def test_performance_targets_defined():
    """Test performance targets match Week 7 requirements."""
    validator = SchemaValidator()
    result = validator.validate("config/memory-schema.yaml")

    assert result.valid is True

    targets = result.schema.get("performance_targets", {})

    # Week 7 targets
    assert targets.get("kv_lookup_latency_ms") == 1  # O(1) target
    assert targets.get("query_latency_p95_ms") == 800  # 95th percentile
    assert targets.get("obsidian_sync_latency_s") == 2  # For 10k token files
