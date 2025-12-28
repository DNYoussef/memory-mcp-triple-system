"""
Query Replay - Refactored Facade for Query Debugging

Replays queries with exact same context for debugging failed queries.
Part of v0.6.0 implementation for Memory MCP Triple System.

REFACTORED: Extracted into focused components for high cohesion:
- QueryTraceRepository: Database operations
- ContextReconstructor: Context state reconstruction
- TraceComparator: Trace comparison logic

This class now acts as a facade coordinating the components.

NASA Rule 10 Compliant: All functions <=60 LOC
Cohesion: HIGH (facade pattern - coordinates focused components)
"""

from typing import Dict, Any, Tuple, Optional
import time
from loguru import logger

from .query_trace import QueryTrace
from .query_trace_repository import QueryTraceRepository
from .context_reconstructor import ContextReconstructor
from .trace_comparator import TraceComparator


class QueryReplay:
    """
    Facade for deterministic query replay and debugging.

    Coordinates focused components:
    - QueryTraceRepository: Database access
    - ContextReconstructor: Context reconstruction
    - TraceComparator: Trace comparison

    Usage:
        replay = QueryReplay(db_path="memory.db")
        new_trace, diff = replay.replay("query-uuid-123")
        print(replay.comparator.summarize(diff))
    """

    def __init__(
        self,
        db_path: str = "memory.db",
        nexus_processor: Optional[Any] = None,
        kv_store: Optional[Any] = None,
        vector_indexer: Optional[Any] = None
    ):
        """
        Initialize query replay engine.

        Args:
            db_path: Path to SQLite database
            nexus_processor: Optional NexusProcessor for real queries
            kv_store: Optional KVStore for context
            vector_indexer: Optional VectorIndexer for snapshots
        """
        self.repository = QueryTraceRepository(db_path)
        self.context_reconstructor = ContextReconstructor(
            kv_store=kv_store,
            vector_indexer=vector_indexer
        )
        self.comparator = TraceComparator()
        self._nexus_processor = nexus_processor

        logger.info(f"QueryReplay initialized: db_path={db_path}")

    def set_nexus_processor(self, nexus_processor: Any) -> None:
        """Set NexusProcessor for real query execution."""
        self._nexus_processor = nexus_processor
        logger.info("QueryReplay wired to NexusProcessor")

    def set_stores(
        self,
        kv_store: Optional[Any] = None,
        vector_indexer: Optional[Any] = None
    ) -> None:
        """Configure stores for context reconstruction."""
        self.context_reconstructor.set_stores(kv_store, vector_indexer)

    def replay(self, query_id: str) -> Tuple[QueryTrace, Dict[str, Any]]:
        """
        Replay query with exact same context.

        Args:
            query_id: UUID of original query

        Returns:
            (new_trace, diff): New trace and differences from original
        """
        # 1. Fetch original trace
        original = self.repository.get_by_id(query_id)
        if original is None:
            logger.error(f"Query trace not found: {query_id}")
            raise ValueError(f"Query trace not found: {query_id}")

        # 2. Reconstruct context
        context = self.context_reconstructor.reconstruct(
            timestamp=original.timestamp,
            user_context=original.user_context
        )

        # 3. Re-run query
        new_trace = self._execute_replay(original.query, context)

        # 4. Compare traces
        diff = self.comparator.compare(original, new_trace)

        logger.info(f"Replay complete for {query_id}")
        return new_trace, diff

    def _execute_replay(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> QueryTrace:
        """Execute query replay with context."""
        start_time = time.time()

        new_trace = QueryTrace.create(
            query=query,
            user_context=context.get("user_context", {})
        )

        if self._nexus_processor is not None:
            self._execute_real_replay(new_trace, query, context)
        else:
            self._execute_mock_replay(new_trace, query)

        new_trace.total_latency_ms = int((time.time() - start_time) * 1000)
        return new_trace

    def _execute_real_replay(
        self,
        trace: QueryTrace,
        query: str,
        context: Dict[str, Any]
    ) -> None:
        """Execute replay using real NexusProcessor."""
        try:
            mode = context.get("user_context", {}).get("mode", "execution")
            result = self._nexus_processor.process(
                query=query,
                mode=mode,
                top_k=50,
                token_budget=10000
            )
            trace.mode_detected = mode
            trace.stores_queried = ["vector", "graph", "bayesian"]
            trace.routing_logic = "NexusProcessor 5-step SOP"
            trace.retrieved_chunks = result.get("core", []) + result.get("extended", [])
            trace.output = f"Real replay: {len(trace.retrieved_chunks)} chunks"
            logger.debug(f"Real replay executed: {query[:50]}...")
        except Exception as e:
            logger.warning(f"Real replay failed, using mock: {e}")
            self._execute_mock_replay(trace, query)

    def _execute_mock_replay(
        self,
        trace: QueryTrace,
        query: str
    ) -> None:
        """Execute mock replay for testing."""
        trace.mode_detected = "execution"
        trace.mode_confidence = 0.95
        trace.mode_detection_ms = 50
        trace.stores_queried = ["vector", "graph"]
        trace.routing_logic = "Mock routing (no NexusProcessor)"
        trace.retrieved_chunks = []
        trace.retrieval_ms = 100
        trace.output = f"Mock replay: {query[:50]}..."
        logger.debug(f"Mock replay executed: {query[:50]}...")
