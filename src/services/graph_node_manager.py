"""
Graph Node Manager - Focused component for node operations.

Extracted from GraphService to improve cohesion.
Single Responsibility: Node CRUD operations.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import math
import networkx as nx
from loguru import logger


class GraphNodeManager:
    """
    Manages node operations for NetworkX graph.

    Single Responsibility: Node CRUD.
    Cohesion: HIGH - all methods work with nodes.
    """

    NODE_TYPE_CHUNK = "chunk"
    NODE_TYPE_ENTITY = "entity"
    NODE_TYPE_CONCEPT = "concept"

    def __init__(self, graph: nx.DiGraph):
        """
        Initialize with graph reference.

        Args:
            graph: NetworkX DiGraph
        """
        self.graph = graph

    def add_chunk(
        self, chunk_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add chunk node to graph."""
        try:
            self.graph.add_node(
                chunk_id, type=self.NODE_TYPE_CHUNK, metadata=metadata or {}
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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add entity node to graph."""
        try:
            self.graph.add_node(
                entity_id,
                type=self.NODE_TYPE_ENTITY,
                entity_type=entity_type,
                metadata=metadata or {},
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
        return {"id": node_id, **self.graph.nodes[node_id]}

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

    def increment_frequency(self, node_id: str) -> bool:
        """Increment node access frequency and last-access timestamp."""
        if node_id not in self.graph:
            logger.warning(f"Node not found for frequency update: {node_id}")
            return False
        node = self.graph.nodes[node_id]
        node["frequency"] = int(node.get("frequency", 0)) + 1
        node["last_accessed"] = datetime.now(timezone.utc).isoformat()
        return True

    def update_importance(self, node_id: str, explicit_weight: float = 0.5) -> bool:
        """Update importance from explicit weight, frequency, and decay."""
        if node_id not in self.graph:
            logger.warning(f"Node not found for importance update: {node_id}")
            return False
        node = self.graph.nodes[node_id]
        frequency_score = min(
            1.0, math.log1p(float(node.get("frequency", 0))) / math.log(101)
        )
        decay_score = float(node.get("decay_score", 1.0))
        explicit_weight = max(0.0, min(1.0, explicit_weight))
        node["importance"] = max(
            0.0,
            min(
                1.0,
                (0.5 * explicit_weight) + (0.3 * frequency_score) + (0.2 * decay_score),
            ),
        )
        return True

    def update_decay_score(self, node_id: str) -> bool:
        """Update exponential decay score from last access/creation timestamp."""
        if node_id not in self.graph:
            logger.warning(f"Node not found for decay update: {node_id}")
            return False
        node = self.graph.nodes[node_id]
        timestamp = node.get("last_accessed") or node.get("created_at")
        age_days = _age_days(timestamp)
        node["decay_score"] = math.exp(-age_days / 30.0)
        return True

    def get_nodes_by_importance(
        self, min_importance: float = 0.0, max_importance: float = 1.0
    ) -> list[tuple]:
        """Return nodes whose importance is within the requested range."""
        matches = []
        for node_id, attrs in self.graph.nodes(data=True):
            importance = float(attrs.get("importance", 0.0))
            if min_importance <= importance <= max_importance:
                matches.append((node_id, attrs))
        return sorted(
            matches,
            key=lambda item: float(item[1].get("importance", 0.0)),
            reverse=True,
        )


def _age_days(timestamp: Optional[str]) -> float:
    if not timestamp:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(
        0.0,
        (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        / 86400.0,
    )
