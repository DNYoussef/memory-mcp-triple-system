# Memory MCP Triple System - Completion Plan v10 (2026-09-03; convergence fixes folded; READY FOR PHASE 0)

Provenance: v1 Claude -> R1 (Codex gpt-5.6-sol xhigh 24 / Gemini-served-as-3.5-flash 12) -> v2 ->
v3 (H1-H6 decided by Torvalds rules) -> R2 (31/18) -> v4 -> R3 (20/23) -> v5 -> R4 (17/17, 14
BLOCKER) -> v6 (computed reachability) -> R5 (Codex 8 groups / 5 BLOCKER,
audits/codex-mece-round5-2026-09-03.md; Gemini 3.8-flash 8 groups / 3 BLOCKER,
audits/gemini-mece-round5-2026-09-03.md) -> v7. Every R5 finding was verified against the
code before folding. BOTH R5 verdicts: the remaining gaps are bounded static corrections, closable
in one revision; execution is needed only to produce the actual computed closure and the
environment measurements. Opus 5 and Gemini 3.8 Flash then ran one blind read-only pre-execution
pass each; their verified findings are folded here. Ledger: audits/GATES-2026-09-03.md (v10).

**Near-miss worth stating plainly (R5, both models):** v6's "delete processor.py:126-169" would
have deleted the core 5-step pipeline at :140-152 and cut `_process_rlm` in half. The corrected
ranges are in section 5. This is what the round bought.

## 0. Frame
- Ruling: HARD. The server gates every edit in the user's sessions via hooks (R3: never break the
  user). Work in a worktree; the live server keeps running from main until merge.
- Done = one branch merged where (a) no live-path tool (stdio OR http) reports fake success,
  (b) every sentence in the ten current-facing docs is true, (c) src/ contains nothing outside the
  computed live closure except named, reasoned exceptions, (d) the ledger is green on both models
  after the last edit, (e) the Railway image passes a hermetic smoke.
- Worktree: `D:/Projects/_crucible/memory-mcp-completion-20260903`, branch
  `completion-2026-09-v7`, based on audited commit `00be8a6`.
  venv-memory/ is gitignored (.gitignore:79) and absent there.
- Interpreter: gates call `$MMTS_PY`. Each gate script does `sys.path.insert(0, worktree_root)`.

## 1. Reachability, computed (scripts/gates/reachability.py)
Builds the live set by AST import-graph closure from a declared ROOT SET; every `src/**.py`
outside it is reported dead. ROOT SET (the only hand-written part; each entry carries its evidence):
  R1 src/mcp/stdio_server.py, src/mcp/http_server.py         two servers
  R2 src/hooks/*.py                                          C:\Users\17175\.claude\settings.json:17,41,45,...
     (their deps - models/observation_types, services/{observation_bridge,token_calculator,
     session_summarizer} - are pulled in BY the closure, not by a list)
  R3 scripts/gate_tri_tier.py                                .github/workflows/ci.yml:28
  R4 scripts/check_docs.py, scripts/acceptance_all_parts.py, scripts/bench_tools.py
                                                             docs/CURRENT.md "Verification"
  R5 scripts/obsidian_sync.py                                README.md:446
     scripts/fix_imports.py                                  docs/QUICK-START.md:22
     scripts/ingest_documentation.py                         docs/architecture/SELF-REFERENTIAL-MEMORY.md:80
     (R5 additions - Codex R5 #1: v6 would have deleted three scripts its own current docs tell
     users to run. Alternative if the owner prefers: delete the scripts AND their doc lines.
     Default taken: root them, because the docs describe real workflows.)
  R6 scripts/gates/**                                        this plan's tooling
  R7 conftest.py, tests/conftest.py, tests/unit/conftest.py, tests/fixtures/real_services.py
     (pytest loads the nested conftests implicitly and tests/conftest.py:21 loads the fixture
     module via `pytest_plugins = ["fixtures.real_services"]` - a string, invisible to an import
     graph. Codex R5 #1.)
  R8 src/bridges/cytoscape_exporter.py                       tested public package export
     (`src/bridges/__init__.py` exports it and TestCytoscapeExporter is an explicit KEEP path.)
Graph semantics:
  G1 `ast.walk()` the whole module, not `Module.body`: src/mcp/__init__.py:22-44,
     src/nexus/__init__.py:11-21 and src/services/__init__.py:4-10 use PEP 562 `__getattr__` lazy
     re-exports, so their real imports live inside a function body.
  G2 Resolve relative imports (`ast.ImportFrom.level > 0`) against the package directory, and
     mark every ancestor `__init__.py` of a live module live (Python runs them first).
  G3 Context rules, or the walk marks dead code live: an import inside a `TYPE_CHECKING` block
     (request_router.py:22-23) is a non-edge; an import inside a function body that is itself
     being deleted (processor.py:160-164 imports RLM inside `_process_rlm`) is a non-edge once
     that function is gone, so reachability is re-run AFTER each deletion batch, not once.
  G4 The optional-sidecar exemption is a list of exact (file, imported-module) pairs, never a
     generic "try/except ImportError" rule. Codex R5 audited all 17 such blocks under src/: beads
     (service_wiring.py:44-55) is registered and live; reranking (:59-62) defaults ENABLED at
     :420-423; the Bayesian pgmpy/lightweight fallback is live on both branches; ChromaDB and
     spaCy are external-dependency choices. ONLY the two visual blocks at service_wiring.py:65-77
     qualify. The gate asserts the exemption list is exactly those pairs and that no other path
     reaches those modules.
  G5 Resolve absolute local imports too: `from src.a.b import c`, `import src.a.b`, and
     `from src import x` map to `<root>/src/a/b.py` or `<root>/src/a/b/__init__.py`; a package
     name maps to its submodule when that file exists, otherwise the package initializer. This is
     load-bearing for http_server.py and every installed hook, which use absolute `src.*` imports.
Limits stated honestly: this proves import-unreachability, not absence of all dead code. Modules
that are import-live but call-unreachable are reported separately (section 11), never auto-deleted.

## 2. Phase 0 - environment and gates. No product code.
P0.0 Commit the 14 audit input artifacts copied byte-for-byte from the live checkout, so later
     clean-checkpoint assertions are meaningful. This is commit 4fc48d6.
P0.1 Worktree + branch; `git status` clean after each Phase 0 checkpoint commit.
P0.2 Canonical gate shape (so the AST oracle is load-bearing, Codex R4 #3 and R5 #2):
         def probe(fixture) -> bool: ...
         def self_test() -> bool:
             bad = _planted_bad_fixture()
             assert not probe(bad)
             return True
         def main(argv) -> int:
             if "--self-test" in argv:
                 ok = self_test()                 # result controls exit
                 if not ok: return 1
                 print(f"SELF_TEST_REJECTED {GATE_ID}"); return 0
             ok = probe(_real_fixture())
             if not ok: return 1
             print(TOKEN); return 0
         if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
     run_self_tests.py AST-matches ALL of: assert-not-probe inside self_test; the `--self-test`
     branch calling self_test() with its result controlling the return; an assigned probe call in
     main; the token printed only after the `if not ok` guard; and `__main__` invoking main()
     (v6 checked only the first and third, so a script with two dead canonical functions that
     merely printed the token would have passed).
     It excludes non-gate helpers (run_self_tests.py itself, reachability.py, _embed_stub.py) and
     cross-checks its fixed 12-id MANIFEST against the executable gates discovered on disk, so a
     thirteenth gate cannot escape validation.
     railway_smoke.py's probe takes a CLIENT object (FastAPI TestClient in self-test with
     MEMORY_MCP_API_KEY set in-process; real HTTP client in the run), so Phase 0 needs no Docker.
P0.3 Two exclusive-created artifacts:
     - audits/baseline-2026-09-03.json, `open(path,"x")` in Phase 0: pytest --no-cov passed and
       collected counts, the collected NODEID SET, the acceptance summary parsed exactly
       (12 PASS | 0 XFAIL | 0 FAIL of 12, exit 0), bench p95 memory_store + unified_search
       (`scripts/bench_tools.py` must benchmark memory_store, not merely use it for seeding),
       coverage TOTAL, harvested tool count, and `sha256` = digest of the canonical JSON WITH THE
       sha256 FIELD OMITTED (Codex R5 #3: including it is self-referential).
     - audits/phase3-pre-deletion.json, `open(path,"x")` at the START of Phase 3, recording the
       CURRENT `HEAD` - and Phase 0-2 must be committed first so that HEAD is a clean checkpoint
       containing the pre-deletion tests and source (Codex R5 #3: with uncommitted work the
       comparison checkout is not the real pre-deletion tree). The writer checks `git status
       --porcelain` before creation and records `checkpoint_clean: true`; P3 verifies that field
       because creating the artifact itself makes porcelain non-empty.
     baseline.py --verify recomputes the digest under the omission rule, re-checks the acceptance
     summary, and asserts a second --write is refused.
P0.4 Delete eight stale root oracles: gate0_verify.py (calls the removed _parse_metadata; the live
     method is _metadata_from_string, src/memory/lifecycle_manager.py:263), gate1_verify.py,
     gate2_verify.py, gate4_verify.py, test_rlm_quick.py, test_all_14_tools.py,
     test_rlm_organ_map.py, tests/test_all_14_tools.py. The reference scan excludes .git/,
     audits/, archive/, docs/connascence/** (42 literal matches) and the gate's own target
     declaration. `--root` keeps the planted-bad fixture a 3-file temp dir.
P0.5 Coverage threshold untouched until Phase 5; all gates run pytest --no-cov.
P0.6 Deletion floor: nodeid SET difference between the working tree and a temp
     `git worktree add <tmp> <pre_deletion_sha>` checkout, `git worktree remove` in a finally
     block with all handles closed first (Windows PermissionError, Gemini R5 C2). The expected set
     is DERIVED, never read from the prose list: a nodeid is expected to vanish exactly when its own
     AST body references a symbol imported from the computed dead source set; a whole test file is
     expected to vanish only when every collected nodeid in that file does. Module-scope imports
     alone do not make live sibling nodeids dead. The section 5 lists are cross-checks, not the
     source of truth. --self-test uses dummy sets and never calls git.

## 3. Phase 1 - live-path honesty. Order: P1d -> P1a -> P1b -> P1c.
P1d Lightweight Bayesian parity: lightweight_query_engine.py:38-65 and :67+ adopt the pgmpy
     signature (probabilistic_query_engine.py:61-66), result shape (:225-256), and failure shape:
     no network, no valid variables, timeout, or exception return None on both backends. Update
     query_marginal and get_most_probable_explanation to call the new signature correctly. In
     tier_queries.py KEEP `_query_bayesian_conditional` at :195-204, delete its TypeError fallback
     arm :205-210, and unwrap the now-handlerless `try` so the primary call is a bare return. Add
     MEMORY_MCP_BAYESIAN_BACKEND in src/bayesian/__init__.py:12-39;
     update tests pinning the old shape.
P1a bayesian_inference: three fake-success branches -> isError True (request_router.py:576-588,
     :616-627, :636-639); update tests/unit/test_request_router_handlers.py:120-131; fix the stale
     ":570 rebuilt per call" comment (cached by graph version, service_wiring.py:470-487).
P1b Beads: _run_command (beads_bridge.py:282-310) raises BeadsCLIError on rc!=0 / timeout /
     exception, [] only for empty stdout; stdio handlers :753-779, :791-826, :838-859 -> isError
     True. HTTP `_retrieve_beads` returns `(tasks, error)` request-locally, `_coerce_tasks` unpacks
     it, `retrieve()` adds `beads_error`, and http_server.py:994-1002 exposes that field in the
     response body. No singleton attribute may carry the error. Update
     tests/unit/test_beads_bridge.py:55-68 to pytest.raises. All 9 combinations.
P1c Request-local degradation across every TRI-TIER path (the wording is now precise - Codex R5 #4:
     v6 claimed "every live retrieval path" while the token counted three routes):
     - Three degradation causes recorded in tier_queries.py, not two: missing service
       (:39-41, :85-87, :136-138), runtime exception (:70-72, :116-118, :188-193), and a PRESENT
       Bayesian engine returning no result (:145-149).
     - Tier functions keep their LIST return and gain `status: Optional[dict]`.
     - The nine lambdas at tests/unit/test_nexus_processor.py:133-135,162-164,189-191 become
       `lambda q, k, status=None: ...`.
     - recall() (processor.py:428-464) keeps its list return; process() (:95-152) owns the
       per-call status dict and adds "degraded_tiers": sorted(status).
     - service_wiring.py:492-529 gains execute_with_status() -> (results, degraded); execute()
       delegates and returns results only. Both the nexus_processor-is-None path and the path where
       NexusProcessor raises before the vector fallback record degraded=["hipporag","bayesian"].
     - FIVE stdio handlers use it and set isError True only when all three are degraded:
       handle_vector_search (:161-208), handle_unified_search (:644-699, incl. the
       nexus_processor-is-None fallback at :653 reporting degraded=["hipporag","bayesian"]),
       handle_context_retrieve (:995-1022), handle_graph_query (:354-385) and
       handle_hipporag_retrieve (:431-479) - the last two reach the fused path through their
       execute() fallbacks and returned isError False through v5.
     - THREE tri-tier HTTP routes include degraded_tiers and return 503 when all three are down:
       /tools/vector_search (:757-796), /tools/search (:873-907), /tools/unified_retrieve
       (:938-980); add `except HTTPException: raise` before the blanket `except Exception -> 500`
       at :794, :905, and :1003. unified_router.py:84-109 preserves degraded_tiers from process(),
       records all three on its exception/fallback paths, and http_server.py:994-1002 hoists it to
       the top-level response. /tools/graph_query (:854-870) is SINGLE-TIER, already converts
       exceptions to 500, and is explicitly out of scope - stated here so it is not silently omitted.
     - A four-thread gate proves request-local degradation state cannot leak between calls.
     - Fixture: tests/unit/test_stdio_server.py:102 sets only execute.return_value; add
       `execute_with_status.return_value = (execute.return_value, [])` and update assertions at
       :135-171 and :220-227.

## 4. Phase 2 - tracing and cleanup
P2a One trace site: request_router.handle_call_tool (:1028-1050), which protocol_handler.py:42-57
     imports directly. Create the trace (service_wiring.py:364-368), time the handler, record
     isError + error text, call trace.log(db_path=f"{data_dir}/query_traces.db") explicitly
     (query_trace.py:172 defaults to memory.db). Trace logging is isolated from tool results:
     catch every exception around log(), treat it as False, and warn; an unwritable trace path must
     never change the handler result. Remove the handler-local trace assignment at :173 and the
     trace-only block at :177-192; KEEP :174-175 (start_time and the execute_with_status call), and
     replace `trace.retrieval_ms` at :201 with a local elapsed_ms. The stdio_server.py:144-163 facade stays; each branch keeps its literal
     `tool_name == "..."` line and delegates to `_handle_call_tool(...)`. Delete
     scripts/verify_wiring.py (it asserts the old handler-local pattern at :43).
P2b cleanup_expired under stdio, rolling 24h, atomic, RE-ACQUIRABLE. `KVStore.set_if_absent(key,
     value, ttl)` must run BOTH statements in ONE transaction:
         DELETE FROM kv_store WHERE key=? AND expires_at IS NOT NULL AND expires_at <= ?;
         INSERT OR IGNORE INTO kv_store (...) VALUES (...);   -> return cursor.rowcount > 0
     A bare INSERT OR IGNORE deadlocks forever: `key` is TEXT PRIMARY KEY (kv_store.py:113),
     SQLite has no TTL, and only get() lazily deletes expired rows (:234) - which only the claim
     winner would ever reach (both R4 audits found this independently).
     The comparison parameter uses `datetime.now().isoformat()`, matching KVStore.set; lock or
     integrity contention returns False and never fails ingestion. _run_lifecycle_maintenance
     (memory_ingestion_service.py:265-273) claims
     "lifecycle:cleanup:claim" with ttl=86400; only the winner calls cleanup_expired(). __init__
     (:34-55) gains kv_store=None; http_server.py:262 passes get_kv_store(),
     request_router.py:284 passes tool.kv_store; kv_store None = no-op (the MagicMock at
     tests/unit/test_memory_ingestion_service.py:36 must not be read through).
     Gate uses raw SQL (never kv.get(), which deletes expired rows itself) plus a spy on
     cleanup_expired, including the re-acquisition regression case.

## 5. Phase 3 - delete what reachability.py computes as dead
Procedure: first apply the four range-surgery groups below and remove their newly orphaned imports.
Then run the first authoritative `reachability.py --report`, review its computed dead list, delete
that batch, and RE-RUN after every batch (G3: deleting a function removes edges). Repeat until
dead_remaining is 0 or exactly the named exceptions. Never use the pre-surgery report as the
deletion authority because the soon-removed lazy and optional edges still make RLM, public_api,
and the visual stack appear live.
Expected in the computed dead set (cross-check, not the source of truth): src/safety/, src/sleep/,
src/woundhealer/, src/visualization/, src/cache/, src/validation/, the visual stack
(qwen3vl_embedder, visual_memory_service, visual_indexer, unified_search_router),
src/mcp/tools/* except vector_search.py, src/services/{capture,confidence}/,
src/services/{ownership_registry,ontology_bridge,curation_service,proactive_context_injector}.py,
src/services/{finetune,improvement,weekly_review,trigger_watchers}/, src/guardspine/, src/ui/,
src/rlm/, src/routing/mode_aware_router.py, src/nexus/public_api.py,
src/integrations/{claude_code_hooks,ontology_schema,proactive_schema,ephemeral_buffer_schema,
confidence_scoring_schema,external_import_schema,frontmatter_mapper,property_inheritance,
loop_interfaces}.py, src/debug/error_attribution.py, src/telemetry/namespace_router.py,
src/memory/{tier_deduplication,drift_detector}.py, src/utils/bead_completion_logger.py, and
the ~38 unrooted scripts/ files (now that R5's three doc-named scripts are rooted).
`src/stores/event_log.py.init` is a separate named non-Python artifact deletion; the gate asserts
it is gone because a `src/**.py` reachability scan cannot see it. `src/integrations/metadata_sync.py`
and its test stay: the live `src.integrations` package initializer eagerly imports and publicly
exports MetadataSync, and the current Beads manifest documents it.
RANGE SURGERY (every range below re-read from the file on 2026-09-03):
- src/nexus/processor.py - CORRECTED, v6's range was destructive: delete the rlm_adapter
  param/doc/assignment at :45,:63,:77; the `use_rlm` argument at :101; the dispatch block
  :126-138 ONLY (`if use_rlm:` through `return rlm_result`); and the complete `_process_rlm`
  method :154-177. KEEP :140-152 - that is the core `self._execute_pipeline(...)` call and its
  timing/logging. Deleting :126-169 as v6 said would have removed the pipeline and clipped the
  method.
- src/mcp/service_wiring.py: the two optional-import try blocks :64-77 (Qwen3VLEmbedder is at :66)
  and the visual sidecar :254-317 as one unit (_init_visual_memory runs to :317).
- src/nexus/__init__.py: "MemoryMCPQueryService" in __all__ at :8 and the lazy branch :17-21.
- src/integrations/beads_bridge.py: BeadsMemoryBridge :530-763 (EOF; :750-763 are its cache
  methods - "748+" would have left them).
TESTS - whole files: tests/unit/{test_configguard,test_curation_app,test_curation_service,
test_approval_gate,test_outcome_measurement,test_pattern_detection_drift,test_quality_trends,
test_rule_deployment,test_usage_aggregator_buckets,test_quality_gate,test_tag_scorer,
test_memory_cache,test_schema_validator,test_visual_indexer,test_visual_memory_service,
test_unified_search_router,test_qwen3vl_embedder}.py;
tests/{test_ontology_bridge,test_ownership_registry,test_proactive_schema,test_trigger_watchers,
test_proactive_integration,test_proactive_context_injector}.py;
tests/integration/test_curation_workflow.py; tests/performance/test_curation_performance.py.
The derived closure also removes whole test files for computed-dead offline utilities, including
test_error_attribution.py, test_namespace_router.py, test_tier_deduplication.py,
test_drift_detector.py, and test_bead_completion_logger.py; this list is a cross-check only.
TESTS - surgery: after each deletion below, remove every import made unused by the deleted tests;
`ruff check src tests` is the authority, not a pinned leading-line range.
- tests/unit/test_phase5_memory_mcp_tail.py: keep the GraphService import at :15 and the complete
  GraphService test :18-30; delete the complete dead import block :7-14 and complete dead test
  blocks :31-119, then remove the now-unused general imports at :1-5.
- tests/integration/test_nexus_integration.py: delete the deleted-module imports at :28-37 (not
  just :33) and the classes TestFrontmatterMapper :111-191, TestPropertyInheritanceChain
  :194-269, TestDashboardGraphVisualizer :272-392, and TestCrossModuleIntegration :395-485 (both
  its tests use deleted mapper/inheritance/visualizer classes - both auditors agree it is 100%
  dead). KEEP TestCytoscapeExporter :40-110.
- tests/integration/test_week7_integration.py: remove the SchemaValidator import at :10 and all
  five dependent tests (both auditors enumerated them; v6's line numbers had drifted - re-read
  them at execution time, the file is 157 lines).
- tests/unit/test_nexus_processor.py: the rlm test :670-687.
SCRIPTS: scripts/test_bead_implementations.py is NOT in the ROOT SET, so it is dead by
construction - DELETE IT WHOLE (Gemini R5 A3). v6's line surgery on it contradicted the computed
rule, and three of its six checks import modules being deleted anyway
(loop_interfaces, extract_graph_entities, promotion_pipeline).
Gate deletion_closure.py: dead_remaining == 0 (or exactly the named exceptions with reasons);
KEEP paths present; both servers import; tool count == baseline; derived nodeid set difference
exact; the non-Python artifact is gone; `ruff check src tests` and `black --check src tests` pass;
failed=0.

## 6. Phase 4 - docs
- check_docs.py gains `--docs-root` and `--code-root`, and a reference rule for four forms:
  `src/<path>.py`, `src\<path>.py`, `from src.<dotted> import`, and a bare `from <pkg>.<mod>
  import` - the last counts as LOCAL only when `<pkg>` resolves under `code_root/src` (the docs
  also contain `typing`, `fastapi`, `pydantic` imports at
  BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:339,665-666 which must not be flagged - Codex R5 #6).
  A package import (README.md:458) resolves to `src/<pkg>/__init__.py`. An external block runs
  from an absolute `Location:` line through its fenced block (manifest :661-668) and is exempt.
- Negative control: the fixture copies ALL TEN CURRENT_DOCS paths into the temp docs-root
  (copying only one produces nine spurious missing-document violations - Codex R5 #6), mutates
  only docs/CURRENT.md with one planted violation per form (4 expected), and plants a
  local-looking import inside the Life OS external block that must NOT be flagged. Then the real
  run must print the literal "OK: all current docs match code reality." (check_docs.py:104), exit 0.
- Edits: README.md:12-15, :44-52, :285-301; docs/CURRENT.md:18-21, :51, :52 (stdio-only tracing),
  :65 (P2b), :68-73; the manifest's public_api references; docs/MCP-INTEGRATION.md:285
  (nonexistent scripts/test-mode-detection.py); docs/api/MCP-DEPLOYMENT-GUIDE.md:443
  (`src/mcp/server.py` -> `src/mcp/http_server.py`); every other sentence naming a module in the ten
  CURRENT_DOCS gets kept-true / reworded / removed. docs/phase6/** and
  GRAPH-001-COMPLETION-REPORT.md -> docs/project-history/.

## 7. Phase 5 - Railway smoke, coverage ratchet, cross-model verification, merge
- P6 railway_smoke.py: Dockerfile.railway:10-15 pins EMBEDDING_MODE=api and EMBEDDING_API_BASE to
  litellm.railway.internal; embedding_pipeline_api.py:28 reads it at construction (appending
  /embeddings at :43). The gate runs scripts/gates/_embed_stub.py on the HOST bound to 0.0.0.0,
  returning one indexed 384-float embedding for EACH input item, seeded by hashlib from that text,
  and accepting `dimensions` and `encoding_format`. Container:
  `--add-host=host.docker.internal:host-gateway`, `-e EMBEDDING_API_BASE=http://host.docker.
  internal:<port>/v1 -e MEMORY_MCP_API_KEY=<uuid> -e MEMORY_MCP_DATA_DIR=/data -v <tmp>:/data
  -p 18080:8080`. Sequence: GET /health 200 with components.bayesian == "available (lightweight)"
  (http_server.py:604; add a top-level "bayesian_backend"); POST /tools/memory_store with the
  canary; POST /tools/search and /tools/unified_retrieve with X-MCP-API-Key (auth :118-147,
  bodies :516-532); the canary must return from both; a wrong key gives exactly 401 while /health
  is 200. Cleanup: stop + rm container and image. Mirrored in .github/workflows/railway-smoke.yml.
- Coverage: after Phase 3 measure `pytest --cov=src` TOTAL once, set pytest.ini:13
  --cov-fail-under to floor(TOTAL). Put `# ratchet up only` on its own line above `addopts`, never
  inside the multi-line value where pytest would parse it as arguments. The gate asserts
  configured <= measured.
- Claude: `UNLAZY_SHELL=bash MMTS_PY=<venv python> gate-check.mjs --reverify` exit 0.
- Codex: re-runs every scripts/gates/*.py directly in the worktree; appended to the ledger log
  with a timestamp; `author not in verifiers` stated per phase.
- Merge; `/mcp` restart; live smoke = one memory_store + one unified_search from a real session
  showing degraded_tiers==[] and a new query_traces.db row.

## 8. H1-H6: decided in v3, closure now computed. No handoffs remain.
Decay-at-rank (SYSTEM-MAP design gap): out of scope, recorded so it is not silently dropped.

## 9. Convergence (honest)
Findings per round: R1 36, R2 49, R3 43, R4 34, R5 16 - and R5's were concentrated in text written
for v6, with both auditors explicitly calling the residue bounded and closable without execution.
The FIX plan (P1a-d, P2a-b) has been stable since v4 apart from genuinely missed live paths. The
requested Opus 5 and Gemini 3.8 Flash preflight exposed additional executable-range and propagation
defects; v9 folds them. Recommendation: START PHASE 0. The gates themselves are now the better
oracle, and Phase 0's first deliverable replaces the last hand-written reachability artifact.

## 10. Recorded dissent, RESOLVED by evidence (crucible: the gate could not settle it, but one
## model found evidence the other missed - that is what the second method is for)
src/universal_components.py. Gemini R4 #14 said DELETE (no caller invokes get_tagger /
get_memory_client / get_telemetry_bridge / get_connascence_bridge). Gemini R5 #H then showed the
v6 remedy was self-contradictory: the module is imported at module scope by both servers, so the
import graph marks it LIVE and it could never appear in the dead set that ALLOWED_DEAD indexes.
Codex R5 #8 supplied the deciding evidence: those wrappers are deliberate public compatibility
exports - `__all__` at src/mcp/stdio_server.py:172-181 and dynamic attribute routing through
`__getattr__` at :40-51 ("Lazy module-level access for backwards compatibility"). Deleting them
would break a documented compatibility surface, which R3 forbids without an explicit deprecation.
RESOLUTION: KEEP. reachability.py reports it under a separate informational
ALLOWED_CALL_UNREACHABLE list that does NOT feed dead_remaining. Revisit only via an explicit
deprecation decision with a call graph, never as Phase 3 cleanup.

`src/integrations/metadata_sync.py`: KEEP. Gemini's preflight followed the v7 deletion list, but
`src/integrations/__init__.py` eagerly imports and publicly exports MetadataSync whenever the live
Beads submodule is imported; its unit test and current Beads manifest also remain. Deletion would
require an explicit deprecation and is outside this cleanup. `src/bridges/cytoscape_exporter.py` is
also KEEP as an explicit tested public package export, represented by ROOT SET R8.

## 11. Audit log
- v1 Claude; R1 Codex 24 / Gemini(3.5 served) 12; v2; v3 (H1-H6 by Torvalds rules);
  R2 Codex 31 / Gemini 18; v4; R3 Codex 20 / Gemini 23; v5; R4 Codex 17 / Gemini 17; v6.
- R5 (v6): Codex xhigh 8 groups, 5 BLOCKER (incomplete roots + underspecified graph semantics;
  AST cannot prove the CLI branch calls self_test; self-referential baseline hash and missing
  pre-deletion checkpoint; unsafe processor.py range and two incomplete ranges; ALLOWED_DEAD is
  the wrong model for an import-live module). Gemini 3.8-flash 8 groups, 3 BLOCKER (processor.py
  range would destroy the pipeline; ALLOWED_DEAD contradiction; test_bead_implementations
  contradicts the ROOT SET rule). Both: bounded static corrections, then start.
- v7: all R5 findings folded.
- Pre-execution Crucible: Claude Code 2.1.259 routed `--model opus` to canonical
  `claude-opus-5`; Gemini CLI 0.58.0 routed the main audit to `gemini-3.8-flash`. Both canaries
  passed and both audits were read-only. v8 folds every verified finding; the one contested
  MetadataSync deletion was rejected by import, export, test, and current-doc evidence above.
- v8 convergence: Gemini 3.8 Flash passed; Opus 5 found four blocking specification defects and
  two unowned evidence paths. v9 fixes all six: handlerless Bayesian try, trace range, phase5 test
  range, non-circular nodeid derivation, processor-exception degradation, and checkpoint evidence.
- v9 convergence: Gemini 3.8 Flash passed; Opus 5 found orphaned imports left by test surgery,
  making the lint gate unreachable. v10 makes the orphan-import sweep apply to every test surgery.
- v10: NEXT ACTION IS PHASE 0 gate implementation, after final two-model convergence.
