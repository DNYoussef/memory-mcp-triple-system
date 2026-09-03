1. Where the framing is wrong:
   - **Tag**: MAJOR
   - **Rationale**: The completion plan asserts that `docs/CURRENT.md` is the "declared source of truth for the contract" (`COMPLETION-PLAN-2026-09-03.md:10`). However, `docs/CURRENT.md` contains multiple unfulfilled, aspirational claims (e.g., `ProactiveContextInjector` at `docs/CURRENT.md:51`, tracking every tool with `QueryTrace` at `docs/CURRENT.md:52`, and scheduled background lifecycle scheduler at `docs/CURRENT.md:65`). The actual working contract of the system is defined by the 18 active stdio tools registered in `src/mcp/tool_registry.py:get_tool_definitions` and verified by `scripts/acceptance_all_parts.py`. Treating `docs/CURRENT.md` as the contract for WIRE/DELETE/DEFER triage leads to circular reasoning and unnecessary complexity (retaining/wiring dead systems).
   - **Tag**: MAJOR
   - **Rationale**: In `P2b`, the plan proposes not wiring `src/sleep/consolidation_scheduler.py` but instead implementing a custom throttled maintenance call in `MemoryIngestionService.ingest` (`COMPLETION-PLAN-2026-09-03.md:103-107`). This is a framing error: `src/memory/lifecycle_scheduler.py` already implements a complete background lifecycle scheduler that runs `demote_stale_chunks`, `archive_demoted_chunks`, and `cleanup_expired` periodically. `src/sleep/consolidation_scheduler.py` is entirely dead, redundant, and contains placeholder callbacks (`src/sleep/consolidation_scheduler.py:128-136`). Instead of keeping `src/sleep` deferred in section 7, `src/sleep` should be flatly deleted, and we should trigger `MemoryLifecycleManager`'s existing maintenance methods on demand for stdio.

2. Gaps (dead/broken things omitted; callers DELETE breaks; fake-success/fail-open):
   - **Tag**: BLOCKER
   - **Rationale**: The plan's Phase 3 DELETE list (`COMPLETION-PLAN-2026-09-03.md:120`) includes `src/routing/query_router.py`. However, deleting this file will break `src/mcp/http_server.py:44` (`from src.routing.query_router import QueryRouter`) and `src/mcp/http_server.py:338` (`_router = QueryRouter()`), preventing the HTTP server from launching. It will also break `tests/integration/test_mcp_tools_e2e.py:463` and `:481` which explicitly import and instantiate `QueryRouter`.
   - **Tag**: MAJOR
   - **Rationale**: In `P1b`, changing `BeadsBridge._run_command` (cited as `_run_bd` in plan) to raise `BeadsCLIError` on returncode != 0 will break `tests/unit/test_beads_bridge.py:53-69` (`test_query_tasks_handles_failure`). That test mock-exits with returncode 1 and asserts that `tasks == []`. If `BeadsCLIError` is raised, this test will raise an uncaught exception and FAIL. The plan must include updating this test to assert `pytest.raises(BeadsCLIError)`.
   - **Tag**: MINOR
   - **Rationale**: In P1b, the plan references `_run_bd` as the method wrapping lines 285-310 in `src/integrations/beads_bridge.py` (`COMPLETION-PLAN-2026-09-03.md:65`). The actual method at `src/integrations/beads_bridge.py:282` is named `_run_command`, not `_run_bd`.

3. Overlaps or double-work between phases:
   - **Tag**: MAJOR
   - **Rationale**: In Phase 1 (P1a, P1b, P1c), the plan makes surgical edits to individual tool handlers in `src/mcp/request_router.py` to route errors and return `isError: True`. Then in Phase 2 (P2a), it proposes wrapping the dispatcher dict at `src/mcp/request_router.py:1032-1050` in a unified `_traced` wrapper function and deleting the per-handler tracing logic. This introduces double-work and regression risk: refactoring to a unified traced dispatcher (P2a) should occur BEFORE or alongside Phase 1 error handling so that errors are uniformly routed, captured, and traced in a single clean pass.

4. Ordering errors and hidden dependencies:
   - **Tag**: BLOCKER
   - **Rationale**: In `P2a`, the plan proposes to "delete the redundant 8-branch facade at `src/mcp/stdio_server.py:144-163` so there is ONE dispatch path." (`COMPLETION-PLAN-2026-09-03.md:95-97`). However, `tests/integration/test_phase4_mcp_tools.py:130-148` (`TestHandleCallToolRouting.test_routes_to_all_7_tools`) uses `inspect.getsource(handle_call_tool)` to inspect the literal source code of `stdio_server.py` and asserts that lines like `tool_name == "vector_search"` exist in the source! If the facade is deleted, this test will break.

5. GATES.md line analysis (lazy implementation; EXPECT on failure; non-hermetic):
   - **Tag**: MAJOR
   - **Rationale**: The coverage gate command `pytest ... | grep -E "^TOTAL|Required test coverage"` in `GATES-2026-09-03.md:9` is piped to `grep`. In Bash, the exit code of a pipe is the exit code of the last command (`grep`). If `pytest` fails on the coverage threshold and exits non-zero, the command still returns exit code 0 because `grep` successfully finds `"TOTAL"` in the printed summary table, causing a silent fail-open.
   - **Tag**: MAJOR
   - **Rationale**: The stale root oracle gate `! grep -rqE "gate[0-9]_verify|test_all_14_tools|test_rlm_quick" ... .` in `GATES-2026-09-03.md:14` recursively searches the entire directory without excluding `.git/`. Since Git index and history contain these filenames, this check will always fail-closed. It must exclude VCS and cache directories (e.g., `--exclude-dir=.git`).
   - **Tag**: BLOCKER
   - **Rationale**: In `GATES-2026-09-03.md:49`, the check command for `scripts/check_docs.py` expects `"DOCS_OK"`. However, inspecting `scripts/check_docs.py:105` reveals that upon success, it prints `"OK: all current docs match code reality."` and returns exit code 0. It never prints `"DOCS_OK"`. This gate will always fail-closed.

6. LOC Accuracy:
   - All cited line ranges are extremely accurate: `src/memory/lifecycle_manager.py:264` (`_metadata_from_string` starts at 263), `test_rlm_quick.py:10-16` (projects config line is 11), `test_all_14_tools.py:189-198` (checks ok_count/empty_count/error_count), `request_router.py:576-588` (bayesian isError: False fallback), and `request_router.py:173-188` (vector_search trace logging).

7. What will fail in practice on Windows + this venv:
   - **Tag**: MAJOR
   - **Rationale**: Native Windows Command Prompt does not support inline environment variables (`PYTHONPATH=.` or `MEMORY_MCP_BAYESIAN_BACKEND=lightweight`), which will cause syntax errors. POSIX commands like `test`, `tail`, `grep`, and `bash` are not natively available on Windows. The gate check commands in `GATES-2026-09-03.md` must be written in a cross-platform Python syntax or wrapped in scripts.

=== CORRECTED PHASE ORDER ===
1. Phase 0: Update GATES.md (remove POSIX tail/test, exclude .git/ from grep, fix check_docs.py EXPECT), lower cov-fail-under to floor, clean stale gate files.
2. Phase 1a: Refactor request_router.py to unified dispatch with tracing (_traced wrapper), keeping stdio_server.py facade to satisfy inspection tests.
3. Phase 1b: Fix Bayesian engine fake-successes and fix the broken lightweight backend API query signature/probabilities shape.
4. Phase 1c: Raise BeadsCLIError on CLI failures in beads_bridge.py, update failing test_query_tasks_handles_failure, and route to isError=True.
5. Phase 1d: Track degraded_tiers in NexusProcessor.process, routing exceptions from vector/hipporag tiers without failing closed.
6. Phase 2: Add throttled maintenance trigger inside memory_store's ingest path, triggering demote/archive/cleanup_expired via MemoryLifecycleManager.
7. Phase 3: Flatly delete dead src/sleep/ and unused test files. Keep query_router.py as it is imported by http_server.py and test_mcp_tools_e2e.py.
8. Phase 4: Rewrite README.md and docs/CURRENT.md to match code reality, updating check_docs.py to reject any stale claims, and verify gate passes.