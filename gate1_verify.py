"""GATE 1: Surgery quality gate verification."""
import sys
import types

sys.path.insert(0, '.')

# Mock spacy deeply
spacy_mock = types.ModuleType('spacy')
spacy_mock.load = lambda *a, **kw: None
spacy_mock.__path__ = []
sys.modules['spacy'] = spacy_mock
spacy_cli_mock = types.ModuleType('spacy.cli')
spacy_cli_mock.download = lambda *a, **kw: None
sys.modules['spacy.cli'] = spacy_cli_mock

results = []

# CHECK 1: mode_detection tool removed from registry
print("=" * 60)
print("CHECK 1: Duplicate mode_detection tool removed")
print("=" * 60)

with open("src/mcp/tool_registry.py", "r") as f:
    registry_source = f.read()

ok = '"mode_detection"' not in registry_source
print(f"  mode_detection not in tool_registry: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = '"detect_mode"' in registry_source
print(f"  detect_mode still in tool_registry: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "_mode_detection_tool" not in registry_source
print(f"  _mode_detection_tool function removed: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 2: mode_detection removed from router
print()
print("=" * 60)
print("CHECK 2: Duplicate mode_detection route removed")
print("=" * 60)

with open("src/mcp/request_router.py", "r") as f:
    router_source = f.read()

ok = '"mode_detection"' not in router_source
print(f"  mode_detection not in router: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = '"detect_mode"' in router_source
print(f"  detect_mode still in router: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 3: _calculate_hybrid_score exists and is used
print()
print("=" * 60)
print("CHECK 3: Scoring logic consolidated")
print("=" * 60)

with open("src/nexus/processing_utils.py", "r") as f:
    utils_source = f.read()

ok = "def _calculate_hybrid_score(" in utils_source
print(f"  _calculate_hybrid_score in processing_utils: {'PASS' if ok else 'FAIL'}")
results.append(ok)

with open("src/nexus/processor.py", "r") as f:
    proc_source = f.read()

# Count uses of the shared method
uses = proc_source.count("self._calculate_hybrid_score(")
ok = uses >= 2
print(f"  _calculate_hybrid_score called {uses} times in processor: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# No inline weight calculations remain
inline_pattern = 'self.weights.get("vector", 0.4) * '
inline_count = proc_source.count(inline_pattern)
ok = inline_count == 0
print(f"  No inline weight calculations remain: {'PASS' if ok else 'FAIL'} (found {inline_count})")
results.append(ok)

# CHECK 4: Exception narrowing applied
print()
print("=" * 60)
print("CHECK 4: Critical exceptions narrowed")
print("=" * 60)

with open("src/indexing/vector_indexer.py", "r") as f:
    vi_source = f.read()

ok = "except (ValueError, KeyError):" in vi_source
print(f"  vector_indexer collection init narrowed: {'PASS' if ok else 'FAIL'}")
results.append(ok)

with open("src/chunking/semantic_chunker.py", "r") as f:
    sc_source = f.read()

ok = "[0.0] * (len(sentences) - 1)" in sc_source
print(f"  semantic_chunker fallback fixed (0.0 not 1.0): {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "except (ValueError, RuntimeError)" in sc_source
print(f"  semantic_chunker exception narrowed: {'PASS' if ok else 'FAIL'}")
results.append(ok)

with open("src/stores/event_log.py", "r") as f:
    el_source = f.read()

ok = "except (OSError, IOError)" in el_source
print(f"  event_log storage failures re-raised: {'PASS' if ok else 'FAIL'}")
results.append(ok)

with open("src/mcp/http_server.py", "r") as f:
    hs_source = f.read()

ok = "except (ValueError, RuntimeError, TimeoutError)" in hs_source
print(f"  http_server Bayesian build narrowed: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# SUMMARY
print()
print("=" * 60)
passed = sum(results)
total = len(results)
print(f"GATE 1 RESULT: {passed}/{total} checks passed")
if passed == total:
    print("GATE 1: PASSED")
else:
    print(f"GATE 1: FAILED ({total - passed} failures)")
print("=" * 60)

sys.exit(0 if passed == total else 1)
