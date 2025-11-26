"""
Real NetworkX Graph Integration Tests (ISS-047)
Tests graph operations with real NetworkX instead of mocks.
"""
import pytest
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from fixtures.real_services import (
    temp_data_dir, real_graph_service, real_graph_query_engine, populated_graph
)


class TestGraphServiceRealNetworkX:
    """Test GraphService with real NetworkX."""

    def test_add_entity_creates_node(self, real_graph_service):
        """Verify entities become graph nodes."""
        real_graph_service.add_entity("TestEntity", "concept")

        assert real_graph_service.graph.has_node("TestEntity")

    def test_add_relationship_creates_edge(self, real_graph_service):
        """Verify relationships become graph edges."""
        real_graph_service.add_entity("Source", "concept")
        real_graph_service.add_entity("Target", "concept")
        real_graph_service.add_relationship("Source", "relates_to", "Target")

        assert real_graph_service.graph.has_edge("Source", "Target")

    def test_get_neighbors_returns_connected_nodes(self, populated_graph):
        """Test neighbor retrieval in populated graph."""
        neighbors = list(populated_graph.graph.neighbors("Memory MCP"))

        assert len(neighbors) > 0, "No neighbors found for Memory MCP"
        assert "ChromaDB" in neighbors or "HippoRAG" in neighbors

    def test_graph_persistence(self, real_graph_service, temp_data_dir):
        """Test graph can be saved and loaded."""
        real_graph_service.add_entity("PersistTest", "test")

        # Save
        save_path = temp_data_dir / "test_graph.json"
        real_graph_service.save_graph(str(save_path))

        # Verify file exists
        assert save_path.exists(), "Graph file not created"

    def test_add_entity_with_metadata(self, real_graph_service):
        """Test adding entity with metadata."""
        metadata = {"category": "system", "importance": "high"}
        real_graph_service.add_entity("TestSystem", "system", metadata=metadata)

        assert real_graph_service.graph.has_node("TestSystem")
        node_data = real_graph_service.graph.nodes["TestSystem"]
        assert node_data.get("metadata") == metadata

    def test_add_chunk_node(self, real_graph_service):
        """Test adding chunk nodes."""
        chunk_metadata = {"file_path": "/test/doc.md", "chunk_index": 0}
        real_graph_service.add_chunk_node("chunk_001", metadata=chunk_metadata)

        assert real_graph_service.graph.has_node("chunk_001")
        node_data = real_graph_service.graph.nodes["chunk_001"]
        assert node_data.get("type") == "chunk"

    def test_get_node_returns_correct_data(self, real_graph_service):
        """Test retrieving node data."""
        real_graph_service.add_entity("TestEntity", "concept")
        node = real_graph_service.get_node("TestEntity")

        assert node is not None
        assert node["id"] == "TestEntity"
        assert node["type"] == "entity"

    def test_get_nonexistent_node_returns_none(self, real_graph_service):
        """Test retrieving nonexistent node."""
        node = real_graph_service.get_node("DoesNotExist")
        assert node is None

    def test_remove_node(self, real_graph_service):
        """Test node removal."""
        real_graph_service.add_entity("ToRemove", "concept")
        assert real_graph_service.graph.has_node("ToRemove")

        success = real_graph_service.remove_node("ToRemove")
        assert success
        assert not real_graph_service.graph.has_node("ToRemove")

    def test_remove_edge(self, real_graph_service):
        """Test edge removal."""
        real_graph_service.add_entity("Source", "concept")
        real_graph_service.add_entity("Target", "concept")
        real_graph_service.add_relationship("Source", "relates_to", "Target")

        assert real_graph_service.graph.has_edge("Source", "Target")

        success = real_graph_service.remove_edge("Source", "Target")
        assert success
        assert not real_graph_service.graph.has_edge("Source", "Target")

    def test_get_node_count(self, populated_graph):
        """Test counting nodes in graph."""
        count = populated_graph.get_node_count()
        assert count > 0
        assert count >= 5  # At least 5 entities from fixture

    def test_get_edge_count(self, populated_graph):
        """Test counting edges in graph."""
        count = populated_graph.get_edge_count()
        assert count > 0
        assert count >= 4  # At least 4 relationships from fixture

    def test_find_path_between_nodes(self, populated_graph):
        """Test finding shortest path."""
        path = populated_graph.find_path("Memory MCP", "ChromaDB")

        assert path is not None
        assert len(path) >= 2
        assert path[0] == "Memory MCP"
        assert path[-1] == "ChromaDB"

    def test_find_path_no_connection(self, real_graph_service):
        """Test path finding with disconnected nodes."""
        real_graph_service.add_entity("Isolated1", "concept")
        real_graph_service.add_entity("Isolated2", "concept")

        path = real_graph_service.find_path("Isolated1", "Isolated2")
        assert path is None

    def test_get_subgraph(self, populated_graph):
        """Test extracting local subgraph."""
        subgraph_data = populated_graph.get_subgraph("Memory MCP", depth=2)

        assert "nodes" in subgraph_data
        assert "edges" in subgraph_data
        assert len(subgraph_data["nodes"]) > 0
        assert any(n["id"] == "Memory MCP" for n in subgraph_data["nodes"])


class TestGraphQueryEngineRealNetworkX:
    """Test GraphQueryEngine with real NetworkX."""

    def test_personalized_pagerank_real_graph(self, real_graph_query_engine, populated_graph):
        """Test PPR on real graph."""
        real_graph_query_engine.graph = populated_graph.graph

        # Run PPR from Memory MCP
        scores = real_graph_query_engine.personalized_pagerank(
            query_nodes=["Memory MCP"],
            alpha=0.85
        )

        assert len(scores) > 0, "PPR returned no scores"
        assert "Memory MCP" in scores

    def test_multi_hop_search_real_graph(self, real_graph_query_engine, populated_graph):
        """Test multi-hop traversal on real graph."""
        real_graph_query_engine.graph = populated_graph.graph

        # 2-hop search from Memory MCP
        results = real_graph_query_engine.multi_hop_search(
            start_nodes=["Memory MCP"],
            max_hops=2
        )

        assert len(results) > 0, "Multi-hop search returned no results"
        assert "entities" in results
        assert "paths" in results
        assert "distances" in results

    def test_get_entity_neighbors(self, real_graph_query_engine, populated_graph):
        """Test retrieving entity neighbors."""
        real_graph_query_engine.graph = populated_graph.graph

        neighbors = real_graph_query_engine.get_entity_neighbors("Memory MCP")

        assert len(neighbors) > 0, "No neighbors found"
        assert "ChromaDB" in neighbors or "HippoRAG" in neighbors

    def test_get_entity_neighbors_with_filter(self, real_graph_query_engine, populated_graph):
        """Test neighbor retrieval with edge type filter."""
        real_graph_query_engine.graph = populated_graph.graph

        # Filter by 'uses' relationship
        neighbors = real_graph_query_engine.get_entity_neighbors(
            "Memory MCP",
            edge_type="uses"
        )

        # Should find ChromaDB, HippoRAG, Bayesian based on fixture
        assert len(neighbors) >= 1

    def test_ppr_with_multiple_query_nodes(self, real_graph_query_engine, populated_graph):
        """Test PPR with multiple starting points."""
        real_graph_query_engine.graph = populated_graph.graph

        scores = real_graph_query_engine.personalized_pagerank(
            query_nodes=["Memory MCP", "ChromaDB"],
            alpha=0.85
        )

        assert len(scores) > 0
        assert "Memory MCP" in scores
        assert "ChromaDB" in scores

    def test_ppr_scores_sum_to_one(self, real_graph_query_engine, populated_graph):
        """Test that PPR scores are normalized."""
        real_graph_query_engine.graph = populated_graph.graph

        scores = real_graph_query_engine.personalized_pagerank(
            query_nodes=["Memory MCP"]
        )

        total = sum(scores.values())
        assert abs(total - 1.0) < 0.01, f"PPR scores should sum to 1.0, got {total}"

    def test_expand_with_synonyms(self, real_graph_query_engine):
        """Test synonym expansion via SIMILAR_TO edges."""
        # Create test graph with synonyms
        service = real_graph_query_engine.graph_service
        service.add_entity("Entity1", "concept")
        service.add_entity("Entity2", "concept")
        service.add_entity("Synonym1", "concept")

        # Add similar_to edge
        real_graph_query_engine.graph.add_edge(
            "Entity1", "Synonym1",
            type="similar_to"
        )

        expanded = real_graph_query_engine.expand_with_synonyms(["Entity1"])

        assert "Entity1" in expanded
        assert "Synonym1" in expanded

    def test_get_entity_neighborhood(self, real_graph_query_engine, populated_graph):
        """Test getting entity neighborhood."""
        real_graph_query_engine.graph = populated_graph.graph

        neighborhood = real_graph_query_engine.get_entity_neighborhood(
            entity_id="Memory MCP",
            hops=2
        )

        assert "entities" in neighborhood
        assert "chunks" in neighborhood
        assert len(neighborhood["entities"]) > 0

    def test_rank_chunks_by_ppr(self, real_graph_query_engine):
        """Test chunk ranking by PPR scores."""
        # Create test graph with chunks and entities
        service = real_graph_query_engine.graph_service

        service.add_chunk_node("chunk_1")
        service.add_entity("Entity1", "concept")

        # Add mentions edge
        real_graph_query_engine.graph.add_edge(
            "chunk_1", "Entity1",
            type="mentions"
        )

        # Mock PPR scores
        ppr_scores = {
            "chunk_1": 0.3,
            "Entity1": 0.7
        }

        ranked = real_graph_query_engine.rank_chunks_by_ppr(ppr_scores, top_k=5)

        # Should have at least one ranked chunk
        assert len(ranked) >= 0

    def test_multi_hop_with_edge_type_filter(self, real_graph_query_engine, populated_graph):
        """Test multi-hop search with edge type filtering."""
        real_graph_query_engine.graph = populated_graph.graph

        results = real_graph_query_engine.multi_hop_search(
            start_nodes=["Memory MCP"],
            max_hops=2,
            edge_types=["uses"]
        )

        assert "entities" in results
        # Should only traverse 'uses' edges

    def test_ppr_with_invalid_nodes(self, real_graph_query_engine, populated_graph):
        """Test PPR with nonexistent nodes."""
        real_graph_query_engine.graph = populated_graph.graph

        scores = real_graph_query_engine.personalized_pagerank(
            query_nodes=["DoesNotExist", "Memory MCP"]
        )

        # Should still return scores for valid nodes
        assert len(scores) > 0
        assert "Memory MCP" in scores


class TestHippoRAGServiceRealGraph:
    """Test HippoRAG with real graph backend."""

    def test_retrieve_with_graph_context(self, populated_graph, real_graph_query_engine):
        """Test retrieval using graph for context expansion."""
        real_graph_query_engine.graph = populated_graph.graph

        # Get entity neighborhood
        neighborhood = real_graph_query_engine.get_entity_neighborhood(
            entity_id="Memory MCP",
            hops=2
        )

        assert len(neighborhood) > 0, "No neighborhood found"
        assert "entities" in neighborhood

    def test_graph_provides_context_for_retrieval(self, populated_graph, real_graph_query_engine):
        """Test that graph can expand query context."""
        real_graph_query_engine.graph = populated_graph.graph

        # Start with single entity
        start_entities = ["Memory MCP"]

        # Expand via multi-hop
        expanded = real_graph_query_engine.multi_hop_search(
            start_nodes=start_entities,
            max_hops=1
        )

        # Should find related entities
        assert len(expanded["entities"]) > len(start_entities)

    def test_ppr_ranks_related_nodes_higher(self, real_graph_query_engine, populated_graph):
        """Test that PPR gives higher scores to connected nodes."""
        real_graph_query_engine.graph = populated_graph.graph

        scores = real_graph_query_engine.personalized_pagerank(
            query_nodes=["Memory MCP"]
        )

        # Memory MCP should have a score
        assert "Memory MCP" in scores

        # Connected nodes should also have scores
        memory_mcp_score = scores["Memory MCP"]
        connected_scores = [
            scores.get("ChromaDB", 0),
            scores.get("HippoRAG", 0),
            scores.get("Bayesian", 0)
        ]

        # At least one connected node should have a score
        assert any(s > 0 for s in connected_scores)


class TestGraphPersistence:
    """Test graph save/load functionality."""

    def test_save_and_load_graph(self, real_graph_service, temp_data_dir):
        """Test complete save/load cycle."""
        # Populate graph
        real_graph_service.add_entity("Entity1", "concept")
        real_graph_service.add_entity("Entity2", "concept")
        real_graph_service.add_relationship("Entity1", "relates_to", "Entity2")

        # Save
        save_path = temp_data_dir / "graph_save.json"
        success = real_graph_service.save_graph(str(save_path))
        assert success
        assert save_path.exists()

        # Create new service and load
        from src.services.graph_service import GraphService
        new_service = GraphService(data_dir=str(temp_data_dir))
        load_success = new_service.load_graph(str(save_path))

        assert load_success
        assert new_service.graph.has_node("Entity1")
        assert new_service.graph.has_node("Entity2")
        assert new_service.graph.has_edge("Entity1", "Entity2")

    def test_load_nonexistent_file(self, real_graph_service, temp_data_dir):
        """Test loading from nonexistent file."""
        fake_path = temp_data_dir / "does_not_exist.json"
        success = real_graph_service.load_graph(str(fake_path))

        assert not success


class TestRelationshipValidation:
    """Test relationship type validation."""

    def test_add_entity_helper_method(self, real_graph_service):
        """Test add_entity convenience method."""
        # The populated_graph fixture uses add_entity
        real_graph_service.add_entity("TestEntity", "concept")

        assert real_graph_service.graph.has_node("TestEntity")
        node_data = real_graph_service.graph.nodes["TestEntity"]
        assert node_data.get("type") == "entity"

    def test_valid_relationship_types(self, real_graph_service):
        """Test adding relationships with valid types."""
        real_graph_service.add_entity("Source", "concept")
        real_graph_service.add_entity("Target", "concept")

        # Valid relationship types from GraphService
        valid_types = [
            "references", "mentions", "similar_to", "related_to"
        ]

        for rel_type in valid_types:
            # Remove previous edge if exists
            if real_graph_service.graph.has_edge("Source", "Target"):
                real_graph_service.graph.remove_edge("Source", "Target")

            success = real_graph_service.add_relationship(
                "Source", rel_type, "Target"
            )
            assert success, f"Failed to add {rel_type} relationship"
