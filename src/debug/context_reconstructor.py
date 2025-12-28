"""
Context Reconstructor - Focused component for reconstructing query context.

Extracted from QueryReplay to improve cohesion.
Single Responsibility: Reconstruct execution context at a point in time.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger


class ContextReconstructor:
    """
    Reconstructs execution context for query replay.

    Single Responsibility: Context reconstruction from stores.
    Cohesion: HIGH - all methods relate to context state.
    """

    def __init__(
        self,
        kv_store: Optional[Any] = None,
        vector_indexer: Optional[Any] = None
    ):
        """
        Initialize context reconstructor.

        Args:
            kv_store: KVStore for preferences and sessions
            vector_indexer: VectorIndexer for memory snapshots
        """
        self._kv_store = kv_store
        self._vector_indexer = vector_indexer

    def set_stores(
        self,
        kv_store: Optional[Any] = None,
        vector_indexer: Optional[Any] = None
    ) -> None:
        """Configure stores for context reconstruction."""
        if kv_store:
            self._kv_store = kv_store
        if vector_indexer:
            self._vector_indexer = vector_indexer
        logger.info("Context reconstructor stores configured")

    def reconstruct(
        self,
        timestamp: datetime,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Reconstruct exact context at timestamp.

        Args:
            timestamp: Original query timestamp
            user_context: User context from original query

        Returns:
            Reconstructed context dictionary
        """
        context = {
            "timestamp": timestamp.isoformat(),
            "user_context": user_context,
            "memory_snapshot": self._get_memory_snapshot(timestamp),
            "preferences": self._get_preferences(),
            "sessions": self._get_sessions()
        }

        logger.debug(f"Reconstructed context for {timestamp}")
        return context

    def _get_memory_snapshot(self, timestamp: datetime) -> Dict[str, Any]:
        """Get memory state at timestamp."""
        if not self._vector_indexer:
            return {}
        try:
            collection = self._vector_indexer.collection
            return {
                "chunk_count": collection.count(),
                "timestamp": timestamp.isoformat()
            }
        except Exception as e:
            logger.warning(f"Memory snapshot failed: {e}")
            return {}

    def _get_preferences(self) -> Dict[str, Any]:
        """Get user preferences from KV store."""
        if not self._kv_store:
            return {}
        try:
            prefs = self._kv_store.get("user:preferences")
            return prefs if prefs else {}
        except Exception as e:
            logger.warning(f"Preferences fetch failed: {e}")
            return {}

    def _get_sessions(self) -> list:
        """Get active sessions from KV store."""
        if not self._kv_store:
            return []
        try:
            sessions = self._kv_store.get("active:sessions")
            return sessions if sessions else []
        except Exception as e:
            logger.warning(f"Sessions fetch failed: {e}")
            return []
