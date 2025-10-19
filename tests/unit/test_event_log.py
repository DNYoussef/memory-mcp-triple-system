"""
Unit tests for Event Log Store.

Week 9 component - Tests temporal queries, event logging, retention.

Target: 8 tests, ~80 LOC
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from src.stores.event_log import EventLog, EventType


class TestEventLog:
    """Test suite for EventLog."""

    @pytest.fixture
    def event_log(self):
        """Create EventLog instance with temporary database."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        log = EventLog(db_path=temp_db.name)
        yield log
        # Cleanup
        try:
            os.unlink(temp_db.name)
        except:
            pass

    def test_initialization(self, event_log):
        """Test EventLog initialization creates schema."""
        assert event_log.db_path is not None
        # Schema should be created (tables exist)
        stats = event_log.get_event_stats(
            datetime.now() - timedelta(hours=1), datetime.now()
        )
        assert isinstance(stats, dict)

    def test_log_event_success(self, event_log):
        """Test successful event logging."""
        success = event_log.log_event(
            event_type=EventType.CHUNK_ADDED,
            data={"chunk_id": "test-123", "content": "Test chunk"},
        )

        assert success is True

    def test_query_by_timerange_retrieves_events(self, event_log):
        """Test querying events by time range."""
        now = datetime.now()

        # Log event
        event_log.log_event(
            event_type=EventType.CHUNK_ADDED,
            data={"chunk_id": "test-456"},
            timestamp=now,
        )

        # Query for event
        events = event_log.query_by_timerange(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )

        assert len(events) == 1
        assert events[0]["event_type"] == EventType.CHUNK_ADDED.value
        assert events[0]["data"]["chunk_id"] == "test-456"

    def test_query_by_timerange_with_type_filter(self, event_log):
        """Test querying with event type filtering."""
        now = datetime.now()

        # Log multiple event types
        event_log.log_event(EventType.CHUNK_ADDED, {"id": "1"}, now)
        event_log.log_event(EventType.QUERY_EXECUTED, {"id": "2"}, now)

        # Query for only CHUNK_ADDED
        events = event_log.query_by_timerange(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            event_types=[EventType.CHUNK_ADDED],
        )

        assert len(events) == 1
        assert events[0]["event_type"] == EventType.CHUNK_ADDED.value

    def test_cleanup_old_events(self, event_log):
        """Test cleanup of old events."""
        now = datetime.now()
        old_time = now - timedelta(days=35)

        # Log old event
        event_log.log_event(EventType.CHUNK_ADDED, {"id": "old"}, old_time)

        # Cleanup events older than 30 days
        deleted = event_log.cleanup_old_events(retention_days=30)

        assert deleted >= 1

    def test_get_event_stats(self, event_log):
        """Test event statistics aggregation."""
        now = datetime.now()

        # Log multiple events
        event_log.log_event(EventType.CHUNK_ADDED, {"id": "1"}, now)
        event_log.log_event(EventType.CHUNK_ADDED, {"id": "2"}, now)
        event_log.log_event(EventType.QUERY_EXECUTED, {"id": "3"}, now)

        stats = event_log.get_event_stats(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )

        # get_event_stats returns {event_type: count}
        assert stats[EventType.CHUNK_ADDED.value] == 2
        assert stats[EventType.QUERY_EXECUTED.value] == 1
        assert sum(stats.values()) == 3  # Total events

    def test_query_empty_timerange(self, event_log):
        """Test querying with no events in timerange."""
        future_time = datetime.now() + timedelta(days=365)

        events = event_log.query_by_timerange(
            start_time=future_time,
            end_time=future_time + timedelta(hours=1),
        )

        assert events == []


# NASA Rule 10 Compliance Check
def test_nasa_rule_10_compliance():
    """Verify all EventLog methods are ≤60 LOC."""
    import ast

    with open("src/stores/event_log.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = node.end_lineno - node.lineno + 1
            assert func_lines <= 60, f"{node.name} exceeds 60 LOC ({func_lines})"
