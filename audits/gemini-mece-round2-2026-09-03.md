### Round-2 Adversarial MECE Audit Findings (Plan v3 / Gates v3)

---

#### A. Section 1 Triage Rule (KEEP/FIX/DELETE)

1. **Contradiction between KEEP and DELETE on tested dead code**  
   **Tag:** BLOCKER  
   **File:** `audits/COMPLETION-PLAN-2026-09-03.md:18-22`  
   **Evidence & Impact:** The triage rule defines:  
   `- KEEP: reachable from stdio or http, or covered by a test that exercises it.`  
   `- DELETE: unreachable AND the whole dependency closure (... the specific test functions) goes with it.`  
   Every major subsystem slated for deletion under H1-H5 (`src/guardspine/` covered by `tests/unit/test_configguard.py`, `src/services/curation_service.py` covered by `tests/unit/test_curation_service.py`, `src/services/trigger_watchers/` covered by `tests/test_trigger_watchers.py`, `src/rlm/` covered by `tests/unit/test_nexus_processor.py`) has existing unit tests written when the modules were built. Under the literal condition `"or covered by a test that exercises it"`, all unreachable dead code with existing unit tests is classified as KEEP, directly contradicting DELETE. The rule must be amended to specify tests exercising live entrypoints or external interfaces.

2. **Misclassification of maintenance, migration, and CLI scripts**  
   **Tag:** MINOR  
   **File:** `audits/COMPLETION-PLAN-2026-09-03.md:18-22`, `scripts/`  
   **Evidence & Impact:** Operational scripts (e.g., `scripts/populate_memory_mcp.py`, `scripts/obsidian_sync.py`, `scripts/check_docs.py`, `scripts/ci_drift_validator.py`, `migrations/`) are neither reachable from stdio/http transports nor covered by unit tests. A literal application of the triage rule marks these valid operational utilities as DELETE candidates.

---

#### B. Section 2 Gate-Script Design

3. **Broken regex syntax in P2a EXPECT token causes permanent spurious failure**  
   **Tag:** BLOCKER  
   **File:** `audits/GATES-2026-09-03.md:43`, `audits/COMPLETION-PLAN-2026-09-03.md:65-69`  
   **Evidence & Impact:** In `GATES-2026-09-03.md:43`, gate P2a specifies:  
   `EXPECT: /TRACE_EVERY_TOOL_OK tools=(\d+) rows=\1 error_rows>=1/`  
   In standard regular expressions, `>=` matches the literal characters `>` and `=`. If the script outputs `error_rows=1` or `error_rows=2`, `re.search(r"error_rows>=1", text)` evaluates to `None`. The gate is guaranteed to fail spuriously on a working implementation. The regex pattern must be `error_rows=[1-9]\d*` or `error_rows=\d+`.

4. **Flawed `--self-test` failure contract and lazy regex matching**  
   **Tag:** MAJOR  
   **File:** `audits/COMPLETION-PLAN-2026-09-03.md:39-40`, `audits/GATES-2026-09-03.md:21-23`  
   **Evidence & Impact:** P0.5 requires that `--self-test` "runs the probe against a planted-bad input and must exit 1". If a script simply exits 1 on planted error, `run_self_tests.py` cannot distinguish a legitimate detected failure from an uncaught `SyntaxError`, `ImportError`, or `ModuleNotFoundError` (which also exits 1). A broken script that crashes immediately on import will be reported as a passed self-test. Furthermore, P0-6's expectation `/SELF_TESTS_FAILED_AS_EXPECTED \d+\/\d+/` matches `0/12`, allowing total failure to register as green. The contract should require exiting 0 on successful failure detection or printing an unambiguous token like `SELF_TEST_REJECTED_PLANTED_ERROR`.

5. **Test count drift between Phase 0 baseline and Phase 3 deletion gate**  
   **Tag:** MAJOR  
   **File:** `audits/COMPLETION-PLAN-2026-09-03.md:31-35, 96-101`, `audits/GATES-2026-09-03.md:52-54`  
   **Evidence & Impact:** Phase 0 records `baseline.json` before Phase 1. Phase 1 adds and updates tests across Bayesian backends, beads errors, and tier degradation. By the time Phase 3 executes, the baseline test count recorded in Phase 0 is stale. Additionally, `deleted_test_count is written by the deletion commit, read by the gate` lacks an independent oracle: an author can artificially inflate `deleted_test_count` to mask regressions in unrelated test suites.

6. **Hardcoded Windows absolute path in ledger CHECK lines breaks Linux and CI**  
   **Tag:** MAJOR  
   **File:** `audits/GATES-2026-09-03.md:11-64`, `audits/COMPLETION-PLAN-2026-09-03.md:14-16, 116-118`  
   **Evidence & Impact:** All CHECK commands in `GATES-2026-09-03.md` hardcode:  
   `D:/Projects/memory-mcp-triple-system/venv-memory/Scripts/python.exe`  
   Section 8 dictates that P6 runs in `.github/workflows/railway-smoke.yml` on `ubuntu-latest`. On Linux and any system without a `D:` drive, the CHECK lines will fail immediately with `No such file or directory`.

---

#### C. P1c Request-Local Tuple Design & All-Tiers-Down Rule

7. **Tuple return signature breaks `test_error_injection.py` and `test_nexus_processor.py`**  
   **Tag:** BLOCKER  
   **File:** `src/nexus/processor.py:445-464`, `tests/unit/test_error_injection.py:54, 63, 72`, `tests/unit/test_nexus_processor.py:133-135, 162-164, 189-191`  
   **Evidence & Impact:** Changing `_query_vector_tier`, `_query_hipporag_tier`, and `_query_bayesian_tier` to return `(results, error_or_None)` breaks multiple existing unit tests:  
   - `tests/unit/test_error_injection.py:54, 63, 72` asserts `result == []` directly against `proc._query_*_tier(...)`; these assertions will fail with `assert ([], "...") == []`.  
   - `tests/unit/test_nexus_processor.py:133-135, 162-164, 189-191` mocks `processor._query_vector_tier = lambda q, k: [dict(real_doc)]` and `_query_hipporag_tier = lambda q, k: []`. When `processor.recall()` unpacks `(results, err) = self._query_*_tier(...)`, these lambdas will raise `ValueError: not enough values to unpack (expected 2, got 1 or 0)`, breaking three tests.

8. **Public `processor.recall()` callers break if signature changes to a tuple**  
   **Tag:** MAJOR  
   **File:** `src/nexus/processor.py:428-464`, `tests/integration/test_nexus_search.py:105`, `tests/integration/test_pipeline_integration.py:175`, `tests/unit/test_nexus_processor.py:104, 138, 403, 415`  
   **Evidence & Impact:** The method at lines 428-464 of `processor.py` is named `recall()`, not `_recall()`. Tests in `tests/integration/test_nexus_search.py:105` and `tests/unit/test_nexus_processor.py:138` call `candidates = processor.recall(...)` and expect a list of dicts. If `recall()` returns `(candidates, degraded_tiers)`, calls such as `c.get("id")` and `assert all(isinstance(c, dict) for c in candidates)` fail with `AttributeError` and assertion errors.

9. **Architectural divergence on `tool.execute` in `handle_context_retrieve`**  
   **Tag:** MAJOR  
   **File:** `audits/COMPLETION-PLAN-2026-09-03.md:58-60`, `src/mcp/request_router.py:656, 1008`, `src/mcp/service_wiring.py:488-510`  
   **Evidence & Impact:** P1c claims `handle_context_retrieve` "shares tool.execute" with unified search. This is incorrect: `handle_unified_search` calls `tool.nexus_processor.process(...)` (`request_router.py:656`), while `handle_context_retrieve` calls `tool.execute(...)` (`request_router.py:1008`). `tool.execute` returns `List[Dict[str, Any]]` (`service_wiring.py:488`) without degradation details. Modifying `tool.execute`'s return type to include degraded tiers breaks its other callers (`handle_vector_search:175` and tests in `test_stdio_server.py:204`).

---

#### D. P2a Facade Routing & Tracing

10. **`UnboundLocalError` on `trace.retrieval_ms` in `handle_vector_search`**  
    **Tag:** MAJOR  
    **File:** `audits/COMPLETION-PLAN-2026-09-03.md:65-66`, `src/mcp/request_router.py:173-188, 201`  
    **Evidence & Impact:** P2a specifies: "Delete the per-handler block at request_router.py:173-188 (vector_search) so there is one tracing site." However, line 201 of `request_router.py` accesses `trace.retrieval_ms`:  
    `"latency_ms": trace.retrieval_ms`  
    Deleting lines 173-188 leaves `trace` undefined at line 201, triggering `UnboundLocalError` on every `handle_vector_search` call and failing 10 vector search tests in `tests/unit/test_stdio_server.py`. The handler must record elapsed time directly without referencing `trace`.

11. **Facade string inspection in `test_phase4_mcp_tools.py` preserved**  
    **Tag:** MINOR  
    **File:** `src/mcp/stdio_server.py:144-163`, `tests/integration/test_phase4_mcp_tools.py:130-148`  
    **Evidence & Impact:** `tests/integration/test_phase4_mcp_tools.py:130-148` inspects the AST source text of `handle_call_tool` for `tool_name == "vector_search"` etc. Routing each branch to `_handle_call_tool(tool_name, arguments, tool)` will keep these tests passing as long as the conditional statements remain verbatim. In `tests/unit/test_stdio_server.py`, fixtures are `MagicMock` instances and do not break on facade delegation.

---

#### E. P2b Throttled Cleanup

12. **Target object confusion in P2b gate specification (chunks vs. KV store entries)**  
    **Tag:** MINOR  
    **File:** `audits/COMPLETION-PLAN-2026-09-03.md:73-77`, `src/memory/lifecycle_manager.py:90-100`, `src/stores/kv_store.py:684-712`  
    **Evidence & Impact:** P2b specifies: "Gate: scripts/gates/cleanup_under_stdio.py stores a chunk with an expired TTL... asserts the chunk is gone". `cleanup_expired()` invokes `kv_store.cleanup_expired()`, which purges expired entries from the SQLite `kv_store` table. Ingested memory chunks are stored in ChromaDB/vector store and do not have TTL fields. The gate must test expired KV entries via `kv_set`, not chunks.

13. **MagicMock type error during throttled lifecycle execution**  
    **Tag:** MINOR  
    **File:** `src/services/memory_ingestion_service.py:265-273`, `tests/unit/test_memory_ingestion_service.py:36, 90-93`  
    **Evidence & Impact:** In `test_memory_ingestion_service.py`, `lifecycle_manager` is a `MagicMock`. Calling `float(self._lifecycle_manager.kv_store.get("lifecycle:last_cleanup"))` will raise `TypeError` when parsing mock objects unless handled with safe type guards or `try/except`.

---

#### F. Phase 3 & Section 7 Deletion Closure

14. **Unlisted test files omitted from deletion list will crash pytest collection**  
    **Tag:** BLOCKER  
    **File:** `audits/COMPLETION-PLAN-2026-09-03.md:88-95`, `tests/unit/test_quality_trends.py:5`, `tests/unit/test_usage_aggregator_buckets.py:13`, `tests/unit/test_phase5_memory_mcp_tail.py:8`, `tests/integration/test_curation_workflow.py:15`, `tests/unit/test_curation_service.py:10`, `tests/test_proactive_context_injector.py:13`, `test_rlm_organ_map.py:4`  
    **Evidence & Impact:** Deleting H1-H5 directories without removing their active test importers will cause test collection to fail with `ModuleNotFoundError`:  
    - H1 deletion misses `tests/unit/test_quality_trends.py` and `tests/unit/test_usage_aggregator_buckets.py`.  
    - H1 deletion misses `tests/unit/test_phase5_memory_mcp_tail.py` (mixed test importing deleted `BeadsTools` and `capture` while testing live `GraphService`).  
    - H3 deletion misses `tests/integration/test_curation_workflow.py` and `tests/unit/test_curation_service.py`.  
    - H4 deletion misses `tests/test_proactive_context_injector.py` (482 lines).  
    - H5 deletion misses the root test script `test_rlm_organ_map.py`.

15. **Incomplete backend deletion closure for H1 tools leaves orphaned services**  
    **Tag:** MAJOR  
    **File:** `audits/COMPLETION-PLAN-2026-09-03.md:88-91, 108`, `src/services/`  
    **Evidence & Impact:** H1 deletes `src/mcp/tools/{confidence_tools,capture,ownership,proactive,ontology,beads_tools}.py`, but leaves behind `src/services/capture/`, `src/services/confidence/`, `src/services/ownership_registry.py`, and `src/services/ontology_bridge.py`. These backend services have zero remaining callers outside deleted tools and scripts, violating Section 1's dependency closure rule.

16. **Curation service and beads namespace router verification**  
    **Tag:** MINOR  
    **File:** `src/services/curation_service.py`, `src/indexing/vector_indexer.py:25`, `src/integrations/beads_bridge.py:638`, `tests/unit/test_namespace_router.py`  
    **Evidence & Impact:**  
    - `resolve_persist_dir` is defined in `src/indexing/vector_indexer.py:25` (not `curation_service.py`). Deleting `curation_service.py` does not affect path resolution or any module in `src/mcp`.  
    - Deleting the `namespace_router` branches in `beads_bridge.py` does not break `tests/unit/test_namespace_router.py` (which only tests key parsing functions in `src/telemetry/`) or beads tests.

---

#### G. Phase 4 Ten-Docs Procedure & `check_docs.py`

17. **`check_docs.py` cannot test negative controls without path override support**  
    **Tag:** MAJOR  
    **File:** `audits/COMPLETION-PLAN-2026-09-03.md:104-106`, `scripts/check_docs.py:16-30`  
    **Evidence & Impact:** The plan states: "the gate script plants a stale sentence in a temp copy of README and asserts check_docs reports 1 violation". However, `scripts/check_docs.py` hardcodes `ROOT` relative to `__file__` and reads `README.md` at `os.path.join(ROOT, "README.md")` with no CLI flags or env var support. `docs_truth.py` cannot test a temp copy without either modifying `check_docs.py` to accept `--root` or mutating the tracked `README.md` in place.

---

#### H. P6 Railway Smoke Docker Gate

18. **Railway HTTP API endpoints, auth, and schema confirmation**  
    **Tag:** MINOR  
    **File:** `src/mcp/http_server.py:81, 125-155, 516-521, 583-611, 873-912`, `Dockerfile.railway:1-50`  
    **Evidence & Impact:**  
    - `/health` is a real GET endpoint (`http_server.py:583-611`). It returns `"components": {"bayesian": "available (lightweight)"}` when pgmpy is absent, but lacks a top-level `"bayesian_backend"` key (must be added per P6).  
    - The Railway image starts without `pgmpy` today: `Dockerfile.railway` installs `requirements-api.txt` (no torch/pgmpy), and `src/bayesian/__init__.py:17-38` catches `ImportError` and falls back to lightweight engines.  
    - `/tools/search` (lines 873-912) requires header `X-MCP-API-Key: <key>` or `Authorization: Bearer <key>` (validated against `MCP_API_KEY` / `MEMORY_MCP_API_KEY`, line 81) and JSON body matching `SearchRequest` (`{"query": "<str>", "limit": 10, "mode": null}`, lines 516-521).

---

### Verdict: Is v3 Safe to Start Phase 0?

NO. Plan v3 contains three BLOCKER defects that prevent execution:
1. Section 1 triage rule misclassifies all tested dead code as KEEP.
2. Gates v3 P2a contains an invalid regex (`error_rows>=1`) that will fail spuriously.
3. Phase 3 deletion omits 7 active test files across H1, H3, H4, and H5, guaranteeing broken test collection.
Plan v3 must be updated to v4 to resolve these findings before Phase 0 begins.