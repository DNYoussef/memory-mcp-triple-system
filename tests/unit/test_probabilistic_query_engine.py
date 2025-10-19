"""
Unit tests for Probabilistic Query Engine.

Week 10 component - Tests conditional/marginal queries, MAP, entropy.

Target: 10 tests, ~240 LOC
"""

import pytest
import networkx as nx
from src.bayesian.network_builder import NetworkBuilder
from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine
from pgmpy.models import BayesianNetwork
from pgmpy.factors.discrete import TabularCPD


class TestProbabilisticQueryEngine:
    """Test suite for ProbabilisticQueryEngine."""

    @pytest.fixture
    def engine(self):
        """Create ProbabilisticQueryEngine instance."""
        return ProbabilisticQueryEngine(timeout_seconds=2.0)

    @pytest.fixture
    def simple_network(self):
        """Create simple Bayesian network for testing."""
        # Create network: A → B → C
        network = BayesianNetwork([("A", "B"), ("B", "C")])

        # Add CPDs
        cpd_a = TabularCPD("A", 2, [[0.6], [0.4]])
        cpd_b = TabularCPD(
            "B",
            2,
            [[0.7, 0.3], [0.3, 0.7]],
            evidence=["A"],
            evidence_card=[2],
        )
        cpd_c = TabularCPD(
            "C",
            2,
            [[0.8, 0.2], [0.2, 0.8]],
            evidence=["B"],
            evidence_card=[2],
        )

        network.add_cpds(cpd_a, cpd_b, cpd_c)
        assert network.check_model()

        return network

    def test_initialization(self, engine):
        """Test ProbabilisticQueryEngine initialization."""
        assert engine.timeout_seconds == 2.0

    def test_query_conditional_simple(self, engine, simple_network):
        """Test P(X|Y=y) conditional probability."""
        result = engine.query_conditional(
            network=simple_network,
            query_vars=["C"],
            evidence={"B": 0},
        )

        assert result is not None
        assert "results" in result
        assert "C" in result["results"]
        assert "probabilities" in result["results"]["C"]
        assert "entropy" in result["results"]["C"]

    def test_query_marginal(self, engine, simple_network):
        """Test P(X) marginal probability."""
        result = engine.query_marginal(network=simple_network, query_vars=["C"])

        assert result is not None
        assert "results" in result
        assert "C" in result["results"]

    def test_calculate_entropy(self, engine):
        """Test entropy calculation."""
        # Low entropy (certain)
        low_entropy_dist = {0: 0.95, 1: 0.05}
        entropy_low = engine.calculate_entropy(low_entropy_dist)

        # High entropy (uncertain)
        high_entropy_dist = {0: 0.5, 1: 0.5}
        entropy_high = engine.calculate_entropy(high_entropy_dist)

        assert entropy_high > entropy_low
        assert entropy_low < 0.5  # Low uncertainty
        assert entropy_high > 0.9  # High uncertainty (close to 1.0 for binary)

    def test_most_probable_explanation(self, engine, simple_network):
        """Test MAP (Maximum A Posteriori) query."""
        result = engine.get_most_probable_explanation(
            network=simple_network, evidence={"A": 0}
        )

        assert result is not None
        assert "assignment" in result
        assert "probability" in result
        assert isinstance(result["assignment"], dict)

    def test_timeout_fallback(self, engine):
        """Test 1s timeout triggers fallback (returns None)."""
        # Create engine with very short timeout
        fast_engine = ProbabilisticQueryEngine(timeout_seconds=0.001)

        # Create complex network (slow query)
        large_network = BayesianNetwork()
        for i in range(20):
            large_network.add_node(f"node_{i}")

        # This should timeout
        def slow_query():
            import time
            time.sleep(0.1)
            return {"result": "slow"}

        result = fast_engine.execute_with_timeout(slow_query, timeout=0.001)

        assert result is None  # Timeout

    def test_multiple_evidence_vars(self, engine, simple_network):
        """Test P(X|Y=y, Z=z) with multiple evidence variables."""
        result = engine.query_conditional(
            network=simple_network,
            query_vars=["C"],
            evidence={"A": 0, "B": 1},
        )

        assert result is not None
        assert len(result["evidence"]) == 2

    def test_query_all_states(self, engine, simple_network):
        """Test that all probability states are returned."""
        result = engine.query_conditional(
            network=simple_network, query_vars=["C"], evidence={}
        )

        assert result is not None
        probs = result["results"]["C"]["probabilities"]

        # Should have probabilities for both states (0 and 1)
        assert len(probs) == 2
        # Probabilities should sum to ~1.0
        total_prob = sum(probs.values())
        assert abs(total_prob - 1.0) < 0.01

    def test_uncertainty_high_entropy(self, engine):
        """Test high entropy detection for uncertain distributions."""
        # Maximum uncertainty for binary variable
        uniform_dist = {0: 0.5, 1: 0.5}
        entropy = engine.calculate_entropy(uniform_dist)

        # Entropy should be 1.0 for uniform binary distribution
        assert abs(entropy - 1.0) < 0.01

    def test_query_performance(self, engine, simple_network):
        """Test query performance <1s."""
        import time

        start = time.time()
        result = engine.query_conditional(
            network=simple_network, query_vars=["C"], evidence={"A": 0}
        )
        elapsed = time.time() - start

        assert result is not None
        assert elapsed < 1.0  # Should be fast for simple network


# NASA Rule 10 Compliance Check
def test_nasa_rule_10_compliance():
    """Verify all ProbabilisticQueryEngine methods are ≤60 LOC."""
    import ast

    with open(
        "src/bayesian/probabilistic_query_engine.py", "r", encoding="utf-8"
    ) as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = node.end_lineno - node.lineno + 1
            assert func_lines <= 60, f"{node.name} exceeds 60 LOC ({func_lines})"
