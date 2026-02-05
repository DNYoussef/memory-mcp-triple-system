"""
GATE 4: Phase 4 Polish Verification
Validates P4-1 through P4-3 changes.
"""
import ast
import sys
import importlib

sys.path.insert(0, ".")
passed = 0
total = 0

def check(name, condition, detail=""):
    global passed, total
    total += 1
    status = "PASS" if condition else "FAIL"
    if condition:
        passed += 1
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))
    return condition

print("=== GATE 4: Phase 4 Polish Verification ===\n")

# --- P4-1: Connection Pooling ---
print("CHECK 1: EventLog connection pooling (P4-1)")
with open("src/stores/event_log.py", "r") as f:
    event_log_src = f.read()

check("threading imported", "import threading" in event_log_src)
check("_local in __init__", "self._local = threading.local()" in event_log_src)
check("_get_connection method exists", "def _get_connection(self)" in event_log_src)

# No raw sqlite3.connect() calls outside _get_connection
lines = event_log_src.split("\n")
raw_connects = []
in_get_connection = False
for i, line in enumerate(lines, 1):
    if "_get_connection" in line and "def " in line:
        in_get_connection = True
    elif "def " in line and in_get_connection:
        in_get_connection = False
    if "sqlite3.connect(" in line and not in_get_connection:
        raw_connects.append(i)
check("no raw sqlite3.connect() outside _get_connection",
      len(raw_connects) == 0,
      f"found at lines {raw_connects}" if raw_connects else "all methods use _get_connection()")

# log_event uses pooled connection
check("log_event uses _get_connection", "self._get_connection()" in event_log_src.split("def log_event")[1].split("def ")[0])
# query_by_timerange uses pooled connection
check("query_by_timerange uses _get_connection", "self._get_connection()" in event_log_src.split("def query_by_timerange")[1].split("def ")[0])
# cleanup_old_events uses pooled connection
check("cleanup_old_events uses _get_connection", "self._get_connection()" in event_log_src.split("def cleanup_old_events")[1].split("def ")[0])
# get_event_stats uses pooled connection
check("get_event_stats uses _get_connection", "self._get_connection()" in event_log_src.split("def get_event_stats")[1].split("def ")[0])
# _init_schema uses pooled connection
check("_init_schema uses _get_connection", "self._get_connection()" in event_log_src.split("def _init_schema")[1])

# --- P4-2: PPR Caching ---
print("\nCHECK 2: PPR result caching (P4-2)")
with open("src/services/ppr_algorithms.py", "r") as f:
    ppr_src = f.read()

check("lru_cache imported", "from functools import lru_cache" in ppr_src)
check("@lru_cache decorator present", "@lru_cache" in ppr_src)
check("_cached_pagerank method exists", "def _cached_pagerank" in ppr_src)
check("_execute_pagerank builds cache_key", "cache_key" in ppr_src.split("def _execute_pagerank")[1].split("def ")[0])
check("frozenset used for hashable personalization",
      "frozenset(personalization.items())" in ppr_src)
check("graph size in cache key for invalidation",
      "len(self.graph.nodes)" in ppr_src and "len(self.graph.edges)" in ppr_src)

# --- P4-3: Tool Versioning ---
print("\nCHECK 3: Tool versioning (P4-3)")
with open("src/mcp/tool_registry.py", "r") as f:
    registry_src = f.read()

check("REGISTRY_VERSION constant defined", 'REGISTRY_VERSION = "1.0.0"' in registry_src)

# Count tool functions and version occurrences
tool_funcs = [line for line in registry_src.split("\n") if line.strip().startswith("def _") and "tool()" in line]
version_lines = [line for line in registry_src.split("\n") if '"version": REGISTRY_VERSION' in line]
check("13 tool functions defined", len(tool_funcs) == 13, f"found {len(tool_funcs)}")
check("all tools have version field", len(version_lines) == 13, f"found {len(version_lines)}")

# Verify structure: each tool return dict has version after name
check("version appears in tool dicts", registry_src.count('"version": REGISTRY_VERSION') == 13)

# --- Summary ---
print(f"\n{'='*50}")
print(f"GATE 4 RESULT: {passed}/{total} checks passed")
if passed == total:
    print("STATUS: PASS - All Phase 4 changes verified")
else:
    print(f"STATUS: FAIL - {total - passed} checks failed")
    sys.exit(1)
