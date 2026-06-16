"""
Memory Lifecycle Manager: 4-stage lifecycle with rekindling.

Implements gradual memory degradation:
1. Active (100% score, <7 days)
2. Demoted (50% score, 7-30 days, decay applied)
3. Archived (10% score, 30-90 days, compressed to bounded summary)
4. Rehydratable (1% score, >90 days, lossy key only)

Rekindling: Query matches archived -> rehydrate -> promote to active

NASA Rule 10 Compliant: All methods <=60 LOC

Refactored: Extracted stage transitions and consolidation into separate modules.
See: stage_transitions.py, consolidation.py
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import ast
import json
import threading
from loguru import logger

# Import mixins for modular architecture (ISS-006 fix)
from .stage_transitions import StageTransitionsMixin
from .consolidation import ConsolidationMixin
from ._mutation_lock import guarded_mutation

# Archival keeps ONLY the summary (the chunk is deleted from the vector store),
# so this budget is the bound on irreversible loss. A document within budget is
# kept verbatim - truncating it to save a few dozen bytes of cold storage is not
# worth the loss; only larger documents are compressed down to this length.
SUMMARY_MAX_LEN = 200


class MemoryLifecycleManager(StageTransitionsMixin, ConsolidationMixin):
    """
    4-stage lifecycle with rekindling and consolidation.

    Stages:
    1. Active (100% score, accessed <7 days)
    2. Demoted (50% score, 7-30 days no access, decay applied)
    3. Archived (10% score, 30-90 days, compressed to summary)
    4. Rehydratable (1% score, >90 days, lossy key only)

    Rekindling: Query matches archived → rehydrate → promote to active
    Consolidation: Merge similar chunks (cosine >0.95)

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, vector_indexer, kv_store, embedding_pipeline=None):
        """
        Initialize lifecycle manager.

        Args:
            vector_indexer: VectorIndexer instance
            kv_store: KeyValueStore instance
            embedding_pipeline: Optional embedder for merged/rehydrated documents
        """
        self.vector_indexer = vector_indexer
        self.kv_store = kv_store
        self.embedding_pipeline = embedding_pipeline

        # Cross-subsystem mutation lock (E7). Every mutating entry point on this
        # manager - demote/archive/cleanup/rekindle/make_rehydratable across the
        # mixins, plus consolidate - acquires this lock (via @guarded_mutation)
        # so concurrent to_thread workers cannot interleave Chroma mutations.
        # RLock so a guarded method calling another on the same thread re-enters
        # instead of self-deadlocking.
        self._mutation_lock = threading.RLock()

        # Stage configuration
        self.stages = {
            'active': 1.0,
            'demoted': 0.5,
            'archived': 0.1,
            'rehydratable': 0.01
        }

        # Thresholds (days)
        self.demote_threshold = 7
        self.archive_threshold = 30
        self.rehydrate_threshold = 90

        logger.info("MemoryLifecycleManager initialized")

    @guarded_mutation
    def cleanup_expired(self) -> int:
        """Clean up expired entries from KV store.

        Delegates to kv_store.cleanup_expired() which purges
        entries past their TTL. Called by LifecycleScheduler daily at midnight.
        """
        try:
            return self.kv_store.cleanup_expired()
        except Exception as e:
            logger.error(f"cleanup_expired failed: {e}")
            return 0

    # ISS-006 FIX: Stage transition methods extracted to StageTransitionsMixin:
    # - demote_stale_chunks, archive_demoted_chunks, _query_old_demoted,
    #   _archive_chunks_batch, make_rehydratable
    # Consolidation methods extracted to ConsolidationMixin:
    # - consolidate_similar, _get_active_chunks, _find_and_merge_similar,
    #   _merge_chunk_pair, _calculate_similarity, _merge_chunks
    # This reduces lifecycle_manager.py from ~614 LOC to ~280 LOC (54% reduction)

    @guarded_mutation
    def rekindle_archived(
        self,
        query_embedding: List[float],
        chunk_id: str
    ) -> bool:
        """
        Rekindle archived chunk (rehydrate full text).

        Query matches lossy key → retrieve full text from Obsidian →
        re-index in vector store → promote to active

        Args:
            query_embedding: Fallback embedding if document re-embedding is unavailable
            chunk_id: Chunk ID to rekindle

        Returns:
            True if rekindled successfully, False otherwise
        """
        # Retrieve summary and metadata
        summary, metadata_str = self._get_archived_data(chunk_id)
        if not summary:
            return False

        # Extract file path
        file_path = self._extract_file_path(metadata_str)
        if not file_path:
            logger.warning(f"No file_path in metadata for chunk {chunk_id}")
            return False

        # Rehydrate full text from file
        full_text = self._read_full_text(file_path)
        if not full_text:
            return False

        # Re-index and promote
        self._reindex_and_promote(chunk_id, full_text, file_path, query_embedding, metadata_str)

        # Clean up KV store
        self._cleanup_archived_keys(chunk_id)

        logger.info(f"Rekindled chunk {chunk_id} → active")
        return True

    def _get_archived_data(self, chunk_id: str) -> tuple[Optional[str], Optional[str]]:
        """Retrieve summary and metadata from KV store."""
        summary = (
            self.kv_store.get(f"archived:{chunk_id}") or
            self.kv_store.get(f"rehydratable:{chunk_id}")
        )

        if not summary:
            logger.warning(f"Chunk {chunk_id} not found in archive")
            return None, None

        # No silent /default/path.md fabrication (E8): if metadata is genuinely
        # missing, return None so _extract_file_path fails honestly rather than
        # rehydrating from a bogus default path.
        metadata_str = (
            self.kv_store.get(f"archived:{chunk_id}:metadata") or
            self.kv_store.get(f"rehydratable:{chunk_id}:metadata")
        )

        return summary, metadata_str

    def _extract_file_path(self, metadata_str: Optional[str]) -> Optional[str]:
        """Extract file path from archived metadata.

        Production stores metadata as JSON (see _archive_chunks_batch); legacy
        repr strings are also parsed. Structured parse wins. On any miss we
        return None (rekindle then fails cleanly) instead of fabricating a
        /default/path.md - silently rehydrating the wrong file was the E8 bug.
        """
        metadata = self._metadata_from_string(metadata_str or "")
        if metadata.get("file_path"):
            return str(metadata["file_path"])
        if metadata:
            # Parsed to a real dict but it carries no file_path - nothing to
            # rehydrate from. Do not scan the raw string (a "file_path"
            # substring elsewhere would yield a wrong path).
            logger.warning("Archived metadata has no file_path; cannot rehydrate")
            return None

        # Parse failed entirely (empty dict). Tolerantly scan legacy non-JSON
        # strings for a file_path, but fail honestly on a miss.
        if metadata_str and "file_path" in metadata_str:
            try:
                candidate = metadata_str.split("file_path", 1)[1].split(",", 1)[0].strip(": '\"")
                if candidate:
                    return candidate
            except (IndexError, AttributeError):
                pass

        logger.warning("Could not extract file_path from archived metadata")
        return None

    def _read_full_text(self, file_path: str) -> Optional[str]:
        """Read full text from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None

    def _reindex_and_promote(
        self,
        chunk_id: str,
        full_text: str,
        file_path: str,
        query_embedding: List[float],
        metadata_str: Optional[str] = None
    ):
        """Re-index chunk and promote to active."""
        now = datetime.utcnow()
        metadata = self._metadata_from_string(metadata_str or "")
        metadata.update({
            'stage': 'active',
            'score_multiplier': 1.0,
            'last_accessed': now.isoformat(),
            'last_accessed_ts': now.timestamp(),
            'rekindled_at': now.isoformat(),
            'rekindled_at_ts': now.timestamp(),
        })

        embedding = self._embed_text(full_text, fallback_embedding=query_embedding)

        self.vector_indexer.index_chunks(
            chunks=[{
                'id': chunk_id,
                'text': full_text,
                'file_path': file_path,
                'chunk_index': 0,
                'metadata': metadata,
            }],
            embeddings=[embedding]
        )

        self.vector_indexer.collection.update(
            ids=[chunk_id],
            metadatas=[metadata]
        )

    def _cleanup_archived_keys(self, chunk_id: str):
        """Clean up KV store keys."""
        for prefix in ['archived', 'rehydratable']:
            self.kv_store.delete(f"{prefix}:{chunk_id}")
            self.kv_store.delete(f"{prefix}:{chunk_id}:metadata")

    @staticmethod
    def _metadata_from_string(metadata_str: str) -> Dict[str, Any]:
        """Parse archived metadata from JSON or legacy repr strings."""
        if not metadata_str:
            return {}
        try:
            parsed = json.loads(metadata_str)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(metadata_str)
                return parsed if isinstance(parsed, dict) else {}
            except (ValueError, SyntaxError):
                return {}

    def _embed_text(
        self,
        text: str,
        fallback_embedding: Optional[List[float]] = None
    ) -> Optional[List[float]]:
        """Embed document text, falling back only when no embedder is available."""
        if self.embedding_pipeline is not None:
            try:
                if hasattr(self.embedding_pipeline, "encode_single"):
                    return self._embedding_to_list(
                        self.embedding_pipeline.encode_single(text)
                    )
                embeddings = self.embedding_pipeline.encode([text])
                return self._embedding_to_list(embeddings[0])
            except Exception as e:
                logger.warning(f"Document re-embedding failed, using fallback: {e}")
        return self._embedding_to_list(fallback_embedding)

    @staticmethod
    def _embedding_to_list(embedding: Any) -> Optional[List[float]]:
        """Normalize ndarray/list embeddings to a plain vector list."""
        if embedding is None:
            return None
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        if isinstance(embedding, list) and embedding and isinstance(embedding[0], list):
            return list(embedding[0])
        return list(embedding)

    # Consolidation methods provided by ConsolidationMixin:
    # consolidate_similar, _get_active_chunks, _find_and_merge_similar,
    # _merge_chunk_pair, _calculate_similarity, _merge_chunks

    def get_stage_stats(self) -> Dict[str, int]:
        """
        Get statistics for each lifecycle stage.

        Returns:
            {
                'active': count,
                'demoted': count,
                'archived': count,
                'rehydratable': count,
                'total': count
            }
        """
        stats = {
            'active': 0,
            'demoted': 0,
            'archived': 0,
            'rehydratable': 0,
            'total': 0
        }

        # Count active and demoted (in vector store)
        try:
            for stage in ['active', 'demoted']:
                chunks = self.vector_indexer.collection.get(
                    where={"stage": stage}
                )
                stats[stage] = len(chunks.get('ids', []))
        except Exception as e:
            logger.error(f"Failed to query vector store: {e}")

        # Count archived and rehydratable (in KV store)
        # KVStore exposes list_keys(prefix), not keys()
        archived_keys = [
            key for key in self.kv_store.list_keys("archived:")
            if key.startswith("archived:") and ":metadata" not in key
        ]
        stats['archived'] = len(archived_keys)

        rehydratable_keys = [
            key for key in self.kv_store.list_keys("rehydratable:")
            if key.startswith("rehydratable:") and ":metadata" not in key
        ]
        stats['rehydratable'] = len(rehydratable_keys)

        stats['total'] = sum([
            stats['active'],
            stats['demoted'],
            stats['archived'],
            stats['rehydratable']
        ])

        logger.info(f"Stage stats: {stats}")
        return stats

    # Helper methods

    def _summarize(self, full_text: str) -> str:
        """
        ISS-011 FIX: Improved extractive summarization with entity preservation.

        Uses TF-IDF-like scoring to select most informative sentence.
        Falls back to first sentence if analysis fails.

        Args:
            full_text: Full text to summarize

        Returns:
            One-sentence summary preserving key entities

        NASA Rule 10: 55 LOC (<=60)
        """
        # Anything already within the summary budget is kept verbatim - the
        # old bound min(200, max(50, len/5 - 1)) floored at 50 and truncated
        # short documents for a trivial storage saving (E9: irreversible loss).
        if not full_text or len(full_text) <= SUMMARY_MAX_LEN:
            return full_text

        # Split into sentences
        import re
        sentences = re.split(r'(?<=[.!?])\s+', full_text.strip())
        if not sentences:
            return self._truncate_with_entities(full_text, max_len=SUMMARY_MAX_LEN)

        max_len = SUMMARY_MAX_LEN
        if len(sentences) == 1:
            return self._truncate_with_entities(sentences[0], max_len=max_len)

        # ISS-011 FIX: Score sentences by entity density and position
        scored = []
        all_words = set(full_text.lower().split())
        for i, sent in enumerate(sentences):
            # Count capitalized words (entities) and unique terms
            words = sent.split()
            entities = sum(1 for w in words if w and w[0].isupper())
            unique = len(set(w.lower() for w in words) & all_words)
            # Position bonus: first and last sentences often important
            pos_bonus = 1.5 if i == 0 else (1.2 if i == len(sentences) - 1 else 1.0)
            score = (entities * 2 + unique) * pos_bonus / max(len(words), 1)
            scored.append((score, i, sent))

        # Select best sentence
        scored.sort(reverse=True)
        best_sentence = scored[0][2] if scored else sentences[0]

        return self._truncate_with_entities(best_sentence, max_len=max_len)

    def _truncate_with_entities(self, text: str, max_len: int = 200) -> str:
        """Truncate text while preserving complete words and entities."""
        if len(text) <= max_len:
            return text
        # Find last space before max_len to avoid cutting words
        truncate_at = text.rfind(' ', 0, max_len - 3)
        if truncate_at == -1:
            truncate_at = max_len - 3
        return text[:truncate_at] + "..."

    # _calculate_similarity and _merge_chunks are provided by ConsolidationMixin
