"""
Stage Transitions: Memory lifecycle stage transition methods.

Extracted from lifecycle_manager.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, List, Optional
import json
from datetime import datetime, timedelta
from loguru import logger

from ._mutation_lock import guarded_mutation


class StageTransitionsMixin:
    """
    Mixin providing stage transition methods for MemoryLifecycleManager.

    Requires:
        - self.vector_indexer
        - self.kv_store
        - self.demote_threshold
        - self.archive_threshold
        - self.rehydrate_threshold
    """

    @guarded_mutation
    def demote_stale_chunks(self, threshold_days: Optional[int] = None) -> int:
        """
        Demote chunks not accessed in N days.

        Active -> Demoted (apply 50% score multiplier)

        Args:
            threshold_days: Days since last access (default: 7)

        Returns:
            Number of chunks demoted
        """
        threshold = threshold_days or self.demote_threshold
        cutoff = datetime.utcnow() - timedelta(days=threshold)
        cutoff_ts = cutoff.timestamp()

        # Query chunks with last_accessed_ts > threshold (float for ChromaDB $lt)
        try:
            stale_chunks = self.vector_indexer.collection.get(
                where={
                    "$and": [
                        {"stage": "active"},
                        {"last_accessed_ts": {"$lt": cutoff_ts}}
                    ]
                },
                include=['metadatas']
            )
        except Exception as e:
            logger.error(f"Failed to query stale chunks: {e}")
            return 0

        # Update stage and apply decay
        chunk_ids = stale_chunks.get('ids', [])
        if not chunk_ids:
            logger.info("No chunks to demote")
            return 0

        metadatas = stale_chunks.get('metadatas', []) or [{}] * len(chunk_ids)
        for idx, chunk_id in enumerate(chunk_ids):
            try:
                _now = datetime.utcnow()
                metadata = dict(metadatas[idx] or {})
                metadata.update({
                    'stage': 'demoted',
                    'score_multiplier': 0.5,
                    'demoted_at': _now.isoformat(),
                    'demoted_at_ts': _now.timestamp()
                })
                self.vector_indexer.collection.update(
                    ids=[chunk_id],
                    metadatas=[metadata]
                )
            except Exception as e:
                logger.error(f"Failed to demote chunk {chunk_id}: {e}")

        logger.info(f"Demoted {len(chunk_ids)} chunks (>{threshold} days old)")
        return len(chunk_ids)

    @guarded_mutation
    def archive_demoted_chunks(
        self,
        threshold_days: Optional[int] = None
    ) -> int:
        """
        Archive chunks demoted for N days.

        Demoted -> Archived (compress to summary, store in KV)

        Args:
            threshold_days: Days since demotion (default: 30)

        Returns:
            Number of chunks archived
        """
        threshold = threshold_days or self.archive_threshold
        old_chunks = self._query_old_demoted(threshold)

        if not old_chunks:
            logger.info("No chunks to archive")
            return 0

        archived_count = self._archive_chunks_batch(old_chunks)

        logger.info(
            f"Archived {archived_count} chunks "
            f"(compressed to bounded summary, >{threshold} days demoted)"
        )
        return archived_count

    def _query_old_demoted(self, threshold_days: int) -> Optional[Dict]:
        """Query old demoted chunks."""
        cutoff = datetime.utcnow() - timedelta(days=threshold_days)
        cutoff_ts = cutoff.timestamp()

        try:
            old_chunks = self.vector_indexer.collection.get(
                where={
                    "$and": [
                        {"stage": "demoted"},
                        {"demoted_at_ts": {"$lt": cutoff_ts}}
                    ]
                },
                include=['documents', 'metadatas']
            )
            return old_chunks if old_chunks.get('ids') else None
        except Exception as e:
            logger.error(f"Failed to query demoted chunks: {e}")
            return None

    def _archive_chunks_batch(self, old_chunks: Dict) -> int:
        """Archive a batch of chunks."""
        archived_count = 0

        for i, chunk_id in enumerate(old_chunks['ids']):
            full_text = old_chunks['documents'][i]
            metadata = old_chunks['metadatas'][i]
            now = datetime.utcnow()
            metadata = dict(metadata or {})
            metadata.update({
                "stage": "archived",
                "archived_at": now.isoformat(),
                "archived_at_ts": now.timestamp(),
            })

            # Compress and store
            summary = self._summarize(full_text)
            self.kv_store.set(f"archived:{chunk_id}", summary)
            self.kv_store.set(
                f"archived:{chunk_id}:metadata",
                json.dumps(metadata, sort_keys=True, default=str)
            )

            # Delete from vector store
            try:
                self.vector_indexer.collection.delete(ids=[chunk_id])
                archived_count += 1
            except Exception as e:
                logger.error(f"Failed to delete chunk {chunk_id}: {e}")

        return archived_count

    @guarded_mutation
    def make_rehydratable(
        self,
        threshold_days: Optional[int] = None
    ) -> int:
        """
        Make archived chunks rehydratable (lossy key only).

        Archived -> Rehydratable (>90 days, keep lossy key)

        Args:
            threshold_days: Days since archival (default: 90)

        Returns:
            Number of chunks made rehydratable
        """
        threshold = threshold_days or self.rehydrate_threshold

        # Query archived chunks from KV store
        archived_keys = [
            key for key in self.kv_store.list_keys("archived:")
            if ":metadata" not in key
        ]

        rehydratable_count = 0
        for key in archived_keys:
            chunk_id = key.replace("archived:", "")

            # Check archival age
            metadata_str = self.kv_store.get(f"archived:{chunk_id}:metadata")
            if not metadata_str:
                continue

            metadata = self._load_archived_metadata(metadata_str)
            archived_at_ts = metadata.get("archived_at_ts")
            if archived_at_ts is None:
                continue

            cutoff = (datetime.utcnow() - timedelta(days=threshold)).timestamp()
            if float(archived_at_ts) < cutoff:
                # Mark as rehydratable in metadata
                self.kv_store.set(
                    f"rehydratable:{chunk_id}",
                    self.kv_store.get(f"archived:{chunk_id}")
                )
                self.kv_store.set(f"rehydratable:{chunk_id}:metadata", metadata_str)
                self.kv_store.delete(f"archived:{chunk_id}")
                self.kv_store.delete(f"archived:{chunk_id}:metadata")
                rehydratable_count += 1

        logger.info(
            f"Made {rehydratable_count} chunks rehydratable "
            f"(>{threshold} days archived)"
        )
        return rehydratable_count

    @staticmethod
    def _load_archived_metadata(metadata_str: str) -> Dict:
        """Load archived metadata from JSON, with legacy fallback."""
        try:
            return json.loads(metadata_str)
        except (TypeError, json.JSONDecodeError):
            if metadata_str and "archived_at" in metadata_str:
                raw_value = metadata_str.split("archived_at", 1)[1].split(",", 1)[0]
                raw_value = raw_value.strip(": '\"")
                try:
                    archived_at = datetime.fromisoformat(raw_value)
                    return {
                        "archived_at": raw_value,
                        "archived_at_ts": archived_at.timestamp(),
                    }
                except ValueError:
                    # Unparseable date -> far future, NOT 0.0. With 0.0 the
                    # `archived_at_ts < cutoff` check was always true, so
                    # corrupted metadata was auto-rehydrated every sweep. Keep
                    # it archived until handled explicitly.
                    return {"archived_at": raw_value, "archived_at_ts": float("inf")}
            return {}
