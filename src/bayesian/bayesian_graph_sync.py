"""
Bayesian Graph Sync - Bidirectional synchronization between graph and Bayesian network.

BAY-004: Closes the feedback loop between Bayesian inference and graph confidence.

Purpose:
- Update graph edge confidence from Bayesian posteriors
- Propagate graph changes to Bayesian network
- Maintain consistency between both representations

Formula (BAY-003):
    new_confidence = 0.7 * prior + 0.3 * posterior
    Clamped to [0.1, 0.95] to prevent certainty

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, List, Optional, Tuple
from loguru import logger


class BayesianGraphSync:
    """
    Synchronizes confidence between Bayesian inference and knowledge graph.

    Provides bidirectional update:
    - Graph -> Bayesian: Edge confidence feeds CPD estimation
    - Bayesian -> Graph: Posterior probabilities update edge confidence
    """

    # Default weights for confidence update formula
    DEFAULT_PRIOR_WEIGHT = 0.7
    DEFAULT_POSTERIOR_WEIGHT = 0.3

    # Confidence bounds to prevent certainty
    MIN_CONFIDENCE = 0.1
    MAX_CONFIDENCE = 0.95

    def __init__(
        self,
        graph_service: Any,
        prior_weight: float = DEFAULT_PRIOR_WEIGHT,
        posterior_weight: float = DEFAULT_POSTERIOR_WEIGHT,
    ):
        """
        Initialize Bayesian Graph Sync.

        Args:
            graph_service: GraphService instance for edge updates
            prior_weight: Weight for historical confidence (default 0.7)
            posterior_weight: Weight for Bayesian posterior (default 0.3)

        NASA Rule 10: 12 LOC (<=60)
        """
        self.graph_service = graph_service
        self.prior_weight = prior_weight
        self.posterior_weight = posterior_weight
        logger.info(
            f"BayesianGraphSync initialized: "
            f"prior_weight={prior_weight}, posterior_weight={posterior_weight}"
        )

    def update_graph_from_inference(
        self,
        inference_results: Dict[str, Any],
        query_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update graph edge confidence from Bayesian inference results.

        BAY-002: Called after Bayesian tier query completes.

        Args:
            inference_results: Results from ProbabilisticQueryEngine.query_conditional()
                {
                    "results": {var: {"probabilities": {...}, "entropy": float}},
                    "evidence": {...},
                    "timeout": False
                }
            query_context: Optional context with related edges to update

        Returns:
            {
                "edges_updated": int,
                "updates": [(source, target, old_conf, new_conf), ...],
                "skipped": int
            }

        NASA Rule 10: 45 LOC (<=60)
        """
        if not inference_results or inference_results.get("timeout"):
            logger.debug("No inference results to sync (timeout or empty)")
            return {"edges_updated": 0, "updates": [], "skipped": 0}

        results = inference_results.get("results", {})
        evidence = inference_results.get("evidence", {})
        updates = []
        skipped = 0

        # Process each queried variable
        for var, prob_data in results.items():
            probabilities = prob_data.get("probabilities", {})

            # Find edges related to this variable
            related_edges = self._find_related_edges(var, evidence)

            for source, target in related_edges:
                # Get posterior for positive state across pgmpy/lightweight encodings.
                posterior = self._positive_state_probability(probabilities)

                # Update edge confidence
                success = self.graph_service.update_edge_from_bayesian(
                    source=source,
                    target=target,
                    bayesian_posterior=posterior,
                    prior_weight=self.prior_weight,
                    posterior_weight=self.posterior_weight,
                )

                if success:
                    edge_data = self.graph_service.graph.get_edge_data(source, target)
                    new_conf = edge_data.get("confidence", 0.5)
                    updates.append((source, target, posterior, new_conf))
                else:
                    skipped += 1

        logger.info(
            f"BayesianGraphSync: {len(updates)} edges updated, {skipped} skipped"
        )

        return {"edges_updated": len(updates), "updates": updates, "skipped": skipped}

    @staticmethod
    def _positive_state_probability(probabilities: Dict[Any, Any]) -> float:
        """Return P(positive) for common state encodings."""
        for key in ("true", True, "1", 1, "yes", "present"):
            value = probabilities.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return 0.5

    def _find_related_edges(
        self, variable: str, evidence: Dict[str, str]
    ) -> List[Tuple[str, str]]:
        """
        Find graph edges related to a Bayesian variable.

        Looks for edges where:
        - Source or target matches variable name
        - Variable is mentioned in edge metadata

        Args:
            variable: Bayesian network variable name
            evidence: Evidence dict from query

        Returns:
            List of (source, target) tuples

        NASA Rule 10: 30 LOC (<=60)
        """
        related = []
        graph = self.graph_service.graph

        # Check if variable exists as a node
        if variable in graph:
            # Get all edges connected to this node
            for neighbor in graph.neighbors(variable):
                related.append((variable, neighbor))
            for predecessor in graph.predecessors(variable):
                related.append((predecessor, variable))

        # Also check edges where variable appears in evidence
        for evidence_var in evidence.keys():
            if evidence_var in graph:
                for neighbor in graph.neighbors(evidence_var):
                    edge = (evidence_var, neighbor)
                    if edge not in related:
                        related.append(edge)

        return related

    def sync_all_edges(
        self, bayesian_network: Any, threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        Batch sync all graph edges from Bayesian network CPDs.

        Used for periodic full synchronization.

        Args:
            bayesian_network: pgmpy BayesianNetwork with CPDs
            threshold: Minimum probability change to trigger update

        Returns:
            {
                "total_edges": int,
                "updated": int,
                "unchanged": int
            }

        NASA Rule 10: 40 LOC (<=60)
        """
        if bayesian_network is None:
            logger.warning("Cannot sync: Bayesian network is None")
            return {"total_edges": 0, "updated": 0, "unchanged": 0}

        updated = 0
        unchanged = 0
        graph = self.graph_service.graph

        for source, target in graph.edges():
            # Check if both nodes exist in Bayesian network
            if (
                source not in bayesian_network.nodes()
                or target not in bayesian_network.nodes()
            ):
                unchanged += 1
                continue

            # Get CPD probability for this edge relationship
            try:
                posterior = self._get_edge_posterior(bayesian_network, source, target)

                if posterior is not None:
                    success = self.graph_service.update_edge_from_bayesian(
                        source=source,
                        target=target,
                        bayesian_posterior=posterior,
                        prior_weight=self.prior_weight,
                        posterior_weight=self.posterior_weight,
                    )
                    if success:
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    unchanged += 1
            except Exception as e:
                logger.debug(f"CPD lookup failed for {source}->{target}: {e}")
                unchanged += 1

        logger.info(f"Full sync complete: {updated} updated, {unchanged} unchanged")

        return {
            "total_edges": graph.number_of_edges(),
            "updated": updated,
            "unchanged": unchanged,
        }

    def _get_edge_posterior(
        self, network: Any, source: str, target: str
    ) -> Optional[float]:
        """
        Get posterior probability for edge relationship from Bayesian network.

        Args:
            network: pgmpy BayesianNetwork
            source: Source node ID
            target: Target node ID

        Returns:
            Posterior probability or None if unavailable

        NASA Rule 10: 20 LOC (<=60)
        """
        try:
            # Check if target has source as parent
            if source in network.predecessors(target):
                cpd = network.get_cpds(target)
                if cpd is not None:
                    values = self._cpd_values_as_lists(cpd)
                    if values:
                        row = self._positive_state_row(cpd, target)
                        return float(values[row][0])
            return None
        except Exception as e:
            logger.debug(f"CPD extraction failed: {e}")
            return None

    @staticmethod
    def _cpd_values_as_lists(cpd: Any) -> List[List[float]]:
        """Return CPD values as a two-dimensional list."""
        values = cpd.get_values() if hasattr(cpd, "get_values") else cpd.values
        if hasattr(values, "tolist"):
            values = values.tolist()
        if values and not isinstance(values[0], list):
            return [values]
        return values

    @staticmethod
    def _positive_state_row(cpd: Any, variable: str) -> int:
        """Find the CPD row for the positive state."""
        state_names = getattr(cpd, "state_names", {}) or {}
        states = state_names.get(variable, [])
        for key in ("true", True, "1", 1, "yes", "present"):
            if key in states:
                return states.index(key)
        return 0

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current synchronization status.

        Returns graph statistics relevant to Bayesian sync.

        NASA Rule 10: 15 LOC (<=60)
        """
        graph = self.graph_service.graph

        # Count edges with Bayesian-updated confidence
        edges_with_conf = 0
        total_confidence = 0.0

        for _, _, data in graph.edges(data=True):
            conf = data.get("confidence", 0.5)
            if conf != 0.5:  # Non-default confidence
                edges_with_conf += 1
            total_confidence += conf

        avg_confidence = total_confidence / max(1, graph.number_of_edges())

        return {
            "total_edges": graph.number_of_edges(),
            "edges_with_custom_confidence": edges_with_conf,
            "average_confidence": round(avg_confidence, 3),
            "prior_weight": self.prior_weight,
            "posterior_weight": self.posterior_weight,
        }
