"""
Lightweight Probabilistic Query Engine — no torch/pgmpy dependency.

Drop-in replacement for probabilistic_query_engine.py on Railway.
Uses lightweight_bayesian module for inference.
"""

import math
import asyncio
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
        query_variables: List[str],
        evidence: Dict[str, str],
        network: Optional[LightweightBayesianNetwork] = None,
    ) -> Dict[str, float]:
        """
        Compute P(query_variables | evidence).
        Returns dict of {assignment: probability}.
        """
        net = network or self._network
        if net is None:
            logger.warning("No Bayesian network available")
            return {}

        # Filter to variables that exist in the network
        valid_query = [v for v in query_variables if v in net.nodes()]
        valid_evidence = {k: v for k, v in evidence.items() if k in net.nodes()}

        if not valid_query:
            return {}

        try:
            infer = LightweightVariableElimination(net)
            return self.execute_with_timeout(
                infer.query, valid_query, valid_evidence
            )
        except Exception as e:
            logger.error(f"Conditional query failed: {e}")
            return {}

    def query_marginal(
        self,
        variables: List[str],
        network: Optional[LightweightBayesianNetwork] = None,
    ) -> Dict[str, float]:
        """Compute marginal P(variables) without evidence."""
        return self.query_conditional(variables, {}, network)

    def get_most_probable_explanation(
        self,
        evidence: Dict[str, str],
        network: Optional[LightweightBayesianNetwork] = None,
    ) -> Dict[str, str]:
        """Find MAP assignment given evidence."""
        net = network or self._network
        if net is None:
            return {}

        valid_evidence = {k: v for k, v in evidence.items() if k in net.nodes()}
        query_vars = [n for n in net.nodes() if n not in valid_evidence]

        if not query_vars:
            return valid_evidence

        try:
            infer = LightweightVariableElimination(net)
            return self.execute_with_timeout(
                infer.map_query, query_vars, valid_evidence
            )
        except Exception as e:
            logger.error(f"MAP query failed: {e}")
            return {}

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
            return {}
        except Exception as e:
            logger.error(f"Bayesian query error: {e}")
            return {}
