"""
Query Replay - Deterministic Query Debugging

Replays queries with exact same context for debugging failed queries.
Part of Week 8 implementation for Memory MCP Triple System.

NASA Rule 10 Compliant: All functions d60 LOC
"""

from uuid import UUID
from datetime import datetime
from typing import Dict, Tuple, Optional
import sqlite3
import json
from loguru import logger

from .query_trace import QueryTrace


class QueryReplay:
    """
    Replay queries deterministically for debugging.

    PREMORTEM Risk #13 Mitigation:
    - Reconstruct exact context (stores, mode, lifecycle)
    - Re-run query with same context
    - Compare traces (original vs replay)
    - Identify context bugs (wrong store, wrong mode, etc.)

    NOTE: Full implementation requires NexusProcessor (Week 11).
    Week 8: Mock implementation for testing infrastructure.

    NASA Rule 10 Compliant: All methods d60 LOC
    """

    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize query replay engine.

        Args:
            db_path: Path to SQLite database with query_traces table

        NASA Rule 10: 5 LOC (d60) 
        """
        self.db_path = db_path
        logger.info(f"QueryReplay initialized with db_path={db_path}")

    def replay(self, query_id: str) -> Tuple[QueryTrace, Dict]:
        """
        Replay query with exact same context.

        Args:
            query_id: UUID of original query (as string)

        Returns:
            (new_trace, diff): New trace + difference from original

        Example:
            >>> replay = QueryReplay()
            >>> new_trace, diff = replay.replay("abc-123-def-456")
            >>> print(diff)
            {
                "mode_detected": {"original": "execution", "replay": "planning"},
                "stores_queried": {"original": ["vector"], "replay": ["vector", "relational"]},
                "output": {"original": "Wrong answer", "replay": "Correct answer"}
            }

        NASA Rule 10: 29 LOC (d60) 
        """
        # 1. Fetch original trace
        original = self._get_trace(query_id)

        if original is None:
            logger.error(f"Query trace not found: {query_id}")
            raise ValueError(f"Query trace not found: {query_id}")

        # 2. Reconstruct exact context
        context = self._reconstruct_context(
            timestamp=original.timestamp,
            user_context=original.user_context
        )

        # 3. Re-run query (mock for Week 8, real NexusProcessor in Week 11)
        new_trace = self._rerun_query(original.query, context)

        # 4. Compare traces
        diff = self._compare_traces(original, new_trace)

        logger.info(f"Replay complete for query {query_id}, diff: {diff}")
        return new_trace, diff

    def _get_trace(self, query_id: str) -> Optional[QueryTrace]:
        """
        Fetch query trace from SQLite by ID.

        Args:
            query_id: Query UUID as string

        Returns:
            QueryTrace if found, None otherwise

        NASA Rule 10: 39 LOC (d60) 
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

            # Reconstruct QueryTrace from database row
            trace = QueryTrace(
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

            return trace

        except Exception as e:
            logger.error(f"Failed to fetch trace {query_id}: {e}")
            return None

    def _reconstruct_context(
        self,
        timestamp: datetime,
        user_context: Dict
    ) -> Dict:
        """
        Reconstruct exact context at timestamp.

        Context includes:
        - Memory state (chunks available at timestamp)
        - User preferences (as of timestamp)
        - Session lifecycle (active sessions at timestamp)

        NOTE: Week 8 mock implementation returns minimal context.
        Week 11: Full implementation with memory snapshots.

        Args:
            timestamp: Original query timestamp
            user_context: User context from original query

        Returns:
            Reconstructed context dictionary

        NASA Rule 10: 18 LOC (d60) 
        """
        # Week 8: Mock implementation
        context = {
            "timestamp": timestamp.isoformat(),
            "user_context": user_context,
            "memory_snapshot": {},  # TODO: Week 11 - fetch from memory store
            "preferences": {},      # TODO: Week 11 - fetch from KV store
            "sessions": []          # TODO: Week 11 - fetch from session store
        }

        logger.debug(f"Reconstructed context for timestamp {timestamp}")
        return context

    def _rerun_query(self, query: str, context: Dict) -> QueryTrace:
        """
        Re-run query with reconstructed context.

        NOTE: Week 8 mock implementation creates dummy trace.
        Week 11: Wire to real NexusProcessor for actual query execution.

        Args:
            query: Original query text
            context: Reconstructed context

        Returns:
            New QueryTrace from replay

        NASA Rule 10: 29 LOC (d60) 
        """
        # Week 8: Mock implementation (creates dummy trace for testing)
        from uuid import uuid4

        new_trace = QueryTrace.create(
            query=query,
            user_context=context.get("user_context", {})
        )

        # Populate with mock data (deterministic for testing)
        new_trace.mode_detected = "execution"
        new_trace.mode_confidence = 0.95
        new_trace.mode_detection_ms = 50
        new_trace.stores_queried = ["vector", "graph"]
        new_trace.routing_logic = "Mock routing (Week 8)"
        new_trace.retrieved_chunks = []
        new_trace.retrieval_ms = 100
        new_trace.output = f"Mock replay output for: {query}"
        new_trace.total_latency_ms = 200

        logger.debug(f"Reran query (mock): {query}")
        return new_trace

    def _compare_traces(
        self,
        original: QueryTrace,
        replay: QueryTrace
    ) -> Dict:
        """
        Compare two traces, identify differences.

        Returns:
            Dictionary of differences:
            {
                "mode_detected": {"original": "X", "replay": "Y"},
                "stores_queried": {"original": [...], "replay": [...]},
                "output": {"original": "...", "replay": "..."}
            }

        NASA Rule 10: 31 LOC (d60) 
        """
        diff: Dict = {}

        # Compare mode detection
        if original.mode_detected != replay.mode_detected:
            diff["mode_detected"] = {
                "original": original.mode_detected,
                "replay": replay.mode_detected
            }

        # Compare stores queried
        if original.stores_queried != replay.stores_queried:
            diff["stores_queried"] = {
                "original": original.stores_queried,
                "replay": replay.stores_queried
            }

        # Compare output
        if original.output != replay.output:
            diff["output"] = {
                "original": original.output,
                "replay": replay.output
            }

        return diff
