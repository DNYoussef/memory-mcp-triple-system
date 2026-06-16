"""F1: Bayesian node in-degree must be capped so CPD tables stay bounded.

Without the cap a hub node with dozens of parents needs a 2^parents CPD table:
the pgmpy builder tries a 128 GiB+ allocation (CPD skipped, network lost) and
the lightweight builder enumerates 2^parents combinations in a Python loop and
hangs. These tests build a 40-parent hub and assert the result is bounded to
MAX_PARENTS - which fails (raises/hangs/exceeds) before the cap and passes after.
"""
import networkx as nx
import pytest

from src.bayesian._parent_cap import cap_in_degree, MAX_PARENTS


class TestCapHelper:
    def test_caps_to_max_parents_keeping_highest_weight(self):
        # child c has 10 parents p0..p9; weight = index, so p9..p(10-MAX) kept.
        edges = [(f"p{i}", "c") for i in range(10)]
        kept = cap_in_degree(edges, weight=lambda u, v: int(u[1:]))
        parents = sorted(u for u, v in kept if v == "c")
        assert len(parents) == MAX_PARENTS
        # highest-weight parents are the highest indices
        assert parents == sorted(f"p{i}" for i in range(10 - MAX_PARENTS, 10))

    def test_under_cap_unchanged(self):
        edges = [(f"p{i}", "c") for i in range(MAX_PARENTS)]
        kept = cap_in_degree(edges, weight=lambda u, v: 1.0)
        assert len(kept) == MAX_PARENTS

    def test_multiple_children_independent(self):
        edges = [(f"a{i}", "x") for i in range(8)] + [(f"b{i}", "y") for i in range(2)]
        kept = cap_in_degree(edges, weight=lambda u, v: 1.0)
        x_parents = [u for u, v in kept if v == "x"]
        y_parents = [u for u, v in kept if v == "y"]
        assert len(x_parents) == MAX_PARENTS
        assert len(y_parents) == 2  # under cap, untouched

    def test_equal_weights_deterministic_across_order(self):
        # All-equal weights: kept set must not depend on input edge order.
        fwd = [(f"p{i}", "c") for i in range(10)]
        rev = list(reversed(fwd))
        kept_fwd = sorted(u for u, v in cap_in_degree(fwd, weight=lambda u, v: 1.0))
        kept_rev = sorted(u for u, v in cap_in_degree(rev, weight=lambda u, v: 1.0))
        assert kept_fwd == kept_rev

    def test_custom_max_parents(self):
        edges = [(f"p{i}", "c") for i in range(10)]
        kept = cap_in_degree(edges, max_parents=2, weight=lambda u, v: 1.0)
        assert len([u for u, v in kept if v == "c"]) == 2


def _hub_graph(n_parents=40):
    g = nx.DiGraph()
    for i in range(n_parents):
        g.add_edge(f"p{i}", "hub", confidence=0.5, weight=1.0 + i)
    return g


class TestPgmpyBuilderBounded:
    def test_hub_node_capped(self):
        pytest.importorskip("pgmpy")
        from src.bayesian.network_builder import NetworkBuilder

        builder = NetworkBuilder(max_nodes=1000)
        net = builder.build_network(_hub_graph(40), use_cache=False)
        assert net is not None, "build returned None (CPD explosion lost the net)"
        max_in = max((d for _, d in net.in_degree()), default=0)
        assert max_in <= MAX_PARENTS, f"hub kept {max_in} parents, expected <= {MAX_PARENTS}"


class TestLightweightBuilderBounded:
    def test_hub_node_capped_and_fast(self):
        from src.bayesian.lightweight_network_builder import LightweightNetworkBuilder

        builder = LightweightNetworkBuilder(max_nodes=1000)
        net = builder.build_network(_hub_graph(40))
        # Completing at all proves it did not enter the 2^40 loop.
        assert net is not None
        max_in = max((len(net.get_parents(n)) for n in net.nodes()), default=0)
        assert max_in <= MAX_PARENTS, f"hub kept {max_in} parents, expected <= {MAX_PARENTS}"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
