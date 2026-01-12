"""
PPR Algorithms: Personalized PageRank and fallback algorithms.

Extracted from graph_query_engine.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict
import networkx as nx
from loguru import logger


class PPRAlgorithmsMixin:
    """
    Mixin providing PPR algorithm methods for GraphQueryEngine.

    Requires:
        - self.graph: NetworkX graph instance
    """

    def _ppr_fallback(
        self,
        query_nodes: List[str],
        personalization: Dict[str, float],
        alpha: float
    ) -> Dict[str, float]:
        """
        Fallback PPR with relaxed tolerance, then degree centrality.

        Args:
            query_nodes: Original query nodes
            personalization: Personalization vector
            alpha: Damping factor

        Returns:
            Dict mapping node_id -> score
        """
        # Try with higher tolerance (1e-4 instead of 1e-6)
        try:
            ppr_scores = nx.pagerank(
                self.graph,
                alpha=alpha,
                personalization=personalization,
                max_iter=200,  # More iterations
                tol=1e-4       # Relaxed tolerance
            )
            logger.info(f"PPR converged with relaxed tolerance: {len(ppr_scores)} scores")
            return ppr_scores
        except nx.PowerIterationFailedConvergence:
            logger.warning("PPR still failed, using degree centrality fallback")
            return self._degree_centrality_fallback(query_nodes)

    def _execute_pagerank(
        self,
        personalization: Dict[str, float],
        alpha: float,
        max_iter: int,
        tol: float
    ) -> Dict[str, float]:
        """
        Execute NetworkX pagerank with provided personalization.

        Args:
            personalization: Personalization vector
            alpha: Damping factor
            max_iter: Maximum iterations
            tol: Convergence tolerance

        Returns:
            Dict mapping node_id -> score
        """
        return nx.pagerank(
            self.graph,
            alpha=alpha,
            personalization=personalization,
            max_iter=max_iter,
            tol=tol
        )

    def _degree_centrality_fallback(
        self,
        query_nodes: List[str]
    ) -> Dict[str, float]:
        """
        Fallback to degree centrality when PPR fails.

        Provides reasonable ranking based on node connectivity.

        Args:
            query_nodes: Query nodes to boost

        Returns:
            Dict mapping node_id -> centrality score
        """
        try:
            # Use degree centrality as fallback
            centrality = nx.degree_centrality(self.graph)

            # Boost query nodes
            for node in query_nodes:
                if node in centrality:
                    centrality[node] *= 2.0

            # Normalize
            total = sum(centrality.values())
            if total > 0:
                centrality = {k: v / total for k, v in centrality.items()}

            logger.info(
                f"Using degree centrality fallback: {len(centrality)} scores "
                "(PPR convergence failed)"
            )
            return centrality

        except Exception as e:
            logger.error(f"Degree centrality fallback failed: {e}")
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
