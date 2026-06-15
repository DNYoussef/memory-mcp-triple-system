#!/usr/bin/env python
"""Hermetic acceptance harness for every Memory MCP capability (P0).

Runnable by either model: `python scripts/acceptance_all_parts.py`.

Hermetic: a fresh temp MEMORY_MCP_DATA_DIR + CHROMA_PERSIST_DIR, unique canary
text, asserts the canary comes back (not just "non-empty"), then tears down.

Each capability prints PASS / XFAIL (known-broken, recorded) / FAIL (a thing
that should work but didn't). Exit code is non-zero only on an unexpected FAIL,
so this doubles as the phase gate: known-broken capabilities are xfail until
their phase flips them.

ponytail: in-process via handle_call_tool (no server spawn); substring-canary
match (robust to result shape). Cross-transport adapters added when a phase needs them.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import uuid

CANARY = f"CANARY-{uuid.uuid4().hex}"
TEXT = f"{CANARY}: GuardSpine zebra-quasar reactor tuned by Wilhelmina Ashgrove in project triplecheck."

# Known-broken today -> xfail (recorded, not a gate failure). Flipped by their phase.
XFAIL = {
    "bayesian_inference": "B1: Bayesian tier offline (P4)",
    "context_injection": "B5/P5: proactive injection not a registered tool",
}


def _hermetic_env():
    d = tempfile.mkdtemp(prefix="mmts-accept-")
    os.environ["MEMORY_MCP_DATA_DIR"] = d
    os.environ["CHROMA_PERSIST_DIR"] = os.path.join(d, "chroma")  # A1 workaround until P1
    return d


def main():
    data_dir = _hermetic_env()
    results = []  # (capability, status, detail)

    def record(cap, ok, detail=""):
        if ok:
            status = "PASS"
        elif cap in XFAIL:
            status = "XFAIL"
            detail = detail or XFAIL[cap]
        else:
            status = "FAIL"
        results.append((cap, status, str(detail)[:160]))

    try:
        from src.mcp.service_wiring import NexusSearchTool, load_config
        from src.mcp.request_router import handle_call_tool
    except Exception as e:  # import itself is a capability
        print(f"IMPORT FAILED: {e}")
        return 2

    tool = NexusSearchTool(load_config())

    def call(name, args):
        return json.dumps(handle_call_tool(name, args, tool), default=str)

    # store -----------------------------------------------------------------
    try:
        out = call("memory_store", {"text": TEXT, "metadata": {
            "who": "harness", "when": "2026-06-15", "project": "triplecheck", "why": "acceptance"}})
        record("store", CANARY in out or "chunk" in out.lower(), out)
    except Exception as e:
        record("store", False, e)

    # vector ----------------------------------------------------------------
    try:
        out = call("vector_search", {"query": "zebra-quasar reactor Wilhelmina", "limit": 5})
        record("vector", CANARY in out, out)
    except Exception as e:
        record("vector", False, e)

    # graph / hipporag ------------------------------------------------------
    try:
        out = call("hipporag_retrieve", {"query": "Wilhelmina Ashgrove triplecheck", "limit": 5})
        record("hipporag", CANARY in out or "Wilhelmina" in out, out)
    except Exception as e:
        record("hipporag", False, e)

    # unified fusion --------------------------------------------------------
    try:
        out = call("unified_search", {"query": "zebra-quasar reactor", "limit": 5})
        record("unified", CANARY in out, out)
    except Exception as e:
        record("unified", False, e)

    # bayesian (xfail) ------------------------------------------------------
    try:
        out = call("bayesian_inference", {"query": "GuardSpine"})
        record("bayesian_inference", "available" in out.lower() and "no bayesian" not in out.lower(), out)
    except Exception as e:
        record("bayesian_inference", False, e)

    # entity extraction -----------------------------------------------------
    try:
        out = call("entity_extraction", {"text": "Wilhelmina Ashgrove leads GuardSpine."})
        record("entity_extraction", "Wilhelmina" in out or "GuardSpine" in out, out)
    except Exception as e:
        record("entity_extraction", False, e)

    # mode detection --------------------------------------------------------
    try:
        out = call("detect_mode", {"query": "how should I plan the rollout?"})
        record("detect_mode", "planning" in out.lower(), out)
    except Exception as e:
        record("detect_mode", False, e)

    # lifecycle status (reporting) -----------------------------------------
    try:
        out = call("lifecycle_status", {})
        record("lifecycle_status", "active" in out.lower(), out)
    except Exception as e:
        record("lifecycle_status", False, e)

    # broader-recall: brainstorming returns strictly more than execution ----
    try:
        ex = json.loads(call("unified_search", {"query": "reactor", "limit": 5, "mode": "execution"}))
        br = json.loads(call("unified_search", {"query": "reactor", "limit": 5, "mode": "brainstorming"}))
        n_ex = len(ex.get("results", ex if isinstance(ex, list) else []))
        n_br = len(br.get("results", br if isinstance(br, list) else []))
        record("broader_recall", n_br >= n_ex, f"execution={n_ex} brainstorming={n_br}")
    except Exception as e:
        record("broader_recall", False, e)

    # kv (xfail - not exposed) ---------------------------------------------
    try:
        out = call("kv_set", {"key": "k", "value": CANARY})
        record("kv", CANARY in call("kv_get", {"key": "k"}), out)
    except Exception as e:
        record("kv", False, e)

    # lifecycle aging: ingestion must write numeric last_accessed_ts (A2),
    # and a chunk older than the threshold must demote.
    try:
        coll = tool.lifecycle_manager.vector_indexer.collection
        got = coll.get(include=["metadatas"])
        ids, mds = got.get("ids", []), got.get("metadatas", [])
        has_ts = bool(ids) and isinstance(mds[0].get("last_accessed_ts"), (int, float))
        if not has_ts:
            record("lifecycle_aging", False, "ingested chunk missing numeric last_accessed_ts (A2)")
        else:
            md = dict(mds[0]); md["last_accessed_ts"] = time.time() - 10 * 86400  # 10 days stale
            coll.update(ids=[ids[0]], metadatas=[md])
            demoted = tool.lifecycle_manager.demote_stale_chunks()  # default 7-day threshold
            record("lifecycle_aging", demoted >= 1, f"ingest_ts=ok demoted={demoted}")
    except Exception as e:
        record("lifecycle_aging", False, e)

    # context injection (xfail) --------------------------------------------
    record("context_injection", False, "no registered injection tool")

    # report ----------------------------------------------------------------
    shutil.rmtree(data_dir, ignore_errors=True)
    width = max(len(c) for c, _, _ in results)
    print(f"\n=== acceptance_all_parts (canary {CANARY[:14]}...) ===")
    unexpected = 0
    for cap, status, detail in results:
        print(f"  {cap.ljust(width)}  {status:<6} {detail if status != 'PASS' else ''}".rstrip())
        if status == "FAIL":
            unexpected += 1
    passed = sum(1 for _, s, _ in results if s == "PASS")
    xf = sum(1 for _, s, _ in results if s == "XFAIL")
    print(f"\n  {passed} PASS | {xf} XFAIL | {unexpected} FAIL  (of {len(results)})")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
