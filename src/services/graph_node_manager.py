"""
Graph Node Manager - Focused component for node operations.

Extracted from GraphService to improve cohesion.
Single Responsibility: Node CRUD operations.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, Optional
import networkx as nx
from loguru import logger


class GraphNodeManager:
    """
    Manages node operations for NetworkX graph.

    Single Responsibility: Node CRUD.
    Cohesion: HIGH - all methods work with nodes.
    """

    NODE_TYPE_CHUNK = 'chunk'
    NODE_TYPE_ENTITY = 'entity'
    NODE_TYPE_CONCEPT = 'concept'

    def __init__(self, graph: nx.DiGraph):
        """
        Initialize with graph reference.

        Args:
            graph: NetworkX DiGraph
        """
        self.graph = graph

    def add_chunk(
        self,
        chunk_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add chunk node to graph."""
        try:
            self.graph.add_node(
                chunk_id,
                type=self.NODE_TYPE_CHUNK,
                metadata=metadata or {}
            )
            logger.debug(f"Added chunk node: {chunk_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add chunk {chunk_id}: {e}")
            return False

    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add entity node to graph."""
        try:
            self.graph.add_node(
                entity_id,
                type=self.NODE_TYPE_ENTITY,
                entity_type=entity_type,
                metadata=metadata or {}
            )
            logger.debug(f"Added entity: {entity_id} ({entity_type})")
            return True
        except Exception as e:
            logger.error(f"Failed to add entity {entity_id}: {e}")
            return False

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node data by ID."""
        if node_id not in self.graph:
            return None
        return {'id': node_id, **self.graph.nodes[node_id]}

    def remove_node(self, node_id: str) -> bool:
        """Remove node from graph."""
        try:
            if node_id not in self.graph:
                logger.warning(f"Node not found: {node_id}")
                return False
            self.graph.remove_node(node_id)
            logger.debug(f"Removed node: {node_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove node {node_id}: {e}")
            return False

    def get_node_count(self) -> int:
        """Get total number of nodes."""
        return self.graph.number_of_nodes()
