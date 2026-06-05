"""
CytoscapeExporter - Export NetworkX graph to Cytoscape JSON format.

Ported from Nexus-Properties graph-builder.ts with Memory MCP-specific enhancements:
- Memory layer coloring (24h/7d/30d decay)
- PPR score size scaling
- WHO/WHEN/PROJECT/WHY metadata mapping
- Constellation view support

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
import math
from datetime import datetime
import networkx as nx
from loguru import logger


@dataclass
class ConstellationNode:
    """A constellation in the recursive graph structure (ported from graph-builder.ts)."""
    center: str  # Node ID of constellation center
    orbitals: List[str] = field(default_factory=list)  # Node IDs of orbital nodes
    level: int = 0  # Depth in hierarchy (0 = root)


@dataclass
class ConstellationGraphData:
    """Complete constellation graph data (ported from graph-builder.ts)."""
    constellations: List[ConstellationNode] = field(default_factory=list)
    all_node_ids: Set[str] = field(default_factory=set)
    edges: List[Dict[str, Any]] = field(default_factory=list)


# Memory layer colors (24h/7d/30d retention)
LAYER_COLORS = {
    "short": "#4CAF50",   # Green - recent (24h)
    "medium": "#FF9800",  # Orange - mid-term (7d)
    "long": "#9E9E9E",    # Gray - long-term (30d+)
    "default": "#2196F3"  # Blue - unknown
}

# Node type colors
TYPE_COLORS = {
    "chunk": "#2196F3",    # Blue
    "entity": "#9C27B0",   # Purple
    "concept": "#00BCD4",  # Cyan
    "default": "#607D8B"   # Blue-gray
}


class CytoscapeExporter:
    """
    Export Memory MCP NetworkX graph to Cytoscape JSON format.

    Extends NetworkX's built-in cytoscape_data() with Memory MCP features:
    - Memory layer coloring based on decay scores
    - PPR score size scaling for node importance
    - Constellation view support (ported from Nexus-Properties)
    - WHO/PROJECT metadata mapping for filtering

    Usage:
        from src.services.graph_service import GraphService
        service = GraphService()
        service.load_graph()

        exporter = CytoscapeExporter(service.graph)
        cytoscape_json = exporter.export_elements()
    """

    def __init__(self, graph: nx.DiGraph, max_depth: int = 3):
        """
        Initialize CytoscapeExporter.

        Args:
            graph: NetworkX directed graph from GraphService
            max_depth: Maximum depth for recursive constellation building
        """
        self.graph = graph
        self.max_depth = max_depth
        logger.debug(f"CytoscapeExporter initialized with {graph.number_of_nodes()} nodes")

    def export_elements(self) -> Dict[str, Any]:
        """
        Export entire graph to Cytoscape JSON format.

        Returns:
            Dict with 'nodes' and 'edges' arrays in Cytoscape format
        """
        nodes = []
        edges = []

        for node_id, data in self.graph.nodes(data=True):
            node_element = self._create_node_element(node_id, data, level=0)
            nodes.append(node_element)

        for source, target, data in self.graph.edges(data=True):
            edge_element = self._create_edge_element(source, target, data)
            edges.append(edge_element)

        logger.info(f"Exported {len(nodes)} nodes and {len(edges)} edges")
        return {"nodes": nodes, "edges": edges}

    def export_subgraph(self, center_id: str, depth: int = 2) -> Dict[str, Any]:
        """
        Export a subgraph centered on a specific node.

        Args:
            center_id: Node ID to center the subgraph on
            depth: How many hops from center to include

        Returns:
            Dict with 'nodes' and 'edges' for the subgraph
        """
        if not self.graph.has_node(center_id):
            logger.warning(f"Node {center_id} not found in graph")
            return {"nodes": [], "edges": []}

        # Get all nodes within depth
        included = {center_id}
        frontier = {center_id}

        for _ in range(depth):
            next_frontier = set()
            for node in frontier:
                neighbors = set(self.graph.predecessors(node)) | set(self.graph.successors(node))
                next_frontier.update(neighbors - included)
            included.update(next_frontier)
            frontier = next_frontier

        return self._export_node_set(included, center_id)

    def build_recursive_constellations(self, source_id: str) -> ConstellationGraphData:
        """
        Build recursive constellation structure (ported from graph-builder.ts).

        Creates a multi-level constellation where each orbital node becomes
        the center of its own sub-constellation, up to max_depth.

        Args:
            source_id: Starting node ID for constellation

        Returns:
            ConstellationGraphData with all constellations, nodes, and edges
        """
        result = ConstellationGraphData()
        result.all_node_ids.add(source_id)

        # Queue of (center_id, level) to process
        queue = [(source_id, 0)]

        while queue:
            center_id, level = queue.pop(0)

            if level >= self.max_depth:
                continue

            if not self.graph.has_node(center_id):
                continue

            # Get related nodes (successors in directed graph)
            neighbors = list(self.graph.successors(center_id))
            orbitals = [n for n in neighbors if n not in result.all_node_ids]

            # Create constellation if there are orbitals or this is root
            if orbitals or level == 0:
                constellation = ConstellationNode(
                    center=center_id,
                    orbitals=orbitals,
                    level=level
                )
                result.constellations.append(constellation)

                # Add edges from center to orbitals
                for orbital_id in orbitals:
                    edge = {"source": center_id, "target": orbital_id}
                    result.edges.append(edge)

                # Add orbitals to processed set and queue
                for orbital_id in orbitals:
                    result.all_node_ids.add(orbital_id)
                    queue.append((orbital_id, level + 1))

        logger.debug(f"Built {len(result.constellations)} constellations from {source_id}")
        return result

    def export_constellations(self, source_id: str) -> Dict[str, Any]:
        """
        Export constellation view to Cytoscape format.

        Args:
            source_id: Starting node ID for constellation

        Returns:
            Dict with 'nodes' and 'edges' in Cytoscape format with constellation metadata
        """
        constellation_data = self.build_recursive_constellations(source_id)
        return self._convert_constellations_to_cytoscape(constellation_data, source_id)

    def _create_node_element(
        self,
        node_id: str,
        data: Dict[str, Any],
        level: int = 0,
        is_source: bool = False,
        constellation_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create Cytoscape node element with Memory MCP enhancements.

        Args:
            node_id: Unique node identifier
            data: Node metadata from NetworkX
            level: Depth level in graph (for constellation view)
            is_source: Whether this is the source/center node
            constellation_index: Index of containing constellation

        Returns:
            Cytoscape node element dict
        """
        metadata = data.get("metadata", {})

        # Get display label
        label = self._get_node_label(node_id, data, metadata)

        # Calculate node color based on type or memory layer
        node_color = self._get_node_color(data, metadata)

        # Calculate node size based on PPR score
        ppr_score = metadata.get("ppr_score", data.get("ppr_score", 0.5))
        node_size = self._calculate_node_size(ppr_score)

        # Extract WHO/PROJECT for filtering
        who = metadata.get("WHO", {}).get("name") if isinstance(metadata.get("WHO"), dict) else metadata.get("WHO")
        project = metadata.get("PROJECT", "")

        element = {
            "data": {
                "id": str(node_id),
                "label": label,
                "level": level,
                "isSource": is_source,
                "nodeColor": node_color,
                "width": node_size,
                "height": node_size,
                "type": data.get("type", "unknown"),
                "pprScore": ppr_score,
                "who": who,
                "project": project,
            }
        }

        if constellation_index is not None:
            element["data"]["constellationIndex"] = constellation_index

        return element

    def _create_edge_element(
        self,
        source: str,
        target: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create Cytoscape edge element.

        Args:
            source: Source node ID
            target: Target node ID
            data: Edge metadata from NetworkX

        Returns:
            Cytoscape edge element dict
        """
        edge_type = data.get("type", data.get("relationship_type", "related"))
        confidence = data.get("confidence", 1.0)

        return {
            "data": {
                "source": str(source),
                "target": str(target),
                "type": edge_type,
                "confidence": confidence,
            }
        }

    def _get_node_label(self, node_id: str, data: Dict, metadata: Dict) -> str:
        """Get display label for node, truncated to reasonable length."""
        # Try various label sources
        label = (
            metadata.get("title") or
            metadata.get("name") or
            data.get("text", "")[:50] or
            str(node_id)
        )
        # Truncate long labels
        if len(label) > 50:
            label = label[:47] + "..."
        return label

    def _get_node_color(self, data: Dict, metadata: Dict) -> str:
        """Get node color based on type or memory layer."""
        # Check for explicit node type
        node_type = data.get("type", "")
        if node_type in TYPE_COLORS:
            return TYPE_COLORS[node_type]

        # Check memory layer based on decay score
        decay_score = metadata.get("decay_score", 1.0)
        if decay_score > 0.8:
            return LAYER_COLORS["short"]   # Recent (24h)
        elif decay_score > 0.5:
            return LAYER_COLORS["medium"]  # Mid-term (7d)
        elif decay_score > 0:
            return LAYER_COLORS["long"]    # Long-term (30d+)

        return LAYER_COLORS["default"]

    def _calculate_node_size(self, ppr_score: float) -> int:
        """Calculate node size based on PPR score (30-80px range)."""
        # Normalize score to 0-1 range
        normalized = max(0.0, min(1.0, ppr_score))
        # Scale to 30-80px range with slight curve for visual distinction
        size = 30 + int(50 * math.sqrt(normalized))
        return size

    def _export_node_set(
        self,
        node_ids: Set[str],
        center_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Export a specific set of nodes and their connecting edges."""
        nodes = []
        edges = []

        for node_id in node_ids:
            data = self.graph.nodes.get(node_id, {})
            is_source = (node_id == center_id)
            node_element = self._create_node_element(node_id, data, is_source=is_source)
            nodes.append(node_element)

        for source, target, data in self.graph.edges(data=True):
            if source in node_ids and target in node_ids:
                edge_element = self._create_edge_element(source, target, data)
                edges.append(edge_element)

        return {"nodes": nodes, "edges": edges}

    def _convert_constellations_to_cytoscape(
        self,
        constellation_data: ConstellationGraphData,
        source_id: str
    ) -> Dict[str, Any]:
        """Convert constellation data to Cytoscape format with metadata."""
        nodes = []
        edges = []
        processed_nodes = set()

        # Track which nodes are constellation centers
        center_ids = {c.center for c in constellation_data.constellations}

        # Process each constellation
        for idx, constellation in enumerate(constellation_data.constellations):
            # Add center node if not already added
            if constellation.center not in processed_nodes:
                data = self.graph.nodes.get(constellation.center, {})
                is_source = (constellation.center == source_id)
                node = self._create_node_element(
                    constellation.center,
                    data,
                    level=constellation.level,
                    is_source=is_source,
                    constellation_index=idx
                )
                node["data"]["isConstellationCenter"] = True
                node["data"]["orbitalCount"] = len(constellation.orbitals)
                nodes.append(node)
                processed_nodes.add(constellation.center)

            # Add orbital nodes
            for orbital_id in constellation.orbitals:
                if orbital_id not in processed_nodes:
                    data = self.graph.nodes.get(orbital_id, {})
                    is_also_center = orbital_id in center_ids
                    node = self._create_node_element(
                        orbital_id,
                        data,
                        level=constellation.level + 1,
                        constellation_index=idx
                    )
                    node["data"]["isConstellationCenter"] = is_also_center
                    node["data"]["centerPath"] = constellation.center
                    nodes.append(node)
                    processed_nodes.add(orbital_id)

        # Add edges
        for edge_data in constellation_data.edges:
            edge = {
                "data": {
                    "source": str(edge_data["source"]),
                    "target": str(edge_data["target"]),
                }
            }
            edges.append(edge)

        logger.info(f"Constellation export: {len(nodes)} nodes, {len(edges)} edges")
        return {"nodes": nodes, "edges": edges}
