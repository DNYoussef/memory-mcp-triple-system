"""
Integration tests for NexusProcessor 5-step SOP.
MEM-CLEAN-007: Core path verification.

Tests the unified search pipeline:
1. RECALL - Query all 3 tiers
2. FILTER - Confidence threshold (>0.3)
3. DEDUPE - Cosine similarity (>0.95)
4. RANK - Weighted scoring
5. COMPRESS - Mode-aware selection

NASA Rule 10 Compliant: All test methods <=60 LOC
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.nexus.processor import NexusProcessor
from src.nexus.processing_utils import ProcessingUtilsMixin
from src.nexus.tier_queries import TierQueryMixin


@pytest.fixture
def mock_vector_indexer():
    """Mock vector indexer with sample results."""
    indexer = MagicMock()
    indexer.search_similar.return_value = [
        {'id': 'v1', 'document': 'Vector result 1', 'distance': 0.1},
        {'id': 'v2', 'document': 'Vector result 2', 'distance': 0.2},
    ]
    return indexer


@pytest.fixture
def mock_graph_engine():
    """Mock graph query engine."""
    engine = MagicMock()
    engine.query.return_value = [
        {'id': 'g1', 'text': 'Graph result 1', 'score': 0.8},
        {'id': 'g2', 'text': 'Graph result 2', 'score': 0.6},
    ]
    return engine


@pytest.fixture
def mock_bayesian_engine():
    """Mock Bayesian inference engine."""
    engine = MagicMock()
    engine.query_conditional.return_value = {
        'result': [{'id': 'b1', 'text': 'Bayesian result', 'score': 0.7}]
    }
    return engine


@pytest.fixture
def mock_embedding_pipeline():
    """Mock embedding pipeline."""
    pipeline = MagicMock()
    pipeline.encode_single.return_value = MagicMock()
    pipeline.encode_single.return_value.tolist.return_value = [0.1] * 384
    return pipeline


class TestNexusProcessorInit:
    """Test NexusProcessor initialization."""

    def test_init_with_defaults(self):
        """Processor should initialize with default weights."""
        processor = NexusProcessor()
        assert processor.weights['vector'] == 0.4
        assert processor.weights['hipporag'] == 0.4
        assert processor.weights['bayesian'] == 0.2

    def test_init_with_custom_weights(self):
        """Processor should accept custom weights."""
        custom_weights = {'vector': 0.5, 'hipporag': 0.3, 'bayesian': 0.2}
        processor = NexusProcessor(weights=custom_weights)
        assert processor.weights == custom_weights

    def test_init_confidence_threshold(self):
        """Processor should use 0.3 default confidence threshold."""
        processor = NexusProcessor()
        assert processor.confidence_threshold == 0.3

    def test_init_dedup_threshold(self):
        """Processor should use 0.95 default dedup threshold."""
        processor = NexusProcessor()
        assert processor.dedup_threshold == 0.95


class TestRecallStep:
    """Test Step 1: RECALL."""

    def test_recall_queries_all_tiers(
        self, mock_vector_indexer, mock_graph_engine,
        mock_bayesian_engine, mock_embedding_pipeline
    ):
        """RECALL should query vector, graph, and bayesian tiers."""
        processor = NexusProcessor(
            vector_indexer=mock_vector_indexer,
            graph_query_engine=mock_graph_engine,
            probabilistic_query_engine=mock_bayesian_engine,
            embedding_pipeline=mock_embedding_pipeline
        )
        candidates = processor.recall("test query", top_k=10)
        # Should have candidates from multiple tiers
        assert len(candidates) > 0


class TestFilterStep:
    """Test Step 2: FILTER."""

    def test_filter_removes_low_confidence(self):
        """FILTER should remove candidates below threshold."""
        processor = NexusProcessor(confidence_threshold=0.3)
        candidates = [
            {'id': '1', 'score': 0.5, 'text': 'high'},
            {'id': '2', 'score': 0.2, 'text': 'low'},
            {'id': '3', 'score': 0.8, 'text': 'highest'},
        ]
        filtered = processor.filter_by_confidence(candidates)
        assert len(filtered) == 2
        assert all(c['score'] >= 0.3 for c in filtered)


class TestDeduplicateStep:
    """Test Step 3: DEDUPE."""

    def test_dedupe_removes_exact_duplicates(self):
        """DEDUPE should remove exact text matches."""
        processor = NexusProcessor()
        candidates = [
            {'id': '1', 'text': 'Same text content', 'score': 0.8},
            {'id': '2', 'text': 'Same text content', 'score': 0.7},
            {'id': '3', 'text': 'Different content', 'score': 0.6},
        ]
        deduped = processor.deduplicate(candidates)
        assert len(deduped) == 2

    def test_dedupe_keeps_unique_content(self):
        """DEDUPE should keep unique content."""
        processor = NexusProcessor()
        candidates = [
            {'id': '1', 'text': 'Content A', 'score': 0.8},
            {'id': '2', 'text': 'Content B', 'score': 0.7},
            {'id': '3', 'text': 'Content C', 'score': 0.6},
        ]
        deduped = processor.deduplicate(candidates)
        assert len(deduped) == 3


class TestRankStep:
    """Test Step 4: RANK."""

    def test_rank_sorts_by_hybrid_score(self):
        """RANK should sort by hybrid score descending."""
        processor = NexusProcessor()
        candidates = [
            {'id': '1', 'text': 'A', 'vector_score': 0.5, 'graph_score': 0.3, 'bayesian_score': 0.2},
            {'id': '2', 'text': 'B', 'vector_score': 0.9, 'graph_score': 0.8, 'bayesian_score': 0.7},
            {'id': '3', 'text': 'C', 'vector_score': 0.6, 'graph_score': 0.4, 'bayesian_score': 0.3},
        ]
        ranked = processor.rank(candidates)
        # Highest hybrid score should be first
        assert ranked[0]['id'] == '2'

    def test_rank_adds_hybrid_score(self):
        """RANK should add hybrid_score field."""
        processor = NexusProcessor()
        candidates = [{'id': '1', 'text': 'A', 'score': 0.5, 'tier': 'vector'}]
        ranked = processor.rank(candidates)
        assert 'hybrid_score' in ranked[0]


class TestCompressStep:
    """Test Step 5: COMPRESS."""

    def test_compress_returns_core_and_extended(self):
        """COMPRESS should return core and extended results."""
        processor = NexusProcessor()
        candidates = [{'id': str(i), 'text': f'Content {i}', 'score': 1.0 - i*0.1}
                      for i in range(20)]
        result = processor.compress(candidates, mode='execution', token_budget=10000)
        assert 'core' in result
        assert 'extended' in result
        assert len(result['core']) == 5  # Always 5 core

    def test_compress_mode_affects_extended_count(self):
        """COMPRESS should vary extended count by mode."""
        processor = NexusProcessor()
        candidates = [{'id': str(i), 'text': f'Content {i}', 'score': 1.0 - i*0.01}
                      for i in range(50)]

        exec_result = processor.compress(candidates, mode='execution', token_budget=10000)
        brain_result = processor.compress(candidates, mode='brainstorming', token_budget=20000)

        # Brainstorming should have more extended results
        assert len(brain_result['extended']) >= len(exec_result['extended'])


class TestFullPipeline:
    """Test complete 5-step pipeline."""

    def test_process_returns_expected_structure(self):
        """process() should return core, extended, and stats."""
        processor = NexusProcessor()
        result = processor.process(
            query="test query",
            mode="execution",
            top_k=10,
            token_budget=5000
        )
        assert 'core' in result
        assert 'extended' in result
        assert 'pipeline_stats' in result
        assert 'total_ms' in result
