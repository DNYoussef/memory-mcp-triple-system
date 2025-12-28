"""
Graph Query Service - Focused component for graph queries.

Extracted from GraphService to improve cohesion.
Single Responsibility: Graph traversal and queries.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, Optional, List
import networkx as nx
from loguru import logger


class GraphQueryService:
    """
    Handles graph traversal and query operations.

    Single Responsibility: Graph queries.
    Cohesion: HIGH - all methods are query operations.
    """

    def __init__(self, graph: nx.DiGraph):
        """
        Initialize with graph reference.

        Args:
            graph: NetworkX DiGraph
        """
        self.graph = graph

    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find shortest path between nodes."""
        try:
            if source not in self.graph or target not in self.graph:
                return None

            path = nx.shortest_path(self.graph, source, target)
            logger.debug(f"Path: {source} -> {target} ({len(path)} nodes)")
            return path
        except nx.NetworkXNoPath:
            logger.debug(f"No path: {source} -> {target}")
            return None
        except Exception as e:
            logger.error(f"Path finding failed: {e}")
            return None

    def get_subgraph(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get local subgraph around a node."""
        try:
            if node_id not in self.graph:
                return {'nodes': [], 'edges': []}

            # BFS to find nodes within depth
            nodes_to_include = {node_id}
            current_layer = {node_id}

            for _ in range(depth):
                next_layer = set()
                for node in current_layer:
                    next_layer.update(self.graph.successors(node))
                    next_layer.update(self.graph.predecessors(node))
                nodes_to_include.update(next_layer)
                current_layer = next_layer

            subgraph = self.graph.subgraph(nodes_to_include)

            return {
                'nodes': [
                    {'id': n, **self.graph.nodes[n]}
                    for n in subgraph.nodes()
                ],
                'edges': [
                    {'source': u, 'target': v, **self.graph.edges[u, v]}
                    for u, v in subgraph.edges()
                ]
            }
        except Exception as e:
            logger.error(f"Subgraph failed: {e}")
            return {'nodes': [], 'edges': []}
