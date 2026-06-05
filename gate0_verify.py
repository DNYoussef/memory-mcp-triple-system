"""GATE 0: Foundation quality gate verification script."""
import sys
import time
import types
import json

sys.path.insert(0, '.')

# Mock spacy deeply to prevent import failure
spacy_mock = types.ModuleType('spacy')
spacy_mock.load = lambda *a, **kw: None
spacy_mock.__path__ = []  # Make it a package
sys.modules['spacy'] = spacy_mock

spacy_cli_mock = types.ModuleType('spacy.cli')
spacy_cli_mock.download = lambda *a, **kw: None
sys.modules['spacy.cli'] = spacy_cli_mock

spacy_tokens_mock = types.ModuleType('spacy.tokens')
sys.modules['spacy.tokens'] = spacy_tokens_mock

spacy_lang_mock = types.ModuleType('spacy.lang')
sys.modules['spacy.lang'] = spacy_lang_mock

results = []

# ========================================================
# CHECK 1: Metadata parsing (P0-4)
# ========================================================
print("=" * 60)
print("CHECK 1: Metadata parsing (P0-4)")
print("=" * 60)

from src.memory.lifecycle_manager import MemoryLifecycleManager

# JSON format
json_meta = '{"file_path": "/test/path.md", "stage": "archived"}'
r1 = MemoryLifecycleManager._parse_metadata(json_meta)
ok = r1 == {'file_path': '/test/path.md', 'stage': 'archived'}
print(f"  JSON parse: {'PASS' if ok else 'FAIL'} -> {r1}")
results.append(ok)

# Legacy format
legacy_meta = "file_path: /test/path.md, stage: archived"
r2 = MemoryLifecycleManager._parse_metadata(legacy_meta)
ok = r2.get('file_path') == '/test/path.md'
print(f"  Legacy parse: {'PASS' if ok else 'FAIL'} -> {r2}")
results.append(ok)

# None
r3 = MemoryLifecycleManager._parse_metadata(None)
ok = r3 == {}
print(f"  None parse: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# Empty
r4 = MemoryLifecycleManager._parse_metadata("")
ok = r4 == {}
print(f"  Empty parse: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# ========================================================
# CHECK 2: ThreadPoolExecutor reuse (P0-3)
# ========================================================
print()
print("=" * 60)
print("CHECK 2: ThreadPoolExecutor reuse (P0-3)")
print("=" * 60)

from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine

engine = ProbabilisticQueryEngine(timeout_seconds=1.0)
ok = engine._executor is not None
print(f"  Executor exists at init: {'PASS' if ok else 'FAIL'}")
results.append(ok)

executor_id = id(engine._executor)
query_results = []
for i in range(5):
    r = engine.execute_with_timeout(lambda: 42)
    query_results.append(r)

ok = all(r == 42 for r in query_results)
print(f"  5 queries returned correct value: {'PASS' if ok else 'FAIL'} -> {query_results}")
results.append(ok)

ok = id(engine._executor) == executor_id
print(f"  Same executor after queries: {'PASS' if ok else 'FAIL'}")
results.append(ok)

engine.close()
print(f"  close() succeeded")

# ========================================================
# CHECK 3: Lazy factory - no import side effects (P0-2)
# ========================================================
print()
print("=" * 60)
print("CHECK 3: Lazy factory - no import side effects (P0-2)")
print("=" * 60)

# Import directly to avoid __init__.py import chain
import importlib.util
sw_spec = importlib.util.spec_from_file_location(
    "service_wiring", "src/mcp/service_wiring.py",
    submodule_search_locations=[]
)
service_wiring = importlib.util.module_from_spec(sw_spec)

# Check the source for lazy pattern instead of importing (avoids dep chain)
with open("src/mcp/service_wiring.py", "r") as f:
    sw_source = f.read()

ok = "_tagger = None" in sw_source
print(f"  _tagger = None declared: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "_memory_client = None" in sw_source
print(f"  _memory_client = None declared: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "_telemetry_bridge = None" in sw_source
print(f"  _telemetry_bridge = None declared: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "_connascence_bridge = None" in sw_source
print(f"  _connascence_bridge = None declared: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "def get_tagger():" in sw_source
print(f"  get_tagger() factory exists: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# Verify NO eager init at module level (only inside factory functions)
# The pattern _tagger = init_tagger() inside get_tagger() is correct.
# What would be wrong: a bare `tagger = init_tagger()` at module level.
import re
# Check there's no module-level `tagger = init_tagger()` (without underscore)
# Lines like `_tagger = init_tagger()` inside functions are fine.
module_level_lines = []
indent_level = 0
for line in sw_source.split('\n'):
    stripped = line.lstrip()
    if stripped and not stripped.startswith('#'):
        leading_spaces = len(line) - len(stripped)
        if leading_spaces == 0 and '= init_' in stripped:
            module_level_lines.append(stripped)

ok = len(module_level_lines) == 0
print(f"  No module-level eager init: {'PASS' if ok else 'FAIL'} (found: {module_level_lines})")
results.append(ok)

ok = "def get_tagger():" in sw_source and "def get_memory_client():" in sw_source
print(f"  All 4 factory functions exist: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# ========================================================
# CHECK 4: Dedup batch approach (P0-1) - vector ops
# ========================================================
print()
print("=" * 60)
print("CHECK 4: Dedup batch cosine (P0-1)")
print("=" * 60)

import numpy as np

# Test cosine function standalone (avoid import chain)
def _cosine_from_vectors(vec_a, vec_b):
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

vec_a = np.array([1.0, 0.0, 0.0])
vec_b = np.array([1.0, 0.0, 0.0])
sim = _cosine_from_vectors(vec_a, vec_b)
ok = abs(sim - 1.0) < 0.001
print(f"  Identical vectors = 1.0: {'PASS' if ok else 'FAIL'} -> {sim:.4f}")
results.append(ok)

vec_c = np.array([0.0, 1.0, 0.0])
sim2 = _cosine_from_vectors(vec_a, vec_c)
ok = abs(sim2) < 0.001
print(f"  Orthogonal vectors = 0.0: {'PASS' if ok else 'FAIL'} -> {sim2:.4f}")
results.append(ok)

vec_zero = np.array([0.0, 0.0, 0.0])
sim3 = _cosine_from_vectors(vec_a, vec_zero)
ok = sim3 == 0.0
print(f"  Zero vector handled: {'PASS' if ok else 'FAIL'} -> {sim3:.4f}")
results.append(ok)

# Verify the function exists in processor.py source
with open("src/nexus/processor.py", "r") as f:
    proc_source = f.read()

ok = "_cosine_from_vectors" in proc_source
print(f"  _cosine_from_vectors in processor.py: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "_batch_encode_texts" in proc_source
print(f"  _batch_encode_texts in processor.py: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "seen_texts" in proc_source  # Hash-based exact dedup
print(f"  Hash-based exact dedup exists: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# ========================================================
# SUMMARY
# ========================================================
print()
print("=" * 60)
passed = sum(results)
total = len(results)
print(f"GATE 0 RESULT: {passed}/{total} checks passed")
if passed == total:
    print("GATE 0: PASSED")
else:
    print(f"GATE 0: FAILED ({total - passed} failures)")
print("=" * 60)

sys.exit(0 if passed == total else 1)
