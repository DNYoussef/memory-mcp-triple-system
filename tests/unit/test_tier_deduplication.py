"""Regression tests for TierDeduplicator accounting honesty (MECE E5).

E5 ("fake dedup counts"): run_deduplication reported fabricated numbers. When
not dry_run it set duplicates_merged = len(all_pairs) (the count of CANDIDATES
found) and bytes_freed = the summed candidate byte sizes - even though the
method performs no merge/update/delete. TierDeduplicator holds no store; it only
finds duplicate pairs and (via get_merge_plan) plans the work. The fix reports
actual work honestly (duplicates_merged=0, bytes_freed=0) and exposes the
potential saving under a separate, honestly-named bytes_reclaimable field.

These tests pin both the no-duplicate accounting and the real-duplicate
accounting (a found candidate must never be reported as a merge).
"""

from datetime import datetime

import numpy as np

from src.memory.tier_deduplication import (
    ChunkReference,
    MemoryTier,
    TierDeduplicator,
)


def _chunk(chunk_id, content_hash, byte_size=100, tier=MemoryTier.SHORT_TERM):
    """Build a ChunkReference with no embedding (exercises the hash path; the
    embedding path skips None embeddings)."""
    return ChunkReference(
        chunk_id=chunk_id,
        tier=tier,
        content_hash=content_hash,
        embedding=None,
        confidence=0.9,
        created_at=datetime(2024, 1, 1),
        last_accessed=datetime(2024, 1, 1),
        access_count=1,
        byte_size=byte_size,
    )


class TestRunDeduplicationAccounting:
    """Accounting must reflect actual operations, not inferred candidates."""

    def test_no_duplicates_reports_zero(self):
        """No real duplicates -> nothing found, merged, or freed."""
        dedup = TierDeduplicator()
        chunks = [
            _chunk("a", "hash-a"),
            _chunk("b", "hash-b"),
            _chunk("c", "hash-c"),
        ]
        result = dedup.run_deduplication(chunks, dry_run=False)

        assert result.duplicates_found == 0
        assert result.duplicates_merged == 0
        assert result.bytes_freed == 0
        assert result.bytes_reclaimable == 0

    def test_real_duplicate_is_found_but_not_counted_as_merged(self):
        """A real duplicate candidate is FOUND, but run_deduplication performs no
        merge, so merged/freed stay 0 (not the old len(all_pairs) fabrication).
        The potential saving is reported separately as bytes_reclaimable."""
        dedup = TierDeduplicator()
        # Two same-hash chunks in the same tier -> exactly one exact-duplicate
        # pair from the hash phase; no embedding or cross-tier pairs.
        chunks = [
            _chunk("primary", "same-hash", byte_size=500),
            _chunk("dup", "same-hash", byte_size=500),
        ]
        result = dedup.run_deduplication(chunks, dry_run=False)

        # The candidate IS found...
        assert result.duplicates_found == 1
        # ...but nothing was actually merged or freed.
        assert result.duplicates_merged == 0, "candidates must not be reported as merged"
        assert result.bytes_freed == 0, "no merge executed -> no bytes actually freed"
        # The potential is preserved honestly (the duplicate's byte_size).
        assert result.bytes_reclaimable == 500

        # to_dict surfaces the honest accounting.
        d = result.to_dict()
        assert d["duplicates_merged"] == 0
        assert d["bytes_freed"] == 0
        assert d["bytes_reclaimable"] == 500

    def test_dry_run_matches_non_dry_run_accounting(self):
        """The method never executes merges, so dry_run must not change the
        merged/freed accounting - both report 0. The old code only zeroed these
        in dry_run, which masked the non-dry-run fabrication."""
        dedup = TierDeduplicator()
        chunks = [
            _chunk("primary", "same-hash", byte_size=300),
            _chunk("dup", "same-hash", byte_size=300),
        ]
        dry = dedup.run_deduplication(chunks, dry_run=True)
        wet = dedup.run_deduplication(chunks, dry_run=False)

        for r in (dry, wet):
            assert r.duplicates_found == 1
            assert r.duplicates_merged == 0
            assert r.bytes_freed == 0
            assert r.bytes_reclaimable == 300

    def test_same_pair_via_hash_and_embedding_counted_once(self):
        """The same two chunks can match BOTH the hash phase and the embedding
        phase with primary/duplicate SWAPPED (equal tier+confidence makes the
        hash sort a stable-order tie -> input order, while the embedding phase
        tie-breaks to older=primary). A directional pair-filter let both through
        -> duplicates_found==2 and bytes_reclaimable double-counted (111+222).
        The orientation-independent _pair_key counts the pair once."""
        emb = np.array([1.0, 0.0, 0.0])
        newer = ChunkReference(
            chunk_id="newer", tier=MemoryTier.SHORT_TERM, content_hash="same",
            embedding=emb, confidence=0.9, created_at=datetime(2024, 6, 1),
            last_accessed=datetime(2024, 6, 1), access_count=1, byte_size=222,
        )
        older = ChunkReference(
            chunk_id="older", tier=MemoryTier.SHORT_TERM, content_hash="same",
            embedding=emb, confidence=0.9, created_at=datetime(2024, 1, 1),
            last_accessed=datetime(2024, 1, 1), access_count=1, byte_size=111,
        )
        dedup = TierDeduplicator()
        # Input order [newer, older] makes the hash phase pick newer as primary
        # and the embedding phase pick older as primary - opposite orientations.
        result = dedup.run_deduplication([newer, older], dry_run=False)

        assert result.duplicates_found == 1, "the same two chunks were paired twice"
        assert len(result.pairs) == 1
        # Exactly one duplicate target's bytes, NOT the 111+222 double-count.
        assert result.bytes_reclaimable == result.pairs[0].duplicate.byte_size
        assert result.bytes_reclaimable < 333

    def test_cluster_of_three_counts_each_duplicate_target_once(self):
        """A cluster of THREE identical chunks yields multiple distinct pairs
        that can share one duplicate target (e.g. newest->middle and
        oldest->middle both name `middle`). Summing per pair double-counts
        `middle`'s bytes. bytes_reclaimable must sum each UNIQUE duplicate
        target once: a chunk reclaims its bytes once when removed, regardless of
        how many pairs nominate it. Repro before fix: found 3, reclaimable 555
        (middle counted twice); unique duplicate bytes are 333."""
        emb = np.array([1.0, 0.0, 0.0])
        newest = ChunkReference(
            chunk_id="newest", tier=MemoryTier.SHORT_TERM, content_hash="same",
            embedding=emb, confidence=0.9, created_at=datetime(2024, 6, 1),
            last_accessed=datetime(2024, 6, 1), access_count=1, byte_size=500,
        )
        middle = ChunkReference(
            chunk_id="middle", tier=MemoryTier.SHORT_TERM, content_hash="same",
            embedding=emb, confidence=0.9, created_at=datetime(2024, 3, 1),
            last_accessed=datetime(2024, 3, 1), access_count=1, byte_size=222,
        )
        oldest = ChunkReference(
            chunk_id="oldest", tier=MemoryTier.SHORT_TERM, content_hash="same",
            embedding=emb, confidence=0.9, created_at=datetime(2024, 1, 1),
            last_accessed=datetime(2024, 1, 1), access_count=1, byte_size=111,
        )
        dedup = TierDeduplicator()
        result = dedup.run_deduplication([newest, middle, oldest], dry_run=False)

        # bytes_reclaimable must equal the sum over UNIQUE duplicate targets,
        # never the naive per-pair sum (which would double-count `middle`).
        unique_duplicate_bytes = sum(
            {p.duplicate.chunk_id: p.duplicate.byte_size for p in result.pairs}.values()
        )
        naive_per_pair_bytes = sum(p.duplicate.byte_size for p in result.pairs)
        assert result.bytes_reclaimable == unique_duplicate_bytes
        assert result.bytes_reclaimable < naive_per_pair_bytes, (
            "a duplicate target shared by multiple pairs was counted more than once"
        )
        # Still no real merge happened.
        assert result.duplicates_merged == 0
        assert result.bytes_freed == 0
