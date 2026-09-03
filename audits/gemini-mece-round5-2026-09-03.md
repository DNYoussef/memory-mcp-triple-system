### A. Computed Reachability Design (Plan Section 1)

1. **[MAJOR] AST Traversal Depth & Relative Import Resolution:**
   - *Evidence:* `src/mcp/__init__.py:22-47` and `src/nexus/__init__.py:11-22` use PEP 562 lazy exports inside `def __getattr__(name):` rather than top-level module imports. A naive AST visitor that only inspects `ast.Module.body` at top-level will miss `ObsidianMCPClient`, `VaultFileManager`, `VaultSyncService`, and `NexusProcessor`. The AST analyzer in `reachability.py` must use `ast.walk()` over the full AST and explicitly resolve relative imports (`level > 0` in `ast.ImportFrom`), resolving against package directory structures.
2. **[MAJOR] Root Set Exclusion of Test-Only Shared Code:**
   - *Evidence:* The ROOT SET (R1-R6) contains `conftest.py` (which only configures `pytest_plugins = []` and imports nothing from `src/`), but excludes `tests/**`. If any utility module under `src/` is imported solely by tests (or `tests/conftest.py`), `reachability.py` will classify it as dead. (Audit check: `tests/fixtures/real_services.py` imports `EmbeddingPipeline`, `VectorIndexer`, `GraphService`, `GraphQueryEngine`, `NexusProcessor`, and `ProbabilisticQueryEngine` -- all are reachable from R1 servers). However, `tests/` collection itself is pattern-based discovery, not an import graph from `conftest.py`.
3. **[BLOCKER] Script Closure Contradiction between Section 1 and Section 5:**
   - *Evidence:* Section 1 declares: *"Scripts: a scripts/*.py file is live only if it is in the ROOT SET; all 38 unclassified scripts are dead by construction"*. `scripts/test_bead_implementations.py` is NOT in R1-R6 (R4 is `{check_docs,acceptance_all_parts,bench_tools}.py`). Yet Section 5 specifies line-level surgery on `scripts/test_bead_implementations.py:21-55, 267` to keep it. Furthermore, tests 3, 5, and 6 in that script import `src.integrations.loop_interfaces`, `scripts.extract_graph_entities`, and `scripts.promotion_pipeline` (all deleted!). Either `test_bead_implementations.py` is in ROOT SET and needs full surgery across all 3 dead imports, or it is outside ROOT SET and deleted in full.
4. **[Soundness of Optional-Sidecar Rule]:**
   - *Audit Check:* Audited all 17 `except ImportError` blocks in `src/`. `bayesian/__init__.py:24` uses `try/except ImportError` to toggle between `pgmpy` and `lightweight` backends; both branches are live code. An automatic heuristic treating all `try/except ImportError` blocks as non-edges would wrongly kill the Bayesian tier. However, Plan Section 1 explicitly specifies a configured list (targeting `service_wiring.py:64-77`), which is sound and avoids collateral damage.

---

### B. Canonical Gate Shape & AST Verification (Plan P0.2, GATES P0-6)

1. **[MINOR] Manifest Count vs. Runner Identity:**
   - *Evidence:* GATES v6 lists 13 items total (P0-3, P0-5, P0-6, P1d, P1a, P1b, P1c, P2a, P2b, P3, P4, P5, P6). Item P0-6 is the runner `scripts/gates/run_self_tests.py`. The remaining gate scripts total exactly 12. `run_self_tests.py` must check the 12 target gate scripts and exclude itself from the self-test probe manifest to yield `modules_accepted=12` and `shape_violations=0`.
2. **[Meaningfulness of AST Check]:**
   - *Audit Check:* Enforcing AST matching for `assert not probe(bad)` in `self_test()`, assignment `ok = probe(...)` in `main()`, and gating `print(TOKEN)` behind `if not ok: return 1` guarantees that exit code and stdout token emission are functionally coupled to the probe return value, resolving Codex R4 #3.

---

### C. Two-Artifact Split (Phase 0 Baseline & Phase 3 Pre-Deletion SHA)

1. **[Soundness & Verification]:**
   - *Audit Check:* `audits/baseline-2026-09-03.json` created in Phase 0 with `open(..., "x")` stores test counts, nodeids, and sha256. `audits/phase3-pre-deletion.json` created at the start of Phase 3 stores only the parent commit SHA. This eliminates the v5 chicken-and-egg immutability violation.
2. **[MINOR] Windows Git Worktree Cleanup:**
   - *Evidence:* `deletion_closure.py` creates a temporary worktree via `git worktree add <tmp> <pre_deletion_sha>` to compute nodeid differences. On Windows (`win32`), open file descriptors or active Python processes holding locks in `<tmp>` will cause `git worktree remove` to fail with `PermissionError`. The subprocess/file handles must be explicitly closed before the finally-block cleanup.

---

### D. Retrieval Coverage & Degradation Causes (Plan P1c, GATES P1c)

1. **[Registered Stdio Tools Enumeration]:**
   - `src/mcp/tool_registry.py:21-40` registers 18 tools. Exactly 5 return multi-tier/vector memory retrieval: `vector_search`, `unified_search`, `context_retrieve`, `graph_query`, and `hipporag_retrieve`.
2. **[HTTP Routes Enumeration]:**
   - `src/mcp/http_server.py` exposes 4 routes returning query results: `/tools/vector_search` (:757), `/tools/search` (:873), `/tools/unified_retrieve` (:938), and `/tools/graph_query` (:854). The first three execute the 3-tier pipeline (via `_run_nexus_query` and `unified_router`). `/tools/graph_query` calls `graph_engine.query()` directly without 3-tier fallback or degradation tracking; P1c covers the 3 multi-tier routes (`http_routes=3`, `http_all_down_503=3`).
3. **[True Number of Degradation Causes in tier_queries.py]:**
   - *Evidence:* `src/nexus/tier_queries.py`:
     - Cause 1 (`service_missing`): `not self.vector_indexer or not self.embedding_pipeline` (:39), `not self.graph_query_engine` (:85), `not self.probabilistic_query_engine` (:136).
     - Cause 2 (`exception`): vector `except Exception` (:73), hipporag `except Exception` (:119), bayesian `except Exception` (:204).
     - Cause 3 (`bayesian_timeout_or_empty`): `if raw_results is None:` (:145).
     Empty query returns (0 matches) are valid empty sets, not degradation. The true number of degradation failure causes is exactly 3 (`causes=3`).

---

### E. Phase 3 Surgery Ranges Verification

1. **[VERIFIED EXACT] `src/mcp/service_wiring.py`:**
   - Lines 64-77: Optional import try-blocks (`Qwen3VLEmbedder`, `VisualMemoryService`, `VisualMemoryIndexer`, `UnifiedSearchRouter`). Exact.
   - Lines 254-317: `_visual_service`, `_unified_router`, `_visual_config`, properties and `_init_visual_memory()`. Exact.
2. **[VERIFIED EXACT] `src/nexus/__init__.py`:**
   - Line 8 (`"MemoryMCPQueryService"` in `__all__`) and Lines 17-21 (`getattr` branch for `MemoryMCPQueryService`). Exact.
3. **[BLOCKER] `src/nexus/processor.py` (Core Pipeline Deletion Risk):**
   - *Evidence:* Plan states: `use_rlm (:101,126-169), _process_rlm (:154-177)`.
   - Inspection of `processor.py`: Lines 126-139 are `if use_rlm: ... return rlm_result`. Lines 141-152 are the CORE non-RLM 5-step pipeline execution (`result, stats = self._execute_pipeline(...)`).
   - If lines 126-169 are deleted as written, the core 5-step pipeline is destroyed, and lines 154-169 of `_process_rlm` are partially clipped.
   - *Correction:* Target `use_rlm` in `process()` at :101 (param) and :126-139 (dispatch block). Target `_process_rlm` at :154-177.
4. **[MINOR] `src/integrations/beads_bridge.py`:**
   - Plan specifies `:530-748+`. Class `BeadsMemoryBridge` starts at line 530 and extends through line 764 (EOF). Range should be `:530-764`.
5. **[VERIFIED EXACT] `tests/unit/test_phase5_memory_mcp_tail.py`:**
   - Lines 7-14 imports deleted; lines 18-30 (`test_graph_node_manager...`) kept; lines 33-53, 56-85, 88-119 deleted. Exact.
6. **[VERIFIED] `tests/integration/test_nexus_integration.py`:**
   - Line 33 import deleted. Lines 272-394 (`TestDashboardGraphVisualizer`) deleted.
   - Lines 395-485 (`TestCrossModuleIntegration`) audit: Both test methods (`test_frontmatter_to_cytoscape_pipeline` and `test_inheritance_to_beads_pipeline`) depend on deleted `DashboardGraphVisualizer`, `FrontmatterMapper`, and `PropertyInheritanceChain`. 100% of the class is dead and must be deleted. Lines 40-110 (`TestCytoscapeExporter`) remain intact.
7. **[MAJOR] `tests/integration/test_week7_integration.py` Line Drift:**
   - *Evidence:* Plan states: `(:19, :95, :106, :126, :147)`. The actual file has only 146 lines total!
   - Actual locations of SchemaValidator tests: `test_schema_validation_with_kv_store` (:17-31), `test_obsidian_sync_with_schema_validation` (:76-94, SchemaValidator at :89), `test_5_tier_storage_query_routing` (:97-112), `test_memory_lifecycle_stages` (:115-130), `test_performance_targets_defined` (:133-145).
8. **[MAJOR] `scripts/test_bead_implementations.py` Remaining Dead Imports:**
   - *Evidence:* Plan targets :21-55 and line 267 (`test_org002_mode_aware_router`). However, lines 95-144 (`test_org003_loop_interfaces`) import deleted `src.integrations.loop_interfaces`; lines 204-225 and lines 228-251 import deleted `scripts.extract_graph_entities` and `scripts.promotion_pipeline`. Keeping this script without fixing or removing those tests will break on execution.

---

### F. Docs Oracle (Plan Section 6, GATES P4)

1. **[VERIFIED SOUND]:**
   - The four reference patterns (`src/<path>.py`, `src\<path>.py`, `from src.<dotted> import`, `from <pkg>.<mod> import`) cover all referenced formats in CURRENT_DOCS.
   - Manifest line 661 (`D:\Projects\life-os-dashboard\...`) is in an external project block. Planting a local import in that external block as a negative control ensures the regex parser does not produce false positives on external documentation.
   - Separate `--docs-root` and `--code-root` prevent `ModuleNotFoundError` during fixture execution.

---

### G. GATES v6 EXPECT Tokens Verification

1. **[VERIFIED SOUND]:**
   - All 13 EXPECT tokens across P0-3 through P6 are strictly defined, syntactically valid regex or exact strings, and map 1:1 to verifiable invariants:
     - `P0-3`: `absent=8 refs=0 excluded_scan_artifacts=[1-9]\d*`
     - `P0-5`: `sha256_match=1 rewrite_refused=1 acceptance="12 PASS \| 0 XFAIL \| 0 FAIL"`
     - `P0-6`: `SELF_TESTS_OK 12/12 modules_accepted=12 shape_violations=0`
     - `P1d`: `pgmpy=12 lightweight=12 adapter_removed=1`
     - `P1a`: `no_network=1 unknown_node=1 none_result=1 positive=1`
     - `P1b`: `handlers=3 modes=3 cases=9 positive=1 http_beads_error=1`
     - `P1c`: `causes=3 stdio_handlers=5 stdio_all_down_error=5 http_routes=3 http_all_down_503=3 clean=1 no_processor=1 threads=4 concurrent_leak=0`
     - `P2a`: `tools=[1-9]\d* rows_expected=[1-9]\d* rows_actual_match=1 error_rows=[1-9]\d*`
     - `P2b`: `expired_row_removed=1 spy_first=1 spy_second=0 reacquired_after_ttl=1 contenders=2 concurrent_runs=1`
     - `P3`: `dead_remaining=0 allowed_dead=[0-9]+ deleted=[1-9]\d* tools=[1-9]\d* nodeid_diff_exact=1 passed=[1-9]\d* failed=0 errors=0`
     - `P4`: `forms=4 planted_violations=4 external_control_clean=1 real_ok=1`
     - `P5`: `configured=[1-9]\d* measured=\d+\.\d+ ok=1`
     - `P6`: `backend=lightweight canary_search=1 canary_unified=1 wrong_key=401`

---

### H. Recorded Dissent: universal_components.py (Plan Section 11)

1. **[MAJOR] Import-Graph Reachability vs. ALLOWED_DEAD Contradiction:**
   - *Evidence:* `universal_components.py` is imported at module scope by `src/mcp/service_wiring.py:18-23` and `src/mcp/http_server.py:71-76`. Because `service_wiring.py` and `http_server.py` are in ROOT SET R1, an AST import-graph reachability traversal will visit `universal_components.py` and classify it as **LIVE**.
   - Consequently, `reachability.py` will NOT place it in the dead set. Placing `universal_components.py` in `ALLOWED_DEAD` expects it to appear in the dead list, creating an immediate assertion contradiction in Gate P3.
   - *Remedy:* Resolve the dissent cleanly: delete `src/universal_components.py` and delete the uncalled wrapper functions and imports in `service_wiring.py:18-23, :98-130` and `http_server.py:71-76, :90-115`.

---

### 5-Line Verdict

1. Plan v6 is NOT safe to execute Phase 0 without correcting the `processor.py` line range.
2. The range error in `processor.py` (deleting lines 126-169) would destroy the core 5-step pipeline execution.
3. The contradiction between `universal_components.py`'s import-reachability and its `ALLOWED_DEAD` parking must be resolved.
4. The status of `scripts/test_bead_implementations.py` must be reconciled with the ROOT SET rule.
5. These three gaps are purely static text corrections that can be resolved immediately in a v6.1 plan before starting Phase 0.