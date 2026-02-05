"""GATE 2: Architecture quality gate verification."""
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
spacy_tokens_mock = types.ModuleType('spacy.tokens')
sys.modules['spacy.tokens'] = spacy_tokens_mock
spacy_lang_mock = types.ModuleType('spacy.lang')
sys.modules['spacy.lang'] = spacy_lang_mock
spacy_lang_en_mock = types.ModuleType('spacy.lang.en')
sys.modules['spacy.lang.en'] = spacy_lang_en_mock

results = []

# CHECK 1: BeadsBridge N+1 fixed in get_critical_path
print("=" * 60)
print("CHECK 1: BeadsBridge N+1 fixed in get_critical_path")
print("=" * 60)

with open("src/integrations/beads_bridge.py", "r") as f:
    beads_source = f.read()

# No more per-task get_task_detail loop in get_critical_path
ok = "detail = await self.get_task_detail(task.id)" not in beads_source.split("get_critical_path")[1].split("async def")[0]
print(f"  No per-task re-fetch in get_critical_path: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# Uses list comprehension filter instead
ok = "critical = [t for t in all_tasks if t.dependencies]" in beads_source
print(f"  Uses direct filter on query_tasks result: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 2: BeadsBridge N+1 fixed in get_execution_order
print()
print("=" * 60)
print("CHECK 2: BeadsBridge N+1 fixed in get_execution_order")
print("=" * 60)

exec_order_section = beads_source.split("get_execution_order")[1].split("def _parse_datetime")[0]

ok = "task_by_id = {t.id: t for t in all_tasks}" in exec_order_section
print(f"  Pre-fetches tasks into lookup dict: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "task_by_id.get(task.id" in exec_order_section
print(f"  Uses lookup dict instead of get_task_detail: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "detail = await self.get_task_detail(task.id)" not in exec_order_section
print(f"  No per-task subprocess call: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 3: GraphPersistence dirty flag
print()
print("=" * 60)
print("CHECK 3: GraphPersistence incremental persistence")
print("=" * 60)

with open("src/services/graph_persistence.py", "r") as f:
    gp_source = f.read()

ok = "self._dirty = False" in gp_source
print(f"  Dirty flag initialized: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "def mark_dirty(self)" in gp_source
print(f"  mark_dirty() method exists: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "self._dirty = True" in gp_source
print(f"  mark_dirty sets flag: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "if not force and not self._dirty:" in gp_source
print(f"  save() checks dirty before write: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "def save(self, file_path: Optional[Path] = None, force: bool = False)" in gp_source
print(f"  save() has force parameter: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 4: GraphService calls mark_dirty on mutations
print()
print("=" * 60)
print("CHECK 4: GraphService dirty tracking integration")
print("=" * 60)

with open("src/services/graph_service.py", "r") as f:
    gs_source = f.read()

ok = "def _mutate(self, result: bool) -> bool:" in gs_source
print(f"  _mutate() helper exists: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "self._persistence.mark_dirty()" in gs_source
print(f"  _mutate calls mark_dirty: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# Count mutation wrappings
mutate_calls = gs_source.count("self._mutate(")
ok = mutate_calls >= 10
print(f"  Mutation methods wrapped: {mutate_calls} (need >=10): {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 5: NexusSearchTool staticmethod
print()
print("=" * 60)
print("CHECK 5: NexusSearchTool cleanup")
print("=" * 60)

with open("src/mcp/service_wiring.py", "r") as f:
    sw_source = f.read()

ok = "@staticmethod" in sw_source and "def _build_bayesian_network(graph_service" in sw_source
print(f"  _build_bayesian_network is @staticmethod: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 6: Vault watcher uses watchdog
print()
print("=" * 60)
print("CHECK 6: Vault watcher uses filesystem events")
print("=" * 60)

with open("src/utils/file_watcher.py", "r") as f:
    vw_source = f.read()

ok = "from watchdog.observers import Observer" in vw_source
print(f"  ObsidianVaultWatcher uses watchdog: {'PASS' if ok else 'FAIL'}")
results.append(ok)

with open("src/services/trigger_watchers/file_watcher.py", "r") as f:
    fw_source = f.read()

ok = "WATCHDOG_AVAILABLE" in fw_source
print(f"  FileWatcher has watchdog detection: {'PASS' if ok else 'FAIL'}")
results.append(ok)

ok = "PollingFileWatcher" in fw_source
print(f"  FileWatcher has polling fallback: {'PASS' if ok else 'FAIL'}")
results.append(ok)

# CHECK 7: Functional verification - dirty flag works
print()
print("=" * 60)
print("CHECK 7: Functional dirty flag test")
print("=" * 60)

import tempfile
import os
from src.services.graph_service import GraphService

with tempfile.TemporaryDirectory() as tmpdir:
    gs = GraphService(data_dir=tmpdir)

    # Save without changes - should skip (not dirty)
    result = gs.save_graph()
    ok = result is True
    print(f"  Save on clean graph returns True: {'PASS' if ok else 'FAIL'}")
    results.append(ok)

    # Check that no file was written (not dirty)
    graph_file = os.path.join(tmpdir, "graph.json")
    ok = not os.path.exists(graph_file)
    print(f"  No file written when not dirty: {'PASS' if ok else 'FAIL'}")
    results.append(ok)

    # Add a node (should mark dirty)
    gs.add_chunk_node("test1", {"text": "hello"})
    result = gs.save_graph()
    ok = result is True and os.path.exists(graph_file)
    print(f"  File written after mutation: {'PASS' if ok else 'FAIL'}")
    results.append(ok)

    # Save again without changes - should skip
    mtime_before = os.path.getmtime(graph_file)
    import time
    time.sleep(0.05)
    gs.save_graph()
    mtime_after = os.path.getmtime(graph_file)
    ok = mtime_before == mtime_after
    print(f"  No write on second save (not dirty): {'PASS' if ok else 'FAIL'}")
    results.append(ok)

    # Force save should always write
    time.sleep(0.05)
    gs.save_graph(force=True)
    mtime_force = os.path.getmtime(graph_file)
    ok = mtime_force > mtime_after
    print(f"  Force save always writes: {'PASS' if ok else 'FAIL'}")
    results.append(ok)

# SUMMARY
print()
print("=" * 60)
passed = sum(results)
total = len(results)
print(f"GATE 2 RESULT: {passed}/{total} checks passed")
if passed == total:
    print("GATE 2: PASSED")
else:
    print(f"GATE 2: FAILED ({total - passed} failures)")
print("=" * 60)

sys.exit(0 if passed == total else 1)
