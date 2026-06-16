#!/usr/bin/env python
"""Hermetic per-tool latency bench + functional gate for the Memory MCP.

Runnable by either model: `python scripts/bench_tools.py`.

Hermetic: fresh temp MEMORY_MCP_DATA_DIR, unique canary, seeds a small corpus
whose texts share entities so the graph + Bayesian path is actually exercised,
then drives every MCP tool through handle_call_tool and records:
  - cold  : the FIRST call (includes lazy processor/Bayesian build on vector_search)
  - warm  : p50 / p95 over BENCH_WARM (default 5) subsequent calls

Hard gate (exit code): every tool must run WITHOUT isError, and the search
tools must return the canary. Latency is REPORTED, not asserted - absolute ms
varies by machine, so it is evidence for before/after comparison, not a flaky
threshold. Writes the latency table as JSON to BENCH_OUT (default
audits/bench-baseline.json) for delta comparison across optimization phases.

ponytail: in-process (no server spawn); reuses the acceptance corpus shape.
"""
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CANARY = f"CANARY-{uuid.uuid4().hex}"
TEXT = f"{CANARY}: GuardSpine zebra-quasar reactor tuned by Wilhelmina Ashgrove in project triplecheck."
REINFORCE = [
    "GuardSpine and Wilhelmina Ashgrove ran the zebra-quasar reactor in project triplecheck.",
    "In project triplecheck, Wilhelmina Ashgrove tuned the GuardSpine reactor again.",
]
WARM = int(os.getenv("BENCH_WARM", "5"))
OUT = os.getenv("BENCH_OUT", os.path.join("audits", "bench-baseline.json"))

# (label, tool_name, args, canary_required)
PROBES = [
    ("kv_set", "kv_set", {"key": "benchk", "value": CANARY}, False),
    ("kv_get", "kv_get", {"key": "benchk"}, True),
    ("detect_mode", "detect_mode", {"query": "how should I plan the rollout?"}, False),
    ("entity_extraction", "entity_extraction", {"text": "Wilhelmina Ashgrove leads GuardSpine."}, False),
    ("lifecycle_status", "lifecycle_status", {}, False),
    ("vector_search", "vector_search", {"query": "zebra-quasar reactor Wilhelmina", "limit": 5}, True),
    ("unified_search", "unified_search", {"query": "zebra-quasar reactor", "limit": 5}, True),
    ("hipporag_retrieve", "hipporag_retrieve", {"query": "Wilhelmina Ashgrove triplecheck", "limit": 5}, False),
    ("graph_query", "graph_query", {"query": "Wilhelmina Ashgrove", "limit": 5}, False),
    ("bayesian_inference", "bayesian_inference", {"query": "Wilhelmina Ashgrove"}, False),
    ("context_retrieve", "context_retrieve", {"query": "Wilhelmina Ashgrove reactor", "limit": 5}, False),
]


def _timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return (time.perf_counter() - t0) * 1000.0, out


def main():
    data_dir = tempfile.mkdtemp(prefix="mmts-bench-")
    os.environ["MEMORY_MCP_DATA_DIR"] = data_dir  # F3: resolver honors this alone
    os.environ.pop("CHROMA_PERSIST_DIR", None)

    try:
        from src.mcp.service_wiring import NexusSearchTool, load_config
        from src.mcp.request_router import handle_call_tool
    except Exception as e:
        print(f"IMPORT FAILED: {e}")
        return 2

    tool = NexusSearchTool(load_config())

    def call(name, args):
        return json.dumps(handle_call_tool(name, args, tool), default=str)

    # seed corpus
    call("memory_store", {"text": TEXT, "metadata": {
        "who": "bench", "when": "2026-06-15", "project": "triplecheck", "why": "bench"}})
    for extra in REINFORCE:
        call("memory_store", {"text": extra, "metadata": {
            "who": "bench", "when": "2026-06-15", "project": "triplecheck", "why": "reinforce"}})

    rows, failures = [], []
    for label, name, args, needs_canary in PROBES:
        try:
            cold_ms, out = _timed(lambda: call(name, args))
            if '"isError": true' in out.lower().replace(" ", "") or '"iserror":true' in out.lower().replace(" ", ""):
                failures.append(f"{label}: isError in response")
            if needs_canary and CANARY not in out:
                failures.append(f"{label}: canary missing")
            warm = [_timed(lambda: call(name, args))[0] for _ in range(WARM)]
            rows.append({
                "tool": label,
                "cold_ms": round(cold_ms, 1),
                "warm_p50_ms": round(statistics.median(warm), 1),
                "warm_p95_ms": round(max(warm), 1) if len(warm) < 20 else round(statistics.quantiles(warm, n=20)[18], 1),
            })
        except Exception as e:
            failures.append(f"{label}: {e}")
            rows.append({"tool": label, "cold_ms": -1, "warm_p50_ms": -1, "warm_p95_ms": -1})

    shutil.rmtree(data_dir, ignore_errors=True)

    width = max(len(r["tool"]) for r in rows)
    print(f"\n=== bench_tools (canary {CANARY[:14]}..., warm n={WARM}) ===")
    print(f"  {'tool'.ljust(width)}   cold_ms  warm_p50  warm_p95")
    for r in rows:
        print(f"  {r['tool'].ljust(width)}  {r['cold_ms']:>8}  {r['warm_p50_ms']:>8}  {r['warm_p95_ms']:>8}")

    if OUT:
        os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump({"warm_n": WARM, "rows": rows}, fh, indent=2)
        print(f"\n  wrote {OUT}")

    if failures:
        print("\n  FAILURES:")
        for f in failures:
            print(f"    - {f}")
        return 1
    print(f"\n  OK: {len(rows)} tools ran clean, canaries present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
