Round-3 Adversarial MECE Audit Findings# Round-3 Adversarial MECE Audit of Completion Plan v4 & GATES v4

## Findings

### A. Section 1 KEEP Rule Wording
1. [BLOCKER] `src/hooks/` and `src/models/observation_types.py` are active live-session tools but are classified as DELETE under Section 1. Section 0 dictates: "The server gates every edit in the user's sessions via hooks (R3)." However, `src/hooks/*.py` are external CLI entrypoints invoked by Claude Code hooks (`.unlazy/memory-gate-codex/hooks.codex.json`), not imported transitively by `stdio_server.py` or `http_server.py`, nor invoked by Dockerfile/railway/.github. Under Section 1's literal triage rule ("DELETE everything else"), `src/hooks/` would be purged, disabling live hook enforcement.
2. [MAJOR] Dead subsystems under `src/` are omitted from Section 5's DELETE list despite matching Section 1 DELETE criteria:
   - `src/woundhealer/` (`woundhealer_core.py`, `rlm_client.py`): dead auto-repair system wired to deleted GuardSpine and RLM.
   - `src/cache/` (`memory_cache.py`): imported only by `src/services/curation_service.py` (which is deleted in Phase 3).
   - `src/visualization/` (`dashboard_graphs.py`): dead UI visualization unreferenced by either server.
   - `src/validation/` (`quality_validator.py`, `schema_validator.py`, `spec_validation.py`): unreferenced by live paths.
   Leaving them in `src/` contradicts Section 1's mandate.
3. [MAJOR] `scripts/ci_drift_validator.py` is misclassified as "repo tooling" to KEEP in Section 1. Section 5 notes: "remove that import and its check". However, lines 1-235 of `ci_drift_validator.py` exist exclusively to validate `OwnershipRegistry` (`from src.services.ownership_registry import OwnershipRegistry`) and `OwnershipViolationType` (`from src.integrations.ontology_schema import OwnershipViolationType`, line 30). Stripping ownership checks reduces the script to a no-op skeleton.
4. [MINOR] `scripts/gate_tri_tier.py` is invoked by `.github/workflows/ci.yml:28`. It is kept via the `.github/**` clause, but should be explicitly listed in Section 1's tooling list to avoid confusion with deleted root oracles (`gate0_verify.py`, etc.).

---

### B. P0.2 Self-Test Contract & P0.3 Immutable Baseline
5. [MAJOR] P0.2 self-test contract can be gamed by lazy scripts: `run_self_tests.py` merely asserts that invoking a gate with `--self-test` prints `SELF_TEST_REJECTED <gate-id>` and exits 0. A stub script could print the token without executing the real probe. The contract must require the gate script to demonstrate probe execution by passing a bad fixture directly to its probe function and asserting failure.
6. [MAJOR] `railway_smoke.py --self-test` deadlocks in Phase 0: Gate P0-6 requires all 12 gate self-tests to pass in Phase 0. But P6 `railway_smoke.py` targets a Docker container running the Railway build. Phase 0 cannot build or spin up Docker containers before product fixes (P1-P4) even begin. `railway_smoke.py --self-test` must execute its verification probe against an in-process local mock HTTP server rather than requiring a live Docker daemon.
7. [MINOR] P0.4 `stale_oracles.py` planted-bad fixture: Copying the entire project directory tree in a temp directory during self-test is slow and prone to Windows file locking. The probe should support `--root <dir>` so the bad fixture only needs a minimal temp folder containing one dummy oracle file.

---

### C. P0.6 Collected-Count Floor
8. [MAJOR] Working tree vs. committed HEAD timing in `deletion_closure.py`: If `deletion_closure.py` is executed before Phase 3 is committed, `HEAD` is the pre-deletion state and `HEAD~1` is Phase 2. `collected(HEAD)` will reflect the uncommitted working directory, breaking the equality assertion. The script must explicitly compare the current working tree against `HEAD` (where `HEAD` is the pre-deletion commit), or the plan must mandate committing Phase 3 before running the gate.
9. [MAJOR] AST function counting vs. pytest collection item discrepancy: Scalar subtraction `collected(HEAD) == collected(pre) - count` fails if AST parses function definitions while pytest counts collected item variants (e.g. test classes or helper nodes). `deletion_closure.py` must compute set difference on collected test nodeids (`S_pre - S_head == S_expected_deleted`) for exact, parametrization-safe verification.

---

### D. P1c Design
10. [MINOR] Stdio `handle_vector_search` (`request_router.py:175`) calls `tool.execute()` which discards `degraded_tiers`. While HTTP `/tools/vector_search` returns 503 on all-three-degraded, stdio `vector_search` returns an empty list with `isError: False`. If total degradation occurs, stdio `vector_search` silently fails open unless updated to use `execute_with_status()`.
11. [MINOR] In `request_router.py:653`, if `tool.nexus_processor` is `None`, `handle_unified_search` delegates to `handle_vector_search` without recording that `hipporag` and `bayesian` are degraded.

---

### E. P2a Tracing
12. [MINOR] In `request_router.py:1028-1064`, `handle_call_tool` logs traces to `query_traces.db`. Calling every tool with empty arguments `{}` triggers input validation errors on tools requiring arguments (e.g. `memory_store`), which guarantees `error_rows >= 1` and produces exactly `2 * tools` total rows across canonical and facade dispatches. The row arithmetic is sound.

---

### F. P2b Cleanup
13. [MAJOR] `MemoryIngestionService.__init__` lacks `kv_store`: `src/services/memory_ingestion_service.py:35-55` does not currently accept `kv_store`. To prevent AttributeError when checking the daily cleanup slot, `__init__` must add `kv_store=None` and `clock=None` parameters. When `kv_store is None` (e.g. in `tests/unit/test_memory_ingestion_service.py:36`), cleanup maintenance must safely no-op.
14. [MINOR] `KVStore` currently has no `set_if_absent` method (`src/stores/kv_store.py:245-310`). Implementing it using `INSERT OR IGNORE INTO kv_store ...` and verifying `cursor.rowcount > 0` is required for atomic slot acquisition.

---

### G. Section 5 DELETE Closure
15. [BLOCKER] Four orphaned test files will crash pytest with `ModuleNotFoundError` during Phase 3 collection:
    - `tests/test_ontology_bridge.py` imports `from src.services.ontology_bridge import OntologyBridge` (deleted).
    - `tests/test_ownership_registry.py` imports `from src.services.ownership_registry import OwnershipRegistry` (deleted).
    - `tests/unit/test_quality_gate.py` imports `from src.services.confidence.quality_gate import QualityGateAggregator` (deleted).
    - `tests/unit/test_tag_scorer.py` imports `from src.services.confidence.tag_scorer import TagAssignmentScorer` (deleted).
    None of these four files are in Section 5's whole-file DELETE list.
16. [BLOCKER] `tests/unit/test_phase5_memory_mcp_tail.py` over-retention: Section 5 instructs: "keep :18-53,88-119". But lines 33-53 test `TranscriptionVerifier` (`src.services.capture.transcription_verifier`) and lines 88-119 test `RailwayBufferService` (`src.services.capture.railway_buffer`). Both modules belong to deleted `src/services/capture/`. Only lines 18-30 test live `GraphService`. Keeping lines 33-53 and 88-119 causes immediate collection crashes.
17. [MAJOR] `tests/test_proactive_schema.py` and `tests/test_all_14_tools.py` omitted: Section 5 misses `tests/test_proactive_schema.py` (which tests deleted `src.integrations.proactive_schema`). Furthermore, `test_all_14_tools.py` exists at root AND inside `tests/test_all_14_tools.py`; Section 5 only deletes the root copy, leaving a broken test in `tests/`.
18. [MINOR] `src/nexus/__init__.py:8`: Section 5 notes removing lines 17-21, but line 8 still contains `"MemoryMCPQueryService"` in `__all__`. Line 8 must be updated to avoid broken wildcard imports.

---

### H. Phase 4 Docs Truth
19. [BLOCKER] `docs_truth.py` crashes if `--root` only contains `README.md` and `docs/`: `check_docs.py` calls `harvest_tool_names()`, which executes `from src.mcp.tool_registry import get_tool_definitions`. If `<temp>` contains only documentation files, Python raises `ModuleNotFoundError: No module named 'src'`. Additionally, all legitimate `src/...` references in documentation will fail to resolve under `<temp>`, producing dozens of false violations. `check_docs.py` must decouple `--docs-root` from `--code-root`, or `docs_truth.py` must copy/link `src/`.
20. [MINOR] Dead script reference in `docs/MCP-INTEGRATION.md:285`: references nonexistent script `scripts/test-mode-detection.py`.

---

### I. P6 Railway Smoke
21. [MAJOR] Embedding stub host binding: `scripts/gates/_embed_stub.py` must bind to `0.0.0.0`, not `127.0.0.1`. Docker Desktop on Windows cannot route `host.docker.internal` to host loopback.
22. [MINOR] Stub payload compliance: `src/indexing/embedding_pipeline_api.py:43-76` expects an OpenAI-compatible JSON structure (`{"data": [{"index": 0, "embedding": [...]}]}`). The stub must return 384-dimensional normalized vectors to guarantee ChromaDB cosine retrieval of the canary.

---

### J. GATES v4 EXPECT Tokens
23. [MAJOR] False positive failure in `stale_oracles.py`: `docs/connascence/scan-2026-06-06/connascence.json:3141` and `connascence.sarif` contain literal references to `gate0_verify.py`. Grepping `docs/` without excluding `docs/connasc