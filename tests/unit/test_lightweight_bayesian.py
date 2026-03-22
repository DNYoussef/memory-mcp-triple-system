"""Tests for lightweight Bayesian inference (no torch/pgmpy)."""
import pytest
from src.bayesian.lightweight_bayesian import (
    LightweightBayesianNetwork,
    LightweightCPD,
    LightweightVariableElimination,
    LightweightMLEstimator,
)


def test_network_creation():
    bn = LightweightBayesianNetwork([("A", "B"), ("A", "C")])
    assert set(bn.nodes()) == {"A", "B", "C"}
    assert len(bn.edges()) == 2


def test_cpd_creation():
    cpd = LightweightCPD(
        variable="A",
        variable_card=2,
        values=[[0.7], [0.3]],
        state_names={"A": ["true", "false"]},
    )
    assert cpd.variable == "A"
    assert cpd.values == [[0.7], [0.3]]


def test_model_check():
    bn = LightweightBayesianNetwork([("A", "B")])
    cpd_a = LightweightCPD("A", 2, [[0.6], [0.4]], state_names={"A": ["true", "false"]})
    cpd_b = LightweightCPD("B", 2, [[0.8, 0.2], [0.2, 0.8]],
        state_names={"B": ["true", "false"], "A": ["true", "false"]},
        evidence=["A"], evidence_card=[2])
    bn.add_cpds(cpd_a, cpd_b)
    assert bn.check_model()


def test_variable_elimination_query():
    bn = LightweightBayesianNetwork([("A", "B")])
    cpd_a = LightweightCPD("A", 2, [[0.6], [0.4]], state_names={"A": ["true", "false"]})
    cpd_b = LightweightCPD("B", 2, [[0.9, 0.1], [0.1, 0.9]],
        state_names={"B": ["true", "false"], "A": ["true", "false"]},
        evidence=["A"], evidence_card=[2])
    bn.add_cpds(cpd_a, cpd_b)

    infer = LightweightVariableElimination(bn)
    result = infer.query(["B"], evidence={"A": "true"})
    # P(B=true|A=true) should be ~0.9
    assert "B=true" in result
    assert result["B=true"] > 0.8


def test_map_query():
    bn = LightweightBayesianNetwork([("A", "B")])
    cpd_a = LightweightCPD("A", 2, [[0.6], [0.4]], state_names={"A": ["true", "false"]})
    cpd_b = LightweightCPD("B", 2, [[0.9, 0.1], [0.1, 0.9]],
        state_names={"B": ["true", "false"], "A": ["true", "false"]},
        evidence=["A"], evidence_card=[2])
    bn.add_cpds(cpd_a, cpd_b)

    infer = LightweightVariableElimination(bn)
    result = infer.map_query(["B"], evidence={"A": "true"})
    assert result.get("B") == "true"


def test_ml_estimator():
    bn = LightweightBayesianNetwork([("A", "B")])
    estimator = LightweightMLEstimator(bn)
    cpd = estimator.estimate_cpd("A")
    assert cpd.variable == "A"
    assert cpd.variable_card == 2
    assert abs(sum(row[0] for row in cpd.values) - 1.0) < 0.01


def test_probabilities_normalize():
    bn = LightweightBayesianNetwork([("A", "B"), ("A", "C")])
    for node in ["A", "B", "C"]:
        est = LightweightMLEstimator(bn)
        cpd = est.estimate_cpd(node)
        bn.add_cpds(cpd)
    
    infer = LightweightVariableElimination(bn)
    result = infer.query(["B"])
    total = sum(result.values())
    assert abs(total - 1.0) < 0.01, f"Probabilities don't sum to 1: {total}"
