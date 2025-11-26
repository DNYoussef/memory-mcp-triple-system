"""
GraphService - NetworkX-based graph database for entity relationships.

Manages in-memory graph of chunks, entities, and their relationships.
Provides graph query operations and JSON persistence.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import json
import networkx as nx
from loguru import logger


class GraphService:
    """
    Service for managing entity relationship graph using NetworkX.

    Provides operations for adding nodes/edges and querying relationships.
    """

    # Node types
    NODE_TYPE_CHUNK = 'chunk'
    NODE_TYPE_ENTITY = 'entity'
    NODE_TYPE_CONCEPT = 'concept'

    # Edge types (relationship types)
    EDGE_REFERENCES = 'references'
    EDGE_MENTIONS = 'mentions'
    EDGE_SIMILAR_TO = 'similar_to'
    EDGE_RELATED_TO = 'related_to'

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize GraphService with NetworkX directed graph.

        Args:
            data_dir: Directory for graph persistence
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize directed graph
        self.graph = nx.DiGraph()

        logger.info("GraphService initialized")

    def add_chunk_node(
        self,
        chunk_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add chunk node to graph.

        Args:
            chunk_id: Unique chunk identifier
            metadata: Optional metadata dictionary

        Returns:
            True if added successfully
        """
        try:
            node_data = {
                'type': self.NODE_TYPE_CHUNK,
                'metadata': metadata or {}
            }

            self.graph.add_node(chunk_id, **node_data)
            logger.debug(f"Added chunk node: {chunk_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add chunk node {chunk_id}: {e}")
            return False

    def add_entity_node(
        self,
        entity_id: str,
        entity_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add entity node to graph.

        Args:
            entity_id: Unique entity identifier
            entity_type: Entity type (PERSON, ORG, GPE, etc.)
            metadata: Optional metadata dictionary

        Returns:
            True if added successfully
        """
        try:
            node_data = {
                'type': self.NODE_TYPE_ENTITY,
                'entity_type': entity_type,
                'metadata': metadata or {}
            }

            self.graph.add_node(entity_id, **node_data)
            logger.debug(f"Added entity node: {entity_id} ({entity_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to add entity node {entity_id}: {e}")
            return False

    def add_relationship(
        self,
        source: str,
        relationship_type: str,
        target: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add relationship edge between two nodes.

        Args:
            source: Source node ID
            relationship_type: Type of relationship (any string allowed)
            target: Target node ID
            metadata: Optional edge metadata

        Returns:
            True if added successfully
        """
        try:
            # Log if using non-standard relationship type
            standard_types = {
                self.EDGE_REFERENCES,
                self.EDGE_MENTIONS,
                self.EDGE_SIMILAR_TO,
                self.EDGE_RELATED_TO
            }

            if relationship_type not in standard_types:
                logger.debug(f"Using custom relationship type: {relationship_type}")

            edge_data = {
                'type': relationship_type,
                'metadata': metadata or {}
            }

            self.graph.add_edge(source, target, **edge_data)
            logger.debug(f"Added edge: {source} --{relationship_type}--> {target}")
            return True

        except Exception as e:
            logger.error(f"Failed to add relationship: {e}")
            return False

    def get_neighbors(
        self,
        node_id: str,
        relationship_type: Optional[str] = None
    ) -> List[str]:
        """
        Get neighboring nodes.

        Args:
            node_id: Node to get neighbors for
            relationship_type: Optional filter by edge type

        Returns:
            List of neighbor node IDs
        """
        try:
            if node_id not in self.graph:
                logger.warning(f"Node not found: {node_id}")
                return []

            # Get all neighbors
            neighbors = list(self.graph.neighbors(node_id))

            # Filter by relationship type if specified
            if relationship_type:
                filtered = []
                for neighbor in neighbors:
                    edge_data = self.graph.get_edge_data(node_id, neighbor)
                    if edge_data and edge_data.get('type') == relationship_type:
                        filtered.append(neighbor)
                return filtered

            return neighbors

        except Exception as e:
            logger.error(f"Failed to get neighbors for {node_id}: {e}")
            return []

    def find_path(
        self,
        source: str,
        target: str
    ) -> Optional[List[str]]:
        """
        Find shortest path between two nodes.

        Args:
            source: Source node ID
            target: Target node ID

        Returns:
            List of node IDs in path, or None if no path exists
        """
        try:
            if source not in self.graph or target not in self.graph:
                logger.warning(f"Node not found: {source} or {target}")
                return None

            path = nx.shortest_path(self.graph, source, target)
            logger.debug(f"Found path: {source} -> {target} ({len(path)} nodes)")
            return path

        except nx.NetworkXNoPath:
            logger.debug(f"No path exists: {source} -> {target}")
            return None

        except Exception as e:
            logger.error(f"Failed to find path: {e}")
            return None

    def get_subgraph(
        self,
        node_id: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get local subgraph around a node.

        Args:
            node_id: Center node ID
            depth: How many hops to include

        Returns:
            Dictionary with nodes and edges
        """
        try:
            if node_id not in self.graph:
                logger.warning(f"Node not found: {node_id}")
                return {'nodes': [], 'edges': []}

            # BFS to find nodes within depth
            nodes_to_include = {node_id}
            current_layer = {node_id}

            for _ in range(depth):
                next_layer = set()
                for node in current_layer:
                    # Add successors and predecessors
                    next_layer.update(self.graph.successors(node))
                    next_layer.update(self.graph.predecessors(node))

                nodes_to_include.update(next_layer)
                current_layer = next_layer

            # Get subgraph
            subgraph = self.graph.subgraph(nodes_to_include)

            # Format as dict
            result = {
                'nodes': [
                    {'id': n, **self.graph.nodes[n]}
                    for n in subgraph.nodes()
                ],
                'edges': [
                    {
                        'source': u,
                        'target': v,
                        **self.graph.edges[u, v]
                    }
                    for u, v in subgraph.edges()
                ]
            }

            logger.debug(f"Subgraph for {node_id}: {len(result['nodes'])} nodes")
            return result

        except Exception as e:
            logger.error(f"Failed to get subgraph: {e}")
            return {'nodes': [], 'edges': []}

    def save_graph(self, file_path: Optional[Path] = None) -> bool:
        """
        Save graph to JSON file.

        Args:
            file_path: Optional file path (defaults to data_dir/graph.json)

        Returns:
            True if saved successfully
        """
        try:
            if file_path is None:
                file_path = self.data_dir / 'graph.json'
            else:
                file_path = Path(file_path)

            # Convert to node-link format for JSON serialization
            data = nx.node_link_data(self.graph)

            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved graph to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save graph: {e}")
            return False

    def load_graph(self, file_path: Optional[Path] = None) -> bool:
        """
        Load graph from JSON file.

        Args:
            file_path: Optional file path (defaults to data_dir/graph.json)

        Returns:
            True if loaded successfully
        """
        try:
            if file_path is None:
                file_path = self.data_dir / 'graph.json'
            else:
                file_path = Path(file_path)

            if not file_path.exists():
                logger.warning(f"Graph file not found: {file_path}")
                return False

            with open(file_path, 'r') as f:
                data = json.load(f)

            # Convert from node-link format
            self.graph = nx.node_link_graph(data, directed=True)

            logger.info(f"Loaded graph from {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load graph: {e}")
            return False

    def get_node_count(self) -> int:
        """
        Get total number of nodes in graph.

        Returns:
            Node count
        """
        return self.graph.number_of_nodes()

    def get_edge_count(self) -> int:
        """
        Get total number of edges in graph.

        Returns:
            Edge count
        """
        return self.graph.number_of_edges()

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get node data.

        Args:
            node_id: Node ID

        Returns:
            Node data dictionary or None if not found
        """
        if node_id not in self.graph:
            return None

        return {'id': node_id, **self.graph.nodes[node_id]}

    def remove_node(self, node_id: str) -> bool:
        """
        Remove node from graph.

        Args:
            node_id: Node ID to remove

        Returns:
            True if removed successfully
        """
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

    def remove_edge(
        self,
        source: str,
        target: str
    ) -> bool:
        """
        Remove edge from graph.

        Args:
            source: Source node ID
            target: Target node ID

        Returns:
            True if removed successfully
        """
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

    def get_graph(self) -> nx.DiGraph:
        """
        Return underlying NetworkX graph for advanced algorithms.

        Used by HippoRAG for Personalized PageRank and other graph algorithms.

        Returns:
            NetworkX DiGraph instance
        """
        return self.graph

    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Convenience method for add_entity_node.

        Args:
            entity_id: Unique entity identifier
            entity_type: Entity type
            metadata: Optional metadata

        Returns:
            True if added successfully
        """
        return self.add_entity_node(entity_id, entity_type, metadata)
