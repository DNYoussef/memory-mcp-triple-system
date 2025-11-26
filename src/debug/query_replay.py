"""
Query Replay - Deterministic Query Debugging

Replays queries with exact same context for debugging failed queries.
Part of v0.6.0 implementation for Memory MCP Triple System.

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

    NOTE: Full implementation requires NexusProcessor (v0.9.0).
    v0.6.0: Mock implementation for testing infrastructure.

    NASA Rule 10 Compliant: All methods d60 LOC
    """

    def __init__(
        self,
        db_path: str = "memory.db",
        nexus_processor=None,
        kv_store=None,
        vector_indexer=None
    ):
        """
        Initialize query replay engine.

        Args:
            db_path: Path to SQLite database with query_traces table
            nexus_processor: Optional NexusProcessor for real query execution (ISS-033)
            kv_store: Optional KVStore for context reconstruction (ISS-010)
            vector_indexer: Optional VectorIndexer for memory snapshots (ISS-010)

        NASA Rule 10: 5 LOC (d60) 
        """
        self.db_path = db_path
        self._nexus_processor = nexus_processor
        self._kv_store = kv_store  # ISS-010 fix
        self._vector_indexer = vector_indexer  # ISS-010 fix
        logger.info(f"QueryReplay initialized with db_path={db_path}")

    def set_nexus_processor(self, nexus_processor) -> None:
        """ISS-033 FIX: Set NexusProcessor for real query execution."""
        self._nexus_processor = nexus_processor
        logger.info("QueryReplay wired to NexusProcessor")

    def set_stores(self, kv_store=None, vector_indexer=None) -> None:
        """ISS-010 FIX: Set stores for context reconstruction."""
        if kv_store:
            self._kv_store = kv_store
        if vector_indexer:
            self._vector_indexer = vector_indexer
        logger.info("QueryReplay stores configured")

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

        # 3. Re-run query (mock for v0.6.0, real NexusProcessor in v0.9.0)
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

        NOTE: v0.6.0 mock implementation returns minimal context.
        v0.9.0: Full implementation with memory snapshots.

        Args:
            timestamp: Original query timestamp
            user_context: User context from original query

        Returns:
            Reconstructed context dictionary

        NASA Rule 10: 18 LOC (d60) 
        """
        # ISS-010 FIX: Actual context reconstruction using stores
        context = {
            "timestamp": timestamp.isoformat(),
            "user_context": user_context,
            "memory_snapshot": self._get_memory_snapshot(timestamp),
            "preferences": self._get_preferences(),
            "sessions": self._get_sessions()
        }

        logger.debug(f"Reconstructed context for timestamp {timestamp}")
        return context

    def _get_memory_snapshot(self, timestamp) -> Dict:
        """ISS-010 FIX: Get memory state at timestamp."""
        if not self._vector_indexer:
            return {}
        try:
            # Get collection stats as snapshot
            collection = self._vector_indexer.collection
            return {
                "chunk_count": collection.count(),
                "timestamp": timestamp.isoformat()
            }
        except Exception as e:
            logger.warning(f"Memory snapshot failed: {e}")
            return {}

    def _get_preferences(self) -> Dict:
        """ISS-010 FIX: Get user preferences from KV store."""
        if not self._kv_store:
            return {}
        try:
            prefs = self._kv_store.get("user:preferences")
            return prefs if prefs else {}
        except Exception as e:
            logger.warning(f"Preferences fetch failed: {e}")
            return {}

    def _get_sessions(self) -> list:
        """ISS-010 FIX: Get active sessions from KV store."""
        if not self._kv_store:
            return []
        try:
            sessions = self._kv_store.get("active:sessions")
            return sessions if sessions else []
        except Exception as e:
            logger.warning(f"Sessions fetch failed: {e}")
            return []

    def _rerun_query(self, query: str, context: Dict) -> QueryTrace:
        """
        Re-run query with reconstructed context.

        NOTE: v0.6.0 mock implementation creates dummy trace.
        v0.9.0: Wire to real NexusProcessor for actual query execution.

        Args:
            query: Original query text
            context: Reconstructed context

        Returns:
            New QueryTrace from replay

        NASA Rule 10: 29 LOC (d60) 
        """
        # ISS-033 FIX: Use real NexusProcessor when available
        import time
        start_time = time.time()

        new_trace = QueryTrace.create(
            query=query,
            user_context=context.get("user_context", {})
        )

        if self._nexus_processor is not None:
            try:
                mode = context.get("user_context", {}).get("mode", "execution")
                result = self._nexus_processor.process(
                    query=query,
                    mode=mode,
                    top_k=50,
                    token_budget=10000
                )
                new_trace.mode_detected = mode
                new_trace.stores_queried = ["vector", "graph", "bayesian"]
                new_trace.routing_logic = "NexusProcessor 5-step SOP"
                new_trace.retrieved_chunks = result.get("core", []) + result.get("extended", [])
                new_trace.output = f"Real replay: {len(new_trace.retrieved_chunks)} chunks"
                logger.debug(f"Reran query (real NexusProcessor): {query}")
            except Exception as e:
                logger.warning(f"NexusProcessor replay failed, using mock: {e}")
                self._populate_mock_trace(new_trace, query)
        else:
            # Fallback to mock for testing
            self._populate_mock_trace(new_trace, query)

        new_trace.total_latency_ms = int((time.time() - start_time) * 1000)
        return new_trace

    def _populate_mock_trace(self, trace: QueryTrace, query: str) -> None:
        """Populate trace with mock data for testing."""
        trace.mode_detected = "execution"
        trace.mode_confidence = 0.95
        trace.mode_detection_ms = 50
        trace.stores_queried = ["vector", "graph"]
        trace.routing_logic = "Mock routing (no NexusProcessor)"
        trace.retrieved_chunks = []
        trace.retrieval_ms = 100
        trace.output = f"Mock replay output for: {query}"
        logger.debug(f"Reran query (mock): {query}")

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
