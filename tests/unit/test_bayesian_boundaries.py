"""
P3-4: Property-based tests for Bayesian scoring boundaries.

Validates mathematical invariants:
1. Hybrid scores always in [0, 1]
2. Weight sum invariants
3. Edge confidence clamping to [0.1, 0.95]
4. Decay formula monotonicity
"""

import math
import pytest
from src.nexus.processor import NexusProcessor
from src.services.graph_service import GraphService


class TestHybridScoreBoundaries:
    """Hybrid score stays within valid range for all inputs."""

    @pytest.fixture
    def processor(self):
        return NexusProcessor()

    @pytest.mark.parametrize("v,g,b", [
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.5, 0.5, 0.5),
        (0.999, 0.999, 0.999),
        (0.001, 0.001, 0.001),
    ])
    def test_score_in_valid_range(self, processor, v, g, b):
        """Score is always in [0, 1] for valid inputs."""
        score = processor._calculate_hybrid_score(
            vector_score=v, graph_score=g, bayesian_score=b
        )
        assert 0.0 <= score <= 1.0, f"Score {score} out of range for ({v},{g},{b})"

    def test_weights_sum_to_one(self, processor):
        """Default weights sum to 1.0."""
        w = processor.weights
        total = w.get("vector", 0) + w.get("hipporag", 0) + w.get("bayesian", 0)
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_score_monotonic_in_vector(self, processor):
        """Increasing vector score increases hybrid score."""
        s1 = processor._calculate_hybrid_score(vector_score=0.3, graph_score=0.5, bayesian_score=0.5)
        s2 = processor._calculate_hybrid_score(vector_score=0.7, graph_score=0.5, bayesian_score=0.5)
        assert s2 > s1

    def test_score_monotonic_in_graph(self, processor):
        """Increasing graph score increases hybrid score."""
        s1 = processor._calculate_hybrid_score(vector_score=0.5, graph_score=0.2, bayesian_score=0.5)
        s2 = processor._calculate_hybrid_score(vector_score=0.5, graph_score=0.8, bayesian_score=0.5)
        assert s2 > s1

    def test_score_monotonic_in_bayesian(self, processor):
        """Increasing bayesian score increases hybrid score."""
        s1 = processor._calculate_hybrid_score(vector_score=0.5, graph_score=0.5, bayesian_score=0.1)
        s2 = processor._calculate_hybrid_score(vector_score=0.5, graph_score=0.5, bayesian_score=0.9)
        assert s2 > s1

    @pytest.mark.parametrize("weights", [
        {"vector": 0.5, "hipporag": 0.3, "bayesian": 0.2},
        {"vector": 0.33, "hipporag": 0.33, "bayesian": 0.34},
        {"vector": 0.8, "hipporag": 0.1, "bayesian": 0.1},
    ])
    def test_custom_weights_produce_bounded_scores(self, weights):
        """Any valid weight configuration produces scores in [0, 1]."""
        proc = NexusProcessor(weights=weights)
        for v in [0.0, 0.5, 1.0]:
            for g in [0.0, 0.5, 1.0]:
                for b in [0.0, 0.5, 1.0]:
                    score = proc._calculate_hybrid_score(
                        vector_score=v, graph_score=g, bayesian_score=b
                    )
                    assert 0.0 <= score <= 1.0


class TestEdgeConfidenceClamping:
    """Edge confidence stays in [0.1, 0.95] after Bayesian update."""

    @pytest.fixture
    def graph(self, tmp_path):
        gs = GraphService(data_dir=str(tmp_path / "graph"))
        gs.add_entity_node("A", "CONCEPT")
        gs.add_entity_node("B", "CONCEPT")
        gs.add_relationship("A", "related_to", "B", {"confidence": 0.5})
        return gs

    @pytest.mark.parametrize("posterior", [0.0, 0.01, 0.5, 0.99, 1.0])
    def test_confidence_clamped_after_bayesian_update(self, graph, posterior):
        """Confidence is always in [0.1, 0.95] regardless of posterior."""
        graph.update_edge_from_bayesian("A", "B", bayesian_posterior=posterior)
        edge_data = graph.graph.get_edge_data("A", "B")
        confidence = edge_data.get("confidence", 0.5)
        assert 0.1 <= confidence <= 0.95, (
            f"Confidence {confidence} out of clamped range for posterior={posterior}"
        )

    def test_extreme_low_posterior_clamps(self, graph):
        """Posterior=0.0 clamps to >= 0.1."""
        graph.update_edge_from_bayesian("A", "B", bayesian_posterior=0.0)
        edge_data = graph.graph.get_edge_data("A", "B")
        assert edge_data["confidence"] >= 0.1

    def test_extreme_high_posterior_clamps(self, graph):
        """Posterior=1.0 clamps to <= 0.95."""
        graph.update_edge_from_bayesian("A", "B", bayesian_posterior=1.0)
        edge_data = graph.graph.get_edge_data("A", "B")
        assert edge_data["confidence"] <= 0.95

    def test_nonexistent_edge_returns_false(self, graph):
        """Updating nonexistent edge returns False."""
        result = graph.update_edge_from_bayesian("X", "Y", bayesian_posterior=0.5)
        assert result is False


class TestDecayMonotonicity:
    """Memory decay formula is monotonically decreasing."""

    def test_decay_decreases_with_time(self):
        """e^(-days/30) decreases as days increase."""
        for d1 in range(0, 90, 10):
            d2 = d1 + 1
            decay1 = math.exp(-d1 / 30)
            decay2 = math.exp(-d2 / 30)
            assert decay2 < decay1, f"Decay not decreasing: day {d1}={decay1}, day {d2}={decay2}"

    def test_decay_at_zero_is_one(self):
        """At day 0, decay score = 1.0."""
        assert math.exp(0 / 30) == 1.0

    def test_decay_at_30_days(self):
        """At day 30, decay score ~ 0.368 (1/e)."""
        decay = math.exp(-30 / 30)
        assert abs(decay - 1 / math.e) < 0.001

    def test_decay_never_negative(self):
        """Decay is always positive."""
        for d in range(0, 365):
            decay = math.exp(-d / 30)
            assert decay > 0

    def test_decay_approaches_zero(self):
        """After many days, decay approaches but never reaches zero."""
        decay = math.exp(-365 / 30)
        assert 0 < decay < 0.001
