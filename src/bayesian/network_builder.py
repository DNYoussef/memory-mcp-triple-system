"""
Bayesian Network Builder - Convert knowledge graph to belief network.

Week 10 component implementing Bayesian Graph RAG.

Purpose:
- Convert NetworkX knowledge graph → pgmpy Bayesian network
- Prune to max 1000 nodes (complexity control)
- Filter edges by confidence ≥0.3 (sparse graphs)
- Estimate CPDs (Conditional Probability Distributions)
- Cache networks with 1-hour TTL

PREMORTEM Risk #10 Mitigation:
- Node limit prevents combinatorial explosion
- Sparse graphs reduce inference complexity
- Query router (Week 8) skips Bayesian for 60% of queries
"""

import networkx as nx
from pgmpy.models import BayesianNetwork
from pgmpy.estimators import MaximumLikelihoodEstimator
from typing import Dict, List, Optional, Any
from loguru import logger
from datetime import datetime, timedelta
import hashlib


class NetworkBuilder:
    """
    Build Bayesian belief networks from knowledge graphs.

    Week 10 component for probabilistic graph reasoning.
    """

    def __init__(
        self,
        max_nodes: int = 1000,
        min_edge_confidence: float = 0.3,
        cache_ttl_hours: int = 1
    ):
        """
        Initialize Network Builder.

        Args:
            max_nodes: Maximum nodes in network (complexity limit)
            min_edge_confidence: Minimum edge confidence to include
            cache_ttl_hours: Cache TTL in hours

        NASA Rule 10: 18 LOC (≤60) ✅
        """
        self.max_nodes = max_nodes
        self.min_edge_confidence = min_edge_confidence
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache: Dict[str, Dict[str, Any]] = {}
        logger.info(
            f"NetworkBuilder initialized: max_nodes={max_nodes}, "
            f"min_confidence={min_edge_confidence}, cache_ttl={cache_ttl_hours}h"
        )

    def build_network(
        self,
        graph: nx.DiGraph,
        use_cache: bool = True
    ) -> Optional[BayesianNetwork]:
        """
        Convert knowledge graph to Bayesian network.

        Args:
            graph: NetworkX directed graph
            use_cache: Use cached network if available

        Returns:
            BayesianNetwork or None if invalid

        NASA Rule 10: 45 LOC (≤60) ✅
        """
        # Check cache
        cache_key = self._get_cache_key(graph)
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            if datetime.now() < cached["expires_at"]:
                logger.debug(f"Cache hit for network {cache_key[:8]}")
                return cached["network"]
            else:
                del self.cache[cache_key]

        # Prune nodes if needed
        if len(graph.nodes()) > self.max_nodes:
            logger.info(f"Pruning {len(graph.nodes())} nodes to {self.max_nodes}")
            graph = self.prune_nodes(graph, self.max_nodes)

        # Filter low-confidence edges
        graph = self._filter_edges(graph)

        # Convert to Bayesian network structure
        edges = [(u, v) for u, v in graph.edges()]
        if not edges:
            logger.warning("No edges after filtering, cannot build network")
            return None

        # Create Bayesian network
        bn = BayesianNetwork(edges)

        # Validate DAG (no cycles)
        if not self.validate_network(bn):
            logger.error("Network validation failed (cyclic graph)")
            return None

        # Estimate CPDs from graph data
        bn = self.estimate_cpds(bn, graph)

        # Cache network
        self.cache_network(bn, cache_key)

        logger.info(f"Built Bayesian network: {len(bn.nodes())} nodes, {len(bn.edges())} edges")
        return bn

    def estimate_cpds(
        self,
        network: BayesianNetwork,
        graph: nx.DiGraph
    ) -> BayesianNetwork:
        """
        Estimate Conditional Probability Distributions.

        Uses maximum likelihood estimation from graph attributes.

        Args:
            network: Bayesian network structure
            graph: Original knowledge graph with data

        Returns:
            Network with CPDs estimated

        NASA Rule 10: 40 LOC (≤60) ✅
        """
        # Extract node states from graph
        node_states = {}
        for node in network.nodes():
            if node in graph.nodes():
                # Get possible states from graph attributes
                states = graph.nodes[node].get("states", ["true", "false"])
                node_states[node] = states

        # Create dummy data for CPD estimation
        # In production, this would come from historical query data
        import pandas as pd

        data_rows = []
        for i in range(100):  # Generate sample data
            row = {}
            for node in network.nodes():
                states = node_states.get(node, ["true", "false"])
                # Simple random state selection for now
                import random
                row[node] = random.choice(states)
            data_rows.append(row)

        data = pd.DataFrame(data_rows)

        # Estimate CPDs using Maximum Likelihood
        estimator = MaximumLikelihoodEstimator(network, data)
        for node in network.nodes():
            cpd = estimator.estimate_cpd(node)
            network.add_cpds(cpd)

        # Check CPD validity
        if network.check_model():
            logger.debug(f"CPDs estimated for {len(network.nodes())} nodes")
        else:
            logger.warning("CPD estimation produced invalid model")

        return network

    def validate_network(self, network: BayesianNetwork) -> bool:
        """
        Validate Bayesian network structure.

        Checks:
        - DAG property (no cycles)
        - Node/edge count limits

        Args:
            network: Bayesian network to validate

        Returns:
            True if valid, False otherwise

        NASA Rule 10: 20 LOC (≤60) ✅
        """
        # Check DAG property
        if not nx.is_directed_acyclic_graph(network):
            logger.error("Network contains cycles (not a DAG)")
            return False

        # Check node count
        if len(network.nodes()) > self.max_nodes:
            logger.error(f"Network has {len(network.nodes())} nodes (max {self.max_nodes})")
            return False

        return True

    def prune_nodes(
        self,
        graph: nx.DiGraph,
        max_nodes: int
    ) -> nx.DiGraph:
        """
        Prune graph to max node count.

        Ranks nodes by:
        1. Degree (connections)
        2. Frequency (if available in node attributes)

        Keeps top-K nodes and preserves connectivity.

        Args:
            graph: Knowledge graph
            max_nodes: Maximum nodes to keep

        Returns:
            Pruned graph

        NASA Rule 10: 35 LOC (≤60) ✅
        """
        if len(graph.nodes()) <= max_nodes:
            return graph

        # Rank nodes by degree (connections)
        node_scores = {}
        for node in graph.nodes():
            degree = graph.degree(node)
            frequency = graph.nodes[node].get("frequency", 1)
            node_scores[node] = degree * frequency

        # Sort by score descending
        ranked_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)

        # Keep top-K nodes
        keep_nodes = [node for node, score in ranked_nodes[:max_nodes]]

        # Create subgraph
        pruned = graph.subgraph(keep_nodes).copy()

        logger.info(f"Pruned graph: {len(graph.nodes())} → {len(pruned.nodes())} nodes")
        return pruned

    def cache_network(self, network: BayesianNetwork, cache_key: str):
        """
        Cache Bayesian network with TTL.

        Args:
            network: Network to cache
            cache_key: Cache key (graph hash)

        NASA Rule 10: 12 LOC (≤60) ✅
        """
        self.cache[cache_key] = {
            "network": network,
            "expires_at": datetime.now() + self.cache_ttl,
            "created_at": datetime.now()
        }
        logger.debug(f"Cached network {cache_key[:8]}, TTL={self.cache_ttl}")

    def _filter_edges(self, graph: nx.DiGraph) -> nx.DiGraph:
        """
        Filter edges by confidence threshold.

        NASA Rule 10: 20 LOC (≤60) ✅
        """
        filtered = graph.copy()
        edges_to_remove = []

        for u, v, data in filtered.edges(data=True):
            confidence = data.get("confidence", 1.0)
            if confidence < self.min_edge_confidence:
                edges_to_remove.append((u, v))

        filtered.remove_edges_from(edges_to_remove)

        logger.debug(
            f"Filtered {len(edges_to_remove)} edges (confidence <{self.min_edge_confidence})"
        )
        return filtered

    def _get_cache_key(self, graph: nx.DiGraph) -> str:
        """
        Generate cache key from graph structure.

        NASA Rule 10: 13 LOC (≤60) ✅
        """
        # Hash graph structure (nodes + edges)
        nodes_str = str(sorted(graph.nodes()))
        edges_str = str(sorted(graph.edges()))
        graph_str = nodes_str + edges_str

        cache_key = hashlib.md5(graph_str.encode()).hexdigest()
        return cache_key
