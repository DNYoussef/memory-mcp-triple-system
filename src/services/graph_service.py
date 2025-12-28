"""
GraphService - Refactored Facade for Graph Operations

NetworkX-based graph database for entity relationships.
Manages in-memory graph with JSON persistence.

REFACTORED: Extracted into focused components for high cohesion:
- GraphNodeManager: Node CRUD
- GraphEdgeManager: Edge CRUD
- GraphQueryService: Graph queries
- GraphPersistence: Save/Load

This class now acts as a facade coordinating the components.

NASA Rule 10 Compliant: All functions <=60 LOC
Cohesion: HIGH (facade pattern - coordinates focused components)
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import networkx as nx
from loguru import logger

from .graph_node_manager import GraphNodeManager
from .graph_edge_manager import GraphEdgeManager
from .graph_query_service import GraphQueryService
from .graph_persistence import GraphPersistence


class GraphService:
    """
    Facade for entity relationship graph operations.

    Coordinates focused components:
    - GraphNodeManager: Node operations
    - GraphEdgeManager: Edge operations
    - GraphQueryService: Queries
    - GraphPersistence: Save/Load

    Usage:
        service = GraphService(data_dir="./data")
        service.add_chunk_node("chunk1", {"text": "..."})
        service.add_relationship("chunk1", "mentions", "entity1")
    """

    # Expose constants for backward compatibility
    NODE_TYPE_CHUNK = GraphNodeManager.NODE_TYPE_CHUNK
    NODE_TYPE_ENTITY = GraphNodeManager.NODE_TYPE_ENTITY
    NODE_TYPE_CONCEPT = GraphNodeManager.NODE_TYPE_CONCEPT
    EDGE_REFERENCES = GraphEdgeManager.EDGE_REFERENCES
    EDGE_MENTIONS = GraphEdgeManager.EDGE_MENTIONS
    EDGE_SIMILAR_TO = GraphEdgeManager.EDGE_SIMILAR_TO
    EDGE_RELATED_TO = GraphEdgeManager.EDGE_RELATED_TO

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize GraphService facade.

        Args:
            data_dir: Directory for graph persistence
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize graph
        self.graph = nx.DiGraph()

        # Initialize focused components
        self._node_manager = GraphNodeManager(self.graph)
        self._edge_manager = GraphEdgeManager(self.graph)
        self._query_service = GraphQueryService(self.graph)
        self._persistence = GraphPersistence(self.graph, self.data_dir)

        logger.info("GraphService initialized")

    # Node operations (delegate to GraphNodeManager)
    def add_chunk_node(self, chunk_id: str, metadata: Optional[Dict] = None) -> bool:
        return self._node_manager.add_chunk(chunk_id, metadata)

    def add_entity_node(self, entity_id: str, entity_type: str, metadata: Optional[Dict] = None) -> bool:
        return self._node_manager.add_entity(entity_id, entity_type, metadata)

    def add_entity(self, entity_id: str, entity_type: str, metadata: Optional[Dict] = None) -> bool:
        return self._node_manager.add_entity(entity_id, entity_type, metadata)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._node_manager.get_node(node_id)

    def remove_node(self, node_id: str) -> bool:
        return self._node_manager.remove_node(node_id)

    def get_node_count(self) -> int:
        return self._node_manager.get_node_count()

    # Edge operations (delegate to GraphEdgeManager)
    def add_relationship(self, source: str, relationship_type: str, target: str, metadata: Optional[Dict] = None) -> bool:
        return self._edge_manager.add_relationship(source, relationship_type, target, metadata)

    def remove_edge(self, source: str, target: str) -> bool:
        return self._edge_manager.remove_edge(source, target)

    def get_neighbors(self, node_id: str, relationship_type: Optional[str] = None) -> List[str]:
        return self._edge_manager.get_neighbors(node_id, relationship_type)

    def get_edge_count(self) -> int:
        return self._edge_manager.get_edge_count()

    # Query operations (delegate to GraphQueryService)
    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        return self._query_service.find_path(source, target)

    def get_subgraph(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        return self._query_service.get_subgraph(node_id, depth)

    # Persistence operations (delegate to GraphPersistence)
    def save_graph(self, file_path: Optional[Path] = None) -> bool:
        return self._persistence.save(file_path)

    def load_graph(self, file_path: Optional[Path] = None) -> bool:
        loaded = self._persistence.load(file_path)
        if loaded is not None:
            self.graph = loaded
            # Re-initialize components with new graph
            self._node_manager = GraphNodeManager(self.graph)
            self._edge_manager = GraphEdgeManager(self.graph)
            self._query_service = GraphQueryService(self.graph)
            self._persistence = GraphPersistence(self.graph, self.data_dir)
            return True
        return False

    def get_graph(self) -> nx.DiGraph:
        """Return underlying NetworkX graph."""
        return self.graph
