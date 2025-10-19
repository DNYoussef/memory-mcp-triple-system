"""
GraphQueryEngine - Personalized PageRank and multi-hop graph queries.

Implements HippoRAG's graph-based retrieval algorithms using NetworkX.
Provides PPR execution, score aggregation, and multi-hop path finding.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from collections import deque
import networkx as nx
from loguru import logger

from .graph_service import GraphService


class GraphQueryEngine:
    """
    Graph query engine for HippoRAG retrieval.

    Provides Personalized PageRank, multi-hop search, and entity neighborhood
    extraction for context-aware retrieval.
    """

    def __init__(self, graph_service: GraphService):
        """
        Initialize GraphQueryEngine with graph service.

        Args:
            graph_service: GraphService instance for graph access

        Raises:
            ValueError: If graph_service is None
        """
        if graph_service is None:
            raise ValueError("graph_service cannot be None")

        self.graph_service = graph_service
        self.graph = graph_service.get_graph()

        logger.info("GraphQueryEngine initialized")

    def personalized_pagerank(
        self,
        query_nodes: List[str],
        alpha: float = 0.85,
        max_iter: int = 100,
        tol: float = 1e-6
    ) -> Dict[str, float]:
        """
        Run Personalized PageRank from query nodes.

        Args:
            query_nodes: List of entity node IDs to start from
            alpha: Damping factor (0.85 = 85% follow edges, 15% teleport)
            max_iter: Maximum iterations for convergence
            tol: Convergence tolerance

        Returns:
            Dict mapping node_id -> PPR score (sum = 1.0)
        """
        try:
            # Validate nodes exist in graph
            valid_nodes = self._validate_nodes(query_nodes)
            if not valid_nodes:
                logger.warning("No valid query nodes found")
                return {}

            # Create personalization vector (equal weight)
            personalization = self._create_personalization_vector(valid_nodes)

            # Run NetworkX PageRank
            ppr_scores = nx.pagerank(
                self.graph,
                alpha=alpha,
                personalization=personalization,
                max_iter=max_iter,
                tol=tol
            )

            logger.info(f"PPR converged with {len(ppr_scores)} scores")
            return ppr_scores

        except nx.PowerIterationFailedConvergence as e:
            logger.error(f"PPR failed to converge: {e}")
            return {}
        except Exception as e:
            logger.error(f"PPR execution failed: {e}")
            return {}

    def _validate_nodes(self, nodes: List[str]) -> List[str]:
        """
        Validate that nodes exist in graph.

        Args:
            nodes: List of node IDs

        Returns:
            List of valid node IDs (exist in graph)
        """
        valid_nodes = []

        for node in nodes:
            if self.graph.has_node(node):
                valid_nodes.append(node)
            else:
                logger.debug(f"Node not in graph: {node}")

        logger.debug(f"Validated {len(valid_nodes)}/{len(nodes)} nodes")
        return valid_nodes

    def _create_personalization_vector(
        self,
        nodes: List[str]
    ) -> Dict[str, float]:
        """
        Create uniform personalization vector over query nodes.

        Args:
            nodes: List of node IDs

        Returns:
            Dict mapping node_id -> weight (sum = 1.0)
        """
        if not nodes:
            return {}

        # Equal weight distribution
        weight = 1.0 / len(nodes)
        personalization = {node: weight for node in nodes}

        logger.debug(f"Created personalization vector: {len(nodes)} nodes")
        return personalization

    def rank_chunks_by_ppr(
        self,
        ppr_scores: Dict[str, float],
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Rank chunks by aggregated PPR scores.

        For each chunk, sum PPR scores of entities mentioned in the chunk.

        Args:
            ppr_scores: Dict of node_id -> PPR score
            top_k: Number of top results to return

        Returns:
            List of (chunk_id, score) tuples, sorted by score descending
        """
        if not ppr_scores:
            logger.warning("Empty PPR scores provided")
            return []

        chunk_scores = {}

        # Get all chunk nodes
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]

            # Only process chunk nodes
            if node_data.get('type') != 'chunk':
                continue

            # Get entities mentioned in chunk
            mentioned_entities = self._get_mentioned_entities(node_id)

            # Sum PPR scores for mentioned entities
            chunk_score = sum(
                ppr_scores.get(entity, 0.0)
                for entity in mentioned_entities
            )

            if chunk_score > 0.0:
                chunk_scores[node_id] = chunk_score

        # Sort by score descending
        ranked_chunks = sorted(
            chunk_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        logger.info(f"Ranked {len(ranked_chunks)} chunks by PPR scores")
        return ranked_chunks[:top_k]

    def _get_mentioned_entities(self, chunk_id: str) -> List[str]:
        """
        Get entities mentioned in chunk.

        Follows 'mentions' edges from chunk to entity nodes.

        Args:
            chunk_id: Chunk node ID

        Returns:
            List of entity node IDs
        """
        mentioned = []

        # Get outgoing edges from chunk
        for successor in self.graph.successors(chunk_id):
            edge_data = self.graph.get_edge_data(chunk_id, successor)

            # Check if edge type is 'mentions'
            if edge_data and edge_data.get('type') == 'mentions':
                mentioned.append(successor)

        return mentioned

    def get_entity_neighbors(
        self,
        entity_id: str,
        edge_type: Optional[str] = None
    ) -> List[str]:
        """
        Get neighboring entities connected to entity.

        Args:
            entity_id: Entity node ID
            edge_type: Optional edge type filter (e.g., 'similar_to')

        Returns:
            List of neighbor entity IDs
        """
        if not self.graph.has_node(entity_id):
            logger.warning(f"Entity not in graph: {entity_id}")
            return []

        neighbors = []

        # Get all successors
        for successor in self.graph.successors(entity_id):
            edge_data = self.graph.get_edge_data(entity_id, successor)

            # Filter by edge type if specified
            if edge_type is None or edge_data.get('type') == edge_type:
                neighbors.append(successor)

        logger.debug(f"Found {len(neighbors)} neighbors for {entity_id}")
        return neighbors

    def multi_hop_search(
        self,
        start_nodes: List[str],
        max_hops: int = 3,
        edge_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Find entities reachable within max_hops using BFS.

        Args:
            start_nodes: Starting entity node IDs
            max_hops: Maximum hops to traverse (default 3)
            edge_types: Filter by edge types (None = all types)

        Returns:
            Dict with:
                - 'entities': List of reachable entity IDs
                - 'paths': Dict mapping entity → shortest path
                - 'distances': Dict mapping entity → hop distance
        """
        try:
            # Initialize BFS structures
            queue, visited, distances, paths = self._init_bfs(start_nodes)
            entities = set(start_nodes)

            # BFS traversal
            while queue:
                current, distance, path = queue.popleft()

                # Stop if max hops reached
                if distance >= max_hops:
                    continue

                # Explore neighbors
                self._explore_neighbors(
                    current, distance, path, edge_types,
                    queue, visited, distances, paths, entities
                )

            logger.info(
                f"Multi-hop search found {len(entities)} entities "
                f"within {max_hops} hops"
            )

            return {
                'entities': list(entities),
                'paths': paths,
                'distances': distances
            }

        except Exception as e:
            logger.error(f"Multi-hop search failed: {e}")
            return {'entities': [], 'paths': {}, 'distances': {}}

    def _init_bfs(
        self,
        start_nodes: List[str]
    ) -> Tuple[deque, set, Dict[str, int], Dict[str, List[str]]]:
        """
        Initialize BFS data structures.

        Args:
            start_nodes: Starting nodes for BFS

        Returns:
            Tuple of (queue, visited, distances, paths)
        """
        queue = deque()
        visited = set()
        distances = {}
        paths = {}

        for node in start_nodes:
            if self.graph.has_node(node):
                queue.append((node, 0, [node]))
                visited.add(node)
                distances[node] = 0
                paths[node] = [node]
            else:
                logger.debug(f"Start node not in graph: {node}")

        return queue, visited, distances, paths

    def _explore_neighbors(
        self,
        current: str,
        distance: int,
        path: List[str],
        edge_types: Optional[List[str]],
        queue: deque,
        visited: set,
        distances: Dict[str, int],
        paths: Dict[str, List[str]],
        entities: set
    ) -> None:
        """
        Explore neighbors during BFS traversal.

        Args:
            current: Current node
            distance: Current distance from start
            path: Current path
            edge_types: Edge type filter
            queue: BFS queue
            visited: Visited nodes
            distances: Distance tracking
            paths: Path tracking
            entities: Entity nodes found
        """
        for neighbor in self.graph.successors(current):
            # Filter by edge type if specified
            if edge_types:
                edge_data = self.graph.get_edge_data(current, neighbor)
                if edge_data.get('type') not in edge_types:
                    continue

            # Skip if already visited
            if neighbor in visited:
                continue

            visited.add(neighbor)
            new_distance = distance + 1
            new_path = path + [neighbor]

            distances[neighbor] = new_distance
            paths[neighbor] = new_path

            # Add entity nodes to results
            node_data = self.graph.nodes[neighbor]
            if node_data.get('type') == 'entity':
                entities.add(neighbor)

            queue.append((neighbor, new_distance, new_path))

    def expand_with_synonyms(
        self,
        entity_nodes: List[str],
        max_synonyms: int = 5
    ) -> List[str]:
        """
        Expand entity list with synonyms from graph.

        Traverses SIMILAR_TO edges to find semantically similar entities.

        Args:
            entity_nodes: List of entity node IDs
            max_synonyms: Max synonyms per entity

        Returns:
            Expanded list including original nodes + synonyms
        """
        try:
            expanded = set(entity_nodes)

            for entity in entity_nodes:
                if not self.graph.has_node(entity):
                    logger.debug(f"Entity not in graph: {entity}")
                    continue

                # Find SIMILAR_TO edges
                synonym_count = 0
                for neighbor in self.graph.successors(entity):
                    edge_data = self.graph.get_edge_data(entity, neighbor)
                    if edge_data.get('type') == 'similar_to':
                        expanded.add(neighbor)
                        synonym_count += 1

                        if synonym_count >= max_synonyms:
                            break

            logger.debug(
                f"Expanded {len(entity_nodes)} entities to "
                f"{len(expanded)} with synonyms"
            )

            return list(expanded)

        except Exception as e:
            logger.error(f"Synonym expansion failed: {e}")
            return entity_nodes

    def get_entity_neighborhood(
        self,
        entity_id: str,
        hops: int = 1,
        include_chunks: bool = True
    ) -> Dict[str, List[str]]:
        """
        Get N-hop neighborhood of entity.

        Args:
            entity_id: Entity node ID
            hops: Number of hops (default 1)
            include_chunks: Include connected chunk nodes

        Returns:
            Dict with 'entities' and optionally 'chunks' lists
        """
        try:
            if not self.graph.has_node(entity_id):
                logger.warning(f"Entity not in graph: {entity_id}")
                return {'entities': [], 'chunks': []}

            # Use multi_hop_search to find neighborhood
            result = self.multi_hop_search(
                start_nodes=[entity_id],
                max_hops=hops
            )

            entities = result['entities']

            # Get connected chunks if requested
            chunks = []
            if include_chunks:
                chunks = self._get_connected_chunks(entities)

            logger.debug(
                f"Found {len(entities)} entities and "
                f"{len(chunks)} chunks in {hops}-hop neighborhood"
            )

            return {
                'entities': entities,
                'chunks': chunks
            }

        except Exception as e:
            logger.error(f"Get entity neighborhood failed: {e}")
            return {'entities': [], 'chunks': []}

    def _get_connected_chunks(self, entity_nodes: List[str]) -> List[str]:
        """
        Get chunks connected to entity nodes.

        Args:
            entity_nodes: List of entity node IDs

        Returns:
            List of chunk node IDs
        """
        chunks = set()

        for entity in entity_nodes:
            if not self.graph.has_node(entity):
                continue

            # Find chunks that mention this entity (incoming edges)
            for predecessor in self.graph.predecessors(entity):
                node_data = self.graph.nodes[predecessor]
                edge_data = self.graph.get_edge_data(predecessor, entity)

                # Check if it's a chunk mentioning the entity
                if (node_data.get('type') == 'chunk' and
                        edge_data.get('type') == 'mentions'):
                    chunks.add(predecessor)

        return list(chunks)
