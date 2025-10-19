"""
Unit tests for EntityService.
Following TDD (London School) with comprehensive coverage.

NASA Rule 10 Compliant: All test functions ≤60 LOC
"""

import pytest
from unittest.mock import MagicMock

from src.services.entity_service import EntityService
from src.services.graph_service import GraphService


@pytest.fixture
def entity_service():
    """Create EntityService instance."""
    return EntityService()


@pytest.fixture
def graph_service(tmp_path):
    """Create GraphService for integration testing."""
    return GraphService(data_dir=str(tmp_path))


class TestInitialization:
    """Test suite for EntityService initialization."""

    def test_initialization_loads_model(self):
        """Test EntityService loads spaCy model."""
        service = EntityService()

        assert service.nlp is not None
        assert service.nlp.lang == 'en'

    def test_initialization_with_custom_model(self):
        """Test initialization with specific model name."""
        service = EntityService(model_name='en_core_web_sm')

        assert service.nlp is not None


class TestExtractEntities:
    """Test suite for extracting entities."""

    def test_extract_entities_person(self, entity_service):
        """Test extracting PERSON entity."""
        text = "Barack Obama was the president."

        entities = entity_service.extract_entities(text)

        # Should extract "Barack Obama" as PERSON
        assert len(entities) > 0

        person_entities = [e for e in entities if e['type'] == 'PERSON']
        assert len(person_entities) >= 1
        assert any('Obama' in e['text'] for e in person_entities)

    def test_extract_entities_organization(self, entity_service):
        """Test extracting ORG entity."""
        text = "Google is a technology company."

        entities = entity_service.extract_entities(text)

        org_entities = [e for e in entities if e['type'] == 'ORG']
        assert len(org_entities) >= 1
        assert any('Google' in e['text'] for e in org_entities)

    def test_extract_entities_gpe(self, entity_service):
        """Test extracting GPE (geo-political) entity."""
        text = "United States is a country in North America."

        entities = entity_service.extract_entities(text)

        gpe_entities = [e for e in entities if e['type'] == 'GPE']
        assert len(gpe_entities) >= 1

    def test_extract_entities_date(self, entity_service):
        """Test extracting DATE entity."""
        text = "The meeting is on January 15, 2025."

        entities = entity_service.extract_entities(text)

        date_entities = [e for e in entities if e['type'] == 'DATE']
        assert len(date_entities) >= 1

    def test_extract_entities_empty_text(self, entity_service):
        """Test extracting from empty text."""
        entities = entity_service.extract_entities("")

        assert entities == []

    def test_extract_entities_no_entities(self, entity_service):
        """Test text with no entities."""
        text = "This is a simple sentence with no names."

        entities = entity_service.extract_entities(text)

        # May have no entities or just generic ones
        assert isinstance(entities, list)

    def test_extract_entities_includes_positions(self, entity_service):
        """Test entity positions are included."""
        text = "Barack Obama lives in Washington."

        entities = entity_service.extract_entities(text)

        # Check that entities have position info
        for ent in entities:
            assert 'start' in ent
            assert 'end' in ent
            assert 'text' in ent
            assert 'type' in ent


class TestExtractEntitiesByType:
    """Test suite for filtering entities by type."""

    def test_filter_person_only(self, entity_service):
        """Test filtering for PERSON entities only."""
        text = "Barack Obama works at Google in California."

        entities = entity_service.extract_entities_by_type(
            text,
            ['PERSON']
        )

        # Should only include PERSON entities
        assert all(e['type'] == 'PERSON' for e in entities)

    def test_filter_multiple_types(self, entity_service):
        """Test filtering for multiple entity types."""
        text = "Barack Obama founded the company in California on January 1, 2020."

        entities = entity_service.extract_entities_by_type(
            text,
            ['PERSON', 'DATE']
        )

        # Should only include PERSON and DATE
        types = {e['type'] for e in entities}
        assert types.issubset({'PERSON', 'DATE'})

    def test_filter_no_matches(self, entity_service):
        """Test filtering with no matching entities."""
        text = "Simple sentence with no names."

        entities = entity_service.extract_entities_by_type(
            text,
            ['PERSON']
        )

        # Should return empty list
        assert entities == []


class TestAddEntitiesToGraph:
    """Test suite for graph integration."""

    def test_add_entities_to_graph(self, entity_service, graph_service):
        """Test adding entities to graph."""
        graph_service.add_chunk_node('chunk1', {'text': 'Sample chunk'})

        text = "Barack Obama was the president."

        result = entity_service.add_entities_to_graph(
            'chunk1',
            text,
            graph_service
        )

        # Should add at least one entity
        assert result['entities_added'] > 0
        assert result['relationships_created'] > 0
        assert len(result['entity_types']) > 0

    def test_entities_added_as_nodes(self, entity_service, graph_service):
        """Test entities are added as graph nodes."""
        graph_service.add_chunk_node('chunk1')

        text = "Google is in California."

        entity_service.add_entities_to_graph('chunk1', text, graph_service)

        # Check graph has entity nodes
        assert graph_service.get_node_count() > 1

    def test_relationships_created(self, entity_service, graph_service):
        """Test mentions relationships are created."""
        graph_service.add_chunk_node('chunk1')

        text = "Barack Obama lives in Washington."

        entity_service.add_entities_to_graph('chunk1', text, graph_service)

        # Check relationships exist
        neighbors = graph_service.get_neighbors('chunk1', GraphService.EDGE_MENTIONS)
        assert len(neighbors) > 0

    def test_empty_text_no_entities(self, entity_service, graph_service):
        """Test empty text adds no entities."""
        graph_service.add_chunk_node('chunk1')

        result = entity_service.add_entities_to_graph('chunk1', '', graph_service)

        assert result['entities_added'] == 0
        assert result['relationships_created'] == 0


class TestGetEntityStats:
    """Test suite for entity statistics."""

    def test_entity_stats_counts(self, entity_service):
        """Test entity stats returns counts."""
        text = "Barack Obama and Joe Biden met in Washington on January 1, 2020."

        stats = entity_service.get_entity_stats(text)

        # Should have counts for different entity types
        assert isinstance(stats, dict)
        assert len(stats) > 0

        # Check some expected types
        if 'PERSON' in stats:
            assert stats['PERSON'] >= 1

    def test_entity_stats_empty_text(self, entity_service):
        """Test stats for empty text."""
        stats = entity_service.get_entity_stats("")

        assert stats == {}

    def test_entity_stats_multiple_same_type(self, entity_service):
        """Test stats counts multiple entities of same type."""
        text = "Barack Obama and Joe Biden are both former presidents."

        stats = entity_service.get_entity_stats(text)

        # Should count multiple PERSON entities
        if 'PERSON' in stats:
            assert stats['PERSON'] >= 2


class TestDeduplicateEntities:
    """Test suite for entity deduplication."""

    def test_deduplicate_removes_duplicates(self, entity_service):
        """Test deduplication removes exact duplicates."""
        entities = [
            {'text': 'Barack Obama', 'type': 'PERSON', 'start': 0, 'end': 12},
            {'text': 'Barack Obama', 'type': 'PERSON', 'start': 20, 'end': 32},
            {'text': 'Google', 'type': 'ORG', 'start': 40, 'end': 46}
        ]

        deduplicated = entity_service.deduplicate_entities(entities)

        assert len(deduplicated) == 2  # Two unique entities

    def test_deduplicate_preserves_unique(self, entity_service):
        """Test deduplication preserves unique entities."""
        entities = [
            {'text': 'Barack Obama', 'type': 'PERSON', 'start': 0, 'end': 12},
            {'text': 'Google', 'type': 'ORG', 'start': 20, 'end': 26}
        ]

        deduplicated = entity_service.deduplicate_entities(entities)

        assert len(deduplicated) == 2

    def test_deduplicate_empty_list(self, entity_service):
        """Test deduplication of empty list."""
        deduplicated = entity_service.deduplicate_entities([])

        assert deduplicated == []


class TestBatchExtract:
    """Test suite for batch entity extraction."""

    def test_batch_extract_multiple_texts(self, entity_service):
        """Test batch extraction from multiple texts."""
        texts = [
            "Barack Obama was president.",
            "Google is a technology company.",
            "The meeting is in California."
        ]

        results = entity_service.batch_extract_entities(texts)

        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)

    def test_batch_extract_empty_list(self, entity_service):
        """Test batch extraction with empty list."""
        results = entity_service.batch_extract_entities([])

        assert results == []

    def test_batch_extract_efficiency(self, entity_service):
        """Test batch extraction processes all texts."""
        texts = ["Barack Obama.", "Google.", "California."]

        results = entity_service.batch_extract_entities(texts)

        # Should have results for each text
        assert len(results) == len(texts)


class TestNormalizeEntityText:
    """Test suite for entity text normalization."""

    def test_normalize_lowercase(self, entity_service):
        """Test normalization converts to lowercase."""
        normalized = entity_service._normalize_entity_text("Barack Obama")

        assert normalized == "barack_obama"

    def test_normalize_removes_spaces(self, entity_service):
        """Test normalization removes spaces."""
        normalized = entity_service._normalize_entity_text("New York City")

        assert " " not in normalized
        assert normalized == "new_york_city"

    def test_normalize_removes_dots(self, entity_service):
        """Test normalization removes dots."""
        normalized = entity_service._normalize_entity_text("U.S.A.")

        assert "." not in normalized
        assert normalized == "usa"
