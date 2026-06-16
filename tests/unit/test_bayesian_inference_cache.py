"""F2b: bayesian_inference must not rebuild the network from scratch every call.

_build_bayesian_network used to construct a fresh NetworkBuilder each call, so
the builder's graph-version cache was discarded and the net was rebuilt every
time (minutes on the real graph). It must now reuse one builder so a repeated
call on an unchanged graph is a cache hit.
"""
import networkx as nx
import pytest


def _graph_service():
    g = nx.DiGraph()
    g.add_edge("guardspine", "reactor", confidence=0.8, weight=2.0)
    g.add_edge("wilhelmina", "reactor", confidence=0.7, weight=1.5)
    g.add_edge("wilhelmina", "guardspine", confidence=0.6, weight=1.0)

    class GS:
        graph = g
    return GS()


class TestBayesianInferenceCache:
    def test_builder_is_reused_and_second_build_is_cache_hit(self):
        pytest.importorskip("pgmpy")
        from src.mcp.service_wiring import NexusSearchTool

        import threading

        class Stub:
            _network_builder = None
            _network_builder_lock = threading.Lock()

        stub = Stub()
        gs = _graph_service()

        net1 = NexusSearchTool._build_bayesian_network(stub, gs)
        assert net1 is not None
        builder1 = stub._network_builder  # set on first call
        assert builder1 is not None

        net2 = NexusSearchTool._build_bayesian_network(stub, gs)
        # Same builder reused (not a fresh one per call)...
        assert stub._network_builder is builder1
        # ...so the unchanged graph hits the builder cache: identical net object.
        assert net2 is net1

    def test_lightweight_builder_caches_by_graph_version(self):
        from src.bayesian.lightweight_network_builder import LightweightNetworkBuilder

        gs = _graph_service()
        b = LightweightNetworkBuilder(max_nodes=1000)
        n1 = b.build_network(gs.graph)
        n2 = b.build_network(gs.graph)  # unchanged graph -> cache hit
        assert n1 is not None and n2 is n1
        # a changed graph misses the cache and builds a different net
        gs.graph.add_edge("reactor", "triplecheck", weight=1.0)
        n3 = b.build_network(gs.graph)
        assert n3 is not n1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
