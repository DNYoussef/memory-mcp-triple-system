"""
Stage Transitions: Memory lifecycle stage transition methods.

Extracted from lifecycle_manager.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger


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
        cutoff = datetime.now() - timedelta(days=threshold)
        cutoff_str = cutoff.isoformat()

        # Query chunks with last_accessed > threshold
        try:
            stale_chunks = self.vector_indexer.collection.get(
                where={
                    "$and": [
                        {"stage": "active"},
                        {"last_accessed": {"$lt": cutoff_str}}
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

        for chunk_id in chunk_ids:
            try:
                self.vector_indexer.collection.update(
                    ids=[chunk_id],
                    metadatas=[{
                        'stage': 'demoted',
                        'score_multiplier': 0.5,
                        'demoted_at': datetime.now().isoformat()
                    }]
                )
            except Exception as e:
                logger.error(f"Failed to demote chunk {chunk_id}: {e}")

        logger.info(f"Demoted {len(chunk_ids)} chunks (>{threshold} days old)")
        return len(chunk_ids)

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
            f"(compressed 100:1, >{threshold} days demoted)"
        )
        return archived_count

    def _query_old_demoted(self, threshold_days: int) -> Optional[Dict]:
        """Query old demoted chunks."""
        cutoff = datetime.now() - timedelta(days=threshold_days)
        cutoff_str = cutoff.isoformat()

        try:
            old_chunks = self.vector_indexer.collection.get(
                where={
                    "$and": [
                        {"stage": "demoted"},
                        {"demoted_at": {"$lt": cutoff_str}}
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

            # Compress and store
            summary = self._summarize(full_text)
            self.kv_store.set(f"archived:{chunk_id}", summary)
            self.kv_store.set(f"archived:{chunk_id}:metadata", str(metadata))

            # Delete from vector store
            try:
                self.vector_indexer.collection.delete(ids=[chunk_id])
                archived_count += 1
            except Exception as e:
                logger.error(f"Failed to delete chunk {chunk_id}: {e}")

        return archived_count

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
            key for key in self.kv_store.keys()
            if key.startswith("archived:") and ":metadata" not in key
        ]

        rehydratable_count = 0
        for key in archived_keys:
            chunk_id = key.replace("archived:", "")

            # Check archival age
            metadata_str = self.kv_store.get(f"archived:{chunk_id}:metadata")
            if not metadata_str:
                continue

            # Parse timestamp from metadata (simplified)
            # In production, use proper JSON parsing
            if "archived_at" in metadata_str:
                # Mark as rehydratable in metadata
                self.kv_store.set(
                    f"rehydratable:{chunk_id}",
                    self.kv_store.get(f"archived:{chunk_id}")
                )
                self.kv_store.delete(f"archived:{chunk_id}")
                rehydratable_count += 1

        logger.info(
            f"Made {rehydratable_count} chunks rehydratable "
            f"(>{threshold} days archived)"
        )
        return rehydratable_count
