#!/usr/bin/env python
"""Check request-local tier degradation propagation across both transports."""

from concurrent.futures import ThreadPoolExecutor
import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
GATE_ID = "P1c"
TOKEN = "TIER_DEGRADATION_OK causes=3 stdio_handlers=5 stdio_all_down_error=5 tri_tier_http_routes=3 http_all_down_503=3 unified_top_level=1 clean=1 no_processor=1 processor_exception=1 threads=4 concurrent_leak=0"


def probe(fixture) -> bool:
    expected = {
        "causes": 3,
        "stdio_handlers": 5,
        "stdio_all_down": 5,
        "http_routes": 3,
        "http_503": 3,
        "unified_top": True,
        "clean": True,
        "no_processor": True,
        "processor_exception": True,
        "threads": 4,
        "leaks": 0,
    }
    return fixture == expected


def _planted_bad_fixture():
    good = {
        "causes": 3,
        "stdio_handlers": 5,
        "stdio_all_down": 5,
        "http_routes": 3,
        "http_503": 3,
        "unified_top": True,
        "clean": True,
        "no_processor": True,
        "processor_exception": True,
        "threads": 4,
        "leaks": 0,
    }
    return [{**good, key: (not value if isinstance(value, bool) else value + 1)} for key, value in good.items()]


def _real_fixture():
    from src.mcp.service_wiring import NexusSearchTool
    from src.nexus.tier_queries import TierQueryMixin

    root = Path(__file__).resolve().parents[2]
    mixin = TierQueryMixin()
    mixin.vector_indexer = None
    mixin.embedding_pipeline = None
    missing = {}
    mixin._query_vector_tier("q", 1, missing)
    mixin.graph_query_engine = MagicMock()
    mixin.graph_query_engine.retrieve_multi_hop.side_effect = RuntimeError("down")
    runtime = {}
    mixin._query_hipporag_tier("q", 1, runtime)
    mixin.probabilistic_query_engine = MagicMock()
    mixin._extract_query_entity = MagicMock(return_value="x")
    mixin._query_bayesian_conditional = MagicMock(return_value=None)
    empty = {}
    mixin._query_bayesian_tier("q", 1, empty)
    causes = sum(bool(item) for item in (missing, runtime, empty))

    def make_tool(processor):
        tool = object.__new__(NexusSearchTool)
        tool.nexus_processor = processor
        tool.vector_search_tool = MagicMock()
        tool.vector_search_tool.execute.return_value = [{"text": "fallback"}]
        return tool

    no_processor_tool = make_tool(None)
    no_processor = no_processor_tool.execute_with_status("q")[1] == ["bayesian", "hipporag"]
    broken = MagicMock()
    broken.process.side_effect = RuntimeError("processor")
    exception_tool = make_tool(broken)
    processor_exception = exception_tool.execute_with_status("q")[1] == ["bayesian", "hipporag"]

    barrier = threading.Barrier(4)
    processor = MagicMock()
    expected = {
        "clean": [],
        "vector": ["vector"],
        "two": ["bayesian", "hipporag"],
        "all": ["bayesian", "hipporag", "vector"],
    }

    def process(query, **kwargs):
        barrier.wait(timeout=5)
        return {"core": [], "extended": [], "degraded_tiers": expected[query]}

    processor.process.side_effect = process
    concurrent_tool = make_tool(processor)
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = dict(zip(expected, pool.map(lambda query: concurrent_tool.execute_with_status(query)[1], expected)))
    leaks = sum(actual[name] != tiers for name, tiers in expected.items())

    import src.mcp.request_router as request_router
    import src.mcp.http_server as http_server
    from fastapi import HTTPException

    handler_functions = (
        request_router.handle_vector_search,
        request_router.handle_unified_search,
        request_router.handle_context_retrieve,
        request_router.handle_graph_query,
        request_router.handle_hipporag_retrieve,
    )
    handler_args = (
        {"query": "q"},
        {"query": "q"},
        {"query": "q"},
        {"query": "q"},
        {"query": "q"},
    )

    def stdio_case(degraded):
        tool = MagicMock()
        tool.nexus_processor = None
        tool.hipporag_service = None
        tool.entity_service = None
        tool.execute_with_status.return_value = ([], degraded)
        return [function(args, tool) for function, args in zip(handler_functions, handler_args)]

    one_stdio = stdio_case(["vector"])
    all_stdio = stdio_case(["bayesian", "hipporag", "vector"])
    stdio_handlers = sum(not item.get("isError") for item in one_stdio)
    stdio_all_down = sum(bool(item.get("isError")) for item in all_stdio)

    async def http_cases(degraded):
        nexus = {"core": [], "extended": [], "degraded_tiers": degraded}
        unified_result = {
            "mode": "execution",
            "token_budget": 1000,
            "beads_budget": 800,
            "memory_budget": 200,
            "beads": [],
            "memory": {"core": [], "extended": []},
            "degraded_tiers": degraded,
            "beads_error": None,
        }
        router = MagicMock()
        router.retrieve = AsyncMock(return_value=unified_result)
        outcomes = []
        with patch.object(http_server, "_run_nexus_query", new=AsyncMock(return_value=nexus)), patch.object(
            http_server, "get_kv_store", return_value=MagicMock()
        ), patch.object(http_server, "get_event_log", return_value=MagicMock()), patch.object(
            http_server, "get_unified_router", return_value=router
        ):
            calls = (
                (http_server.vector_search, http_server.VectorSearchRequest(query="q", mode="execution")),
                (http_server.search, http_server.SearchRequest(query="q", mode="execution")),
                (http_server.unified_retrieve, http_server.UnifiedRetrievalRequest(query="q", mode="execution", token_budget=1000)),
            )
            for function, request in calls:
                try:
                    outcomes.append(await function(request))
                except HTTPException as exc:
                    outcomes.append(exc)
        return outcomes

    one_http = asyncio.run(http_cases(["vector"]))
    all_http = asyncio.run(http_cases(["bayesian", "hipporag", "vector"]))
    http_routes = sum(isinstance(item, dict) and item.get("degraded_tiers") == ["vector"] for item in one_http)
    http_503 = sum(isinstance(item, HTTPException) and item.status_code == 503 for item in all_http)
    unified_top = isinstance(one_http[-1], dict) and one_http[-1].get("degraded_tiers") == ["vector"]
    clean = stdio_handlers == 5 and http_routes == 3
    return {
        "causes": causes,
        "stdio_handlers": stdio_handlers,
        "stdio_all_down": stdio_all_down,
        "http_routes": http_routes,
        "http_503": http_503,
        "unified_top": unified_top,
        "clean": clean,
        "no_processor": no_processor,
        "processor_exception": processor_exception,
        "threads": len(expected),
        "leaks": leaks,
    }


def self_test() -> bool:
    for bad in _planted_bad_fixture():
        assert not probe(bad)
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        self_test_ok = self_test()
        if not self_test_ok:
            return 1
        print(f"SELF_TEST_REJECTED {GATE_ID}")
        return 0
    result = _real_fixture()
    ok = probe(result)
    if not ok:
        return 1
    print(TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
