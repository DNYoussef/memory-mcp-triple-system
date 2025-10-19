"""
Unit tests for GraphService.
Following TDD (London School) with comprehensive coverage.

NASA Rule 10 Compliant: All test functions ≤60 LOC
"""

import pytest
import json
from pathlib import Path

from src.services.graph_service import GraphService


@pytest.fixture
def graph_service(tmp_path):
    """Create GraphService with temporary data directory."""
    return GraphService(data_dir=str(tmp_path))


@pytest.fixture
def populated_graph(graph_service):
    """Create graph with sample data."""
    # Add chunk nodes
    graph_service.add_chunk_node('chunk1', {'text': 'First chunk'})
    graph_service.add_chunk_node('chunk2', {'text': 'Second chunk'})
    graph_service.add_chunk_node('chunk3', {'text': 'Third chunk'})

    # Add entity nodes
    graph_service.add_entity_node('obama', 'PERSON', {'name': 'Barack Obama'})
    graph_service.add_entity_node('whitehouse', 'ORG', {'name': 'White House'})
    graph_service.add_entity_node('usa', 'GPE', {'name': 'United States'})

    # Add relationships
    graph_service.add_relationship('chunk1', 'obama', GraphService.EDGE_MENTIONS)
    graph_service.add_relationship('chunk1', 'usa', GraphService.EDGE_MENTIONS)
    graph_service.add_relationship('chunk2', 'obama', GraphService.EDGE_MENTIONS)
    graph_service.add_relationship('chunk2', 'whitehouse', GraphService.EDGE_MENTIONS)
    graph_service.add_relationship('chunk1', 'chunk2', GraphService.EDGE_REFERENCES)

    return graph_service


class TestInitialization:
    """Test suite for GraphService initialization."""

    def test_initialization_creates_graph(self, tmp_path):
        """Test GraphService initializes with empty graph."""
        service = GraphService(data_dir=str(tmp_path))

        assert service.graph is not None
        assert service.get_node_count() == 0
        assert service.get_edge_count() == 0

    def test_initialization_creates_data_dir(self, tmp_path):
        """Test data directory is created."""
        data_dir = tmp_path / "test_data"
        service = GraphService(data_dir=str(data_dir))

        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_initialization_with_existing_dir(self, tmp_path):
        """Test initialization with existing directory."""
        data_dir = tmp_path / "existing"
        data_dir.mkdir()

        service = GraphService(data_dir=str(data_dir))

        assert service.data_dir == data_dir


class TestAddChunkNode:
    """Test suite for adding chunk nodes."""

    def test_add_chunk_node_success(self, graph_service):
        """Test adding chunk node."""
        success = graph_service.add_chunk_node('chunk1', {'text': 'Sample'})

        assert success is True
        assert graph_service.get_node_count() == 1

        node = graph_service.get_node('chunk1')
        assert node is not None
        assert node['type'] == GraphService.NODE_TYPE_CHUNK
        assert node['metadata']['text'] == 'Sample'

    def test_add_chunk_node_without_metadata(self, graph_service):
        """Test adding chunk without metadata."""
        success = graph_service.add_chunk_node('chunk1')

        assert success is True
        node = graph_service.get_node('chunk1')
        assert node['metadata'] == {}

    def test_add_chunk_node_duplicate(self, graph_service):
        """Test adding duplicate chunk overwrites."""
        graph_service.add_chunk_node('chunk1', {'version': 1})
        graph_service.add_chunk_node('chunk1', {'version': 2})

        assert graph_service.get_node_count() == 1
        node = graph_service.get_node('chunk1')
        assert node['metadata']['version'] == 2


class TestAddEntityNode:
    """Test suite for adding entity nodes."""

    def test_add_entity_node_person(self, graph_service):
        """Test adding PERSON entity."""
        success = graph_service.add_entity_node(
            'obama',
            'PERSON',
            {'name': 'Barack Obama'}
        )

        assert success is True
        node = graph_service.get_node('obama')
        assert node['type'] == GraphService.NODE_TYPE_ENTITY
        assert node['entity_type'] == 'PERSON'
        assert node['metadata']['name'] == 'Barack Obama'

    def test_add_entity_node_organization(self, graph_service):
        """Test adding ORG entity."""
        success = graph_service.add_entity_node(
            'google',
            'ORG',
            {'name': 'Google'}
        )

        assert success is True
        node = graph_service.get_node('google')
        assert node['entity_type'] == 'ORG'

    def test_add_entity_node_geopolitical(self, graph_service):
        """Test adding GPE entity."""
        success = graph_service.add_entity_node(
            'usa',
            'GPE',
            {'name': 'United States'}
        )

        assert success is True
        node = graph_service.get_node('usa')
        assert node['entity_type'] == 'GPE'

    def test_add_entity_node_without_metadata(self, graph_service):
        """Test adding entity without metadata."""
        success = graph_service.add_entity_node('entity1', 'PERSON')

        assert success is True
        node = graph_service.get_node('entity1')
        assert node['metadata'] == {}


class TestAddRelationship:
    """Test suite for adding relationships."""

    def test_add_relationship_mentions(self, graph_service):
        """Test adding mentions relationship."""
        graph_service.add_chunk_node('chunk1')
        graph_service.add_entity_node('obama', 'PERSON')

        success = graph_service.add_relationship(
            'chunk1',
            'obama',
            GraphService.EDGE_MENTIONS
        )

        assert success is True
        assert graph_service.get_edge_count() == 1

        neighbors = graph_service.get_neighbors('chunk1')
        assert 'obama' in neighbors

    def test_add_relationship_references(self, graph_service):
        """Test adding references relationship."""
        graph_service.add_chunk_node('chunk1')
        graph_service.add_chunk_node('chunk2')

        success = graph_service.add_relationship(
            'chunk1',
            'chunk2',
            GraphService.EDGE_REFERENCES
        )

        assert success is True

    def test_add_relationship_with_metadata(self, graph_service):
        """Test adding relationship with metadata."""
        graph_service.add_chunk_node('chunk1')
        graph_service.add_chunk_node('chunk2')

        success = graph_service.add_relationship(
            'chunk1',
            'chunk2',
            GraphService.EDGE_SIMILAR_TO,
            {'confidence': 0.95}
        )

        assert success is True

    def test_add_relationship_invalid_type(self, graph_service):
        """Test adding relationship with invalid type fails."""
        graph_service.add_chunk_node('chunk1')
        graph_service.add_chunk_node('chunk2')

        success = graph_service.add_relationship(
            'chunk1',
            'chunk2',
            'invalid_type'
        )

        assert success is False


class TestGetNeighbors:
    """Test suite for getting neighbors."""

    def test_get_neighbors_all(self, populated_graph):
        """Test getting all neighbors."""
        neighbors = populated_graph.get_neighbors('chunk1')

        assert len(neighbors) == 3
        assert 'obama' in neighbors
        assert 'usa' in neighbors
        assert 'chunk2' in neighbors

    def test_get_neighbors_filtered_by_type(self, populated_graph):
        """Test getting neighbors filtered by relationship type."""
        neighbors = populated_graph.get_neighbors(
            'chunk1',
            GraphService.EDGE_MENTIONS
        )

        assert len(neighbors) == 2
        assert 'obama' in neighbors
        assert 'usa' in neighbors
        assert 'chunk2' not in neighbors

    def test_get_neighbors_non_existent_node(self, graph_service):
        """Test getting neighbors of non-existent node."""
        neighbors = graph_service.get_neighbors('non_existent')

        assert neighbors == []

    def test_get_neighbors_empty(self, graph_service):
        """Test getting neighbors of isolated node."""
        graph_service.add_chunk_node('isolated')

        neighbors = graph_service.get_neighbors('isolated')

        assert neighbors == []


class TestFindPath:
    """Test suite for finding shortest paths."""

    def test_find_path_direct(self, populated_graph):
        """Test finding direct path."""
        path = populated_graph.find_path('chunk1', 'obama')

        assert path is not None
        assert len(path) == 2
        assert path[0] == 'chunk1'
        assert path[1] == 'obama'

    def test_find_path_indirect(self, populated_graph):
        """Test finding indirect path."""
        path = populated_graph.find_path('chunk1', 'whitehouse')

        assert path is not None
        assert len(path) == 3
        assert path[0] == 'chunk1'
        assert path[2] == 'whitehouse'

    def test_find_path_no_path(self, populated_graph):
        """Test finding path when none exists."""
        populated_graph.add_chunk_node('isolated')

        path = populated_graph.find_path('chunk1', 'isolated')

        assert path is None

    def test_find_path_non_existent_nodes(self, graph_service):
        """Test finding path with non-existent nodes."""
        path = graph_service.find_path('non_existent1', 'non_existent2')

        assert path is None


class TestGetSubgraph:
    """Test suite for getting subgraphs."""

    def test_get_subgraph_depth_1(self, populated_graph):
        """Test getting subgraph with depth 1."""
        subgraph = populated_graph.get_subgraph('chunk1', depth=1)

        assert len(subgraph['nodes']) >= 4
        assert len(subgraph['edges']) >= 3

        node_ids = [n['id'] for n in subgraph['nodes']]
        assert 'chunk1' in node_ids
        assert 'obama' in node_ids

    def test_get_subgraph_depth_2(self, populated_graph):
        """Test getting subgraph with depth 2."""
        subgraph = populated_graph.get_subgraph('chunk1', depth=2)

        assert len(subgraph['nodes']) >= 5

        node_ids = [n['id'] for n in subgraph['nodes']]
        assert 'chunk1' in node_ids
        assert 'chunk2' in node_ids

    def test_get_subgraph_non_existent_node(self, graph_service):
        """Test getting subgraph for non-existent node."""
        subgraph = graph_service.get_subgraph('non_existent')

        assert subgraph['nodes'] == []
        assert subgraph['edges'] == []

    def test_get_subgraph_isolated_node(self, graph_service):
        """Test getting subgraph for isolated node."""
        graph_service.add_chunk_node('isolated')

        subgraph = graph_service.get_subgraph('isolated', depth=1)

        assert len(subgraph['nodes']) == 1
        assert subgraph['nodes'][0]['id'] == 'isolated'
        assert len(subgraph['edges']) == 0


class TestPersistence:
    """Test suite for save/load operations."""

    def test_save_graph(self, populated_graph, tmp_path):
        """Test saving graph to JSON."""
        file_path = tmp_path / 'test_graph.json'

        success = populated_graph.save_graph(file_path)

        assert success is True
        assert file_path.exists()

        # Verify JSON content
        with open(file_path, 'r') as f:
            data = json.load(f)

        assert 'nodes' in data
        assert 'links' in data
        assert len(data['nodes']) == 6

    def test_save_graph_default_path(self, populated_graph):
        """Test saving graph to default location."""
        success = populated_graph.save_graph()

        assert success is True

        default_path = populated_graph.data_dir / 'graph.json'
        assert default_path.exists()

    def test_load_graph(self, populated_graph, tmp_path):
        """Test loading graph from JSON."""
        file_path = tmp_path / 'test_graph.json'

        # Save first
        populated_graph.save_graph(file_path)

        # Create new service and load
        new_service = GraphService(data_dir=str(tmp_path))
        success = new_service.load_graph(file_path)

        assert success is True
        assert new_service.get_node_count() == 6
        assert new_service.get_edge_count() == 5

    def test_load_graph_round_trip(self, populated_graph, tmp_path):
        """Test save/load preserves all data."""
        file_path = tmp_path / 'test_graph.json'

        # Save
        populated_graph.save_graph(file_path)

        # Load into new service
        new_service = GraphService(data_dir=str(tmp_path))
        new_service.load_graph(file_path)

        # Verify nodes
        obama_node = new_service.get_node('obama')
        assert obama_node is not None
        assert obama_node['entity_type'] == 'PERSON'

        # Verify edges
        neighbors = new_service.get_neighbors('chunk1', GraphService.EDGE_MENTIONS)
        assert len(neighbors) == 2

    def test_load_graph_non_existent_file(self, graph_service, tmp_path):
        """Test loading non-existent file."""
        file_path = tmp_path / 'non_existent.json'

        success = graph_service.load_graph(file_path)

        assert success is False


class TestNodeOperations:
    """Test suite for node operations."""

    def test_get_node_count(self, populated_graph):
        """Test getting node count."""
        count = populated_graph.get_node_count()

        assert count == 6

    def test_get_edge_count(self, populated_graph):
        """Test getting edge count."""
        count = populated_graph.get_edge_count()

        assert count == 5

    def test_remove_node(self, populated_graph):
        """Test removing node."""
        success = populated_graph.remove_node('chunk3')

        assert success is True
        assert populated_graph.get_node_count() == 5
        assert populated_graph.get_node('chunk3') is None

    def test_remove_node_non_existent(self, graph_service):
        """Test removing non-existent node."""
        success = graph_service.remove_node('non_existent')

        assert success is False

    def test_remove_edge(self, populated_graph):
        """Test removing edge."""
        success = populated_graph.remove_edge('chunk1', 'obama')

        assert success is True
        assert populated_graph.get_edge_count() == 4

        neighbors = populated_graph.get_neighbors('chunk1', GraphService.EDGE_MENTIONS)
        assert 'obama' not in neighbors

    def test_remove_edge_non_existent(self, graph_service):
        """Test removing non-existent edge."""
        success = graph_service.remove_edge('non_existent1', 'non_existent2')

        assert success is False
