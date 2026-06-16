"""Fast structural smoke for scripts/bench_tools.py.

The full latency bench loads ML models (~30-60s) and is run per optimization
phase, not in unit CI. This cheap test just keeps the instrument from rotting:
it imports, its probe table is non-empty, and every probe names a real MCP tool.
"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_bench():
    path = os.path.join(ROOT, "scripts", "bench_tools.py")
    spec = importlib.util.spec_from_file_location("bench_tools", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBenchToolsSmoke(unittest.TestCase):
    def test_imports_and_probes_reference_real_tools(self):
        bench = _load_bench()
        self.assertTrue(bench.PROBES, "bench PROBES table is empty")
        self.assertTrue(callable(bench.main))

        from src.mcp.tool_registry import get_tool_definitions

        registered = {t["name"] for t in get_tool_definitions()}
        # memory_store is seeded directly; every PROBE tool must be registered.
        for label, name, _args, _canary in bench.PROBES:
            self.assertIn(
                name,
                registered,
                f"bench probe {label!r} targets unregistered tool {name!r}",
            )

    def test_timed_returns_ms_and_value(self):
        bench = _load_bench()
        ms, val = bench._timed(lambda: 42)
        self.assertEqual(val, 42)
        self.assertGreaterEqual(ms, 0.0)


if __name__ == "__main__":
    unittest.main()
