"""
Integration tests for Nexus-Properties components.

Tests the integration between:
- CytoscapeExporter (NEX-002)
- BidirectionalSyncEngine (NEX-003)
- FrontmatterMapper (NEX-004)
- PropertyInheritanceChain (NEX-005)
- DashboardGraphVisualizer (NEX-006)

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import pytest
from pathlib import Path
from typing import Dict, Any
import networkx as nx

# Module imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.bridges.cytoscape_exporter import (  # noqa: E402
    CytoscapeExporter,
    ConstellationGraphData,
)
from src.integrations.frontmatter_mapper import (  # noqa: E402
    FrontmatterMapper,
    FileRelationships,
)
from src.integrations.property_inheritance import PropertyInheritanceChain  # noqa: E402
from src.visualization.dashboard_graphs import (  # noqa: E402
    DashboardGraphVisualizer,
    GraphFormat,
    ViewType,
)


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


class TestFrontmatterMapper:
    """Tests for FrontmatterMapper integration."""

    @pytest.fixture
    def mapper(self) -> FrontmatterMapper:
        """Create a FrontmatterMapper instance."""
        return FrontmatterMapper()

    def test_extract_relationships_basic(self, mapper):
        """Test extracting relationships from frontmatter."""
        frontmatter = {
            "parents": ["[[Parent1]]", "[[Parent2]]"],
            "children": ["[[Child1]]"],
            "related": ["[[Related1]]", "[[Related2]]"],
        }
        result = mapper.extract_relationships("test.md", frontmatter)

        assert isinstance(result, FileRelationships)
        assert len(result.parents) == 2
        assert "Parent1" in result.parents
        assert len(result.children) == 1
        assert len(result.related) == 2

    def test_relationships_to_edges(self, mapper):
        """Test converting relationships to Memory MCP edges."""
        frontmatter = {
            "parents": ["[[Parent1]]"],
            "children": ["[[Child1]]"],
            "related": ["[[Related1]]"],
        }
        relationships = mapper.extract_relationships("test.md", frontmatter)
        edges = mapper.relationships_to_edges(relationships)

        assert len(edges) == 3
        assert all("source" in e and "target" in e and "type" in e for e in edges)

    def test_metadata_to_frontmatter(self, mapper):
        """Test converting Memory MCP metadata to frontmatter."""
        metadata = {
            "WHO": {"name": "Claude", "category": "agent"},
            "WHEN": {"iso": "2026-01-19T10:00:00Z", "readable": "Today"},
            "PROJECT": "memory-mcp",
            "WHY": "implementation",
            "title": "Test Note",
        }
        result = mapper.metadata_to_frontmatter(metadata)

        assert result.get("who") == "Claude"
        assert "2026-01-19" in result.get("updated", "")
        assert result.get("project") == "memory-mcp"
        assert result.get("title") == "Test Note"

    def test_frontmatter_to_metadata(self, mapper):
        """Test converting frontmatter to Memory MCP metadata."""
        frontmatter = {
            "who": "David",
            "updated": "2026-01-19",
            "project": "life-os",
            "why": "research",
            "title": "Research Notes",
            "tags": ["memory", "graph"],
        }
        result = mapper.frontmatter_to_metadata(frontmatter)

        assert result.get("WHO") == {"name": "David", "category": "obsidian"}
        assert result.get("PROJECT") == "life-os"
        assert result.get("title") == "Research Notes"
        assert result.get("tags") == ["memory", "graph"]

    def test_compute_relationship_diff(self, mapper):
        """Test computing diff between old and new relationships."""
        old_fm = {"parents": ["[[A]]"], "children": ["[[B]]"], "related": []}
        new_fm = {"parents": ["[[A]]", "[[C]]"], "children": [], "related": ["[[D]]"]}

        old_rel = mapper.extract_relationships("test.md", old_fm)
        new_rel = mapper.extract_relationships("test.md", new_fm)
        diff = mapper.compute_relationship_diff(old_rel, new_rel)

        assert "C" in diff["parents"]["added"]
        assert "B" in diff["children"]["removed"]
        assert "D" in diff["related"]["added"]


class TestPropertyInheritanceChain:
    """Tests for PropertyInheritanceChain integration."""

    @pytest.fixture
    def chain(self) -> PropertyInheritanceChain:
        """Create a PropertyInheritanceChain instance."""
        return PropertyInheritanceChain()

    @pytest.fixture
    def sample_frontmatters(self) -> Dict[str, Dict[str, Any]]:
        """Sample frontmatter hierarchy."""
        return {
            "GrandParent": {"project": "Main", "status": "active", "priority": 1},
            "Parent": {"parents": ["[[GrandParent]]"], "category": "work"},
            "Child": {"parents": ["[[Parent]]"], "title": "Child Task"},
        }

    def test_compute_effective_frontmatter(self, chain, sample_frontmatters):
        """Test computing effective frontmatter with inheritance."""

        def get_fm(path):
            return sample_frontmatters.get(path, {})

        result = chain.compute_effective_frontmatter(
            "Child", sample_frontmatters["Child"], get_fm
        )

        assert result.get("title") == "Child Task"  # Local value
        assert result.get("project") == "Main"  # Inherited from GrandParent
        assert result.get("category") == "work"  # Inherited from Parent
        assert result.get("priority") == 1  # Inherited from GrandParent

    def test_get_inherited_value(self, chain, sample_frontmatters):
        """Test tracing inheritance for a specific property."""

        def get_fm(path):
            return sample_frontmatters.get(path, {})

        result = chain.get_inherited_value("Child", "project", get_fm)

        assert result is not None
        assert result.value == "Main"
        assert result.source_path == "GrandParent"
        assert "Parent" in result.inheritance_chain

    def test_detect_circular_inheritance(self, chain):
        """Test circular inheritance detection."""
        circular_fms = {
            "A": {"parents": ["[[B]]"]},
            "B": {"parents": ["[[C]]"]},
            "C": {"parents": ["[[A]]"]},
        }

        def get_fm(path):
            return circular_fms.get(path, {})

        cycle = chain.detect_circular_inheritance("A", get_fm)

        assert cycle is not None
        assert "A" in cycle
        assert "B" in cycle
        assert "C" in cycle

    def test_path_exclusions(self, chain):
        """Test path-based property exclusions."""
        chain.add_path_exclusion("Archive/*", {"project", "status"})

        fm = {"project": "Old", "title": "Archived"}

        def get_fm(path):
            return fm

        result = chain.compute_effective_frontmatter("Archive/OldNote", {}, get_fm)

        # project should not be inherited for Archive/* paths
        assert "project" not in result or result.get("project") is None


class TestDashboardGraphVisualizer:
    """Tests for DashboardGraphVisualizer integration."""

    @pytest.fixture
    def visualizer(self) -> DashboardGraphVisualizer:
        """Create a DashboardGraphVisualizer instance."""
        return DashboardGraphVisualizer()

    @pytest.fixture
    def sample_tasks(self):
        """Sample task data for Beads view."""
        return [
            {
                "id": "T1",
                "title": "Task 1",
                "status": "closed",
                "priority": 1,
                "dependencies": [],
            },
            {
                "id": "T2",
                "title": "Task 2",
                "status": "in_progress",
                "priority": 2,
                "dependencies": [{"depends_on_id": "T1", "type": "blocks"}],
            },
            {
                "id": "T3",
                "title": "Task 3",
                "status": "open",
                "priority": 3,
                "dependencies": [{"depends_on_id": "T2", "type": "related"}],
            },
        ]

    @pytest.fixture
    def sample_chunks(self):
        """Sample chunk data for Idea Web view."""
        return [
            {
                "id": "C1",
                "text": "Memory systems",
                "type": "chunk",
                "metadata": {"ppr_score": 0.8},
            },
            {
                "id": "C2",
                "text": "Graph algorithms",
                "type": "chunk",
                "metadata": {"ppr_score": 0.6},
            },
        ]

    @pytest.fixture
    def sample_relationships(self):
        """Sample relationships for Idea Web view."""
        return [
            {"source": "C1", "target": "C2", "type": "references"},
        ]

    def test_create_beads_view(self, visualizer, sample_tasks):
        """Test creating Beads DAG view."""
        result = visualizer.create_beads_view(sample_tasks)

        assert result.view_type == ViewType.BEADS_DAG
        assert len(result.nodes) == 3
        assert len(result.edges) == 2

    def test_create_idea_web(self, visualizer, sample_chunks, sample_relationships):
        """Test creating Idea Web view."""
        result = visualizer.create_idea_web(sample_chunks, sample_relationships)

        assert result.view_type == ViewType.IDEA_WEB
        assert len(result.nodes) == 2
        assert len(result.edges) == 1

    def test_export_mermaid(self, visualizer, sample_tasks):
        """Test export to Mermaid format."""
        graph = visualizer.create_beads_view(sample_tasks)
        result = visualizer.export(graph, GraphFormat.MERMAID)

        assert result.format == "mermaid"
        assert "graph TD" in result.graph
        assert "T1" in result.graph
        assert result.nodes_count == 3

    def test_export_dot(self, visualizer, sample_tasks):
        """Test export to DOT format."""
        graph = visualizer.create_beads_view(sample_tasks)
        result = visualizer.export(graph, GraphFormat.DOT)

        assert result.format == "dot"
        assert "digraph G" in result.graph
        assert "rankdir=LR" in result.graph

    def test_export_cytoscape(self, visualizer, sample_chunks, sample_relationships):
        """Test export to Cytoscape format."""
        graph = visualizer.create_idea_web(sample_chunks, sample_relationships)
        result = visualizer.export(graph, GraphFormat.CYTOSCAPE)

        assert result.format == "cytoscape"
        assert "nodes" in result.adjacency
        assert "edges" in result.adjacency
        assert len(result.adjacency["nodes"]) == 2

    def test_export_json(self, visualizer, sample_tasks):
        """Test export to JSON adjacency format."""
        graph = visualizer.create_beads_view(sample_tasks)
        result = visualizer.export(graph, GraphFormat.JSON)

        assert result.format == "json"
        assert "nodes" in result.adjacency
        assert "edges" in result.adjacency

    def test_subgraph_extraction(self, visualizer, sample_tasks):
        """Test subgraph extraction from root."""
        graph = visualizer.create_beads_view(sample_tasks)
        result = visualizer.export(graph, GraphFormat.JSON, root_id="T2", max_depth=1)

        # Should include T2 and T1 (T2's dependency), but not T3
        assert result.nodes_count == 2


class TestCrossModuleIntegration:
    """Tests for integration across multiple modules."""

    def test_frontmatter_to_cytoscape_pipeline(self):
        """Test pipeline from frontmatter to Cytoscape visualization."""
        # Setup
        mapper = FrontmatterMapper()
        visualizer = DashboardGraphVisualizer()

        # Create frontmatter data
        files = {
            "note1.md": {
                "title": "Note 1",
                "children": ["[[note2.md]]", "[[note3.md]]"],
            },
            "note2.md": {"title": "Note 2", "parents": ["[[note1.md]]"]},
            "note3.md": {
                "title": "Note 3",
                "parents": ["[[note1.md]]"],
                "related": ["[[note2.md]]"],
            },
        }

        # Extract relationships and create chunks
        chunks = []
        relationships = []

        for file_path, fm in files.items():
            rel = mapper.extract_relationships(file_path, fm)
            chunks.append(
                {
                    "id": file_path,
                    "text": fm.get("title", ""),
                    "type": "note",
                    "metadata": fm,
                }
            )
            edges = mapper.relationships_to_edges(rel)
            for edge in edges:
                relationships.append(edge)

        # Create visualization
        graph = visualizer.create_idea_web(chunks, relationships)
        result = visualizer.export(graph, GraphFormat.CYTOSCAPE)

        assert result.nodes_count == 3
        assert result.edges_count > 0

    def test_inheritance_to_beads_pipeline(self):
        """Test pipeline from inheritance chain to Beads visualization."""
        # Setup
        chain = PropertyInheritanceChain()
        visualizer = DashboardGraphVisualizer()

        # Create task hierarchy
        tasks_fm = {
            "Epic-1": {"title": "Epic", "status": "in_progress", "priority": 1},
            "Story-1": {"title": "Story", "parents": ["[[Epic-1]]"], "priority": 2},
            "Task-1": {"title": "Task", "parents": ["[[Story-1]]"], "status": "open"},
            "Task-2": {
                "title": "Task 2",
                "parents": ["[[Story-1]]"],
                "status": "blocked",
            },
        }

        def get_fm(path):
            return tasks_fm.get(path, {})

        # Compute effective properties for each task
        tasks = []
        for task_id, fm in tasks_fm.items():
            effective = chain.compute_effective_frontmatter(task_id, fm, get_fm)
            parents = fm.get("parents", [])
            deps = [{"depends_on_id": p.strip("[]"), "type": "blocks"} for p in parents]
            tasks.append(
                {
                    "id": task_id,
                    "title": effective.get("title", task_id),
                    "status": effective.get("status", "open"),
                    "priority": effective.get("priority", 3),
                    "dependencies": deps,
                }
            )

        # Create Beads visualization
        graph = visualizer.create_beads_view(tasks)
        result = visualizer.export(graph, GraphFormat.MERMAID)

        assert result.nodes_count == 4
        assert "Epic_1" in result.graph or "Epic-1" in result.graph


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
