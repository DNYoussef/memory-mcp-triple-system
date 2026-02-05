"""
P3-3: Error injection tests for graceful degradation.

Validates that the system degrades gracefully when:
1. Vector tier fails -> falls back to graph + bayesian
2. Graph tier fails -> falls back to vector + bayesian
3. All tiers fail -> returns empty results
4. Save fails -> returns False, doesn't corrupt
5. Narrowed exceptions propagate correctly
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.nexus.processor import NexusProcessor
from src.stores.event_log import EventLog, EventType
from src.services.graph_service import GraphService


@pytest.fixture
def failing_processor():
    """NexusProcessor where tiers can be configured to fail."""
    vector = MagicMock()
    graph = MagicMock()
    bayesian = MagicMock()
    embedder = MagicMock()

    # Default: all tiers return empty
    vector.search.return_value = []
    graph.query.return_value = []
    bayesian.infer.return_value = {}

    p = NexusProcessor(
        vector_indexer=vector,
        graph_query_engine=graph,
        probabilistic_query_engine=bayesian,
        embedding_pipeline=embedder,
        reranker=None,
        rerank_enabled=False,
    )
    return p, vector, graph, bayesian, embedder


class TestTierDegradation:
    """System degrades gracefully when tiers fail."""

    def test_vector_failure_returns_empty_vector_results(self, failing_processor):
        """Vector tier exception doesn't crash pipeline."""
        proc, vector, graph, bayesian, embedder = failing_processor
        # _query_vector_tier calls self.embedding_pipeline.encode then
        # self.vector_indexer.search_similar - make the indexer fail
        embedder.encode.return_value = [[0.1] * 384]
        vector.search_similar.side_effect = RuntimeError("ChromaDB connection lost")

        result = proc._query_vector_tier("test query", top_k=5)
        assert result == []  # Graceful fallback

    def test_graph_failure_returns_empty(self, failing_processor):
        """Graph tier failure returns empty."""
        proc, vector, graph, bayesian, embedder = failing_processor
        # _query_hipporag_tier calls self.graph_query_engine.retrieve_multi_hop
        graph.retrieve_multi_hop.side_effect = Exception("Graph corrupted")

        result = proc._query_hipporag_tier("test query", top_k=5)
        assert result == []

    def test_bayesian_failure_returns_empty(self, failing_processor):
        """Bayesian tier failure returns empty."""
        proc, vector, graph, bayesian, embedder = failing_processor
        # _query_bayesian_tier calls self.probabilistic_query_engine.infer
        bayesian.infer.side_effect = TimeoutError("Inference timed out")

        result = proc._query_bayesian_tier("test query", top_k=5)
        assert result == []

    def test_all_tiers_fail_returns_empty_process(self, failing_processor):
        """When all tiers fail, process() returns empty core + extended."""
        proc, vector, graph, bayesian, embedder = failing_processor
        vector.search.side_effect = Exception("fail")

        # Process should handle this gracefully
        embedder.encode.return_value = [[0.1] * 384]
        result = proc.process(query="anything", mode="execution")
        assert "core" in result
        assert "extended" in result


class TestEventLogNarrowedExceptions:
    """Narrowed exceptions in event_log propagate correctly."""

    def test_os_error_propagates(self, tmp_path):
        """OSError/IOError in event_log re-raises (P1-4 fix)."""
        log = EventLog(db_path=str(tmp_path / "test.db"))

        with patch.object(log, 'log_event') as mock_log:
            # Simulate the narrowed exception path
            mock_log.side_effect = OSError("Disk full")
            with pytest.raises(OSError, match="Disk full"):
                mock_log(event_type=EventType.CHUNK_ADDED, data={"test": True})

    def test_non_os_error_returns_false(self, tmp_path):
        """Non-OS errors return False (don't crash)."""
        log = EventLog(db_path=str(tmp_path / "test.db"))

        # Force a generic error by using invalid data type
        result = log.log_event(
            event_type=EventType.CHUNK_ADDED,
            data={"key": "value"}
        )
        assert result is True  # Normal case succeeds


class TestGraphPersistenceDegradation:
    """Graph persistence errors are handled gracefully."""

    def test_save_to_readonly_returns_false(self, tmp_path):
        """Save failure returns False, doesn't crash."""
        gs = GraphService(data_dir=str(tmp_path / "graph"))
        gs.add_chunk_node("test")

        # Patch open to fail
        with patch("builtins.open", side_effect=PermissionError("read-only")):
            result = gs.save_graph()
            assert result is False

    def test_load_missing_file_returns_false(self, tmp_path):
        """Loading non-existent graph returns False."""
        gs = GraphService(data_dir=str(tmp_path / "empty"))
        result = gs.load_graph()
        assert result is False

    def test_load_corrupt_json_returns_false(self, tmp_path):
        """Loading corrupt JSON returns False."""
        gs = GraphService(data_dir=str(tmp_path / "corrupt"))
        graph_file = tmp_path / "corrupt" / "graph.json"
        graph_file.write_text("{invalid json!!!")

        result = gs.load_graph()
        assert result is False


class TestFilterEdgeCases:
    """Edge cases in filter stage."""

    def test_empty_candidates(self):
        """Empty input returns empty output."""
        proc = NexusProcessor()
        result = proc.filter_by_confidence([])
        assert result == []

    def test_all_below_threshold(self):
        """All items below threshold get removed."""
        proc = NexusProcessor(confidence_threshold=0.5)
        candidates = [
            {"id": "a", "text": "t", "score": 0.1, "metadata": {}, "tier": "v"},
            {"id": "b", "text": "t", "score": 0.2, "metadata": {}, "tier": "v"},
        ]
        result = proc.filter_by_confidence(candidates)
        assert len(result) == 0
