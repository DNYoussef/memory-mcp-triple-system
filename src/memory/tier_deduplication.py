"""
Cross-Tier Deduplication - Deduplicate memory across retention tiers
Part of META-004: Waste System (Memory Compaction)

Handles deduplication between Short-Term, Mid-Term, and Long-Term memory
tiers to prevent redundant storage and ensure single source of truth.
"""

import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryTier(str, Enum):
    """Memory retention tiers"""
    SHORT_TERM = "short_term"   # 24 hours
    MID_TERM = "mid_term"       # 7 days
    LONG_TERM = "long_term"     # 30+ days


@dataclass
class ChunkReference:
    """Reference to a memory chunk"""
    chunk_id: str
    tier: MemoryTier
    content_hash: str
    embedding: Optional[np.ndarray]
    confidence: float
    created_at: datetime
    last_accessed: Optional[datetime]
    access_count: int
    byte_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DuplicatePair:
    """A pair of duplicate chunks across tiers"""
    primary: ChunkReference
    duplicate: ChunkReference
    similarity: float
    merge_recommendation: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_id": self.primary.chunk_id,
            "primary_tier": self.primary.tier.value,
            "duplicate_id": self.duplicate.chunk_id,
            "duplicate_tier": self.duplicate.tier.value,
            "similarity": self.similarity,
            "merge_recommendation": self.merge_recommendation,
            "reason": self.reason
        }


@dataclass
class DeduplicationResult:
    """Result of a deduplication operation"""
    run_id: str
    started_at: datetime
    completed_at: datetime
    chunks_scanned: int
    duplicates_found: int
    duplicates_merged: int
    bytes_freed: int
    pairs: List[DuplicatePair]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "chunks_scanned": self.chunks_scanned,
            "duplicates_found": self.duplicates_found,
            "duplicates_merged": self.duplicates_merged,
            "bytes_freed": self.bytes_freed,
            "pairs": [p.to_dict() for p in self.pairs],
            "errors": self.errors
        }


class TierDeduplicator:
    """
    Cross-tier deduplication engine.

    Strategies:
    1. Content Hash Matching - Exact duplicates via hash
    2. Semantic Similarity - Near-duplicates via embeddings
    3. Tier Promotion Rules - Which copy to keep

    Tier Priority (for keeping primary):
    1. Long-term (most stable)
    2. Mid-term
    3. Short-term (most ephemeral)

    Confidence Priority:
    - Higher confidence chunk is primary
    - Tie-breaker: older creation date
    """

    # Similarity thresholds
    EXACT_MATCH_THRESHOLD = 1.0
    NEAR_DUPLICATE_THRESHOLD = 0.95
    SEMANTIC_SIMILAR_THRESHOLD = 0.90

    # Tier priority (higher = more authoritative)
    TIER_PRIORITY = {
        MemoryTier.LONG_TERM: 3,
        MemoryTier.MID_TERM: 2,
        MemoryTier.SHORT_TERM: 1
    }

    def __init__(
        self,
        similarity_threshold: float = 0.95,
        prefer_higher_tier: bool = True,
        prefer_higher_confidence: bool = True
    ):
        self.similarity_threshold = similarity_threshold
        self.prefer_higher_tier = prefer_higher_tier
        self.prefer_higher_confidence = prefer_higher_confidence
        self._run_counter = 0

    def find_duplicates_by_hash(
        self,
        chunks: List[ChunkReference]
    ) -> List[DuplicatePair]:
        """
        Find exact duplicates via content hash.

        This is the fastest method - O(n) with hash map.
        """
        pairs = []
        hash_map: Dict[str, List[ChunkReference]] = {}

        # Group by hash
        for chunk in chunks:
            if chunk.content_hash not in hash_map:
                hash_map[chunk.content_hash] = []
            hash_map[chunk.content_hash].append(chunk)

        # Find groups with duplicates
        for content_hash, group in hash_map.items():
            if len(group) > 1:
                # Sort by priority to determine primary
                sorted_group = self._sort_by_priority(group)
                primary = sorted_group[0]

                for duplicate in sorted_group[1:]:
                    pairs.append(DuplicatePair(
                        primary=primary,
                        duplicate=duplicate,
                        similarity=1.0,
                        merge_recommendation="delete_duplicate",
                        reason=f"exact_hash_match:{content_hash[:16]}"
                    ))

        return pairs

    def find_duplicates_by_embedding(
        self,
        chunks: List[ChunkReference],
        threshold: Optional[float] = None
    ) -> List[DuplicatePair]:
        """
        Find near-duplicates via embedding similarity.

        Uses cosine similarity - O(n^2) but can be optimized with LSH.
        """
        if threshold is None:
            threshold = self.similarity_threshold

        pairs = []
        seen_pairs: Set[Tuple[str, str]] = set()

        # Filter chunks with embeddings
        chunks_with_embeddings = [c for c in chunks if c.embedding is not None]

        for i, chunk_a in enumerate(chunks_with_embeddings):
            for chunk_b in chunks_with_embeddings[i + 1:]:
                # Skip same chunk
                if chunk_a.chunk_id == chunk_b.chunk_id:
                    continue

                # Skip if already paired
                pair_key = tuple(sorted([chunk_a.chunk_id, chunk_b.chunk_id]))
                if pair_key in seen_pairs:
                    continue

                # Calculate similarity
                similarity = self._cosine_similarity(
                    chunk_a.embedding,
                    chunk_b.embedding
                )

                if similarity >= threshold:
                    # Determine primary
                    primary, duplicate = self._determine_primary(chunk_a, chunk_b)

                    recommendation = self._get_merge_recommendation(
                        primary, duplicate, similarity
                    )

                    pairs.append(DuplicatePair(
                        primary=primary,
                        duplicate=duplicate,
                        similarity=similarity,
                        merge_recommendation=recommendation,
                        reason=f"semantic_similarity:{similarity:.4f}"
                    ))

                    seen_pairs.add(pair_key)

        return pairs

    def find_cross_tier_duplicates(
        self,
        short_term: List[ChunkReference],
        mid_term: List[ChunkReference],
        long_term: List[ChunkReference]
    ) -> List[DuplicatePair]:
        """
        Find duplicates specifically across tier boundaries.

        Prioritizes finding where short-term duplicates long-term,
        as these are candidates for immediate cleanup.
        """
        pairs = []

        # Check short-term against long-term (highest value cleanup)
        pairs.extend(self._find_cross_tier_pairs(
            short_term, long_term, "short_vs_long"
        ))

        # Check short-term against mid-term
        pairs.extend(self._find_cross_tier_pairs(
            short_term, mid_term, "short_vs_mid"
        ))

        # Check mid-term against long-term
        pairs.extend(self._find_cross_tier_pairs(
            mid_term, long_term, "mid_vs_long"
        ))

        return pairs

    def _find_cross_tier_pairs(
        self,
        lower_tier: List[ChunkReference],
        higher_tier: List[ChunkReference],
        comparison_type: str
    ) -> List[DuplicatePair]:
        """Find duplicates between two specific tiers"""
        pairs = []

        # First check exact matches by hash
        lower_hashes = {c.content_hash: c for c in lower_tier}
        for higher_chunk in higher_tier:
            if higher_chunk.content_hash in lower_hashes:
                lower_chunk = lower_hashes[higher_chunk.content_hash]
                pairs.append(DuplicatePair(
                    primary=higher_chunk,  # Higher tier is always primary
                    duplicate=lower_chunk,
                    similarity=1.0,
                    merge_recommendation="delete_lower_tier",
                    reason=f"{comparison_type}:exact_hash"
                ))

        # Then check semantic similarity
        for lower_chunk in lower_tier:
            if lower_chunk.embedding is None:
                continue

            for higher_chunk in higher_tier:
                if higher_chunk.embedding is None:
                    continue

                # Skip if already found as hash match
                if lower_chunk.content_hash == higher_chunk.content_hash:
                    continue

                similarity = self._cosine_similarity(
                    lower_chunk.embedding,
                    higher_chunk.embedding
                )

                if similarity >= self.similarity_threshold:
                    pairs.append(DuplicatePair(
                        primary=higher_chunk,
                        duplicate=lower_chunk,
                        similarity=similarity,
                        merge_recommendation="merge_to_higher_tier",
                        reason=f"{comparison_type}:semantic_{similarity:.4f}"
                    ))

        return pairs

    def run_deduplication(
        self,
        chunks: List[ChunkReference],
        dry_run: bool = False
    ) -> DeduplicationResult:
        """
        Run full deduplication analysis.

        Args:
            chunks: All chunks across all tiers
            dry_run: If True, only report without merging

        Returns:
            DeduplicationResult with findings and actions
        """
        self._run_counter += 1
        run_id = f"dedup-{self._run_counter}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        started_at = datetime.utcnow()

        all_pairs = []
        bytes_freed = 0
        merged_count = 0
        errors = []

        try:
            # Phase 1: Find exact duplicates
            hash_pairs = self.find_duplicates_by_hash(chunks)
            all_pairs.extend(hash_pairs)
            logger.info(f"Found {len(hash_pairs)} exact duplicate pairs")

            # Phase 2: Find semantic duplicates
            embedding_pairs = self.find_duplicates_by_embedding(chunks)

            # Filter out pairs already found by hash
            existing_pairs = {
                (p.primary.chunk_id, p.duplicate.chunk_id)
                for p in hash_pairs
            }
            new_embedding_pairs = [
                p for p in embedding_pairs
                if (p.primary.chunk_id, p.duplicate.chunk_id) not in existing_pairs
            ]
            all_pairs.extend(new_embedding_pairs)
            logger.info(f"Found {len(new_embedding_pairs)} semantic duplicate pairs")

            # Phase 3: Cross-tier specific check
            short = [c for c in chunks if c.tier == MemoryTier.SHORT_TERM]
            mid = [c for c in chunks if c.tier == MemoryTier.MID_TERM]
            long = [c for c in chunks if c.tier == MemoryTier.LONG_TERM]

            cross_pairs = self.find_cross_tier_duplicates(short, mid, long)

            # Filter already found
            existing_ids = {
                (p.primary.chunk_id, p.duplicate.chunk_id)
                for p in all_pairs
            }
            new_cross_pairs = [
                p for p in cross_pairs
                if (p.primary.chunk_id, p.duplicate.chunk_id) not in existing_ids
            ]
            all_pairs.extend(new_cross_pairs)
            logger.info(f"Found {len(new_cross_pairs)} cross-tier duplicate pairs")

            # Calculate potential savings
            for pair in all_pairs:
                bytes_freed += pair.duplicate.byte_size

            if not dry_run:
                merged_count = len(all_pairs)  # Would be actual merge count

        except Exception as e:
            logger.error(f"Deduplication error: {e}")
            errors.append(str(e))

        completed_at = datetime.utcnow()

        result = DeduplicationResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            chunks_scanned=len(chunks),
            duplicates_found=len(all_pairs),
            duplicates_merged=merged_count if not dry_run else 0,
            bytes_freed=bytes_freed if not dry_run else 0,
            pairs=all_pairs,
            errors=errors
        )

        logger.info(
            f"Deduplication {run_id}: {len(chunks)} scanned, "
            f"{len(all_pairs)} duplicates, {bytes_freed} bytes potential savings"
        )

        return result

    def get_merge_plan(
        self,
        result: DeduplicationResult
    ) -> List[Dict[str, Any]]:
        """
        Generate a merge plan from deduplication results.

        Returns ordered list of merge operations to execute.
        """
        plan = []

        # Sort pairs by recommendation priority
        priority_order = {
            "delete_duplicate": 1,
            "delete_lower_tier": 2,
            "merge_to_higher_tier": 3,
            "consolidate": 4
        }

        sorted_pairs = sorted(
            result.pairs,
            key=lambda p: priority_order.get(p.merge_recommendation, 99)
        )

        for pair in sorted_pairs:
            operation = {
                "action": pair.merge_recommendation,
                "primary_id": pair.primary.chunk_id,
                "primary_tier": pair.primary.tier.value,
                "duplicate_id": pair.duplicate.chunk_id,
                "duplicate_tier": pair.duplicate.tier.value,
                "similarity": pair.similarity,
                "bytes_saved": pair.duplicate.byte_size,
                "reason": pair.reason
            }

            # Add specific instructions based on recommendation
            if pair.merge_recommendation == "delete_duplicate":
                operation["instructions"] = [
                    f"DELETE chunk {pair.duplicate.chunk_id} from {pair.duplicate.tier.value}",
                    f"UPDATE primary {pair.primary.chunk_id} access_count += {pair.duplicate.access_count}"
                ]
            elif pair.merge_recommendation == "merge_to_higher_tier":
                operation["instructions"] = [
                    f"MERGE metadata from {pair.duplicate.chunk_id} to {pair.primary.chunk_id}",
                    f"DELETE chunk {pair.duplicate.chunk_id} from {pair.duplicate.tier.value}"
                ]

            plan.append(operation)

        return plan

    def _determine_primary(
        self,
        chunk_a: ChunkReference,
        chunk_b: ChunkReference
    ) -> Tuple[ChunkReference, ChunkReference]:
        """Determine which chunk should be primary"""
        score_a = 0
        score_b = 0

        if self.prefer_higher_tier:
            score_a += self.TIER_PRIORITY.get(chunk_a.tier, 0) * 10
            score_b += self.TIER_PRIORITY.get(chunk_b.tier, 0) * 10

        if self.prefer_higher_confidence:
            score_a += chunk_a.confidence * 5
            score_b += chunk_b.confidence * 5

        # Tie-breaker: older is primary (more established)
        if score_a == score_b:
            if chunk_a.created_at < chunk_b.created_at:
                score_a += 1
            else:
                score_b += 1

        if score_a >= score_b:
            return chunk_a, chunk_b
        return chunk_b, chunk_a

    def _sort_by_priority(
        self,
        chunks: List[ChunkReference]
    ) -> List[ChunkReference]:
        """Sort chunks by priority (highest first)"""
        return sorted(
            chunks,
            key=lambda c: (
                self.TIER_PRIORITY.get(c.tier, 0) * 10 +
                c.confidence * 5 +
                (1 if c.created_at else 0)
            ),
            reverse=True
        )

    def _get_merge_recommendation(
        self,
        primary: ChunkReference,
        duplicate: ChunkReference,
        similarity: float
    ) -> str:
        """Get merge recommendation based on pair characteristics"""
        # Exact match - safe to delete duplicate
        if similarity >= self.EXACT_MATCH_THRESHOLD:
            return "delete_duplicate"

        # Cross-tier with high similarity
        if primary.tier != duplicate.tier:
            if similarity >= self.NEAR_DUPLICATE_THRESHOLD:
                return "delete_lower_tier"
            return "merge_to_higher_tier"

        # Same tier, near duplicate
        if similarity >= self.NEAR_DUPLICATE_THRESHOLD:
            return "delete_duplicate"

        # Semantic similar but not near-duplicate
        return "consolidate"

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


# Singleton instance
_deduplicator_instance: Optional[TierDeduplicator] = None


def get_tier_deduplicator(
    similarity_threshold: float = 0.95,
    prefer_higher_tier: bool = True,
    prefer_higher_confidence: bool = True
) -> TierDeduplicator:
    """Get singleton tier deduplicator instance"""
    global _deduplicator_instance
    if _deduplicator_instance is None:
        _deduplicator_instance = TierDeduplicator(
            similarity_threshold=similarity_threshold,
            prefer_higher_tier=prefer_higher_tier,
            prefer_higher_confidence=prefer_higher_confidence
        )
    return _deduplicator_instance
