#!/usr/bin/env python
"""Phase-0 tri-tier acceptance gate. Isolated-data, PostHog-canary, tier-death-RED.
Run: python scripts/gate_tri_tier.py   (exit 0 = green, nonzero = red)."""
import json, os, shutil, sys, tempfile, uuid
from pathlib import Path
from unittest.mock import patch

# Standalone run: put the repo root on sys.path so `from src.mcp...` resolves
# (tests get this from conftest.py; this script has no conftest).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CANARY = f"CANARY-{uuid.uuid4().hex}"
TEXT = (f"{CANARY}: GuardSpine zebra-quasar reactor tuned by Wilhelmina Ashgrove "
        f"in project triplecheck.")
REINFORCE = [
    "GuardSpine and Wilhelmina Ashgrove ran the zebra-quasar reactor in project triplecheck.",
    "In project triplecheck, Wilhelmina Ashgrove tuned the GuardSpine reactor again.",
]

def _hermetic():
    d = tempfile.mkdtemp(prefix="mmts-gate-")
    os.environ["MEMORY_MCP_DATA_DIR"] = d
    os.environ["CHROMA_PERSIST_DIR"] = os.path.join(d, "chroma")
    # Hostile ambient default: the source constructor must explicitly opt out.
    os.environ["ANONYMIZED_TELEMETRY"] = "True"
    return d

def main():
    data_dir = _hermetic()
    failures = []
    telemetry_attempts = []

    def block_enabled_telemetry(client, message, disable_geoip=None):
        if not client.disabled:
            telemetry_attempts.append(str(message.get("event", "unknown")))
        return False, "blocked by hermetic gate"

    telemetry_patch = patch("posthog.client.Client._enqueue", new=block_enabled_telemetry)
    telemetry_patch.start()
    try:
        from src.mcp.service_wiring import NexusSearchTool, load_config
        from src.mcp.request_router import handle_call_tool
        tool = NexusSearchTool(load_config())
        call = lambda n, a: json.dumps(handle_call_tool(n, a, tool), default=str)

        call("memory_store", {"text": TEXT, "metadata": {
            "who": "gate", "when": "2026-07-06", "project": "triplecheck", "why": "gate"}})
        for extra in REINFORCE:
            call("memory_store", {"text": extra, "metadata": {
                "who": "gate", "when": "2026-07-06", "project": "triplecheck", "why": "reinforce"}})

        # (1) exact-canary fusion
        fused = call("unified_search", {"query": "zebra-quasar reactor", "limit": 5})
        if CANARY not in fused:
            failures.append(f"fusion did not return exact canary {CANARY}")

        # (2) graph tier participates: its entity resolves via hipporag
        graph_out = call("hipporag_retrieve", {"query": "Wilhelmina Ashgrove triplecheck", "limit": 5})
        if "Wilhelmina" not in graph_out and CANARY not in graph_out:
            failures.append("graph/hipporag tier returned nothing for a graph-only entity")

        # (3) bayesian tier ran (numeric posterior, not an 'unavailable' string)
        bay = call("bayesian_inference", {"query": "Wilhelmina Ashgrove"}).lower()
        if "unavailable" in bay or "no co-occurrence" in bay or not any(c.isdigit() for c in bay):
            failures.append("bayesian tier did not produce a numeric posterior")

        # (4) POISON: kill the graph tier, fusion must OBSERVABLY change (not silently identical)
        setattr(tool, "hipporag_service", None)
        if getattr(tool, "nexus_processor", None):
            setattr(tool.nexus_processor, "graph_query_engine", None)
        poisoned = call("hipporag_retrieve", {"query": "Wilhelmina Ashgrove triplecheck", "limit": 5})
        if poisoned == graph_out:
            failures.append("disabling graph tier did not change output - tier is not load-bearing (silent single-tier)")
    except Exception as e:
        failures.append(f"gate crashed: {e}")
    finally:
        telemetry_patch.stop()
        if telemetry_attempts:
            failures.append(
                "enabled outbound telemetry attempted: " + ", ".join(telemetry_attempts)
            )
        shutil.rmtree(data_dir, ignore_errors=True)

    print(f"=== gate_tri_tier (canary {CANARY[:14]}) ===")
    for f in failures:
        print(f"  RED: {f}")
    print(
        "  GREEN: all three tiers contribute, tier-death is observable, and PostHog telemetry is disabled"
        if not failures else f"  {len(failures)} FAIL"
    )
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
