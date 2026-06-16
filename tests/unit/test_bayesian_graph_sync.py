"""Regression tests for BayesianGraphSync edge-posterior CPD handling (MECE D8).

D8: _get_edge_posterior used `float(cpd.values.flatten()[0])`, which crashed on a
lightweight List[List[float]] CPD (plain lists have no .flatten()) and, on pgmpy
ndarray CPDs, read flatten()[0] = the state-0 cell, not the positive state. The
fix (commit fe2f9946) reads via _cpd_values_as_lists (handles ndarray-or-list, no
flatten) and _positive_state_row (correct positive cell). These tests pin both;
they were absent when D8 sat in the untested backlog.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from src.bayesian.bayesian_graph_sync import BayesianGraphSync


def _sync():
    return BayesianGraphSync(MagicMock())


class _LightweightCPD:
    """Mimics the lightweight Bayesian net CPD: plain List[List[float]] values,
    no get_values() and no .tolist() - exercises the non-ndarray branch."""

    def __init__(self, values, state_names):
        self.values = values
        self.state_names = state_names


# ---- helper-level ----


def test_positive_state_row_finds_positive_state():
    class C:
        state_names = {"B": ["false", "true"]}

    class C2:
        state_names = {"B": ["0", "1"]}

    class C3:
        state_names = {}  # no states -> default row 0

    assert BayesianGraphSync._positive_state_row(C(), "B") == 1
    assert BayesianGraphSync._positive_state_row(C2(), "B") == 1
    assert BayesianGraphSync._positive_state_row(C3(), "B") == 0


def test_cpd_values_as_lists_handles_list_and_ndarray():
    # Lightweight: list stays a list (no .flatten()).
    lw = _LightweightCPD([[0.8, 0.3], [0.2, 0.7]], {"B": ["false", "true"]})
    assert BayesianGraphSync._cpd_values_as_lists(lw) == [[0.8, 0.3], [0.2, 0.7]]

    # pgmpy: ndarray -> list of lists.
    cpd = MagicMock()
    cpd.get_values.return_value = np.array([[0.8, 0.3], [0.2, 0.7]])
    assert BayesianGraphSync._cpd_values_as_lists(cpd) == [[0.8, 0.3], [0.2, 0.7]]


# ---- end-to-end _get_edge_posterior ----


def test_get_edge_posterior_lightweight_cpd_no_flatten_crash():
    """A lightweight List[List[float]] CPD must not hit .flatten(); the positive
    state ('true', row 1) cell is returned."""
    sync = _sync()
    net = MagicMock()
    net.predecessors.return_value = ["A"]
    net.get_cpds.return_value = _LightweightCPD(
        [[0.8, 0.3], [0.2, 0.7]], {"B": ["false", "true"]}
    )

    # Positive state "true" -> row 1 -> values[1][0] = 0.2 (not the state-0 0.8).
    assert sync._get_edge_posterior(net, "A", "B") == pytest.approx(0.2)


def test_get_edge_posterior_pgmpy_reads_positive_cell_not_state0():
    """For an ndarray CPD, the positive-state cell is read - the old
    flatten()[0] read the state-0 cell (0.8) instead."""
    sync = _sync()
    net = MagicMock()
    net.predecessors.return_value = ["A"]
    cpd = MagicMock()
    arr = np.array([[0.8, 0.3], [0.2, 0.7]])
    cpd.values = arr  # what the old code used (flatten()[0] = 0.8)
    cpd.get_values.return_value = arr
    cpd.state_names = {"B": ["false", "true"]}
    net.get_cpds.return_value = cpd

    assert sync._get_edge_posterior(net, "A", "B") == pytest.approx(0.2)
