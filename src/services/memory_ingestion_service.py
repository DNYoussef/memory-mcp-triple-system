"""
Shared Memory Ingestion Service.

Single write path for both HTTP and stdio transports.
Prevents the original bug: HTTP was a stub that skipped 80% of the pipeline.

Pipeline:
1. Validate + normalize metadata
2. Classify hot/cold
3. Generate embedding
4. Index to vector store (with stable chunk ID)
5. Extract entities â†’ populate graph
6. Record metadata beliefs/because in the belief web (only when given)
7. Log event
8. Run lifecycle maintenance

Non-negotiable rule: HTTP and stdio MUST NOT have separate ingestion logic.
"""

import hashlib
import json
import time
from array import array
from datetime import datetime
from typing import Any, Dict, List

from loguru import logger

from src.belief_web.belief_store import (
    BeliefStore,
    BeliefValidationError,
    locate_chunks,
)
from src.belief_web.solver import EDGE_TYPES, EdgeConflict

BELIEF_FIELDS = {
    "key",
    "claim",
    "value",
    "source_type",
    "observed_at",
    "kind",
    "quote",
    "source_ref",
    "reliability",
    "half_life_days",
    *EDGE_TYPES,
}
EDGE_WEIGHT = 0.5  # memory_store edges carry no weight of their own


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
        kv_store=None,
        beliefs_enabled=True,
    ):
        self._embedder = embedder
        self._indexer = indexer
        self._graph_service = graph_service
        self._entity_service = entity_service
        self._classifier = classifier
        self._lifecycle_manager = lifecycle_manager
        self._event_log = event_log
        self._chunker = chunker
        self._kv_store = kv_store
        # Opened on first use next to the KV store (agent_kv.db), so a store
        # without beliefs never creates the belief tables.
        self._belief_store = None
        self._beliefs_enabled = beliefs_enabled

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

        # 0. Validate input
        if not text or not text.strip():
            return {"success": False, "error": "Empty text â€” nothing to ingest"}

        # 1. Stamp metadata
        now = datetime.utcnow()
        now_iso = now.isoformat()
        metadata = {**metadata, "stored_at": now_iso, "source": source}

        # 2. Classify hot/cold
        classification = self._classify(text, metadata)
        metadata["lifecycle_tier"] = classification.get("tier", "hot")
        metadata["decay_score"] = classification.get("decay_score", 1.0)
        metadata["stage"] = classification.get("lifecycle_stage", "active")
        metadata["last_accessed"] = now_iso
        # Numeric ts the demote query filters on ({"last_accessed_ts": {"$lt": cutoff}}).
        # Without it, ingested chunks never match the demote query and never age (A2).
        metadata["last_accessed_ts"] = now.timestamp()
        metadata["access_count"] = 0

        # 3. Chunk text (semantic chunking for long texts, single chunk for short)
        text_chunks = self._chunk_text(text, metadata)
        if not text_chunks:
            text_chunks = [text]  # Fallback: use original text as single chunk

        # 4. Process each chunk: ID â†’ embed â†’ index â†’ graph
        all_entity_stats: Dict[str, Any] = {
            "entities_added": 0,
            "relationships_created": 0,
            "entity_types": [],
        }
        chunk_ids = []
        chunk_id = None  # Initialize to avoid NameError if loop is empty
        warnings: List[str] = []

        for idx, chunk_text in enumerate(text_chunks):
            chunk_id = self._make_chunk_id(chunk_text, source, f"{now_iso}:{idx}")
            chunk_ids.append(chunk_id)

            # Generate embedding
            embedding = self._encode_single_chunk(chunk_text)

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
            self._indexer.index_chunks([chunk], [embedding])

            # Entity extraction â†’ graph population
            stats = self._populate_graph(chunk_id, chunk_text, chunk_meta)
            graph_warning = stats.pop("graph_warning", None)
            if graph_warning and graph_warning not in warnings:
                warnings.append(graph_warning)
            all_entity_stats["entities_added"] += stats.get("entities_added", 0)
            all_entity_stats["relationships_created"] += stats.get(
                "relationships_created", 0
            )
            for et in stats.get("entity_types", []):
                if et not in all_entity_stats["entity_types"]:
                    all_entity_stats["entity_types"].append(et)

        entity_stats = all_entity_stats

        # 6. Beliefs, after the chunks are indexed. Absent keys add nothing to
        # the response, so a store without beliefs answers exactly as before.
        beliefs = None
        if "beliefs" in metadata or "because" in metadata:
            beliefs = self._record_beliefs(metadata, text_chunks, chunk_ids, now_iso)

        # 7. Log event (log all chunk IDs, not just last)
        self._log_event(
            text, metadata, ",".join(chunk_ids) if chunk_ids else "none", entity_stats
        )

        # 8. Lifecycle maintenance (non-critical)
        self._run_lifecycle_maintenance()

        elapsed_ms = (time.monotonic() - t0) * 1000
        result = {
            "success": True,
            "chunk_id": chunk_ids[0] if chunk_ids else None,
            "chunk_ids": chunk_ids,
            "chunks_stored": len(text_chunks),
            "stored_at": now_iso,
            "text_length": len(text),
            "metadata": metadata,
            "entities": entity_stats,
            "lifecycle_tier": metadata["lifecycle_tier"],
            "elapsed_ms": round(elapsed_ms, 1),
            "graph_persisted": not warnings,
            "warnings": warnings,
        }
        if beliefs is not None:
            result["beliefs"] = beliefs
        return result

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

    def _encode_single_chunk(self, text: str) -> List[float]:
        """Encode one chunk and normalize common ndarray/list return shapes."""
        embeddings = self._embedder.encode([text])
        if hasattr(embeddings, "tolist"):
            values = embeddings.tolist()
            return values[0] if values and isinstance(values[0], list) else values

        embedding = embeddings[0]
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)

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
        """Extract entities and add chunk + entities to graph. Graceful fallback.

        graph_warning is set whenever this chunk did not reach graph.json.
        """
        empty = {"entities_added": 0, "relationships_created": 0, "entity_types": []}
        if not self._entity_service or not self._graph_service:
            return {
                **empty,
                "graph_warning": "graph population unavailable; memory stored without graph links",
            }
        try:
            # Add chunk node to graph
            self._graph_service.add_chunk_node(
                chunk_id,
                {
                    "text": text[:500],
                    "file_path": metadata.get("file_path", "/memory/stored.md"),
                    "timestamp": metadata.get("stored_at"),
                },
            )

            # Use EntityService's built-in method (extracts + creates nodes + edges)
            stats = self._entity_service.add_entities_to_graph(
                chunk_id, text, self._graph_service
            )

            # Persist graph to disk (batch save, not per-entity). A failed save
            # keeps the graph dirty, so the next store retries it.
            if self._graph_service.save_graph():
                return stats
            return {
                **stats,
                "graph_warning": "graph not persisted; will retry on next store",
            }
        except Exception as e:
            logger.warning(f"Graph population failed: {e}")
            return {**empty, "graph_warning": f"graph population failed: {e}"}

    # ------------------------------------------------------------------
    # Beliefs (PLAN-B section 4.1)
    # ------------------------------------------------------------------

    def _record_beliefs(
        self,
        metadata: Dict[str, Any],
        chunks: List[str],
        chunk_ids: List[str],
        recorded_at: str,
    ) -> Dict[str, Any]:
        """Record metadata `beliefs`/`because` under origin live (section 2.6).

        A bad entry is rejected on its own (its savepoint rolls back) and
        reported. The valid entries share ONE transaction, so any other write
        failure leaves zero belief rows from this call. The memory itself is
        already stored either way. Errors are sanitized with strip_private.
        """
        from src.hooks.post_tool_handler import strip_private

        errors: List[str] = []
        recorded = 0
        entries = metadata.get("beliefs", [])
        because = metadata.get("because", [])
        try:
            if not self._beliefs_enabled:
                raise BeliefValidationError(
                    "belief ingestion is disabled (belief_web.ingest)"
                )
            if not isinstance(entries, list) or not isinstance(because, list):
                raise BeliefValidationError("beliefs and because must be lists")
            if because and not entries:
                raise BeliefValidationError("because needs at least one belief")
            store = self._beliefs()
            links = [self._link(entry) for entry in entries]  # outside the lock
            with store.batch():
                for i, entry in enumerate(entries):
                    key = entry.get("key") if isinstance(entry, dict) else None
                    label = key if isinstance(key, str) else f"beliefs[{i}]"
                    try:
                        with store.batch():
                            note = self._write_belief(
                                store,
                                entry,
                                because,
                                metadata,
                                chunks,
                                chunk_ids,
                                recorded_at,
                                links[i],
                            )
                        recorded += 1
                        if note:
                            errors.append(f"{label}: {note}")
                    except (BeliefValidationError, EdgeConflict) as e:
                        errors.append(f"{label}: {e}")
        except BeliefValidationError as e:
            errors.append(f"beliefs: {e}")
        except Exception as e:
            logger.warning(f"Belief write failed: {e}")
            recorded = 0
            errors.append(f"beliefs: not recorded ({e}); no belief rows kept")
        return {"recorded": recorded, "errors": [strip_private(e) for e in errors]}

    def _write_belief(
        self, store, entry, because, metadata, chunks, chunk_ids, recorded_at, link
    ) -> str:
        """One entry: an assertion row per chunk (the mention, located by the
        quote rule), then its edges. Returns a non-fatal note, else ''."""
        if not isinstance(entry, dict):
            raise BeliefValidationError("entry must be an object")
        unknown = sorted(set(entry) - BELIEF_FIELDS)
        if unknown:
            raise BeliefValidationError(f"unknown fields {unknown}")
        key, claim, quote = entry.get("key"), entry.get("claim"), entry.get("quote")
        if not isinstance(key, str) or not isinstance(entry.get("value"), bool):
            raise BeliefValidationError("key must be text and value true or false")
        if quote is not None and not isinstance(quote, str):
            raise BeliefValidationError("quote must be text")
        if claim is None and not store.exists(key):
            raise BeliefValidationError("a new key needs a claim")
        located = locate_chunks(chunks, quote)
        for chunk_id, loc in zip(chunk_ids, located):
            store.add_assertion(
                "live",
                key,
                polarity=1 if entry["value"] else -1,
                source_type=entry.get("source_type"),
                observed_at=entry.get("observed_at", recorded_at),  # omitted only
                recorded_at=recorded_at,
                chunk_id=chunk_id,
                source_ref=entry.get("source_ref"),
                who=metadata.get("who"),
                reliability=entry.get("reliability"),
                located=loc,
                kind=entry.get("kind"),
                claim=claim,
                half_life_days=entry.get("half_life_days"),
            )
        for edge_type in EDGE_TYPES:
            targets = entry.get(edge_type, [])
            if not isinstance(targets, list):
                raise BeliefValidationError(f"{edge_type} must be a list of keys")
            if edge_type == "depends_on":
                targets = targets + because
            for target in targets:
                store.add_edge("live", key, target, edge_type, EDGE_WEIGHT)
        if claim is not None:
            store.link("live", key, claim, metadata.get("project"), *link)
        if quote and len(chunks) > 1 and not any(located):
            return "quote not found"
        return ""

    def _link(self, entry: Any) -> tuple:
        """(entities, claim_vec, vec_model) for an entry's claim. Linking is
        enrichment: a failure leaves NULLs and never rejects the belief."""
        claim = entry.get("claim") if isinstance(entry, dict) else None
        if not isinstance(claim, str) or not claim.strip():
            return (None, None, None)
        entities = vec = model = None
        try:
            if self._entity_service:
                found = self._entity_service.extract_entities(claim)
                entities = json.dumps(sorted({e["text"] for e in found}))
        except Exception as e:
            logger.warning(f"Belief entity linking failed: {e}")
        try:
            vec = array("f", self._encode_single_chunk(claim)).tobytes()
            model = getattr(self._embedder, "model_name", None)
            model = model if isinstance(model, str) else None
        except Exception as e:
            logger.warning(f"Belief claim embedding failed: {e}")
        return (entities, vec, model)

    def _beliefs(self) -> BeliefStore:
        if self._belief_store is None:
            path = getattr(self._kv_store, "db_path", None)
            if path is None:
                raise RuntimeError("no belief store (KV store path unknown)")
            self._belief_store = BeliefStore(str(path))
        return self._belief_store

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
            if self._kv_store and self._kv_store.set_if_absent(
                "lifecycle:cleanup:claim", "1", ttl=86400
            ):
                self._lifecycle_manager.cleanup_expired()
            self._lifecycle_manager.demote_stale_chunks()
            self._lifecycle_manager.archive_demoted_chunks()
        except Exception as e:
            logger.warning(f"Lifecycle maintenance failed: {e}")
