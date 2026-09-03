"""
Lightweight Probabilistic Query Engine — no torch/pgmpy dependency.

Drop-in replacement for probabilistic_query_engine.py on Railway.
Uses lightweight_bayesian module for inference.
"""

import math
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from loguru import logger

from .lightweight_bayesian import (
    LightweightBayesianNetwork,
    LightweightVariableElimination,
)


class LightweightQueryEngine:
    """Probabilistic query engine using lightweight Bayesian inference."""

    def __init__(
        self,
        network: Optional[LightweightBayesianNetwork] = None,
        timeout_seconds: float = 10.0,
    ):
        self._network = network
        self._timeout = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=2)

    def close(self) -> None:
        self._executor.shutdown(wait=False)

    def set_network(self, network: LightweightBayesianNetwork) -> None:
        self._network = network

    def query_conditional(
        self,
        network: Optional[LightweightBayesianNetwork] = None,
        query_vars: Optional[List[str]] = None,
        evidence: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Compute P(query_variables | evidence).
        Returns dict of {assignment: probability}.
        """
        net = network if network is not None else self._network
        if net is None:
            logger.warning("No Bayesian network available")
            return None

        evidence = evidence or {}
        valid_query = [v for v in (query_vars or []) if v in net.nodes()]
        valid_evidence = {k: v for k, v in evidence.items() if k in net.nodes()}

        if not valid_query:
            return None

        try:
            infer = LightweightVariableElimination(net)
            results = {}
            for var in valid_query:
                distribution = self.execute_with_timeout(infer.query, [var], valid_evidence)
                if distribution is None:
                    return None
                probabilities = {key.split("=", 1)[-1]: value for key, value in distribution.items()}
                results[var] = {
                    "probabilities": probabilities,
                    "entropy": self.calculate_entropy(probabilities),
                }
            return {"results": results, "evidence": valid_evidence, "timeout": False}
        except Exception as e:
            logger.error(f"Conditional query failed: {e}")
            return None

    def query_marginal(
        self,
        network: Optional[LightweightBayesianNetwork] = None,
        query_vars: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Compute marginal P(variables) without evidence."""
        return self.query_conditional(network, query_vars, evidence={})

    def get_most_probable_explanation(
        self,
        network: Optional[LightweightBayesianNetwork] = None,
        evidence: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find MAP assignment given evidence."""
        net = network if network is not None else self._network
        if net is None:
            return None

        evidence = evidence or {}
        valid_evidence = {k: v for k, v in evidence.items() if k in net.nodes()}
        query_vars = [n for n in net.nodes() if n not in valid_evidence]

        if not query_vars:
            return {"assignment": {}, "probability": 1.0, "evidence": valid_evidence, "timeout": False}

        try:
            infer = LightweightVariableElimination(net)
            assignment = self.execute_with_timeout(infer.map_query, query_vars, valid_evidence)
            if assignment is None:
                return None
            distribution = infer.query(query_vars, valid_evidence)
            probability = max(distribution.values(), default=0.0)
            return {"assignment": assignment, "probability": probability, "evidence": valid_evidence, "timeout": False}
        except Exception as e:
            logger.error(f"MAP query failed: {e}")
            return None

    def calculate_entropy(self, prob_dist: Dict[str, float]) -> float:
        """Calculate Shannon entropy of a probability distribution."""
        entropy = 0.0
        for p in prob_dist.values():
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def execute_with_timeout(self, func, *args, **kwargs):
        """Execute inference with timeout protection."""
        future = self._executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=self._timeout)
        except FuturesTimeoutError:
            logger.warning(f"Bayesian query timed out after {self._timeout}s")
            future.cancel()
            return None
        except Exception as e:
            logger.error(f"Bayesian query error: {e}")
            return None
