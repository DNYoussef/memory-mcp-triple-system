"""
Consolidation Module: Chunk merging and consolidation logic.

Extracted from lifecycle_manager.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np
from loguru import logger


class ConsolidationMixin:
    """
    Mixin providing consolidation methods for MemoryLifecycleManager.

    Requires:
        - self.vector_indexer
    """

    def consolidate_similar(self, threshold: float = 0.95) -> int:
        """
        Consolidate similar chunks (merge if cosine >threshold).

        Args:
            threshold: Cosine similarity threshold (default: 0.95)

        Returns:
            Number of chunks consolidated
        """
        active_chunks = self._get_active_chunks()
        if not active_chunks:
            return 0

        consolidated_count = self._find_and_merge_similar(active_chunks, threshold)

        logger.info(
            f"Consolidated {consolidated_count} chunks (threshold: {threshold})"
        )
        return consolidated_count

    def _get_active_chunks(self) -> Optional[Dict]:
        """Get all active chunks with embeddings."""
        try:
            active_chunks = self.vector_indexer.collection.get(
                where={"stage": "active"},
                include=['documents', 'embeddings', 'metadatas']
            )
        except Exception as e:
            logger.error(f"Failed to query active chunks: {e}")
            return None

        chunk_ids = active_chunks.get('ids', [])
        if len(chunk_ids) < 2:
            logger.info("Not enough chunks to consolidate")
            return None

        if not active_chunks.get('embeddings'):
            logger.warning("No embeddings available for consolidation")
            return None

        return active_chunks

    def _find_and_merge_similar(
        self,
        active_chunks: Dict,
        threshold: float
    ) -> int:
        """Find and merge similar chunk pairs."""
        chunk_ids = active_chunks['ids']
        documents = active_chunks['documents']
        embeddings = active_chunks['embeddings']
        metadatas = active_chunks['metadatas']

        consolidated_count = 0
        processed = set()

        for i in range(len(chunk_ids)):
            if chunk_ids[i] in processed:
                continue

            for j in range(i + 1, len(chunk_ids)):
                if chunk_ids[j] in processed:
                    continue

                similarity = self._calculate_similarity(embeddings[i], embeddings[j])

                if similarity >= threshold:
                    self._merge_chunk_pair(
                        chunk_ids[i], chunk_ids[j],
                        documents[i], documents[j],
                        metadatas[i], metadatas[j],
                        similarity
                    )
                    processed.add(chunk_ids[j])
                    consolidated_count += 1

        return consolidated_count

    def _merge_chunk_pair(
        self,
        id1: str,
        id2: str,
        doc1: str,
        doc2: str,
        meta1: Dict,
        meta2: Dict,
        similarity: float
    ):
        """Merge two similar chunks."""
        merged_text, merged_metadata = self._merge_chunks(doc1, doc2, meta1, meta2)

        # Update first chunk
        self.vector_indexer.collection.update(
            ids=[id1],
            documents=[merged_text],
            metadatas=[merged_metadata]
        )

        # Delete second chunk
        self.vector_indexer.collection.delete(ids=[id2])

        logger.debug(f"Consolidated {id2} into {id1} (similarity: {similarity:.2f})")

    def _calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _merge_chunks(
        self,
        text1: str,
        text2: str,
        metadata1: Dict[str, Any],
        metadata2: Dict[str, Any]
    ) -> tuple:
        """
        Merge two chunks into one.

        Args:
            text1: First chunk text
            text2: Second chunk text
            metadata1: First chunk metadata
            metadata2: Second chunk metadata

        Returns:
            (merged_text, merged_metadata)
        """
        # Combine text
        merged_text = f"{text1}\n\n{text2}"

        # Merge metadata (union of tags, max scores, newer timestamp)
        merged_metadata = metadata1.copy()

        # Merge tags
        tags1 = set(metadata1.get('tags', []))
        tags2 = set(metadata2.get('tags', []))
        merged_metadata['tags'] = list(tags1 | tags2)

        # Take max score
        score1 = metadata1.get('score', 0)
        score2 = metadata2.get('score', 0)
        merged_metadata['score'] = max(score1, score2)

        # Take newer timestamp
        ts1 = metadata1.get('last_accessed', '')
        ts2 = metadata2.get('last_accessed', '')
        merged_metadata['last_accessed'] = max(ts1, ts2)

        # Add consolidation marker
        merged_metadata['consolidated'] = True
        merged_metadata['consolidated_at'] = datetime.now().isoformat()

        return merged_text, merged_metadata
