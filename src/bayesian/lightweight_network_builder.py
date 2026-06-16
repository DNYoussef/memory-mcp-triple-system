"""
Lightweight NetworkBuilder — no torch/pgmpy dependency.

Drop-in replacement for network_builder.py on Railway.
Uses the lightweight_bayesian module instead of pgmpy.
"""

from typing import Dict, List, Optional, Tuple

import networkx as nx
from loguru import logger

from ._parent_cap import cap_in_degree, MAX_PARENTS
from .lightweight_bayesian import (
    LightweightBayesianNetwork,
    LightweightCPD,
    LightweightMLEstimator,
)


class LightweightNetworkBuilder:
    """Build Bayesian network from knowledge graph (no pgmpy/torch)."""

    def __init__(
        self, max_nodes: int = 50, config_path: str = "", max_parents: int = MAX_PARENTS
    ):
        self.max_nodes = max_nodes
        self.max_parents = max_parents
        self._cache: Dict[str, LightweightBayesianNetwork] = {}

    def build_network(
        self,
        graph: nx.DiGraph,
        prune: bool = True,
    ) -> Optional[LightweightBayesianNetwork]:
        """Convert knowledge graph to Bayesian network."""
        if not graph or len(graph.nodes()) == 0:
            logger.warning("Empty graph, cannot build Bayesian network")
            return None

        # F2b: cache by graph version so a repeated build on an unchanged graph
        # is a hit (the builder is reused across bayesian_inference calls).
        cache_key = self._cache_key(graph)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Filter to top nodes by degree
        nodes = sorted(graph.nodes(), key=lambda n: graph.degree(n), reverse=True)
        if len(nodes) > self.max_nodes:
            nodes = nodes[: self.max_nodes]
            subgraph = graph.subgraph(nodes).copy()
        else:
            subgraph = graph

        # Extract edges (only between selected nodes), capping in-degree so the
        # CPD estimator does not enumerate 2^(many) parent combinations and hang.
        edges = cap_in_degree(
            [(u, v) for u, v in subgraph.edges() if u in nodes and v in nodes],
            max_parents=self.max_parents,
            weight=lambda u, v: subgraph[u][v].get("weight", 1.0),
        )
        if not edges:
            logger.warning("No valid edges for Bayesian network")
            return None

        # Ensure DAG (remove back-edges via DFS)
        dag_edges = self._make_dag(edges, nodes)
        if not dag_edges:
            return None

        bn = LightweightBayesianNetwork(dag_edges)

        # Estimate CPDs
        bn = self.estimate_cpds(bn, subgraph)

        if not bn.check_model():
            logger.warning("Bayesian network validation failed")
        else:
            logger.info(
                f"Lightweight Bayesian network built: {len(bn.nodes())} nodes, {len(bn.edges())} edges"
            )
        if len(self._cache) >= 100:  # bound: drop an arbitrary old entry
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = bn  # degraded-but-usable nets are cached too
        return bn

    @staticmethod
    def _cache_key(graph: nx.DiGraph) -> str:
        """Graph-version key: structure + edge weight (the only CPD input here)."""
        import hashlib

        edges = sorted(
            (u, v, round(float(d.get("weight", 1.0)), 4))
            for u, v, d in graph.edges(data=True)
        )
        return hashlib.md5(
            (str(sorted(graph.nodes())) + str(edges)).encode()
        ).hexdigest()

    def estimate_cpds(
        self,
        network: LightweightBayesianNetwork,
        graph: nx.DiGraph,
    ) -> LightweightBayesianNetwork:
        """Estimate CPDs from graph structure."""
        estimator = LightweightMLEstimator(network)

        for node in network.nodes():
            try:
                cpd = self._estimate_node_cpd(node, network, graph)
                network.add_cpds(cpd)
            except Exception as e:
                logger.warning(f"CPD estimation failed for {node}: {e}")
                # Add uniform fallback
                cpd = estimator.estimate_cpd(node)
                network.add_cpds(cpd)

        return network

    def _estimate_node_cpd(
        self,
        node: str,
        network: LightweightBayesianNetwork,
        graph: nx.DiGraph,
    ) -> LightweightCPD:
        """Estimate CPD for a single node using graph edge weights."""
        parents = network.get_parents(node)
        states = ["true", "false"]

        if not parents:
            # Root node: probability based on graph degree
            degree = graph.degree(node) if node in graph else 1
            max_degree = max(dict(graph.degree()).values()) if graph else 1
            p_true = min(0.9, max(0.1, degree / max(max_degree, 1)))
            return LightweightCPD(
                variable=node,
                variable_card=2,
                values=[[p_true], [1.0 - p_true]],
                state_names={node: states},
            )

        # With parents: P(node|parents) based on edge weights
        parent_cards = [2] * len(parents)
        num_cols = 1
        for c in parent_cards:
            num_cols *= c

        values_true = []
        values_false = []
        from itertools import product as iter_product

        for combo in iter_product(*[range(2)] * len(parents)):
            # State index 0 = "true", index 1 = "false"
            # So count true parents as those with index 0
            num_true_parents = sum(1 for c in combo if c == 0)
            if num_true_parents == 0:
                p_true = 0.1  # No parents active → low probability
            else:
                # Scale based on fraction of active parents
                p_true = 0.1 + 0.8 * (num_true_parents / len(parents))

            # Adjust by edge weight if available
            for i, parent in enumerate(parents):
                if combo[i] == 0 and graph.has_edge(parent, node):  # 0 = "true"
                    weight = graph[parent][node].get("weight", 1.0)
                    p_true = min(0.95, p_true * (1.0 + 0.1 * weight))

            values_true.append(min(0.95, max(0.05, p_true)))
            values_false.append(min(0.95, max(0.05, 1.0 - p_true)))

        state_names = {node: states}
        for p in parents:
            state_names[p] = states

        return LightweightCPD(
            variable=node,
            variable_card=2,
            values=[values_true, values_false],
            state_names=state_names,
            evidence=parents,
            evidence_card=parent_cards,
        )

    def _make_dag(
        self, edges: List[Tuple[str, str]], nodes: List[str]
    ) -> List[Tuple[str, str]]:
        """Ensure edges form a DAG by removing back-edges."""
        g = nx.DiGraph()
        g.add_nodes_from(nodes)
        for u, v in edges:
            g.add_edge(u, v)
            if not nx.is_directed_acyclic_graph(g):
                g.remove_edge(u, v)  # Remove back-edge
        return list(g.edges())

    def validate_network(self, network: LightweightBayesianNetwork) -> bool:
        return network.check_model()

    def cache_network(self, network: LightweightBayesianNetwork, cache_key: str):
        self._cache[cache_key] = network

    def get_cached_network(
        self, cache_key: str
    ) -> Optional[LightweightBayesianNetwork]:
        return self._cache.get(cache_key)
