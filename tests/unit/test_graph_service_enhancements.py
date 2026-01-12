"""
Unit tests for GraphService enhancements (Week 5).
Tests for get_graph() method added for HippoRAG.

NASA Rule 10 Compliant: All test functions ≤60 LOC
"""

import pytest
import networkx as nx

from src.services.graph_service import GraphService


@pytest.fixture
def graph_service(tmp_path):
    """Create GraphService instance for testing."""
    return GraphService(data_dir=str(tmp_path))


class TestGetGraph:
    """Test suite for get_graph() method."""

    def test_get_graph_returns_valid_graph(self, graph_service):
        """Test get_graph() returns NetworkX DiGraph."""
        graph = graph_service.get_graph()

        assert graph is not None
        assert isinstance(graph, nx.DiGraph)

    def test_get_graph_returns_same_instance(self, graph_service):
        """Test get_graph() returns same graph instance."""
        graph1 = graph_service.get_graph()
        graph2 = graph_service.get_graph()

        assert graph1 is graph2

    def test_get_graph_allows_mutation(self, graph_service):
        """Test get_graph() allows direct graph manipulation."""
        # Add nodes via service
        graph_service.add_chunk_node('chunk_1', {'text': 'test'})

        # Get graph and verify nodes
        graph = graph_service.get_graph()

        assert 'chunk_1' in graph.nodes()
        assert len(graph.nodes()) == 1

    def test_get_graph_for_pagerank(self, graph_service):
        """Test get_graph() works with NetworkX PageRank."""
        # Build small graph
        graph_service.add_entity_node('entity_1', 'PERSON', {})
        graph_service.add_entity_node('entity_2', 'ORG', {})
        graph_service.add_relationship(
            'entity_1', 'entity_2', 'related_to', {}
        )

        # Get graph and run PageRank
        graph = graph_service.get_graph()
        ppr_scores = nx.pagerank(graph)

        assert ppr_scores is not None
        assert 'entity_1' in ppr_scores
        assert 'entity_2' in ppr_scores


def test_link_similar_entities_adds_edge(graph_service):
    """Ensure similar entities across components are linked."""
    graph_service.add_entity_node('entity_a', 'ORG', {'text': 'Alpha'})
    graph_service.add_entity_node('entity_b', 'ORG', {'text': 'Alpha'})

    class DummyEmbedder:
        def encode(self, texts):
            return [[1.0, 0.0] for _ in texts]

    links_added = graph_service.link_similar_entities(
        'entity_a',
        embedder=DummyEmbedder(),
        similarity_threshold=0.5,
        max_links=1
    )

    assert links_added == 1
    assert graph_service.graph.has_edge('entity_a', 'entity_b')
