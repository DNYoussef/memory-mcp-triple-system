"""F2: the Bayesian net must build OFF the fused-read hot path.

Building it synchronously inside processor construction put a full graph build
on the first read's critical path. _start_bayesian_build now backgrounds it and
wires it in via engine.set_network when ready; the Bayesian tier degrades until
then (the same state it reaches on a query timeout), so vector/HippoRAG are
never blocked on it.
"""
import os
import time

from src.mcp.service_wiring import NexusSearchTool


class _FakeEngine:
    def __init__(self):
        self.net = None

    def set_network(self, n):
        self.net = n


class _Stub:
    graph_service = object()

    def _build_bayesian_network(self, gs):
        time.sleep(0.5)  # simulate an expensive build
        return {"net": True}


def test_background_build_is_non_blocking_then_wires_in():
    os.environ.pop("MEMORY_MCP_SYNC_BAYESIAN", None)
    stub, eng = _Stub(), _FakeEngine()

    t0 = time.perf_counter()
    NexusSearchTool._start_bayesian_build(stub, eng)
    elapsed = time.perf_counter() - t0

    # returned well before the 0.5s build finished -> off the hot path
    assert elapsed < 0.3, f"start blocked for {elapsed:.2f}s (build was inline)"
    # the net is not there yet...
    assert eng.net is None
    # ...but the daemon thread wires it in once the build completes
    stub._bayesian_build_thread.join(timeout=5)
    assert eng.net == {"net": True}


def test_sync_mode_builds_inline():
    os.environ["MEMORY_MCP_SYNC_BAYESIAN"] = "1"
    try:
        stub, eng = _Stub(), _FakeEngine()
        NexusSearchTool._start_bayesian_build(stub, eng)
        assert eng.net == {"net": True}  # built synchronously, already wired in
    finally:
        os.environ.pop("MEMORY_MCP_SYNC_BAYESIAN", None)


if __name__ == "__main__":
    import sys
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
