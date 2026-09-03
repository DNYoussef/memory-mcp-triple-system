# Round-4 Adversarial MECE Audit: Completion Plan v5 & GATES v5

## Findings

### A. Section 1 KEEP Rule Clauses (a)-(d)
1. **[BLOCKER] Clause (b) deletes active hook dependencies (`src/models/observation_types.py` and helper services).**
   - *Evidence*: Section 1 clause (b) explicitly protects only `src/hooks/*.py`. However, `src/hooks/session_start_handler.py:28-29`, `src/hooks/post_tool_handler.py:32`, and `src/hooks/stop_handler.py:29` directly import `src.models.observation_types.Session`, `src.services.observation_bridge.ObservationBridge`, `src.services.token_calculator.TokenTracker`, and `src.services.session_summarizer.SessionSummarizer`. None of these 4 modules are reachable from tool handlers (clause a) or CI/docs (c, d). Section 1 declares: *"A transitive import is NOT enough ... DELETE = everything else"*. Under this literal rule, `src/models/observation_types.py` and the 3 hook services would be deleted, breaking Claude Code hooks (`.unlazy/memory-gate-codex/hooks.codex.json`).
   - *Remedy*: Expand clause (b) to include `src/hooks/*.py` and its direct dependencies: `src/models/observation_types.py`, `src/services/observation_bridge.py`, `src/services/token_calculator.py`, and `src/services/session_summarizer.py`.

2. **[MAJOR] Section 1 contradicts Section 5 regarding ~30 unmaintained scripts.**
   - *Evidence*: Section 1 restricts kept repo tooling to `scripts/{check_docs,acceptance_all_parts,bench_tools,obsidian_sync,populate_memory_mcp}.py`, `scripts/gate_tri_tier.py`, and `scripts/gates/**`. Everything else is marked for DELETE. Yet Section 5 lists only 16 scripts under DELETE. Over 30 scripts (e.g. `scripts/migrate_confidence.py`, `scripts/migrate_tagging.py`, `scripts/extract_graph_entities.py`, `scripts/demo_rem_fixes.py`) are dead and unreferenced, but omitted from Section 5's DELETE list.
   - *Remedy*: Either reconcile Section 1 to permit archival scripts in `scripts/`, or add the dead scripts to Section 5 DELETE.

3. **[MAJOR] Unused integration schemas and mappers omitted from DELETE.**
   - *Evidence*: `src/integrations/external_import_schema.py`, `frontmatter_mapper.py`, `property_inheritance.py`, `loop_interfaces.py`, and `metadata_sync.py` have 0 callers across all live tool handlers and HTTP routes. None are reachable under clauses (a)-(d), yet none are listed in Section 5 DELETE.
   - *Remedy*: Add these 5 dead integration files to Section 5 DELETE.

4. **[MINOR] Stray artifact `src/stores/event_log.py.init` omitted.**
   - *Evidence*: `src/stores/event_log.py.init` is an abandoned 130-byte rename artifact. It should be deleted in Phase 3.

---

### B. AST-Backed Self-Test Contract (P0.2)
5. **[MAJOR] AST check cannot verify control flow reachability of `--self-test` without a fixed interface.**
   - *Evidence*: Plan v5 requires `run_self_tests.py` to assert by AST that the module's `main()` and `--self-test` branch both call `probe`. Because argument parsing logic varies (argparse vs sys.argv checks), AST inspection of arbitrary conditional branches cannot prove execution without a defined contract.
   - *Remedy*: Standardize gate structure: each gate exposes `def probe(fixture) -> bool:` and `def self_test() -> bool:`, where `self_test()` builds the planted-bad fixture and asserts `probe(bad_fixture) is False`. AST then simply inspects `def self_test` and `def main`.

6. **[MINOR] `railway_smoke.py --self-test` in-process probe requires mock environment credentials.**
   - *Evidence*: `src/mcp/http_server.py:84` reads `MEMORY_MCP_API_KEY`. When `railway_smoke.py --self-test` invokes FastAPI `TestClient(app)` in-process during Phase 0, it must pass a mock `X-MCP-API-Key` or set the env var in the test process to verify 401 on bad keys.

---

### C. P0.3 Exclusive-Create Baseline & P0.6 Pre-Deletion SHA
7. **[MAJOR] `baseline.py --write` exclusive-create prevents stamping `pre_deletion_sha`.**
   - *Evidence*: P0.3 mandates `baseline.py --write` use `open(path, "x")` and refuse if the file exists with `BASELINE_EXISTS`. In Phase 0, `baseline.json` is created and committed. In Phase 3, P0.6 requires writing `pre_deletion_sha` into `baseline.json`. Calling `baseline.py --write` in Phase 3 will immediately fail with `BASELINE_EXISTS`.
   - *Remedy*: Specify a dedicated subcommand: `baseline.py --stamp-pre-deletion <sha>` that loads existing JSON, asserts `pre_deletion_sha is None`, updates the field, and rewrites the file.

8. **[MINOR] `deletion_closure.py --self-test` in Phase 0 must tolerate null `pre_deletion_sha`.**
   - *Evidence*: During Phase 0, `baseline.json` has no `pre_deletion_sha`. The planted fixture for `deletion_closure.py --self-test` must provide dummy test sets rather than executing `git worktree add`.

---

### D. P1c Degradation & Error Reporting
9. **[BLOCKER] `handle_hipporag_retrieve` returns `isError: False` with all tiers down.**
   - *Evidence*: `hipporag_retrieve` is a registered tool (`src/mcp/tool_registry.py:24`). In `src/mcp/request_router.py:440-442`, when `tool.hipporag_service` is None, it falls back to: `results = tool.execute(query, limit, mode)`. If all three tiers are down, `tool.execute` returns `[]`, and line 464 returns `{"content": content, "isError": False}`. This is an active stdio path reporting success on total failure, violating Done criterion (a).
   - *Remedy*: Update `handle_hipporag_retrieve` to call `tool.execute_with_status()` and return `isError: True` when all tiers are degraded.

10. **[MAJOR] `test_stdio_server.py` vector search tests break on `execute_with_status`.**
    - *Evidence*: In `tests/unit/test_stdio_server.py:120-145`, fixture `mock_vector_tool` configures standard `MagicMock`. When `handle_vector_search` unpacks `(results, degraded) = tool.execute_with_status(...)`, `MagicMock` cannot unpack as a 2-tuple. Lines 163, 171, and 222 also assert specifically on `mock_vector_tool.execute`.
    - *Remedy*: Update fixture `mock_vector_tool.execute_with_status.return_value = ([], [])` and update assertions at :163, 171 to `execute_with_status`.

---

### E. P2b Cleanup Claim Semantics
11. **[BLOCKER] Naive `INSERT OR IGNORE` in `set_if_absent` permanently deadlocks rolling TTL claim.**
    - *Evidence*: Section 4 specifies: `set_if_absent(key, value, ttl) = INSERT OR IGNORE + rowcount > 0`. In `src/stores/kv_store.py:114`, `key` is `TEXT PRIMARY KEY`. SQLite `INSERT OR IGNORE` rejects any insert if `key` already exists, completely ignoring `expires_at`. When the 24h TTL expires, the expired row remains in the SQLite table until deleted. On the next day, `INSERT OR IGNORE` conflicts on `key`, inserts 0 rows (`rowcount == 0`), and returns False! Because only the claim winner calls `cleanup_expired()`, the expired claim row is never purged, permanently preventing any process from ever acquiring the claim again.
    - *Remedy*: `set_if_absent` must atomically clear expired keys first: inside the transaction execute `DELETE FROM kv_store WHERE key = ? AND expires_at IS NOT NULL AND expires_at < ?;` using current ISO timestamp, followed by `INSERT OR IGNORE INTO kv_store ...`, returning `cursor.rowcount > 0`.

---

### F. Section 5 DELETE Closure Misses & Over-Deletions
12. **[BLOCKER] `tests/integration/test_nexus_integration.py` imports deleted `src.visualization`.**
    - *Evidence*: `tests/integration/test_nexus_integration.py:33` top-level imports `from src.visualization.dashboard_graphs import DashboardGraphVisualizer`. When `src/visualization/` is deleted in Phase 3, running pytest collection crashes with `ModuleNotFoundError`. The file also contains `TestDashboardGraphVisualizer` (:272-394). It is omitted from Section 5's DELETE lists.
    - *Remedy*: Add `tests/integration/test_nexus_integration.py` to Section 5 mixed-file edits: delete line 33 import and lines 272-394 (`TestDashboardGraphVisualizer`).

13. **[BLOCKER] `tests/unit/test_qwen3vl_embedder.py` omitted from DELETE tests.**
    - *Evidence*: `tests/unit/test_qwen3vl_embedder.py:19` top-level imports `from src.services.qwen3vl_embedder import Qwen3VLEmbedder`. Section 5 deletes the visual embedder (`src/services/qwen3vl_embedder.py`), but does not list `test_qwen3vl_embedder.py` under whole-file test deletions. Pytest collection will fail immediately with `ModuleNotFoundError`.
    - *Remedy*: Add `tests/unit/test_qwen3vl_embedder.py` to Section 5 "DELETE tests (whole files)".

14. **[MAJOR] `src/universal_components.py` unreferenced by routes but imported in `http_server.py`.**
    - *Evidence*: `src/universal_components.py` is imported at `src/mcp/http_server.py:71-76` and wrapped in helper functions `_get_tagger` etc. (:90-115). No HTTP route or tool handler calls these helpers. It is dead under Section 1 reachability, but omitted from Section 5 DELETE.
    - *Remedy*: Delete `src/universal_components.py` and strip lines 71-115 from `src/mcp/http_server.py`.

15. **[MINOR] `test_phase5_memory_mcp_tail.py:56-85` tests deleted `BeadsTools`.**
    - *Evidence*: Lines 56-85 test `BeadsTools`, which is deleted with `src/mcp/tools/beads_tools.py`. Plan v5 states "keep ONLY :18-30; :33-53 and :88-119 go too". Lines 56-85 and imports :7-14 must be explicitly removed.

---

### G. Phase 4 Docs Truth
16. **[MAJOR] `docs_truth.py` negative control must plant into a file listed in `CURRENT_DOCS`.**
    - *Evidence*: `scripts/check_docs.py:16-27` only scans files explicitly enumerated in `CURRENT_DOCS`. If `docs_truth.py` creates a temporary file in `docs-root` not in `CURRENT_DOCS`, `check_docs.py` ignores it and reports 0 violations.
    - *Remedy*: Specify that the planted stale reference is appended to `<temp_docs_root>/docs/CURRENT.md`.

---

### H. GATES v5 EXPECT Tokens
17. **[MAJOR] P0-3 EXPECT token has arithmetic mismatch (`absent=7` vs 8 files).**
   - *Evidence*: Plan v5 Section 2 P0.4 enumerates EIGHT files: `gate0_verify.py`, `gate1_verify.py`, `gate2_verify.py`, `gate4_verify.py`, `test_rlm_quick.py`, root `test_all_14_tools.py`, root `test_rlm_organ_map.py`, AND `tests/test_all_14_tools.py`. Yet both Plan v5 prose ("Seven files") and GATES v5 P0-3 EXPECT specify `absent=7`. Deleting all 8 files will cause the gate regex `absent=7` to fail.
   - *Remedy*: Update GATES v5 P0-3 EXPECT token to `absent=8`.

---

## Verdict

NOT SAFE to start Phase 0 from v5.
Four BLOCKERS remain:
1. Clause (b) deletes active hook dependencies (`src/models/observation_types.py`, etc.).
2. `handle_hipporag_retrieve` returns `isError: False` when all tiers are down.
3. Naive `INSERT OR IGNORE` in `set_if_absent` permanently deadlocks rolling TTL claims after 24h.
4. Omission of `test_qwen3vl_embedder.py` and `test_nexus_integration.py` causes immediate `ModuleNotFoundError` during Phase 3 collection.