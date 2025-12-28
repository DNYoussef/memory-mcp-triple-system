"""
Graph Edge Manager - Focused component for edge operations.

Extracted from GraphService to improve cohesion.
Single Responsibility: Edge CRUD operations.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, Optional, List
import networkx as nx
from loguru import logger


class GraphEdgeManager:
    """
    Manages edge operations for NetworkX graph.

    Single Responsibility: Edge CRUD.
    Cohesion: HIGH - all methods work with edges.
    """

    EDGE_REFERENCES = 'references'
    EDGE_MENTIONS = 'mentions'
    EDGE_SIMILAR_TO = 'similar_to'
    EDGE_RELATED_TO = 'related_to'

    def __init__(self, graph: nx.DiGraph):
        """
        Initialize with graph reference.

        Args:
            graph: NetworkX DiGraph
        """
        self.graph = graph

    def add_relationship(
        self,
        source: str,
        relationship_type: str,
        target: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add relationship edge between nodes."""
        try:
            standard_types = {
                self.EDGE_REFERENCES,
                self.EDGE_MENTIONS,
                self.EDGE_SIMILAR_TO,
                self.EDGE_RELATED_TO
            }

            if relationship_type not in standard_types:
                logger.debug(f"Custom relationship: {relationship_type}")

            self.graph.add_edge(
                source, target,
                type=relationship_type,
                metadata=metadata or {}
            )
            logger.debug(f"Added edge: {source} --{relationship_type}--> {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to add relationship: {e}")
            return False

    def remove_edge(self, source: str, target: str) -> bool:
        """Remove edge from graph."""
        try:
            if not self.graph.has_edge(source, target):
                logger.warning(f"Edge not found: {source} -> {target}")
                return False
            self.graph.remove_edge(source, target)
            logger.debug(f"Removed edge: {source} -> {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove edge: {e}")
            return False

    def get_neighbors(
        self,
        node_id: str,
        relationship_type: Optional[str] = None
    ) -> List[str]:
        """Get neighboring nodes, optionally filtered by edge type."""
        try:
            if node_id not in self.graph:
                return []

            neighbors = list(self.graph.neighbors(node_id))

            if relationship_type:
                filtered = []
                for neighbor in neighbors:
                    edge_data = self.graph.get_edge_data(node_id, neighbor)
                    if edge_data and edge_data.get('type') == relationship_type:
                        filtered.append(neighbor)
                return filtered

            return neighbors
        except Exception as e:
            logger.error(f"Failed to get neighbors: {e}")
            return []

    def get_edge_count(self) -> int:
        """Get total number of edges."""
        return self.graph.number_of_edges()
