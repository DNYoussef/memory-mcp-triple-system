"""
Shared Memory Ingestion Service.

Single write path for both HTTP and stdio transports.
Prevents the original bug: HTTP was a stub that skipped 80% of the pipeline.

Pipeline:
1. Validate + normalize metadata
2. Classify hot/cold
3. Generate embedding
4. Index to vector store (with stable chunk ID)
5. Extract entities → populate graph
6. Log event
7. Run lifecycle maintenance

Non-negotiable rule: HTTP and stdio MUST NOT have separate ingestion logic.
"""

import hashlib
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


class MemoryIngestionService:
    """Orchestrates the full memory ingestion pipeline."""

    # Minimum text length (in chars) to attempt semantic chunking.
    # Below this, store as single chunk (no point splitting a sentence).
    MIN_CHUNKING_LENGTH = 300

    def __init__(
        self,
        embedder,
        indexer,
        graph_service,
        entity_service,
        classifier,
        lifecycle_manager,
        event_log,
        chunker=None,
    ):
        self._embedder = embedder
        self._indexer = indexer
        self._graph_service = graph_service
        self._entity_service = entity_service
        self._classifier = classifier
        self._lifecycle_manager = lifecycle_manager
        self._event_log = event_log
        self._chunker = chunker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        text: str,
        metadata: Dict[str, Any],
        source: str = "http_api",
    ) -> Dict[str, Any]:
        """
        Full ingestion pipeline. Called by both HTTP and stdio transports.

        Returns dict with ingestion stats.
        """
        t0 = time.monotonic()

        # 1. Stamp metadata
        now_iso = datetime.utcnow().isoformat()
        metadata = {**metadata, "stored_at": now_iso, "source": source}

        # 2. Classify hot/cold
        classification = self._classify(text, metadata)
        metadata["lifecycle_tier"] = classification.get("tier", "hot")
        metadata["decay_score"] = classification.get("decay_score", 1.0)
        metadata["stage"] = classification.get("lifecycle_stage", "active")
        metadata["last_accessed"] = now_iso
        metadata["access_count"] = 0

        # 3. Chunk text (semantic chunking for long texts, single chunk for short)
        text_chunks = self._chunk_text(text, metadata)

        # 4. Process each chunk: ID → embed → index → graph
        all_entity_stats: Dict[str, Any] = {
            "entities_added": 0, "relationships_created": 0, "entity_types": []
        }
        chunk_ids = []

        for idx, chunk_text in enumerate(text_chunks):
            chunk_id = self._make_chunk_id(chunk_text, source, f"{now_iso}:{idx}")
            chunk_ids.append(chunk_id)

            # Generate embedding
            embedding = self._embedder.encode([chunk_text])[0]

            # Index to vector store
            chunk_meta = {
                **metadata,
                "chunk_index": idx,
                "total_chunks": len(text_chunks),
                "parent_text_length": len(text),
            }
            chunk = {
                "text": chunk_text,
                "file_path": metadata.get("file_path", "/memory/stored.md"),
                "chunk_index": idx,
                "metadata": chunk_meta,
                "id": chunk_id,
            }
            self._indexer.index_chunks([chunk], [embedding.tolist()])

            # Entity extraction → graph population
            stats = self._populate_graph(chunk_id, chunk_text, chunk_meta)
            all_entity_stats["entities_added"] += stats.get("entities_added", 0)
            all_entity_stats["relationships_created"] += stats.get("relationships_created", 0)
            for et in stats.get("entity_types", []):
                if et not in all_entity_stats["entity_types"]:
                    all_entity_stats["entity_types"].append(et)

        entity_stats = all_entity_stats

        # 7. Log event
        self._log_event(text, metadata, chunk_id, entity_stats)

        # 8. Lifecycle maintenance (non-critical)
        self._run_lifecycle_maintenance()

        elapsed_ms = (time.monotonic() - t0) * 1000
        return {
            "success": True,
            "chunk_ids": chunk_ids,
            "chunks_stored": len(text_chunks),
            "stored_at": now_iso,
            "text_length": len(text),
            "metadata": metadata,
            "entities": entity_stats,
            "lifecycle_tier": metadata["lifecycle_tier"],
            "elapsed_ms": round(elapsed_ms, 1),
        }

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[str]:
        """Split text into semantic chunks. Falls back to single chunk for short texts."""
        if not self._chunker or len(text) < self.MIN_CHUNKING_LENGTH:
            return [text]
        try:
            file_path = metadata.get("file_path", "/memory/stored.md")
            chunks = self._chunker.chunk_text(text, file_path)
            if chunks:
                return [c["text"] for c in chunks if c.get("text")]
            return [text]
        except Exception as e:
            logger.warning(f"Semantic chunking failed, using single chunk: {e}")
            return [text]

    @staticmethod
    def _make_chunk_id(text: str, source: str, timestamp: str) -> str:
        """Stable, collision-safe chunk ID used across vector + graph stores."""
        raw = f"{source}:{text}:{timestamp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _classify(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Hot/cold classification. Graceful fallback."""
        if not self._classifier:
            return {"tier": "hot", "decay_score": 1.0, "lifecycle_stage": "active"}
        try:
            return self._classifier.classify(text, metadata)
        except Exception as e:
            logger.warning(f"Hot/cold classification failed: {e}")
            return {"tier": "hot", "decay_score": 1.0, "lifecycle_stage": "active"}

    def _populate_graph(
        self, chunk_id: str, text: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract entities and add chunk + entities to graph. Graceful fallback."""
        if not self._entity_service or not self._graph_service:
            return {"entities_added": 0, "relationships_created": 0, "entity_types": []}
        try:
            # Add chunk node to graph
            self._graph_service.add_chunk_node(chunk_id, {
                "text": text[:500],
                "file_path": metadata.get("file_path", "/memory/stored.md"),
                "timestamp": metadata.get("stored_at"),
            })

            # Use EntityService's built-in method (extracts + creates nodes + edges)
            stats = self._entity_service.add_entities_to_graph(
                chunk_id, text, self._graph_service
            )

            # Persist graph to disk (batch save, not per-entity)
            self._graph_service.save_graph()

            return stats
        except Exception as e:
            logger.warning(f"Graph population failed: {e}")
            return {"entities_added": 0, "relationships_created": 0, "entity_types": []}

    def _log_event(
        self,
        text: str,
        metadata: Dict[str, Any],
        chunk_id: str,
        entity_stats: Dict[str, Any],
    ) -> None:
        """Log ingestion event. Non-critical."""
        if not self._event_log:
            return
        try:
            from src.stores.event_log import EventType
            self._event_log.log_event(
                EventType.CHUNK_ADDED,
                {
                    "chunk_id": chunk_id,
                    "text_length": len(text),
                    "project": metadata.get("project"),
                    "entities_added": entity_stats.get("entities_added", 0),
                    "lifecycle_tier": metadata.get("lifecycle_tier", "hot"),
                    "timestamp": metadata.get("stored_at"),
                },
            )
        except Exception as e:
            logger.warning(f"Event logging failed: {e}")

    def _run_lifecycle_maintenance(self) -> None:
        """Demote stale + archive demoted. Non-critical."""
        if not self._lifecycle_manager:
            return
        try:
            self._lifecycle_manager.demote_stale_chunks()
            self._lifecycle_manager.archive_demoted_chunks()
        except Exception as e:
            logger.warning(f"Lifecycle maintenance failed: {e}")
