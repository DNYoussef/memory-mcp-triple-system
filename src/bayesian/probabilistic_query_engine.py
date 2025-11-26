"""
Probabilistic Query Engine - Execute probabilistic queries over Bayesian networks.

v0.8.0 component for Bayesian Graph RAG.

Purpose:
- Conditional probability queries: P(X|Y=y, Z=z)
- Marginal probability queries: P(X)
- MAP (Maximum A Posteriori) queries
- Uncertainty quantification (entropy)
- 1s timeout with fallback to Vector + HippoRAG

PREMORTEM Risk #10 Mitigation:
- Timeout prevents long-running queries
- Complexity controlled by network size (max 1000 nodes)
- Query router skips Bayesian for simple queries
"""

from pgmpy.models import BayesianNetwork
from pgmpy.inference import VariableElimination
from typing import Dict, List, Optional, Any
from loguru import logger
import math
from concurrent.futures import TimeoutError, ThreadPoolExecutor


class ProbabilisticQueryEngine:
    """
    Execute probabilistic queries over Bayesian networks.

    v0.8.0 component for uncertainty quantification.
    """

    def __init__(
        self,
        timeout_seconds: float = 1.0,
        network: Optional[BayesianNetwork] = None
    ):
        """
        Initialize Probabilistic Query Engine.

        Args:
            timeout_seconds: Query timeout (default 1s, fallback if exceeded)
            network: Optional pre-built Bayesian network (ISS-018 fix)

        NASA Rule 10: 15 LOC (<=60)
        """
        self.timeout_seconds = timeout_seconds
        self._network = network  # ISS-018: Store network internally
        logger.info(f"ProbabilisticQueryEngine initialized: timeout={timeout_seconds}s")

    def set_network(self, network: BayesianNetwork) -> None:
        """ISS-018 FIX: Set or update the Bayesian network."""
        self._network = network
        logger.info("Bayesian network updated")

    def query_conditional(
        self,
        network: Optional[BayesianNetwork],
        query_vars: List[str],
        evidence: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate conditional probability P(X|Y=y, Z=z).

        Args:
            network: Bayesian network (uses stored network if None - ISS-018 fix)
            query_vars: Variables to query
            evidence: Evidence dict {var: value}

        Returns:
            {
                var: {state: probability},
                entropy: float,
                timeout: False
            }
            or None if timeout

        NASA Rule 10: 55 LOC (<=60)
        """
        # ISS-018 FIX: Use stored network if none provided
        effective_network = network if network is not None else self._network
        if effective_network is None:
            logger.warning("No Bayesian network available (pass network or call set_network)")
            return None

        if evidence is None:
            evidence = {}

        # Execute with timeout
        result = self.execute_with_timeout(
            lambda: self._query_conditional_impl(effective_network, query_vars, evidence)
        )

        if result is None:
            logger.warning(
                f"Conditional query timeout ({self.timeout_seconds}s): "
                f"vars={query_vars}, evidence={evidence}"
            )
            return None

        return result

    def query_marginal(
        self,
        network: BayesianNetwork,
        query_vars: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate marginal probability P(X).

        Marginalizes over all other variables.

        Args:
            network: Bayesian network
            query_vars: Variables to query

        Returns:
            {var: {state: probability}, entropy: float}
            or None if timeout

        NASA Rule 10: 30 LOC (≤60) ✅
        """
        # Marginal is just conditional with no evidence
        return self.query_conditional(network, query_vars, evidence={})

    def get_most_probable_explanation(
        self,
        network: BayesianNetwork,
        evidence: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Find MAP (Maximum A Posteriori) assignment.

        Given evidence, find most likely values for remaining variables.

        Args:
            network: Bayesian network
            evidence: Evidence dict {var: value}

        Returns:
            {
                var: value,
                probability: float,
                timeout: False
            }
            or None if timeout

        NASA Rule 10: 45 LOC (≤60) ✅
        """
        result = self.execute_with_timeout(
            lambda: self._map_query_impl(network, evidence)
        )

        if result is None:
            logger.warning(f"MAP query timeout ({self.timeout_seconds}s): evidence={evidence}")
            return None

        return result

    def calculate_entropy(self, prob_dist: Dict[str, float]) -> float:
        """
        Calculate Shannon entropy H(X) = -Σ p(x) log₂ p(x).

        Measures uncertainty:
        - Low entropy: certain (e.g., {A: 0.95, B: 0.05})
        - High entropy: uncertain (e.g., {A: 0.5, B: 0.5})

        Args:
            prob_dist: Probability distribution {state: prob}

        Returns:
            Entropy in bits

        NASA Rule 10: 20 LOC (≤60) ✅
        """
        entropy = 0.0
        for prob in prob_dist.values():
            if prob > 0:  # Avoid log(0)
                entropy -= prob * math.log2(prob)

        return entropy

    def execute_with_timeout(
        self,
        query_func,
        timeout: Optional[float] = None
    ) -> Optional[Any]:
        """
        Execute query with timeout.

        If timeout exceeded, return None (signals fallback to Vector + HippoRAG).

        Args:
            query_func: Function to execute
            timeout: Timeout in seconds (default: self.timeout_seconds)

        Returns:
            Query result or None if timeout

        NASA Rule 10: 22 LOC (≤60) ✅
        """
        if timeout is None:
            timeout = self.timeout_seconds

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(query_func)
                result = future.result(timeout=timeout)
                return result
        except TimeoutError:
            logger.warning(f"Query timeout after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return None

    def _query_conditional_impl(
        self,
        network: BayesianNetwork,
        query_vars: List[str],
        evidence: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Internal implementation of conditional query.

        NASA Rule 10: 35 LOC (≤60) ✅
        """
        # Create inference engine
        infer = VariableElimination(network)

        # Query each variable
        results = {}
        for var in query_vars:
            # Query probability distribution
            phi = infer.query(variables=[var], evidence=evidence)

            # Extract probabilities
            prob_dist = {}
            for i, state in enumerate(phi.state_names[var]):
                prob_dist[state] = phi.values[i]

            # Calculate entropy
            entropy = self.calculate_entropy(prob_dist)

            results[var] = {
                "probabilities": prob_dist,
                "entropy": entropy
            }

        return {
            "results": results,
            "evidence": evidence,
            "timeout": False
        }

    def _map_query_impl(
        self,
        network: BayesianNetwork,
        evidence: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Internal implementation of MAP query.

        NASA Rule 10: 30 LOC (≤60) ✅
        """
        # Create inference engine
        infer = VariableElimination(network)

        # Get MAP assignment
        map_assignment = infer.map_query(variables=None, evidence=evidence)

        # Calculate probability of MAP assignment
        # Query P(MAP|evidence)
        full_evidence = {**evidence, **map_assignment}
        prob = self._calculate_assignment_probability(network, full_evidence)

        return {
            "assignment": map_assignment,
            "probability": prob,
            "evidence": evidence,
            "timeout": False
        }

    def _calculate_assignment_probability(
        self,
        network: BayesianNetwork,
        assignment: Dict[str, str]
    ) -> float:
        """
        Calculate probability of full assignment.

        NASA Rule 10: 20 LOC (≤60) ✅
        """
        # Query probability of assignment
        infer = VariableElimination(network)

        # For each variable, query P(var|parents)
        prob = 1.0
        for var in assignment:
            # Get parents
            parents = list(network.predecessors(var))
            parent_evidence = {p: assignment[p] for p in parents if p in assignment}

            # Query P(var|parents)
            phi = infer.query(variables=[var], evidence=parent_evidence)
            var_state = assignment[var]
            state_idx = phi.state_names[var].index(var_state)
            prob *= phi.values[state_idx]

        return prob
