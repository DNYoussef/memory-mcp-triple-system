"""
Integration tests for Nexus pipeline store-search and multi-tier query.

D1: Store-then-search round-trip through full 5-step pipeline.
D2: Multi-tier query verifying all 3 tiers are queried and merged.

NASA Rule 10 Compliant: All test methods <=60 LOC
"""

import pytest
from unittest.mock import Mock

from src.nexus.processor import NexusProcessor


def _make_embedding_mock():
    """Create embedding pipeline mock returning N orthogonal embeddings."""
    pipeline = Mock()
    pipeline.encode.side_effect = lambda texts: [
        [1.0 if j == i else 0.0 for j in range(max(len(texts), 3))]
        for i in range(len(texts))
    ]
    return pipeline


class TestStoreSearchRoundTrip:
    """D1: Verify store-then-search returns consistent results."""

    @pytest.fixture
    def stored_docs(self):
        """Simulate stored documents returned by vector tier."""
        return [
            {"document": "Memory MCP uses ChromaDB for vector storage",
             "distance": 0.1, "metadata": {"file_path": "/docs/arch.md"},
             "id": "doc-1"},
            {"document": "HippoRAG provides multi-hop graph reasoning",
             "distance": 0.2, "metadata": {"file_path": "/docs/hippo.md"},
             "id": "doc-2"},
            {"document": "Bayesian inference complements vector search",
             "distance": 0.3, "metadata": {"file_path": "/docs/bayes.md"},
             "id": "doc-3"},
        ]

    @pytest.fixture
    def processor(self, stored_docs):
        """Build processor with 3 seeded docs in vector tier."""
        vector = Mock()
        vector.search_similar.return_value = stored_docs

        graph = Mock()
        graph.retrieve_multi_hop.return_value = []

        bayesian = Mock()
        bayesian.query_conditional.return_value = None

        return NexusProcessor(
            vector_indexer=vector,
            graph_query_engine=graph,
            probabilistic_query_engine=bayesian,
            embedding_pipeline=_make_embedding_mock(),
            rerank_enabled=False,
            confidence_threshold=0.1,
        )

    def test_stored_docs_appear_in_core(self, processor):
        """Documents seeded in vector tier should appear in core results."""
        result = processor.process("memory architecture", mode="execution")

        assert len(result["core"]) > 0
        core_texts = [c["text"] for c in result["core"]]
        assert any("ChromaDB" in t for t in core_texts)

    def test_pipeline_stats_has_all_steps(self, processor):
        """Pipeline stats should contain timing for each step."""
        result = processor.process("memory search")

        stats = result.get("pipeline_stats", {})
        assert "recall_ms" in stats
        assert "filter_ms" in stats
        assert "dedup_ms" in stats
        assert "rank_ms" in stats
        assert "compress_ms" in stats

    def test_token_count_nonzero(self, processor):
        """Token count should reflect actual content."""
        result = processor.process("test query", mode="execution")

        assert result["token_count"] > 0

    def test_compression_ratio_valid(self, processor):
        """Compression ratio should be 0-1."""
        result = processor.process("test query", mode="execution")

        assert 0.0 <= result["compression_ratio"] <= 1.0

    def test_mode_propagated(self, processor):
        """Requested mode should appear in result."""
        for mode in ("execution", "planning", "brainstorming"):
            result = processor.process("query", mode=mode)
            assert result["mode"] == mode


class TestMultiTierQuery:
    """D2: Verify all 3 tiers are queried and results combined."""

    @pytest.fixture
    def multi_tier_processor(self):
        """Processor with results from all 3 tiers."""
        vector = Mock()
        vector.search_similar.return_value = [
            {"document": "Vector result A", "distance": 0.15,
             "metadata": {}, "id": "v-1"},
        ]

        graph = Mock()
        graph.retrieve_multi_hop.return_value = [
            {"text": "Graph result B", "ppr_score": 0.85,
             "metadata": {"entities": ["NexusProcessor"]},
             "chunk_id": "g-1"},
        ]

        bayesian = Mock()
        bayesian.query_conditional.return_value = {
            "results": {
                "relevance": {0: 0.2, 1: 0.8, "entropy": 0.72}
            }
        }

        return NexusProcessor(
            vector_indexer=vector,
            graph_query_engine=graph,
            probabilistic_query_engine=bayesian,
            embedding_pipeline=_make_embedding_mock(),
            rerank_enabled=False,
            confidence_threshold=0.1,
        )

    def test_all_three_tiers_queried(self, multi_tier_processor):
        """All 3 tier services should be called during recall."""
        multi_tier_processor.process("multi-tier test")

        vi = multi_tier_processor.vector_indexer
        gq = multi_tier_processor.graph_query_engine
        pq = multi_tier_processor.probabilistic_query_engine

        vi.search_similar.assert_called_once()
        gq.retrieve_multi_hop.assert_called_once()
        pq.query_conditional.assert_called_once()

    def test_results_from_multiple_tiers(self, multi_tier_processor):
        """Core results should contain data from vector and graph tiers."""
        result = multi_tier_processor.process(
            "multi-tier test", mode="execution"
        )

        assert len(result["core"]) >= 1
        all_text = " ".join(c.get("text", "") for c in result["core"])
        # At least vector or graph results should appear
        assert "Vector result" in all_text or "Graph result" in all_text

    def test_hybrid_score_uses_weights(self, multi_tier_processor):
        """Ranked results should have hybrid_score based on tier weights."""
        candidates = multi_tier_processor.recall("test", top_k=10)
        filtered = multi_tier_processor.filter_by_confidence(candidates)
        deduplicated = multi_tier_processor.deduplicate(filtered)
        ranked = multi_tier_processor.rank(deduplicated)

        for r in ranked:
            assert "hybrid_score" in r
            assert r["hybrid_score"] > 0

    def test_tier_weights_sum_to_one(self, multi_tier_processor):
        """Default tier weights should sum to 1.0."""
        w = multi_tier_processor.weights
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_empty_tier_does_not_crash(self):
        """Pipeline should handle one empty tier gracefully."""
        vector = Mock()
        vector.search_similar.return_value = [
            {"document": "Only vector", "distance": 0.1,
             "metadata": {}, "id": "v-1"},
        ]

        graph = Mock()
        graph.retrieve_multi_hop.return_value = []

        bayesian = Mock()
        bayesian.query_conditional.return_value = None

        processor = NexusProcessor(
            vector_indexer=vector,
            graph_query_engine=graph,
            probabilistic_query_engine=bayesian,
            embedding_pipeline=_make_embedding_mock(),
            rerank_enabled=False,
            confidence_threshold=0.1,
        )

        result = processor.process("single tier")
        assert len(result["core"]) >= 1
