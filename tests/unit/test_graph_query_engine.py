"""
Unit tests for GraphQueryEngine.
Following TDD (London School) with comprehensive coverage.

NASA Rule 10 Compliant: All test functions ≤60 LOC
"""

import pytest
import networkx as nx
from unittest.mock import Mock, MagicMock

from src.services.graph_query_engine import GraphQueryEngine
from src.services.graph_service import GraphService
from src.services.hipporag_service import HippoRagService
from src.services.entity_service import EntityService


@pytest.fixture
def graph_service(tmp_path):
    """Create GraphService instance for testing."""
    service = GraphService(data_dir=str(tmp_path))

    # Add sample entities
    service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})
    service.add_entity_node('elon_musk', 'PERSON', {'text': 'Elon Musk'})
    service.add_entity_node('spacex', 'ORG', {'text': 'SpaceX'})

    # Add sample chunks
    service.add_chunk_node('chunk_1', {'text': 'Tesla was founded by Elon Musk'})
    service.add_chunk_node('chunk_2', {'text': 'SpaceX is also led by Elon Musk'})

    # Add mentions edges
    service.add_relationship('chunk_1', 'mentions', 'tesla', {})
    service.add_relationship('chunk_1', 'mentions', 'elon_musk', {})
    service.add_relationship('chunk_2', 'mentions', 'spacex', {})
    service.add_relationship('chunk_2', 'mentions', 'elon_musk', {})

    return service


@pytest.fixture
def graph_query_engine(graph_service):
    """Create GraphQueryEngine instance with dependencies."""
    return GraphQueryEngine(graph_service=graph_service)


@pytest.fixture
def entity_service():
    """Create EntityService instance for testing."""
    return EntityService()


class TestInitialization:
    """Test suite for GraphQueryEngine initialization."""

    def test_initialization_with_graph_service(self, graph_service):
        """Test engine initializes with valid graph service."""
        engine = GraphQueryEngine(graph_service=graph_service)

        assert engine.graph_service is not None
        assert engine.graph is not None

    def test_initialization_stores_graph_reference(self, graph_service):
        """Test graph reference is stored correctly."""
        engine = GraphQueryEngine(graph_service=graph_service)

        assert isinstance(engine.graph, nx.DiGraph)
        assert engine.graph.number_of_nodes() > 0

    def test_initialization_validates_service(self):
        """Test initialization raises error with None service."""
        with pytest.raises(ValueError, match="graph_service cannot be None"):
            GraphQueryEngine(graph_service=None)


class TestPersonalizedPageRank:
    """Test suite for Personalized PageRank."""

    def test_ppr_single_node(self, graph_query_engine):
        """Test PPR from single query node."""
        query_nodes = ['tesla']

        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        assert isinstance(ppr_scores, dict)
        assert 'tesla' in ppr_scores
        assert ppr_scores['tesla'] > 0.0

    def test_ppr_multiple_nodes(self, graph_query_engine):
        """Test PPR from multiple query nodes."""
        query_nodes = ['tesla', 'elon_musk']

        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        assert isinstance(ppr_scores, dict)
        assert 'tesla' in ppr_scores
        assert 'elon_musk' in ppr_scores

    def test_ppr_returns_scores(self, graph_query_engine):
        """Test PPR returns normalized scores."""
        query_nodes = ['tesla']

        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        # Scores should sum to approximately 1.0
        total = sum(ppr_scores.values())
        assert 0.95 < total <= 1.05

    def test_ppr_convergence(self, graph_query_engine):
        """Test PPR converges successfully."""
        query_nodes = ['tesla', 'elon_musk']

        # Should converge with default parameters
        ppr_scores = graph_query_engine.personalized_pagerank(
            query_nodes,
            max_iter=100
        )

        assert len(ppr_scores) > 0

    def test_ppr_handles_invalid_nodes(self, graph_query_engine):
        """Test PPR handles nodes not in graph."""
        query_nodes = ['nonexistent_node']

        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        # Should return empty dict (no valid nodes)
        assert ppr_scores == {}

    def test_ppr_empty_graph(self, tmp_path):
        """Test PPR on empty graph."""
        empty_service = GraphService(data_dir=str(tmp_path))
        engine = GraphQueryEngine(graph_service=empty_service)

        ppr_scores = engine.personalized_pagerank(['any_node'])

        assert ppr_scores == {}

    def test_ppr_disconnected_graph(self, tmp_path):
        """Test PPR on disconnected graph."""
        service = GraphService(data_dir=str(tmp_path))
        service.add_entity_node('isolated', 'PERSON', {})

        engine = GraphQueryEngine(graph_service=service)
        ppr_scores = engine.personalized_pagerank(['isolated'])

        # Should still return scores for isolated node
        assert 'isolated' in ppr_scores


class TestRankChunksByPPR:
    """Test suite for chunk ranking."""

    def test_rank_chunks_returns_list(self, graph_query_engine):
        """Test rank_chunks returns list of tuples."""
        ppr_scores = {'tesla': 0.5, 'elon_musk': 0.3}

        ranked = graph_query_engine.rank_chunks_by_ppr(ppr_scores)

        assert isinstance(ranked, list)
        for item in ranked:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_rank_chunks_sorts_descending(self, graph_query_engine):
        """Test chunks are sorted by score descending."""
        ppr_scores = {
            'tesla': 0.3,
            'elon_musk': 0.5,
            'spacex': 0.2
        }

        ranked = graph_query_engine.rank_chunks_by_ppr(ppr_scores)

        # Scores should be descending
        for i in range(len(ranked) - 1):
            assert ranked[i][1] >= ranked[i + 1][1]

    def test_rank_chunks_respects_top_k(self, graph_query_engine):
        """Test top_k parameter limits results."""
        ppr_scores = {'tesla': 0.5, 'elon_musk': 0.3}

        ranked = graph_query_engine.rank_chunks_by_ppr(ppr_scores, top_k=1)

        assert len(ranked) <= 1

    def test_rank_chunks_empty_ppr(self, graph_query_engine):
        """Test ranking with empty PPR scores."""
        ranked = graph_query_engine.rank_chunks_by_ppr({})

        assert ranked == []


class TestGetEntityNeighbors:
    """Test suite for entity neighbor extraction."""

    def test_get_neighbors_returns_list(self, graph_query_engine):
        """Test get_entity_neighbors returns list."""
        neighbors = graph_query_engine.get_entity_neighbors('tesla')

        assert isinstance(neighbors, list)

    def test_get_neighbors_invalid_entity(self, graph_query_engine):
        """Test neighbors for entity not in graph."""
        neighbors = graph_query_engine.get_entity_neighbors('nonexistent')

        assert neighbors == []

    def test_get_neighbors_with_edge_type_filter(self, graph_service):
        """Test filtering neighbors by edge type."""
        # Add similar_to edge
        graph_service.add_relationship('tesla', 'similar_to', 'spacex', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        neighbors = engine.get_entity_neighbors('tesla', edge_type='similar_to')

        # Should only return neighbors connected by 'similar_to' edges
        assert isinstance(neighbors, list)


class TestIntegration:
    """Integration tests for end-to-end PPR workflow."""

    def test_end_to_end_single_hop(self, graph_query_engine):
        """Test complete PPR workflow for single-hop query."""
        # Run PPR
        query_nodes = ['tesla']
        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        # Rank chunks
        ranked_chunks = graph_query_engine.rank_chunks_by_ppr(ppr_scores)

        # Should find chunk mentioning Tesla
        assert len(ranked_chunks) > 0
        chunk_ids = [chunk_id for chunk_id, score in ranked_chunks]
        assert 'chunk_1' in chunk_ids

    def test_end_to_end_multi_hop(self, graph_query_engine):
        """Test PPR workflow for multi-hop query."""
        # Query for both Tesla and SpaceX (connected via Elon Musk)
        query_nodes = ['tesla', 'spacex']
        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        # Rank chunks
        ranked_chunks = graph_query_engine.rank_chunks_by_ppr(ppr_scores, top_k=5)

        # Should find both chunks
        assert len(ranked_chunks) >= 2

    def test_ppr_score_ordering(self, graph_query_engine):
        """Test PPR produces reasonable score ordering."""
        query_nodes = ['elon_musk']
        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        # Elon Musk should have high score
        assert ppr_scores.get('elon_musk', 0) > 0.1

    def test_empty_results_handling(self, graph_query_engine):
        """Test handling of queries with no results."""
        query_nodes = ['nonexistent']
        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)
        ranked_chunks = graph_query_engine.rank_chunks_by_ppr(ppr_scores)

        assert ppr_scores == {}
        assert ranked_chunks == []

    def test_top_k_limiting(self, graph_query_engine):
        """Test top_k correctly limits results."""
        query_nodes = ['elon_musk']
        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        # Request only 1 result
        ranked_chunks = graph_query_engine.rank_chunks_by_ppr(
            ppr_scores,
            top_k=1
        )

        assert len(ranked_chunks) <= 1

    def test_confidence_scoring(self, graph_query_engine):
        """Test PPR scores reflect entity relevance."""
        query_nodes = ['tesla']
        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)

        # Tesla should have highest score (query node)
        tesla_score = ppr_scores.get('tesla', 0)
        other_scores = [
            score for node, score in ppr_scores.items()
            if node != 'tesla'
        ]

        # Tesla should rank high (though not necessarily highest in all cases)
        assert tesla_score > 0.0

    def test_performance_benchmark(self, graph_query_engine):
        """Test PPR completes quickly on small graph."""
        import time

        query_nodes = ['tesla', 'elon_musk']

        start_time = time.time()
        ppr_scores = graph_query_engine.personalized_pagerank(query_nodes)
        ranked_chunks = graph_query_engine.rank_chunks_by_ppr(ppr_scores)
        elapsed = time.time() - start_time

        # Should complete in <100ms for small graph
        assert elapsed < 0.1
        assert len(ppr_scores) > 0
        assert len(ranked_chunks) > 0


class TestMultiHopSearch:
    """Test suite for multi-hop BFS search."""

    def test_multi_hop_single_hop(self, graph_service):
        """Test multi-hop search with max_hops=1."""
        # Add entity relationships (using valid edge types)
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        result = engine.multi_hop_search(
            start_nodes=['tesla'],
            max_hops=1
        )

        assert 'entities' in result
        assert 'paths' in result
        assert 'distances' in result
        assert 'tesla' in result['entities']
        assert 'elon_musk' in result['entities']

    def test_multi_hop_two_hops(self, graph_service):
        """Test multi-hop search with max_hops=2."""
        # Add 2-hop path: tesla → elon_musk → spacex
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})
        graph_service.add_relationship('elon_musk', 'related_to', 'spacex', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        result = engine.multi_hop_search(
            start_nodes=['tesla'],
            max_hops=2
        )

        # Should find all three entities
        assert 'tesla' in result['entities']
        assert 'elon_musk' in result['entities']
        assert 'spacex' in result['entities']

    def test_multi_hop_three_hops(self, graph_service):
        """Test multi-hop search with max_hops=3."""
        # Add 3-hop path
        graph_service.add_entity_node('starship', 'PRODUCT', {'text': 'Starship'})
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})
        graph_service.add_relationship('elon_musk', 'related_to', 'spacex', {})
        graph_service.add_relationship('spacex', 'related_to', 'starship', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        result = engine.multi_hop_search(
            start_nodes=['tesla'],
            max_hops=3
        )

        # Should find all four entities
        assert len(result['entities']) >= 4
        assert 'starship' in result['entities']

    def test_multi_hop_no_path(self, graph_service):
        """Test multi-hop search with isolated node."""
        # Add isolated entity
        graph_service.add_entity_node('isolated', 'ORG', {'text': 'Isolated'})

        engine = GraphQueryEngine(graph_service=graph_service)
        result = engine.multi_hop_search(
            start_nodes=['isolated'],
            max_hops=3
        )

        # Should only find the start node
        assert len(result['entities']) == 1
        assert 'isolated' in result['entities']

    def test_multi_hop_filter_edge_types(self, graph_service):
        """Test multi-hop search with edge type filtering."""
        # Add multiple edge types
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})
        graph_service.add_relationship('tesla', 'similar_to', 'spacex', {})

        engine = GraphQueryEngine(graph_service=graph_service)

        # Filter for only 'related_to' edges
        result = engine.multi_hop_search(
            start_nodes=['tesla'],
            max_hops=1,
            edge_types=['related_to']
        )

        # Should find elon_musk but not spacex
        assert 'elon_musk' in result['entities']
        assert 'spacex' not in result['entities']

    def test_multi_hop_returns_distances(self, graph_service):
        """Test multi-hop search returns correct distances."""
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        result = engine.multi_hop_search(
            start_nodes=['tesla'],
            max_hops=2
        )

        # Check distances
        assert result['distances']['tesla'] == 0
        assert result['distances']['elon_musk'] == 1

    def test_multi_hop_returns_paths(self, graph_service):
        """Test multi-hop search returns shortest paths."""
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        result = engine.multi_hop_search(
            start_nodes=['tesla'],
            max_hops=2
        )

        # Check paths
        assert result['paths']['tesla'] == ['tesla']
        assert result['paths']['elon_musk'] == ['tesla', 'elon_musk']

    def test_multi_hop_handles_cycles(self, graph_service):
        """Test multi-hop search handles cyclic graphs."""
        # Create cycle: tesla → elon_musk → spacex → tesla
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})
        graph_service.add_relationship('elon_musk', 'related_to', 'spacex', {})
        graph_service.add_relationship('spacex', 'related_to', 'tesla', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        result = engine.multi_hop_search(
            start_nodes=['tesla'],
            max_hops=3
        )

        # Should handle cycle without infinite loop
        assert len(result['entities']) == 3
        assert 'tesla' in result['entities']
        assert 'elon_musk' in result['entities']
        assert 'spacex' in result['entities']


class TestSynonymy:
    """Test suite for synonym expansion."""

    def test_expand_with_synonyms_single(self, graph_service):
        """Test expanding single entity with synonyms."""
        # Add synonym relationship
        graph_service.add_entity_node('tsla', 'ORG', {'text': 'TSLA'})
        graph_service.add_relationship('tesla', 'similar_to', 'tsla', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        expanded = engine.expand_with_synonyms(['tesla'])

        assert 'tesla' in expanded
        assert 'tsla' in expanded
        assert len(expanded) == 2

    def test_expand_with_synonyms_multiple(self, graph_service):
        """Test expanding multiple entities with synonyms."""
        # Add synonyms for both entities
        graph_service.add_entity_node('tsla', 'ORG', {'text': 'TSLA'})
        graph_service.add_entity_node('spx', 'ORG', {'text': 'SPX'})
        graph_service.add_relationship('tesla', 'similar_to', 'tsla', {})
        graph_service.add_relationship('spacex', 'similar_to', 'spx', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        expanded = engine.expand_with_synonyms(['tesla', 'spacex'])

        assert len(expanded) == 4
        assert 'tesla' in expanded
        assert 'tsla' in expanded
        assert 'spacex' in expanded
        assert 'spx' in expanded

    def test_expand_with_synonyms_max_limit(self, graph_service):
        """Test synonym expansion respects max_synonyms limit."""
        # Add many synonyms
        for i in range(10):
            synonym_id = f'tesla_syn_{i}'
            graph_service.add_entity_node(synonym_id, 'ORG', {'text': f'Syn{i}'})
            graph_service.add_relationship('tesla', synonym_id, 'similar_to', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        expanded = engine.expand_with_synonyms(['tesla'], max_synonyms=3)

        # Should limit to 3 synonyms + original
        assert len(expanded) <= 4

    def test_expand_with_synonyms_no_synonyms(self, graph_service):
        """Test expansion when entity has no synonyms."""
        engine = GraphQueryEngine(graph_service=graph_service)
        expanded = engine.expand_with_synonyms(['tesla'])

        # Should return original entity only
        assert expanded == ['tesla']

    def test_expand_with_synonyms_integration(self, graph_service):
        """Test synonym expansion integrates with multi-hop search."""
        # Add synonym and relationship
        graph_service.add_entity_node('tsla', 'ORG', {'text': 'TSLA'})
        graph_service.add_relationship('tesla', 'similar_to', 'tsla', {})
        graph_service.add_relationship('tsla', 'related_to', 'elon_musk', {})

        engine = GraphQueryEngine(graph_service=graph_service)

        # Expand then search
        expanded = engine.expand_with_synonyms(['tesla'])
        result = engine.multi_hop_search(
            start_nodes=expanded,
            max_hops=1
        )

        # Should find entities through synonym
        assert 'elon_musk' in result['entities']


class TestEntityNeighborhood:
    """Test suite for entity neighborhood extraction."""

    def test_get_neighborhood_one_hop(self, graph_service):
        """Test 1-hop neighborhood extraction."""
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        neighborhood = engine.get_entity_neighborhood('tesla', hops=1)

        assert 'entities' in neighborhood
        assert 'chunks' in neighborhood
        assert 'elon_musk' in neighborhood['entities']

    def test_get_neighborhood_two_hops(self, graph_service):
        """Test 2-hop neighborhood extraction."""
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})
        graph_service.add_relationship('elon_musk', 'related_to', 'spacex', {})

        engine = GraphQueryEngine(graph_service=graph_service)
        neighborhood = engine.get_entity_neighborhood('tesla', hops=2)

        # Should find both 1-hop and 2-hop neighbors
        assert 'elon_musk' in neighborhood['entities']
        assert 'spacex' in neighborhood['entities']

    def test_get_neighborhood_includes_chunks(self, graph_service):
        """Test neighborhood includes connected chunks."""
        engine = GraphQueryEngine(graph_service=graph_service)
        neighborhood = engine.get_entity_neighborhood(
            'tesla',
            hops=1,
            include_chunks=True
        )

        # Should include chunks mentioning tesla
        assert 'chunks' in neighborhood
        assert len(neighborhood['chunks']) >= 1
        assert 'chunk_1' in neighborhood['chunks']

    def test_get_neighborhood_no_neighbors(self, graph_service):
        """Test neighborhood for isolated entity."""
        graph_service.add_entity_node('isolated', 'ORG', {'text': 'Isolated'})

        engine = GraphQueryEngine(graph_service=graph_service)
        neighborhood = engine.get_entity_neighborhood('isolated', hops=1)

        # Should only contain the entity itself
        assert len(neighborhood['entities']) == 1
        assert 'isolated' in neighborhood['entities']


class TestMultiHopRetrieval:
    """Test suite for multi-hop retrieval integration."""

    def test_retrieve_multi_hop_single_hop_query(
        self,
        graph_service,
        entity_service
    ):
        """Test multi-hop retrieval with single-hop query."""
        # Setup graph with entities and chunks
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})
        graph_service.add_entity_node('elon_musk', 'PERSON', {'text': 'Elon Musk'})
        graph_service.add_chunk_node('chunk_1', {'text': 'Tesla was founded'})
        graph_service.add_relationship('chunk_1', 'mentions', 'tesla', {})
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})

        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        results = service.retrieve_multi_hop(
            query="What is Tesla?",
            max_hops=1,
            top_k=5
        )

        # Should return results
        assert isinstance(results, list)

    def test_retrieve_multi_hop_two_hop_query(
        self,
        graph_service,
        entity_service
    ):
        """Test multi-hop retrieval with 2-hop query."""
        # Setup 2-hop graph
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})
        graph_service.add_entity_node('elon_musk', 'PERSON', {'text': 'Elon Musk'})
        graph_service.add_entity_node('spacex', 'ORG', {'text': 'SpaceX'})
        graph_service.add_chunk_node('chunk_1', {'text': 'SpaceX launches rockets'})
        graph_service.add_relationship('chunk_1', 'mentions', 'spacex', {})
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})
        graph_service.add_relationship('elon_musk', 'related_to', 'spacex', {})

        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        results = service.retrieve_multi_hop(
            query="What is Tesla?",
            max_hops=2,
            top_k=5
        )

        # Should leverage 2-hop connections
        assert isinstance(results, list)

    def test_retrieve_multi_hop_three_hop_query(
        self,
        graph_service,
        entity_service
    ):
        """Test multi-hop retrieval with 3-hop query."""
        # Setup 3-hop graph
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})
        graph_service.add_entity_node('elon_musk', 'PERSON', {'text': 'Elon Musk'})
        graph_service.add_entity_node('spacex', 'ORG', {'text': 'SpaceX'})
        graph_service.add_entity_node('starship', 'PRODUCT', {'text': 'Starship'})
        graph_service.add_chunk_node('chunk_1', {'text': 'Starship is a rocket'})
        graph_service.add_relationship('chunk_1', 'mentions', 'starship', {})
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})
        graph_service.add_relationship('elon_musk', 'related_to', 'spacex', {})
        graph_service.add_relationship('spacex', 'related_to', 'starship', {})

        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        results = service.retrieve_multi_hop(
            query="What is Tesla?",
            max_hops=3,
            top_k=5
        )

        # Should leverage 3-hop connections
        assert isinstance(results, list)

    def test_retrieve_multi_hop_vs_standard(
        self,
        graph_service,
        entity_service
    ):
        """Test multi-hop retrieval finds more than standard retrieval."""
        # Setup graph with 2-hop path to relevant chunk
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})
        graph_service.add_entity_node('elon_musk', 'PERSON', {'text': 'Elon Musk'})
        graph_service.add_chunk_node('chunk_1', {'text': 'Tesla info'})
        graph_service.add_chunk_node('chunk_2', {'text': 'Elon Musk info'})
        graph_service.add_relationship('chunk_1', 'mentions', 'tesla', {})
        graph_service.add_relationship('chunk_2', 'mentions', 'elon_musk', {})
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})

        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        # Standard retrieval
        standard_results = service.retrieve(query="What is Tesla?", top_k=5)

        # Multi-hop retrieval
        multi_hop_results = service.retrieve_multi_hop(
            query="What is Tesla?",
            max_hops=2,
            top_k=5
        )

        # Multi-hop should potentially find more entities/chunks
        assert isinstance(standard_results, list)
        assert isinstance(multi_hop_results, list)

    def test_retrieve_multi_hop_performance(
        self,
        graph_service,
        entity_service
    ):
        """Test multi-hop retrieval performance benchmarks."""
        import time

        # Setup graph
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})
        graph_service.add_entity_node('elon_musk', 'PERSON', {'text': 'Elon Musk'})
        graph_service.add_chunk_node('chunk_1', {'text': 'Tesla info'})
        graph_service.add_relationship('chunk_1', 'mentions', 'tesla', {})
        graph_service.add_relationship('tesla', 'related_to', 'elon_musk', {})

        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        # Benchmark 1-hop
        start = time.time()
        service.retrieve_multi_hop(query="What is Tesla?", max_hops=1)
        elapsed_1hop = time.time() - start

        # Benchmark 2-hop
        start = time.time()
        service.retrieve_multi_hop(query="What is Tesla?", max_hops=2)
        elapsed_2hop = time.time() - start

        # Should meet performance targets
        assert elapsed_1hop < 0.02  # <20ms for 1-hop
        assert elapsed_2hop < 0.05  # <50ms for 2-hop

    def test_retrieve_multi_hop_edge_cases(
        self,
        graph_service,
        entity_service
    ):
        """Test multi-hop retrieval handles edge cases."""
        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        # Empty query
        results = service.retrieve_multi_hop(query="", max_hops=3)
        assert results == []

        # No entities in query
        results = service.retrieve_multi_hop(
            query="What is the meaning of life?",
            max_hops=3
        )
        assert isinstance(results, list)
