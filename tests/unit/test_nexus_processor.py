"""
Unit tests for Nexus Processor.

Tests the 5-step SOP pipeline:
1. Recall - Query all 3 tiers
2. Filter - Confidence threshold
3. Deduplicate - Cosine similarity
4. Rank - Weighted scoring
5. Compress - Curated core pattern
"""

import pytest
from unittest.mock import Mock, patch
from src.nexus.processor import NexusProcessor


class TestNexusProcessor:
    """Test suite for NexusProcessor class."""

    @pytest.fixture
    def mock_vector_indexer(self):
        """Mock VectorIndexer."""
        indexer = Mock()
        indexer.search_similar.return_value = [
            {
                "document": "Test chunk 1",
                "distance": 0.2,  # similarity = 0.8
                "metadata": {"file_path": "/docs/test1.md"},
                "id": "vec-1"
            },
            {
                "document": "Test chunk 2",
                "distance": 0.3,  # similarity = 0.7
                "metadata": {"file_path": "/docs/test2.md"},
                "id": "vec-2"
            }
        ]
        return indexer

    @pytest.fixture
    def mock_graph_query_engine(self):
        """Mock GraphQueryEngine."""
        engine = Mock()
        engine.retrieve_multi_hop.return_value = [
            {
                "text": "Graph chunk 1",
                "ppr_score": 0.9,
                "metadata": {"entities": ["entity1"]},
                "chunk_id": "graph-1"
            },
            {
                "text": "Graph chunk 2",
                "ppr_score": 0.6,
                "metadata": {"entities": ["entity2"]},
                "chunk_id": "graph-2"
            }
        ]
        return engine

    @pytest.fixture
    def mock_probabilistic_query_engine(self):
        """Mock ProbabilisticQueryEngine."""
        engine = Mock()
        engine.query_conditional.return_value = {
            "results": {
                "var1": {
                    0: 0.7,
                    1: 0.3,
                    "entropy": 0.88
                }
            }
        }
        return engine

    @pytest.fixture
    def mock_embedding_pipeline(self):
        """Mock EmbeddingPipeline."""
        pipeline = Mock()
        pipeline.encode.return_value = [[0.1, 0.2, 0.3]]  # Mock embedding
        return pipeline

    @pytest.fixture
    def processor(
        self,
        mock_vector_indexer,
        mock_graph_query_engine,
        mock_probabilistic_query_engine,
        mock_embedding_pipeline
    ):
        """Create NexusProcessor with mocked dependencies."""
        return NexusProcessor(
            vector_indexer=mock_vector_indexer,
            graph_query_engine=mock_graph_query_engine,
            probabilistic_query_engine=mock_probabilistic_query_engine,
            embedding_pipeline=mock_embedding_pipeline
        )

    def test_initialization(self, processor):
        """Test processor initialization."""
        assert processor.confidence_threshold == 0.3
        assert processor.dedup_threshold == 0.95
        assert processor.weights == {
            "vector": 0.4,
            "hipporag": 0.4,
            "bayesian": 0.2
        }

    def test_recall_from_all_tiers(self, processor):
        """Test recall queries all 3 tiers."""
        results = processor.recall("test query", top_k=10)

        # Should have results from vector + graph + bayesian
        assert len(results) > 0

        # Verify tiers represented
        tiers = set(r["tier"] for r in results)
        assert "vector" in tiers
        assert "hipporag" in tiers
        # Bayesian may be None (timeout), so optional

    def test_filter_low_confidence(self, processor):
        """Test filtering removes low confidence results."""
        candidates = [
            {"text": "chunk1", "score": 0.5, "tier": "vector"},
            {"text": "chunk2", "score": 0.2, "tier": "vector"},  # Below threshold
            {"text": "chunk3", "score": 0.4, "tier": "hipporag"},
            {"text": "chunk4", "score": 0.1, "tier": "hipporag"}  # Below threshold
        ]

        filtered = processor.filter_by_confidence(candidates)

        assert len(filtered) == 2  # 0.5 and 0.4 pass threshold
        assert all(r["score"] >= 0.3 for r in filtered)

    def test_deduplicate_similar_chunks(self, processor):
        """Test deduplication removes similar chunks (cosine >0.95)."""
        candidates = [
            {"text": "this is a test", "score": 0.8, "tier": "vector"},
            {"text": "this is a test", "score": 0.7, "tier": "hipporag"},  # Exact duplicate
            {"text": "completely different content", "score": 0.6, "tier": "vector"}
        ]

        deduplicated = processor.deduplicate(candidates)

        # Should keep first occurrence of duplicate
        assert len(deduplicated) == 2
        assert deduplicated[0]["text"] == "this is a test"
        assert deduplicated[1]["text"] == "completely different content"

    def test_rank_weighted_sum(self, processor):
        """Test ranking uses weighted sum (Vector 0.4 + HippoRAG 0.4 + Bayesian 0.2)."""
        candidates = [
            {"text": "vector chunk", "score": 0.8, "tier": "vector"},
            {"text": "graph chunk", "score": 0.9, "tier": "hipporag"},
            {"text": "bayesian chunk", "score": 0.5, "tier": "bayesian"}
        ]

        ranked = processor.rank(candidates)

        # Verify hybrid scores calculated correctly
        assert ranked[0]["hybrid_score"] == pytest.approx(0.9 * 0.4)  # HippoRAG: 0.36
        assert ranked[1]["hybrid_score"] == pytest.approx(0.8 * 0.4)  # Vector: 0.32
        assert ranked[2]["hybrid_score"] == pytest.approx(0.5 * 0.2)  # Bayesian: 0.10

        # Verify sorted by hybrid score (descending)
        assert ranked[0]["tier"] == "hipporag"
        assert ranked[1]["tier"] == "vector"
        assert ranked[2]["tier"] == "bayesian"

    def test_compress_execution_mode(self, processor):
        """Test compression in execution mode (5 core + 0 extended)."""
        ranked_results = [
            {"text": f"chunk {i}", "score": 1.0 - i * 0.1}
            for i in range(10)
        ]

        result = processor.compress(ranked_results, mode="execution", token_budget=10000)

        assert len(result["core"]) == 5
        assert len(result["extended"]) == 0
        assert result["mode"] == "execution"

    def test_compress_planning_mode(self, processor):
        """Test compression in planning mode (5 core + 15 extended)."""
        ranked_results = [
            {"text": f"chunk {i}", "score": 1.0 - i * 0.05}
            for i in range(30)
        ]

        result = processor.compress(ranked_results, mode="planning", token_budget=10000)

        assert len(result["core"]) == 5
        assert len(result["extended"]) == 15
        assert result["mode"] == "planning"

    def test_compress_brainstorming_mode(self, processor):
        """Test compression in brainstorming mode (5 core + 25 extended)."""
        ranked_results = [
            {"text": f"chunk {i}", "score": 1.0 - i * 0.03}
            for i in range(40)
        ]

        result = processor.compress(ranked_results, mode="brainstorming", token_budget=10000)

        assert len(result["core"]) == 5
        assert len(result["extended"]) == 25
        assert result["mode"] == "brainstorming"

    def test_token_budget_enforcement(self, processor):
        """Test token budget truncates extended results."""
        # Create chunks with known token counts (10 tokens each)
        ranked_results = [
            {"text": " ".join([f"word{j}" for j in range(10)]), "score": 1.0 - i * 0.05}
            for i in range(30)
        ]

        # Set token budget to allow only core (5 chunks * 10 tokens = 50 tokens)
        result = processor.compress(ranked_results, mode="planning", token_budget=60)

        # Core should always be included (50 tokens)
        assert len(result["core"]) == 5

        # Extended should be truncated to fit budget (10 tokens remaining = 1 chunk max)
        assert len(result["extended"]) <= 1
        assert result["token_count"] <= 60

    def test_empty_results(self, processor):
        """Test handling of empty results."""
        # Mock empty results from all tiers
        processor.vector_indexer.search_similar.return_value = []
        processor.graph_query_engine.retrieve_multi_hop.return_value = []
        processor.probabilistic_query_engine.query_conditional.return_value = None

        result = processor.process("test query")

        assert result["core"] == []
        assert result["extended"] == []
        assert result["token_count"] == 0

    def test_single_tier_results(self, processor):
        """Test when one tier returns empty."""
        # Mock graph tier returning empty
        processor.graph_query_engine.retrieve_multi_hop.return_value = []

        results = processor.recall("test query", top_k=10)

        # Should still have vector results
        assert len(results) > 0
        tiers = set(r["tier"] for r in results)
        assert "vector" in tiers

    def test_recall_performance(self, processor):
        """Test recall latency <500ms."""
        import time

        start = time.time()
        processor.recall("test query", top_k=50)
        elapsed = (time.time() - start) * 1000  # Convert to ms

        assert elapsed < 500, f"Recall took {elapsed:.0f}ms (expected <500ms)"

    def test_compression_ratio(self, processor):
        """Test compression ratio calculation."""
        ranked_results = [
            {"text": " ".join([f"word{j}" for j in range(100)]), "score": 0.9}
            for i in range(50)
        ]

        result = processor.compress(ranked_results, mode="execution", token_budget=10000)

        # Should calculate compression ratio
        assert "compression_ratio" in result
        assert 0.0 <= result["compression_ratio"] <= 1.0

    def test_mode_invalid(self, processor):
        """Test default to execution mode for invalid mode."""
        ranked_results = [
            {"text": f"chunk {i}", "score": 1.0}
            for i in range(10)
        ]

        result = processor.compress(ranked_results, mode="invalid_mode", token_budget=10000)

        # Should default to execution mode (5 core + 0 extended)
        assert len(result["core"]) == 5
        assert len(result["extended"]) == 0

    def test_duplicate_removal_threshold(self, processor):
        """Test cosine similarity threshold boundary (0.95)."""
        candidates = [
            {"text": "the quick brown fox jumps over the lazy dog", "score": 0.8, "tier": "vector"},
            {"text": "the quick brown fox jumps over", "score": 0.7, "tier": "hipporag"},  # Similar but <0.95
            {"text": "completely unrelated sentence here now", "score": 0.6, "tier": "vector"}
        ]

        deduplicated = processor.deduplicate(candidates)

        # All chunks should remain (similarity <0.95)
        assert len(deduplicated) == 3


def test_nasa_rule_10_compliance():
    """Test all methods ≤60 LOC."""
    import ast
    import inspect
    from src.nexus.processor import NexusProcessor

    # Get source code
    source = inspect.getsource(NexusProcessor)
    tree = ast.parse(source)

    # Find all methods
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Calculate LOC
            length = node.end_lineno - node.lineno + 1

            # Check NASA Rule 10 (≤60 LOC)
            assert length <= 60, (
                f"Method {node.name} has {length} LOC (violates NASA Rule 10: ≤60 LOC)"
            )
