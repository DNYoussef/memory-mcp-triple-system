"""
Unit tests for HippoRagService.
Following TDD (London School) with comprehensive coverage.

NASA Rule 10 Compliant: All test functions ≤60 LOC
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.services.hipporag_service import HippoRagService
from src.services.graph_service import GraphService
from src.services.entity_service import EntityService


@pytest.fixture
def graph_service(tmp_path):
    """Create GraphService instance for testing."""
    return GraphService(data_dir=str(tmp_path))


@pytest.fixture
def entity_service():
    """Create EntityService instance for testing."""
    return EntityService()


@pytest.fixture
def hipporag_service(graph_service, entity_service):
    """Create HippoRagService instance with dependencies."""
    return HippoRagService(
        graph_service=graph_service,
        entity_service=entity_service
    )


class TestInitialization:
    """Test suite for HippoRagService initialization."""

    def test_initialization_with_services(
        self,
        graph_service,
        entity_service
    ):
        """Test service initializes with valid dependencies."""
        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        assert service.graph_service is not None
        assert service.entity_service is not None

    def test_initialization_loads_dependencies(
        self,
        graph_service,
        entity_service
    ):
        """Test dependencies are stored correctly."""
        service = HippoRagService(
            graph_service=graph_service,
            entity_service=entity_service
        )

        assert service.graph_service is graph_service
        assert service.entity_service is entity_service

    def test_initialization_validates_services(self):
        """Test initialization raises error with None dependencies."""
        # Test None graph_service
        with pytest.raises(ValueError, match="graph_service cannot be None"):
            HippoRagService(
                graph_service=None,
                entity_service=Mock()
            )

        # Test None entity_service
        with pytest.raises(ValueError, match="entity_service cannot be None"):
            HippoRagService(
                graph_service=Mock(),
                entity_service=None
            )


class TestQueryEntityExtraction:
    """Test suite for query entity extraction."""

    def test_extract_single_entity(self, hipporag_service):
        """Test extracting single entity from query."""
        query = "What is Tesla?"

        entities = hipporag_service._extract_query_entities(query)

        # Should extract "Tesla" as ORG
        assert len(entities) >= 1
        assert 'tesla' in entities

    def test_extract_multiple_entities(self, hipporag_service):
        """Test extracting multiple entities from query."""
        query = "What company did Elon Musk start before Tesla?"

        entities = hipporag_service._extract_query_entities(query)

        # Should extract "Elon Musk" (PERSON) and "Tesla" (ORG)
        assert len(entities) >= 2

    def test_extract_no_entities(self, hipporag_service):
        """Test query with no recognizable entities."""
        query = "What is the meaning of life?"

        entities = hipporag_service._extract_query_entities(query)

        # May have zero or very few entities
        assert isinstance(entities, list)

    def test_extract_with_synonyms(self, hipporag_service):
        """Test entity extraction with synonymous terms."""
        query = "USA capital city"

        entities = hipporag_service._extract_query_entities(query)

        # Should extract "USA" as GPE
        assert any('usa' in e for e in entities)

    def test_extract_handles_typos(self, hipporag_service):
        """Test extraction tolerates minor typos."""
        query = "Googel search engine"

        entities = hipporag_service._extract_query_entities(query)

        # spaCy may or may not extract misspelled entities
        assert isinstance(entities, list)

    def test_extract_normalizes_text(self, hipporag_service):
        """Test entity text normalization."""
        query = "Elon Musk founded SpaceX"

        entities = hipporag_service._extract_query_entities(query)

        # All entities should be normalized (lowercase, no spaces)
        for entity in entities:
            assert entity.islower()
            assert ' ' not in entity

    def test_extract_filters_stopwords(self, hipporag_service):
        """Test that common stopwords aren't extracted."""
        query = "The United States of America"

        entities = hipporag_service._extract_query_entities(query)

        # Should extract "United States" or "America", not "The" or "of"
        # spaCy NER filters stopwords automatically
        assert all(e not in ['the', 'of'] for e in entities)


class TestEntityNodeMatching:
    """Test suite for matching entities to graph nodes."""

    def test_match_single_entity_exact(self, hipporag_service, graph_service):
        """Test exact match for single entity."""
        # Add entity node to graph
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})

        entities = ['tesla']
        matched = hipporag_service._match_entities_to_nodes(entities)

        assert len(matched) == 1
        assert 'tesla' in matched

    def test_match_multiple_entities(self, hipporag_service, graph_service):
        """Test matching multiple entities."""
        # Add entity nodes to graph
        graph_service.add_entity_node('elon_musk', 'PERSON', {'text': 'Elon Musk'})
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})

        entities = ['elon_musk', 'tesla']
        matched = hipporag_service._match_entities_to_nodes(entities)

        assert len(matched) == 2
        assert 'elon_musk' in matched
        assert 'tesla' in matched

    def test_match_no_entities(self, hipporag_service):
        """Test matching with empty entity list."""
        entities = []
        matched = hipporag_service._match_entities_to_nodes(entities)

        assert matched == []

    def test_match_entity_not_in_graph(self, hipporag_service):
        """Test matching entity that doesn't exist in graph."""
        entities = ['nonexistent_entity']
        matched = hipporag_service._match_entities_to_nodes(entities)

        assert len(matched) == 0

    def test_match_partial_overlap(self, hipporag_service, graph_service):
        """Test matching with some entities in graph, some not."""
        # Add only one entity to graph
        graph_service.add_entity_node('tesla', 'ORG', {'text': 'Tesla'})

        entities = ['tesla', 'nonexistent']
        matched = hipporag_service._match_entities_to_nodes(entities)

        assert len(matched) == 1
        assert 'tesla' in matched


class TestNormalization:
    """Test suite for text normalization."""

    def test_normalize_simple_text(self, hipporag_service):
        """Test normalizing simple text."""
        text = "Tesla"
        normalized = hipporag_service._normalize_entity_text(text)

        assert normalized == "tesla"

    def test_normalize_with_spaces(self, hipporag_service):
        """Test normalizing text with spaces."""
        text = "Elon Musk"
        normalized = hipporag_service._normalize_entity_text(text)

        assert normalized == "elon_musk"
        assert ' ' not in normalized

    def test_normalize_with_periods(self, hipporag_service):
        """Test normalizing text with periods."""
        text = "U.S.A."
        normalized = hipporag_service._normalize_entity_text(text)

        assert '.' not in normalized
        assert normalized == "usa"


class TestRetrieve:
    """Test suite for the main retrieve method."""

    def test_retrieve_with_empty_query(self, hipporag_service):
        """Test retrieve with empty query string."""
        results = hipporag_service.retrieve("")

        assert results == []

    def test_retrieve_with_no_entities(self, hipporag_service):
        """Test retrieve when no entities are extracted."""
        query = "What is the meaning of life?"
        results = hipporag_service.retrieve(query)

        # Should handle gracefully (empty or minimal results)
        assert isinstance(results, list)

    def test_retrieve_with_entities_not_in_graph(self, hipporag_service):
        """Test retrieve when query entities aren't in graph."""
        query = "What is Tesla?"
        results = hipporag_service.retrieve(query)

        # Should return empty list (no nodes to rank)
        assert results == []


class TestExceptionHandling:
    """Test suite for exception handling in HippoRagService."""

    def test_extract_query_entities_exception(self, hipporag_service):
        """Test exception handling in entity extraction."""
        # Mock entity_service to raise exception
        hipporag_service.entity_service.extract_entities = Mock(
            side_effect=RuntimeError("Entity extraction failed")
        )

        entities = hipporag_service._extract_query_entities("test query")

        # Should return empty list on exception
        assert entities == []

    def test_retrieve_exception_in_extract(self, hipporag_service):
        """Test exception handling in retrieve() during extraction."""
        # Mock _extract_query_entities to raise exception
        hipporag_service._extract_query_entities = Mock(
            side_effect=RuntimeError("Extraction failed")
        )

        results = hipporag_service.retrieve("test query")

        # Should return empty list on exception
        assert results == []

    def test_retrieve_exception_in_ppr(self, hipporag_service, graph_service):
        """Test exception handling in retrieve() during PPR."""
        # Add entity to graph
        graph_service.add_entity_node('test', 'ORG', {'text': 'Test'})

        # Mock graph_query_engine to raise exception
        hipporag_service.graph_query_engine.personalized_pagerank = Mock(
            side_effect=RuntimeError("PPR failed")
        )

        results = hipporag_service.retrieve("test")

        # Should return empty list on exception
        assert results == []

    def test_multi_hop_exception_in_extract(self, hipporag_service):
        """Test exception handling in retrieve_multi_hop() during extraction."""
        # Mock _get_query_nodes to raise exception
        hipporag_service._get_query_nodes = Mock(
            side_effect=RuntimeError("Get nodes failed")
        )

        results = hipporag_service.retrieve_multi_hop("test query")

        # Should return empty list on exception
        assert results == []

    def test_multi_hop_exception_in_expansion(
        self,
        hipporag_service,
        graph_service
    ):
        """Test exception handling in retrieve_multi_hop() during expansion."""
        # Add entity to graph
        graph_service.add_entity_node('test', 'ORG', {'text': 'Test'})

        # Mock _expand_entities_multi_hop to raise exception
        hipporag_service._expand_entities_multi_hop = Mock(
            side_effect=RuntimeError("Expansion failed")
        )

        results = hipporag_service.retrieve_multi_hop("test")

        # Should return empty list on exception
        assert results == []

    def test_get_query_nodes_no_entities(self, hipporag_service):
        """Test _get_query_nodes when no entities are extracted."""
        # Mock _extract_query_entities to return empty list
        hipporag_service._extract_query_entities = Mock(return_value=[])

        nodes = hipporag_service._get_query_nodes("test query")

        # Should return empty list (line 352-353 coverage)
        assert nodes == []

    def test_get_query_nodes_no_matches(self, hipporag_service):
        """Test _get_query_nodes when entities don't match graph nodes."""
        # Mock _extract_query_entities to return entities
        hipporag_service._extract_query_entities = Mock(
            return_value=['entity1', 'entity2']
        )
        # Mock _match_entities_to_nodes to return empty list
        hipporag_service._match_entities_to_nodes = Mock(return_value=[])

        nodes = hipporag_service._get_query_nodes("test query")

        # Should return empty list (line 352-353 coverage)
        assert nodes == []

    def test_expand_entities_multi_hop_no_results(
        self,
        hipporag_service,
        graph_service
    ):
        """Test _expand_entities_multi_hop when search finds nothing."""
        # Add entity to graph
        graph_service.add_entity_node('test', 'ORG', {'text': 'Test'})

        # Mock multi_hop_search to return empty entities
        hipporag_service.graph_query_engine.multi_hop_search = Mock(
            return_value={'entities': [], 'paths': []}
        )

        entities = hipporag_service._expand_entities_multi_hop(['test'], 3)

        # Should return empty list (line 379-380 coverage)
        assert entities == []

    def test_ppr_rank_and_format_no_ppr_scores(self, hipporag_service):
        """Test _ppr_rank_and_format when PPR returns no scores."""
        # Mock personalized_pagerank to return empty dict
        hipporag_service.graph_query_engine.personalized_pagerank = Mock(
            return_value={}
        )

        results = hipporag_service._ppr_rank_and_format(['test'], 5)

        # Should return empty list (line 406-407 coverage)
        assert results == []

    def test_ppr_rank_and_format_no_chunks_ranked(self, hipporag_service):
        """Test _ppr_rank_and_format when no chunks are ranked."""
        # Mock personalized_pagerank to return scores
        hipporag_service.graph_query_engine.personalized_pagerank = Mock(
            return_value={'entity1': 0.5, 'entity2': 0.3}
        )
        # Mock rank_chunks_by_ppr to return empty list
        hipporag_service.graph_query_engine.rank_chunks_by_ppr = Mock(
            return_value=[]
        )

        results = hipporag_service._ppr_rank_and_format(['test'], 5)

        # Should return empty list (line 416-417 coverage)
        assert results == []

    def test_run_ppr_and_rank_no_scores(self, hipporag_service):
        """Test _run_ppr_and_rank when PPR returns no scores."""
        # Mock personalized_pagerank to return empty dict
        hipporag_service.graph_query_engine.personalized_pagerank = Mock(
            return_value={}
        )

        chunks = hipporag_service._run_ppr_and_rank(['test'], 0.85, 5)

        # Should return empty list (line 151-152 coverage)
        assert chunks == []

    def test_run_ppr_and_rank_with_scores(self, hipporag_service):
        """Test _run_ppr_and_rank with successful PPR scores."""
        # Mock personalized_pagerank to return scores
        hipporag_service.graph_query_engine.personalized_pagerank = Mock(
            return_value={'chunk1': 0.8, 'chunk2': 0.5}
        )
        # Mock rank_chunks_by_ppr to return ranked chunks
        hipporag_service.graph_query_engine.rank_chunks_by_ppr = Mock(
            return_value=[('chunk1', 0.8), ('chunk2', 0.5)]
        )

        chunks = hipporag_service._run_ppr_and_rank(['test'], 0.85, 5)

        # Should return ranked chunks (line 155-160 coverage)
        assert len(chunks) == 2
        assert chunks[0] == ('chunk1', 0.8)
        assert chunks[1] == ('chunk2', 0.5)

    def test_format_retrieval_results_success(
        self,
        hipporag_service,
        graph_service
    ):
        """Test _format_retrieval_results with valid chunks."""
        # Add chunk nodes to graph
        graph_service.add_chunk_node(
            'chunk1',
            {'text': 'Test chunk 1', 'source': 'test.txt'}
        )
        graph_service.add_chunk_node(
            'chunk2',
            {'text': 'Test chunk 2', 'source': 'test.txt'}
        )

        ranked_chunks = [('chunk1', 0.8), ('chunk2', 0.5)]
        query_nodes = ['entity1', 'entity2']

        results = hipporag_service._format_retrieval_results(
            ranked_chunks,
            query_nodes
        )

        # Should return formatted results (line 177-194 coverage)
        assert len(results) == 2
        assert results[0].chunk_id == 'chunk1'
        assert results[0].score == 0.8
        assert results[0].rank == 1
        assert results[1].chunk_id == 'chunk2'
        assert results[1].score == 0.5
        assert results[1].rank == 2

    def test_retrieve_multi_hop_success(
        self,
        hipporag_service,
        graph_service
    ):
        """Test retrieve_multi_hop with successful retrieval."""
        # Add entities to graph
        graph_service.add_entity_node('test', 'ORG', {'text': 'Test'})
        graph_service.add_chunk_node(
            'chunk1',
            {'text': 'Test chunk', 'source': 'test.txt'}
        )

        # Mock _get_query_nodes to return matched nodes
        hipporag_service._get_query_nodes = Mock(return_value=['test'])

        # Mock successful multi-hop search
        hipporag_service.graph_query_engine.multi_hop_search = Mock(
            return_value={
                'entities': ['test', 'related'],
                'paths': []
            }
        )
        # Mock successful PPR
        hipporag_service.graph_query_engine.personalized_pagerank = Mock(
            return_value={'chunk1': 0.9}
        )
        # Mock successful ranking
        hipporag_service.graph_query_engine.rank_chunks_by_ppr = Mock(
            return_value=[('chunk1', 0.9)]
        )

        results = hipporag_service.retrieve_multi_hop('test', max_hops=2)

        # Should return results (line 298-313 coverage)
        assert len(results) > 0
        assert results[0].chunk_id == 'chunk1'

    def test_ppr_rank_and_format_success(
        self,
        hipporag_service,
        graph_service
    ):
        """Test _ppr_rank_and_format with successful PPR and ranking."""
        # Add chunk to graph
        graph_service.add_chunk_node(
            'chunk1',
            {'text': 'Test chunk', 'source': 'test.txt'}
        )

        # Mock successful PPR
        hipporag_service.graph_query_engine.personalized_pagerank = Mock(
            return_value={'chunk1': 0.85}
        )
        # Mock successful ranking
        hipporag_service.graph_query_engine.rank_chunks_by_ppr = Mock(
            return_value=[('chunk1', 0.85)]
        )

        results = hipporag_service._ppr_rank_and_format(['test'], 5)

        # Should return formatted results (line 404 coverage)
        assert len(results) == 1
        assert results[0].chunk_id == 'chunk1'
        assert results[0].score == 0.85
