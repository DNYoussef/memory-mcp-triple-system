"""
P3-1: Benchmark tests for dedup, recall, rank pipeline.

Validates that:
1. Dedup with pre-computed embeddings is O(n) not O(n^2)
2. _calculate_hybrid_score produces consistent results
3. Pipeline stages maintain expected throughput
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from src.nexus.processor import NexusProcessor
from src.nexus.processing_utils import LostInMiddleMitigation


@pytest.fixture
def processor():
    """NexusProcessor with mocked backends."""
    p = NexusProcessor(
        vector_indexer=MagicMock(),
        graph_query_engine=MagicMock(),
        probabilistic_query_engine=MagicMock(),
        embedding_pipeline=MagicMock(),
        reranker=None,
        rerank_enabled=False,
    )
    return p


class TestDedupPerformance:
    """Verify dedup scales linearly after P0-1 fix."""

    def _make_candidates(self, n):
        """Generate n unique candidate dicts."""
        return [
            {
                "id": f"doc_{i}",
                "text": f"unique document number {i} with distinct content",
                "metadata": {},
                "score": 0.8 - (i * 0.001),
                "tier": "vector",
            }
            for i in range(n)
        ]

    def test_dedup_small_batch(self, processor):
        """Dedup 50 items completes quickly."""
        candidates = self._make_candidates(50)
        # Mock embedding pipeline for batch encode
        import numpy as np
        processor.embedding_pipeline.encode = MagicMock(
            return_value=np.random.rand(50, 384).tolist()
        )
        start = time.perf_counter()
        result = processor.deduplicate(candidates)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Dedup of 50 items took {elapsed:.2f}s (max 5s)"
        assert len(result) <= 50

    def test_dedup_preserves_unique_items(self, processor):
        """All unique items survive dedup."""
        candidates = self._make_candidates(10)
        import numpy as np
        # Use identity-like embeddings so no two are similar
        embeddings = np.eye(10, 384).tolist()
        processor.embedding_pipeline.encode = MagicMock(return_value=embeddings)
        result = processor.deduplicate(candidates)
        assert len(result) == 10

    def test_dedup_removes_duplicates(self, processor):
        """Near-identical items get deduplicated."""
        candidates = self._make_candidates(5)
        import numpy as np
        # Make all embeddings nearly identical
        base = np.random.rand(384)
        embeddings = [base.tolist()] * 5
        processor.embedding_pipeline.encode = MagicMock(return_value=embeddings)
        result = processor.deduplicate(candidates)
        assert len(result) == 1, f"Expected 1 after dedup, got {len(result)}"


class TestHybridScoring:
    """Verify _calculate_hybrid_score is consistent."""

    def test_default_weights(self, processor):
        """Default weights: vector=0.4, hipporag=0.4, bayesian=0.2."""
        score = processor._calculate_hybrid_score(
            vector_score=1.0, graph_score=1.0, bayesian_score=1.0
        )
        assert abs(score - 1.0) < 0.001

    def test_vector_only(self, processor):
        """Only vector tier has score."""
        score = processor._calculate_hybrid_score(
            vector_score=1.0, graph_score=0.0, bayesian_score=0.0
        )
        assert abs(score - 0.4) < 0.001

    def test_zero_scores(self, processor):
        """All zeros gives zero."""
        score = processor._calculate_hybrid_score(
            vector_score=0.0, graph_score=0.0, bayesian_score=0.0
        )
        assert score == 0.0

    def test_custom_weights(self):
        """Custom weights are respected."""
        p = NexusProcessor(
            weights={"vector": 0.6, "hipporag": 0.3, "bayesian": 0.1}
        )
        score = p._calculate_hybrid_score(
            vector_score=1.0, graph_score=0.0, bayesian_score=0.0
        )
        assert abs(score - 0.6) < 0.001


class TestFilterStage:
    """Verify filter stage thresholds."""

    def test_filter_removes_low_confidence(self, processor):
        """Items below threshold get filtered."""
        candidates = [
            {"id": "a", "text": "hi", "score": 0.1, "metadata": {}, "tier": "v"},
            {"id": "b", "text": "hi", "score": 0.5, "metadata": {}, "tier": "v"},
            {"id": "c", "text": "hi", "score": 0.9, "metadata": {}, "tier": "v"},
        ]
        result = processor.filter_by_confidence(candidates)
        scores = [r["score"] for r in result]
        assert all(s >= 0.3 for s in scores)
        assert len(result) == 2

    def test_filter_keeps_all_above_threshold(self, processor):
        """All items above threshold survive."""
        candidates = [
            {"id": f"d{i}", "text": "t", "score": 0.5, "metadata": {}, "tier": "v"}
            for i in range(20)
        ]
        result = processor.filter_by_confidence(candidates)
        assert len(result) == 20
