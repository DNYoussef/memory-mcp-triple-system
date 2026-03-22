"""
Lightweight Bayesian inference — no torch/pgmpy dependency.

Adapted for Railway deployment where torch is not available.
Implements the subset of pgmpy's API that memory-mcp actually uses:
- DAG structure with CPDs
- Variable elimination (exact inference)
- Maximum likelihood CPD estimation
- Conditional and marginal queries

This replaces pgmpy for production. Full pgmpy is used in local dev.
"""

import math
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
from itertools import product

import networkx as nx
from loguru import logger


class LightweightCPD:
    """Conditional Probability Distribution (simplified TabularCPD)."""

    def __init__(
        self,
        variable: str,
        variable_card: int,
        values: List[List[float]],
        state_names: Optional[Dict[str, List[str]]] = None,
        evidence: Optional[List[str]] = None,
        evidence_card: Optional[List[int]] = None,
    ):
        self.variable = variable
        self.variable_card = variable_card
        self.values = values  # rows = states of variable, cols = combos of evidence
        self.state_names = state_names or {variable: [str(i) for i in range(variable_card)]}
        self.evidence = evidence or []
        self.evidence_card = evidence_card or []

    def get_values(self) -> List[List[float]]:
        return self.values

    def __repr__(self) -> str:
        return f"LightweightCPD({self.variable}, card={self.variable_card}, evidence={self.evidence})"


class LightweightBayesianNetwork:
    """Drop-in replacement for pgmpy.models.BayesianNetwork."""

    def __init__(self, edges: List[Tuple[str, str]]):
        self._graph = nx.DiGraph(edges)
        self._cpds: Dict[str, LightweightCPD] = {}

    def nodes(self) -> List[str]:
        return list(self._graph.nodes())

    def edges(self) -> List[Tuple[str, str]]:
        return list(self._graph.edges())

    def add_cpds(self, *cpds: LightweightCPD) -> None:
        for cpd in cpds:
            self._cpds[cpd.variable] = cpd

    def get_cpds(self, node: Optional[str] = None):
        if node:
            return self._cpds.get(node)
        return list(self._cpds.values())

    def get_parents(self, node: str) -> List[str]:
        return list(self._graph.predecessors(node))

    def get_children(self, node: str) -> List[str]:
        return list(self._graph.successors(node))

    def check_model(self) -> bool:
        """Basic validity check: all nodes have CPDs, columns sum to ~1."""
        for node in self._graph.nodes():
            if node not in self._cpds:
                return False
            cpd = self._cpds[node]
            for col_idx in range(len(cpd.values[0]) if cpd.values else 0):
                col_sum = sum(row[col_idx] for row in cpd.values)
                if abs(col_sum - 1.0) > 0.05:
                    return False
        return True


class LightweightVariableElimination:
    """Simplified variable elimination for exact Bayesian inference."""

    def __init__(self, model: LightweightBayesianNetwork):
        self._model = model

    def query(
        self,
        variables: List[str],
        evidence: Optional[Dict[str, str]] = None,
        show_progress: bool = False,
    ) -> Dict[str, float]:
        """
        Compute P(variables | evidence) via enumeration.

        For small networks (<50 nodes), enumeration is fast enough.
        Returns dict mapping state assignments to probabilities.
        """
        evidence = evidence or {}
        all_nodes = self._model.nodes()

        # Collect state spaces
        state_spaces: Dict[str, List[str]] = {}
        for node in all_nodes:
            cpd = self._model.get_cpds(node)
            if cpd and cpd.state_names and node in cpd.state_names:
                state_spaces[node] = cpd.state_names[node]
            else:
                state_spaces[node] = ["0", "1"]

        # Hidden variables = all nodes - query vars - evidence vars
        hidden = [n for n in all_nodes if n not in variables and n not in evidence]

        # Enumerate over query variables, marginalize over hidden
        result: Dict[str, float] = {}
        query_combos = list(product(*[state_spaces.get(v, ["0", "1"]) for v in variables]))

        for combo in query_combos:
            assignment = dict(zip(variables, combo))
            assignment.update(evidence)

            # Marginalize over hidden variables
            prob = self._marginalize(assignment, hidden, state_spaces, all_nodes)
            key = ",".join(f"{v}={s}" for v, s in zip(variables, combo))
            result[key] = prob

        # Normalize
        total = sum(result.values())
        if total > 0:
            result = {k: v / total for k, v in result.items()}

        return result

    def map_query(
        self,
        variables: List[str],
        evidence: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Find most probable assignment (MAP query)."""
        posteriors = self.query(variables, evidence)
        if not posteriors:
            return {}
        best_key = max(posteriors, key=posteriors.get)
        result = {}
        for part in best_key.split(","):
            if "=" in part:
                var, state = part.split("=", 1)
                result[var] = state
        return result

    def _marginalize(
        self,
        fixed: Dict[str, str],
        hidden: List[str],
        state_spaces: Dict[str, List[str]],
        all_nodes: List[str],
    ) -> float:
        """Sum over all assignments of hidden variables."""
        if not hidden:
            return self._compute_joint(fixed, all_nodes)

        total = 0.0
        hidden_combos = product(*[state_spaces.get(h, ["0", "1"]) for h in hidden])
        for combo in hidden_combos:
            full_assignment = {**fixed, **dict(zip(hidden, combo))}
            total += self._compute_joint(full_assignment, all_nodes)
        return total

    def _compute_joint(self, assignment: Dict[str, str], all_nodes: List[str]) -> float:
        """Compute P(full assignment) = product of P(node | parents)."""
        prob = 1.0
        for node in all_nodes:
            cpd = self._model.get_cpds(node)
            if cpd is None:
                continue
            p = self._lookup_cpd(cpd, node, assignment)
            prob *= p
        return prob

    def _lookup_cpd(self, cpd: LightweightCPD, node: str, assignment: Dict[str, str]) -> float:
        """Look up P(node=state | parents=parent_states) from CPD table."""
        node_state = assignment.get(node, "0")
        states = cpd.state_names.get(node, ["0", "1"])
        try:
            row_idx = states.index(node_state)
        except ValueError:
            row_idx = 0

        if not cpd.evidence:
            # Root node: single column
            if cpd.values and row_idx < len(cpd.values):
                return cpd.values[row_idx][0] if cpd.values[row_idx] else 0.5
            return 0.5

        # Compute column index from parent assignments
        col_idx = 0
        multiplier = 1
        for ev_var, ev_card in zip(reversed(cpd.evidence), reversed(cpd.evidence_card)):
            ev_state = assignment.get(ev_var, "0")
            ev_states = cpd.state_names.get(ev_var, [str(i) for i in range(ev_card)])
            try:
                ev_idx = ev_states.index(ev_state)
            except ValueError:
                ev_idx = 0
            col_idx += ev_idx * multiplier
            multiplier *= ev_card

        if row_idx < len(cpd.values) and col_idx < len(cpd.values[row_idx]):
            return cpd.values[row_idx][col_idx]
        return 0.5


class LightweightMLEstimator:
    """Maximum Likelihood CPD estimation from data."""

    def __init__(self, model: LightweightBayesianNetwork, data=None):
        self._model = model
        self._data = data  # list of dicts

    def estimate_cpd(self, node: str) -> LightweightCPD:
        """Estimate CPD for a node using frequency counts."""
        parents = self._model.get_parents(node)
        states = ["true", "false"]

        if not parents:
            # Root node: uniform prior
            return LightweightCPD(
                variable=node,
                variable_card=2,
                values=[[0.5], [0.5]],
                state_names={node: states},
            )

        # With parents: estimate from data or use uniform
        parent_cards = [2] * len(parents)
        num_cols = 1
        for c in parent_cards:
            num_cols *= c

        values = [[1.0 / 2] * num_cols for _ in range(2)]  # Uniform prior

        if self._data:
            # Count frequencies
            counts = defaultdict(lambda: defaultdict(int))
            for row in self._data:
                parent_key = tuple(row.get(p, "false") for p in parents)
                node_val = row.get(node, "false")
                counts[parent_key][node_val] += 1

            for col_idx, parent_combo in enumerate(product(*[states] * len(parents))):
                key = tuple(parent_combo)
                total = sum(counts[key].values())
                if total > 0:
                    values[0][col_idx] = counts[key].get("true", 0) / total
                    values[1][col_idx] = counts[key].get("false", 0) / total

        state_names = {node: states}
        for p in parents:
            state_names[p] = states

        return LightweightCPD(
            variable=node,
            variable_card=2,
            values=values,
            state_names=state_names,
            evidence=parents,
            evidence_card=parent_cards,
        )


# Compatibility aliases for pgmpy API
BayesianNetwork = LightweightBayesianNetwork
VariableElimination = LightweightVariableElimination
TabularCPD = LightweightCPD
MaximumLikelihoodEstimator = LightweightMLEstimator
