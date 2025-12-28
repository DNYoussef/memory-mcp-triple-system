"""
Query Trace Repository - Focused database operations for query traces.

Extracted from QueryReplay to improve cohesion.
Single Responsibility: Database CRUD for query traces.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List
import sqlite3
import json
from loguru import logger

from .query_trace import QueryTrace


class QueryTraceRepository:
    """
    Repository for query trace database operations.

    Single Responsibility: Database access for QueryTrace entities.
    Cohesion: HIGH - all methods work with query_traces table.
    """

    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize repository.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def get_by_id(self, query_id: str) -> Optional[QueryTrace]:
        """
        Fetch query trace by ID.

        Args:
            query_id: Query UUID as string

        Returns:
            QueryTrace if found, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM query_traces WHERE query_id = ?",
                (query_id,)
            )

            row = cursor.fetchone()
            conn.close()

            if row is None:
                return None

            return self._row_to_trace(row)

        except Exception as e:
            logger.error(f"Failed to fetch trace {query_id}: {e}")
            return None

    def _row_to_trace(self, row: sqlite3.Row) -> QueryTrace:
        """Convert database row to QueryTrace object."""
        return QueryTrace(
            query_id=UUID(row["query_id"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            query=row["query"],
            user_context=json.loads(row["user_context"]),
            mode_detected=row["mode_detected"] or "",
            mode_confidence=row["mode_confidence"] or 0.0,
            mode_detection_ms=row["mode_detection_ms"] or 0,
            stores_queried=json.loads(row["stores_queried"]) if row["stores_queried"] else [],
            routing_logic=row["routing_logic"] or "",
            retrieved_chunks=json.loads(row["retrieved_chunks"]) if row["retrieved_chunks"] else [],
            retrieval_ms=row["retrieval_ms"] or 0,
            verification_result=json.loads(row["verification_result"]) if row["verification_result"] else None,
            verification_ms=row["verification_ms"] or 0,
            output=row["output"] or "",
            total_latency_ms=row["total_latency_ms"] or 0,
            error=row["error"],
            error_type=row["error_type"]
        )

    def list_recent(self, limit: int = 100) -> List[QueryTrace]:
        """
        List recent query traces.

        Args:
            limit: Maximum number of traces to return

        Returns:
            List of QueryTrace objects
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM query_traces ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )

            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_trace(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to list traces: {e}")
            return []
