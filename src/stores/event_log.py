"""
Event Log - Temporal Query Support

Implements SQLite-backed event logging for temporal queries.
Tier 5 of 5-tier storage architecture: Event Log (temporal).

Part of Week 9 implementation for Memory MCP Triple System.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4
import sqlite3
import json
from loguru import logger


class EventType(Enum):
    """Event types for memory system."""
    CHUNK_ADDED = "chunk_added"
    CHUNK_UPDATED = "chunk_updated"
    CHUNK_DELETED = "chunk_deleted"
    QUERY_EXECUTED = "query_executed"
    ENTITY_CONSOLIDATED = "entity_consolidated"
    LIFECYCLE_TRANSITION = "lifecycle_transition"


class EventLog:
    """
    Temporal event log for memory system.

    Week 9 component implementing Tier 5 (Event Log) of 5-tier architecture.
    Enables temporal queries like "What happened on 2025-10-15?".

    Target: <100ms temporal query latency
    Storage: SQLite with timestamp indexing
    Retention: 30 days (auto-cleanup)

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize event log with SQLite database.

        Args:
            db_path: Path to SQLite database file

        NASA Rule 10: 9 LOC (≤60) ✅
        """
        self.db_path = db_path
        self._init_schema()
        logger.info(f"EventLog initialized with db_path={db_path}")

    def log_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Log event to database.

        Args:
            event_type: Type of event
            data: Event payload (JSON-serializable)
            timestamp: Event time (default: now)

        Returns:
            True if logged successfully

        NASA Rule 10: 32 LOC (≤60) ✅
        """
        if timestamp is None:
            timestamp = datetime.now()

        event_id = str(uuid4())

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO event_log (event_id, event_type, timestamp, data)
                VALUES (?, ?, ?, ?)
            """, (
                event_id,
                event_type.value,
                timestamp.isoformat(),
                json.dumps(data)
            ))

            conn.commit()
            conn.close()

            logger.debug(f"Logged event {event_type.value}: {event_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            return False

    def query_by_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
        event_types: Optional[List[EventType]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query events by time range.

        Example: "What happened on 2025-10-15?"

        Args:
            start_time: Range start
            end_time: Range end
            event_types: Filter by event types (None = all)

        Returns:
            List of events in chronological order

        NASA Rule 10: 37 LOC (≤60) ✅
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build and execute query
            query, params = self._build_timerange_query(start_time, end_time, event_types)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dicts
            events = self._convert_rows_to_events(rows)

            logger.info(f"Retrieved {len(events)} events from {start_time} to {end_time}")
            return events

        except Exception as e:
            logger.error(f"Failed to query events: {e}")
            return []

    def cleanup_old_events(
        self,
        retention_days: int = 30
    ) -> int:
        """
        Delete events older than retention period.

        Args:
            retention_days: Number of days to retain (default: 30)

        Returns:
            Number of events deleted

        NASA Rule 10: 27 LOC (≤60) ✅
        """
        cutoff = datetime.now() - timedelta(days=retention_days)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM event_log
                WHERE timestamp < ?
            """, (cutoff.isoformat(),))

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"Cleaned up {deleted} events older than {retention_days} days")
            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup events: {e}")
            return 0

    def get_event_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get event count statistics by type.

        Args:
            start_time: Stats start time (None = all time)
            end_time: Stats end time (None = now)

        Returns:
            {
                "chunk_added": 42,
                "query_executed": 128,
                ...
            }

        NASA Rule 10: 43 LOC (≤60) ✅
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build query
            if start_time and end_time:
                query = """
                    SELECT event_type, COUNT(*) as count
                    FROM event_log
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY event_type
                """
                params = [start_time.isoformat(), end_time.isoformat()]
            else:
                query = """
                    SELECT event_type, COUNT(*) as count
                    FROM event_log
                    GROUP BY event_type
                """
                params = []

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Convert to dict
            stats: Dict[str, int] = {}
            for row in rows:
                stats[str(row[0])] = int(row[1])

            logger.debug(f"Event stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get event stats: {e}")
            return {}

    def _build_timerange_query(
        self,
        start_time: datetime,
        end_time: datetime,
        event_types: Optional[List[EventType]]
    ) -> tuple[str, List[Any]]:
        """
        Build SQL query for timerange with optional type filtering.

        NASA Rule 10: 23 LOC (≤60) ✅
        """
        if event_types:
            type_params = ','.join(['?'] * len(event_types))
            query = f"""
                SELECT * FROM event_log
                WHERE timestamp BETWEEN ? AND ?
                AND event_type IN ({type_params})
                ORDER BY timestamp ASC
            """
            params = [
                start_time.isoformat(),
                end_time.isoformat()
            ] + [et.value for et in event_types]
        else:
            query = """
                SELECT * FROM event_log
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """
            params = [start_time.isoformat(), end_time.isoformat()]

        return query, params

    def _convert_rows_to_events(self, rows: List[Any]) -> List[Dict[str, Any]]:
        """
        Convert SQLite rows to event dictionaries.

        NASA Rule 10: 15 LOC (≤60) ✅
        """
        events = []
        for row in rows:
            events.append({
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "data": json.loads(row["data"])
            })
        return events

    def _init_schema(self) -> None:
        """
        Initialize event_log table schema.

        Creates table if not exists with timestamp indexing.

        NASA Rule 10: 33 LOC (≤60) ✅
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_log (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    data TEXT NOT NULL
                )
            """)

            # Create indexes for fast temporal queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_timestamp
                ON event_log(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type_timestamp
                ON event_log(event_type, timestamp)
            """)

            conn.commit()
            conn.close()

            logger.debug("Event log schema initialized")

        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
