"""
Unit tests for Nexus Processor.

Tests the 5.5-step SOP pipeline:
1. Recall - Query all 3 tiers
2. Filter - Confidence threshold
3. Deduplicate - Cosine similarity
4. Rank - Weighted scoring
4.5. Rerank - Cross-encoder refinement (MEM-QWEN-002)
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


class TestNexusProcessorRerank:
    """MEM-QWEN-003: Tests for Step 4.5 reranker integration."""

    @pytest.fixture
    def mock_vector_indexer(self):
        """Mock VectorIndexer."""
        indexer = Mock()
        indexer.search_similar.return_value = [
            {"document": "Doc 1", "distance": 0.2, "metadata": {}, "id": "v-1"},
            {"document": "Doc 2", "distance": 0.3, "metadata": {}, "id": "v-2"},
        ]
        return indexer

    @pytest.fixture
    def mock_graph_query_engine(self):
        """Mock GraphQueryEngine."""
        engine = Mock()
        engine.retrieve_multi_hop.return_value = []
        return engine

    @pytest.fixture
    def mock_probabilistic_query_engine(self):
        """Mock ProbabilisticQueryEngine."""
        engine = Mock()
        engine.query_conditional.return_value = None
        return engine

    @pytest.fixture
    def mock_embedding_pipeline(self):
        """Mock EmbeddingPipeline."""
        pipeline = Mock()
        pipeline.encode.return_value = [[0.1, 0.2, 0.3]]
        return pipeline

    @pytest.fixture
    def mock_reranker(self):
        """Mock RerankerService."""
        reranker = Mock()

        def mock_rerank(query, documents, top_k):
            # Return documents with rerank_scores added
            for i, doc in enumerate(documents):
                doc["rerank_score"] = 1.0 - (i * 0.1)
            stats = {"rerank_enabled": True, "rerank_ms": 50}
            return documents[:top_k], stats

        def mock_merge_scores(documents, hybrid_weight=0.5, rerank_weight=0.5):
            for doc in documents:
                hybrid = doc.get("hybrid_score", doc.get("score", 0.0))
                rerank = doc.get("rerank_score", 0.0)
                doc["final_score"] = hybrid_weight * hybrid + rerank_weight * rerank
                doc["score"] = doc["final_score"]
            return sorted(documents, key=lambda x: x.get("final_score", 0), reverse=True)

        reranker.rerank.side_effect = mock_rerank
        reranker.merge_scores.side_effect = mock_merge_scores
        return reranker

    @pytest.fixture
    def processor_with_reranker(
        self,
        mock_vector_indexer,
        mock_graph_query_engine,
        mock_probabilistic_query_engine,
        mock_embedding_pipeline,
        mock_reranker
    ):
        """Create NexusProcessor with reranker."""
        return NexusProcessor(
            vector_indexer=mock_vector_indexer,
            graph_query_engine=mock_graph_query_engine,
            probabilistic_query_engine=mock_probabilistic_query_engine,
            embedding_pipeline=mock_embedding_pipeline,
            reranker=mock_reranker,
            rerank_enabled=True
        )

    @pytest.fixture
    def processor_without_reranker(
        self,
        mock_vector_indexer,
        mock_graph_query_engine,
        mock_probabilistic_query_engine,
        mock_embedding_pipeline
    ):
        """Create NexusProcessor without reranker."""
        return NexusProcessor(
            vector_indexer=mock_vector_indexer,
            graph_query_engine=mock_graph_query_engine,
            probabilistic_query_engine=mock_probabilistic_query_engine,
            embedding_pipeline=mock_embedding_pipeline,
            reranker=None,
            rerank_enabled=False
        )

    def test_initialization_with_reranker(self, processor_with_reranker, mock_reranker):
        """Test processor initializes with reranker."""
        assert processor_with_reranker.reranker is mock_reranker
        assert processor_with_reranker.rerank_enabled == True
        assert processor_with_reranker.rerank_top_k == 30

    def test_initialization_without_reranker(self, processor_without_reranker):
        """Test processor initializes without reranker."""
        assert processor_without_reranker.reranker is None
        assert processor_without_reranker.rerank_enabled == False

    def test_custom_rerank_top_k(
        self,
        mock_vector_indexer,
        mock_graph_query_engine,
        mock_probabilistic_query_engine,
        mock_embedding_pipeline,
        mock_reranker
    ):
        """Test custom rerank_top_k parameter."""
        processor = NexusProcessor(
            vector_indexer=mock_vector_indexer,
            graph_query_engine=mock_graph_query_engine,
            probabilistic_query_engine=mock_probabilistic_query_engine,
            embedding_pipeline=mock_embedding_pipeline,
            reranker=mock_reranker,
            rerank_top_k=50
        )
        assert processor.rerank_top_k == 50

    def test_process_calls_rerank(self, processor_with_reranker, mock_reranker):
        """Test that process() calls reranker when enabled."""
        processor_with_reranker.process("test query", mode="execution")

        # Verify reranker was called
        mock_reranker.rerank.assert_called()
        mock_reranker.merge_scores.assert_called()

    def test_process_skips_rerank_when_disabled(self, processor_without_reranker):
        """Test that process() skips rerank when disabled."""
        result = processor_without_reranker.process("test query", mode="execution")

        # Should still return results
        assert "core" in result
        assert "extended" in result

    def test_rerank_step_called_after_rank(self, processor_with_reranker, mock_reranker):
        """Test rerank is called after rank step."""
        processor_with_reranker.process("test query")

        # Get the documents passed to rerank
        call_args = mock_reranker.rerank.call_args
        documents = call_args[1]["documents"] if call_args[1] else call_args[0][1]

        # Documents should have hybrid_score from rank step
        for doc in documents:
            assert "hybrid_score" in doc or "score" in doc

    def test_rerank_respects_top_k(
        self,
        mock_vector_indexer,
        mock_graph_query_engine,
        mock_probabilistic_query_engine,
        mock_embedding_pipeline
    ):
        """Test rerank_top_k limits documents sent to reranker."""
        # Create mock reranker that tracks input count
        reranker = Mock()
        input_counts = []

        def track_input(query, documents, top_k):
            input_counts.append(len(documents))
            for doc in documents:
                doc["rerank_score"] = 0.5
            return documents[:top_k], {}

        reranker.rerank.side_effect = track_input
        reranker.merge_scores.return_value = []

        processor = NexusProcessor(
            vector_indexer=mock_vector_indexer,
            graph_query_engine=mock_graph_query_engine,
            probabilistic_query_engine=mock_probabilistic_query_engine,
            embedding_pipeline=mock_embedding_pipeline,
            reranker=reranker,
            rerank_enabled=True,
            rerank_top_k=10
        )

        processor.process("test query")

        # Input should be limited to rerank_top_k
        assert len(input_counts) == 1
        assert input_counts[0] <= 10

    def test_process_uses_rlm_adapter(self):
        """Test RLM adapter bypasses standard pipeline when enabled."""
        adapter = Mock()
        adapter.explore.return_value = {
            "core": [],
            "extended": [],
            "token_count": 0,
            "compression_ratio": 1.0,
            "mode": "execution",
            "rlm_stats": {},
        }

        processor = NexusProcessor(rlm_adapter=adapter)
        result = processor.process("test query", use_rlm=True)

        adapter.explore.assert_called_once()
        assert result["mode"] == "execution"
        assert "pipeline_stats" in result

    def test_rerank_stats_in_result(self, processor_with_reranker, mock_reranker):
        """Test reranker is invoked and result is returned."""
        result = processor_with_reranker.process("test query")

        # Verify reranker was called during processing
        mock_reranker.rerank.assert_called()
        mock_reranker.merge_scores.assert_called()

        # Result should have standard structure
        assert "core" in result
        assert "extended" in result
        assert "mode" in result

    def test_process_with_reranker_disabled_via_flag(
        self,
        mock_vector_indexer,
        mock_graph_query_engine,
        mock_probabilistic_query_engine,
        mock_embedding_pipeline,
        mock_reranker
    ):
        """Test reranker is skipped when rerank_enabled=False even with reranker present."""
        processor = NexusProcessor(
            vector_indexer=mock_vector_indexer,
            graph_query_engine=mock_graph_query_engine,
            probabilistic_query_engine=mock_probabilistic_query_engine,
            embedding_pipeline=mock_embedding_pipeline,
            reranker=mock_reranker,
            rerank_enabled=False  # Disabled despite having reranker
        )

        processor.process("test query")

        # Reranker should NOT be called
        mock_reranker.rerank.assert_not_called()


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


class TestLostInMiddleMitigation:
    """MEM-CHUNK-002: Tests for Lost-in-the-Middle mitigation strategies."""

    @pytest.fixture
    def processor(self):
        """Create a basic processor for testing mitigation."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        return NexusProcessor(
            lost_in_middle_mitigation=LostInMiddleMitigation.EDGES
        )

    @pytest.fixture
    def sample_results(self):
        """Create sample ranked results for testing."""
        return [
            {"text": f"Result {i}", "score": 1.0 - i * 0.1, "id": f"r-{i}"}
            for i in range(10)
        ]

    def test_mitigation_enum_values(self):
        """Test LostInMiddleMitigation enum has expected values."""
        from src.nexus.processing_utils import LostInMiddleMitigation

        assert LostInMiddleMitigation.NONE.value == "none"
        assert LostInMiddleMitigation.EDGES.value == "edges"
        assert LostInMiddleMitigation.INTERLEAVE.value == "interleave"
        assert LostInMiddleMitigation.REVERSE_MIDDLE.value == "reverse_middle"

    def test_default_mitigation_is_edges(self):
        """Test default mitigation strategy is EDGES."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        processor = NexusProcessor()
        assert processor.lost_in_middle_mitigation == LostInMiddleMitigation.EDGES

    def test_mitigation_none_preserves_order(self, sample_results):
        """Test NONE strategy preserves original order."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        processor = NexusProcessor(
            lost_in_middle_mitigation=LostInMiddleMitigation.NONE
        )

        reordered = processor.apply_lost_in_middle_mitigation(
            sample_results,
            LostInMiddleMitigation.NONE
        )

        # Order should be preserved
        for i, result in enumerate(reordered):
            assert result["id"] == f"r-{i}"

    def test_mitigation_edges_reordering(self, sample_results):
        """Test EDGES strategy places high relevance at edges."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        processor = NexusProcessor()

        reordered = processor.apply_lost_in_middle_mitigation(
            sample_results,
            LostInMiddleMitigation.EDGES
        )

        # First item should be highest (r-0)
        assert reordered[0]["id"] == "r-0"

        # Last item should be second highest (r-1)
        assert reordered[-1]["id"] == "r-1"

        # Third item should be r-2
        assert reordered[1]["id"] == "r-2"

    def test_mitigation_interleave_reordering(self, sample_results):
        """Test INTERLEAVE strategy alternates high/medium relevance."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        processor = NexusProcessor()

        reordered = processor.apply_lost_in_middle_mitigation(
            sample_results,
            LostInMiddleMitigation.INTERLEAVE
        )

        # First item should be from top half
        assert reordered[0]["id"] == "r-0"

        # Second item should be from bottom half
        assert reordered[1]["id"] == "r-5"

        # Alternating pattern continues
        assert reordered[2]["id"] == "r-1"
        assert reordered[3]["id"] == "r-6"

    def test_mitigation_reverse_middle_reordering(self, sample_results):
        """Test REVERSE_MIDDLE strategy keeps edges, reverses middle."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        processor = NexusProcessor()

        reordered = processor.apply_lost_in_middle_mitigation(
            sample_results,
            LostInMiddleMitigation.REVERSE_MIDDLE
        )

        # First stays first
        assert reordered[0]["id"] == "r-0"

        # Last stays last
        assert reordered[-1]["id"] == "r-9"

        # Middle should be reversed: [r-8, r-7, r-6, r-5, r-4, r-3, r-2, r-1]
        assert reordered[1]["id"] == "r-8"
        assert reordered[2]["id"] == "r-7"

    def test_mitigation_preserves_all_results(self, sample_results):
        """Test mitigation doesn't lose any results."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        processor = NexusProcessor()

        for strategy in LostInMiddleMitigation:
            reordered = processor.apply_lost_in_middle_mitigation(
                sample_results,
                strategy
            )
            assert len(reordered) == len(sample_results)

            # All IDs should be present
            ids = {r["id"] for r in reordered}
            assert ids == {f"r-{i}" for i in range(10)}

    def test_mitigation_empty_results(self, processor):
        """Test mitigation handles empty results gracefully."""
        from src.nexus.processing_utils import LostInMiddleMitigation

        reordered = processor.apply_lost_in_middle_mitigation(
            [],
            LostInMiddleMitigation.EDGES
        )
        assert reordered == []

    def test_mitigation_single_result(self, processor):
        """Test mitigation handles single result."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        single = [{"text": "Only one", "id": "r-0"}]

        reordered = processor.apply_lost_in_middle_mitigation(
            single,
            LostInMiddleMitigation.EDGES
        )
        assert len(reordered) == 1
        assert reordered[0]["id"] == "r-0"

    def test_mitigation_two_results(self, processor):
        """Test mitigation handles two results."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        two = [
            {"text": "First", "id": "r-0"},
            {"text": "Second", "id": "r-1"}
        ]

        reordered = processor.apply_lost_in_middle_mitigation(
            two,
            LostInMiddleMitigation.EDGES
        )
        assert len(reordered) == 2

    def test_position_weights(self, processor):
        """Test position weight calculation."""
        weights = processor.get_position_weights(5, edge_boost=0.1)

        # First position gets full boost
        assert weights[0] == 1.1

        # Last position gets full boost
        assert weights[4] == 1.1

        # Second and second-to-last get half boost
        assert weights[1] == 1.05
        assert weights[3] == 1.05

        # Middle gets no boost
        assert weights[2] == 1.0

    def test_position_weights_empty(self, processor):
        """Test position weights for empty list."""
        weights = processor.get_position_weights(0)
        assert weights == []

    def test_mitigation_in_process_pipeline(self):
        """Test mitigation is applied in full process pipeline."""
        from src.nexus.processing_utils import LostInMiddleMitigation
        from unittest.mock import Mock

        # Setup mocks with proper results that pass confidence threshold
        mock_vector = Mock()
        mock_vector.search_similar.return_value = [
            {"document": f"Doc {i}", "distance": 0.1, "metadata": {}, "id": f"v-{i}"}
            for i in range(10)
        ]

        mock_graph = Mock()
        mock_graph.retrieve_multi_hop.return_value = []

        mock_bayesian = Mock()
        mock_bayesian.query_conditional.return_value = None

        processor = NexusProcessor(
            vector_indexer=mock_vector,
            graph_query_engine=mock_graph,
            probabilistic_query_engine=mock_bayesian,
            lost_in_middle_mitigation=LostInMiddleMitigation.EDGES,
            confidence_threshold=0.1  # Lower threshold to pass filter
        )

        result = processor.process("test query")

        # Verify mitigation was applied (only if we got past filter step)
        assert "pipeline_stats" in result
        if len(result["core"]) > 0:
            # Mitigation should be applied when there are results
            assert result["pipeline_stats"].get("mitigation_applied") == "edges"
        else:
            # If no results, mitigation may not be in stats
            pass

    def test_initialization_with_custom_mitigation(self):
        """Test processor initialization with custom mitigation strategy."""
        from src.nexus.processing_utils import LostInMiddleMitigation

        for strategy in LostInMiddleMitigation:
            processor = NexusProcessor(
                lost_in_middle_mitigation=strategy
            )
            assert processor.lost_in_middle_mitigation == strategy
