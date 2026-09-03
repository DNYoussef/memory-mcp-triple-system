"""Integration tests for the live Cytoscape exporter."""

import networkx as nx
import pytest

from src.bridges.cytoscape_exporter import CytoscapeExporter, ConstellationGraphData


class TestCytoscapeExporter:
    """Tests for CytoscapeExporter integration with NetworkX."""

    @pytest.fixture
    def sample_graph(self) -> nx.DiGraph:
        """Create a sample NetworkX graph."""
        G = nx.DiGraph()
        G.add_node(
            "chunk-1",
            type="chunk",
            metadata={
                "ppr_score": 0.8,
                "decay_score": 0.9,
                "title": "Memory Architecture",
            },
        )
        G.add_node(
            "chunk-2",
            type="chunk",
            metadata={"ppr_score": 0.6, "decay_score": 0.7, "title": "Vector Search"},
        )
        G.add_node(
            "chunk-3",
            type="chunk",
            metadata={"ppr_score": 0.5, "decay_score": 0.4, "title": "Graph Traversal"},
        )
        G.add_edge("chunk-1", "chunk-2", type="REFERENCES")
        G.add_edge("chunk-1", "chunk-3", type="MENTIONS")
        G.add_edge("chunk-2", "chunk-3", type="RELATED_TO")
        return G

    def test_export_elements(self, sample_graph):
        """Test full graph export to Cytoscape format."""
        exporter = CytoscapeExporter(sample_graph)
        result = exporter.export_elements()

        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 3

    def test_export_subgraph(self, sample_graph):
        """Test subgraph export from a center node."""
        exporter = CytoscapeExporter(sample_graph)
        result = exporter.export_subgraph("chunk-1", depth=1)

        assert len(result["nodes"]) == 3  # chunk-1 and its neighbors
        assert len(result["edges"]) == 3  # all edges between included nodes

    def test_build_recursive_constellations(self, sample_graph):
        """Test constellation building algorithm."""
        exporter = CytoscapeExporter(sample_graph, max_depth=2)
        constellations = exporter.build_recursive_constellations("chunk-1")

        assert isinstance(constellations, ConstellationGraphData)
        assert len(constellations.constellations) >= 1
        assert "chunk-1" in constellations.all_node_ids

    def test_export_constellations(self, sample_graph):
        """Test constellation export to Cytoscape format."""
        exporter = CytoscapeExporter(sample_graph)
        result = exporter.export_constellations("chunk-1")

        assert "nodes" in result
        assert "edges" in result

        # Check constellation metadata on nodes
        center_node = next(n for n in result["nodes"] if n["data"]["id"] == "chunk-1")
        assert center_node["data"].get("isConstellationCenter") is True
