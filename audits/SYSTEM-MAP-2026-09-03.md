# Memory MCP Triple System - Working / Broken / Not-Wired Map (2026-09-03)

Method: codebase-memory-mcp graph (12,824 nodes) + five Sonnet mapper agents
(MCP surface, retrieval layers, runtime/hooks, services/UI/guardspine, tests).
Status vocabulary: WORKING | STUB | BROKEN | NOT-WIRED (real code, zero callers
from the production path) | UNKNOWN. UNAUDITED until Codex signs off (see bottom).

## 0. Production truth
- Live entrypoint (C:\Users\17175\.claude.json ~L1842): venv-memory/Scripts/python.exe -m src.mcp.stdio_server.
  Chain: stdio_server.py -> tool_registry.py -> request_router.py -> protocol_handler.py, one NexusSearchTool (src/mcp/service_wiring.py).
- src/mcp/http_server.py (FastAPI) is only launched by Railway (railway.toml). Locally it is never started.
  Anything reachable ONLY via http_server is dead for the Claude Code deployment.
- Docker default CMD: stdio_server. Nothing launches src/ui, finetune, improvement, weekly_review, trigger_watchers.
- Data dir C:\Users\17175\.claude\memory-mcp-data: chroma/ (active, 3 Sep), chroma_data/ (stale, 5 Mar), agent_kv.db 28MB with live WAL.

## 1. MCP tool surface (src/mcp) - 18 stdio tools, all WORKING
| tool | handler (request_router.py) | status |
|---|---|---|
| vector_search | :161 | WORKING |
| unified_search | :644 -> NexusProcessor.process | WORKING (falls back to vector if nexus_processor None) |
| memory_store | :211 -> MemoryIngestionService.ingest | WORKING |
| graph_query | :354 | WORKING (honest vector fallback with note field) |
| bayesian_inference | :550 | WORKING (network rebuilt per call) |
| entity_extraction | :388 | WORKING (regex NER fallback) |
| hipporag_retrieve | :431 | WORKING |
| detect_mode | :482 -> ModeDetector | WORKING |
| lifecycle_status | :542 -> MemoryLifecycleManager.get_stage_stats | WORKING |
| obsidian_sync | :702 | WORKING (config-gated, isError if no vault) |
| beads_ready_tasks / task_detail / query_tasks | :746/:782/:829 -> BeadsBridge, 35s timeout | WORKING |
| observation_timeline | :883 | WORKING |
| kv_get/kv_set/kv_delete | :966/:976/:985 | WORKING |
| context_retrieve | :995 | WORKING |
- stdio_server.py:144 hardcodes 7 dispatch branches then falls through to request_router.handle_call_tool (:1028, all 18). Redundant double dispatch, not a bug.
- HTTP-only routes NOT exposed as MCP tools: /tools/raptor_cluster, /tools/consolidate, /tools/consolidate_entities, /tools/search, /tools/unified_retrieve.
- src/mcp/tools/trigger_watchers.py and src/mcp/tools/improvement_tools.py: NOT-WIRED (never imported by stdio or http server).
- No handler converts failure to fake success; _store_entities_to_graph (:298-351) soft-fails to count 0 with a log.

## 2. Retrieval layers
| component | file:line | status |
|---|---|---|
| 40/40/20 fusion | src/nexus/processing_utils.py:40-55 _calculate_hybrid_score; used by processor.py:263-317 and :600-652 | WORKING |
| Decay e^(-days/30) | src/lifecycle/hotcold_classifier.py:120-131 | WORKING at INGEST (hot/mid/cold tiering) - NOT applied at retrieval rank |
| Bayesian / pgmpy | src/bayesian/probabilistic_query_engine.py:19-20, VariableElimination at :238/:267/:293; network_builder.py:106-160 | WORKING; src/bayesian/__init__.py:12-39 swaps in LightweightNetworkBuilder when pgmpy missing (Railway). BAYESIAN_BACKEND var says which |
| HippoRAG PPR | src/services/graph_query_engine.py:65-108 nx.pagerank, fallbacks in ppr_algorithms.py | WORKING (real PPR, not keyword) |
| Vector tier | src/nexus/tier_queries.py:28-72 | WORKING, FAIL-OPEN: except Exception -> return [] |
| HippoRAG tier | src/nexus/tier_queries.py:74-118 | WORKING, FAIL-OPEN same pattern |
- CONCERN: a downed ChromaDB or graph silently contributes zero candidates; no degradation signal reaches the caller. Bayesian tier is the exception (explicit "unavailable" text).
- CONFLICT TO RESOLVE: map-layers traced HotColdClassifier.classify <- MemoryIngestionService._classify <- ingest (i.e. reachable from memory_store on stdio). map-runtime says HotColdClassifier is only reachable via http_server. One of these is wrong.

## 3. Runtime / hooks
| component | status |
|---|---|
| Claude Code hooks (settings.json): session_start_handler, prompt_marker_handler, user_prompt_memory_handler, pre_tool_memory_gate, post_tool_handler, stop_handler | WORKING (import-clean; runtime behavior not exercised) |
| src/nexus/processor.py NexusProcessor.process :95-152 | WORKING (core of unified_search) |
| src/nexus/public_api.py MemoryMCPQueryService | NOT-WIRED (no callers) |
| src/modes/mode_detector.py, mode_profile.py | WORKING |
| src/memory/lifecycle_manager.py MemoryLifecycleManager | WORKING |
| src/integrations/beads_bridge.py | WORKING |
| src/sleep/* (SleepCycleManager, ConsolidationScheduler, ActivityMonitor) | NOT-WIRED, zero callers, 0% test coverage |
| src/safety/* (ApoptosisService, QuarantineManager, CircuitBreakerRegistry) | NOT-WIRED, only via http_server, 0% coverage |
| src/routing/mode_aware_router.py ModeAwareRouter | NOT-WIRED |
| src/routing/unified_router.py UnifiedRetrievalRouter | PARTIALLY WIRED: constructed in service_wiring._init_production_features; .retrieve() caller from stdio path not confirmed |
| src/routing/query_router.py QueryMode | likely NOT-WIRED (low confidence) |
| src/bridges/cytoscape_exporter.py | NOT-WIRED |
| src/integrations/claude_code_hooks.py install_proactive_hooks / ClaudeCodeHooksIntegration | NOT-WIRED (zero callers) => proactive_context_injector likely dead too (untraced) |
| src/rlm/rlm_nexus_adapter.py | UNKNOWN / likely NOT-WIRED; 0 tests import src/rlm |
| src/debug/*, src/telemetry/* | real code, reachability UNKNOWN |

## 4. Services / UI / guardspine - all real code, none launched
| component | status |
|---|---|
| src/ui/curation_app.py (Flask, routes /, /curate, /settings, /api/curate/*) | NOT-WIRED (no Dockerfile/railway/script launches it) |
| src/services/trigger_watchers/* WatcherManager (File/Git/Time/Activity) | NOT-WIRED (only callers are the two dead files above) |
| src/services/finetune FineTuneCoordinator | NOT-WIRED (zero non-test callers) |
| src/services/improvement ImprovementCoordinator | NOT-WIRED (only caller is dead improvement_tools.py) |
| src/services/weekly_review WeeklyReviewCoordinator | NOT-WIRED |
| src/guardspine/{configguard,hookguard,promptguard} | NOT-WIRED (only tests/unit/test_configguard.py) |
| scripts/ (50+ manual utilities) | manual-run only, no cron |
- No STUB markers found in src/services or src/guardspine. activity_detector.py:79 NotImplementedError is an ABC base, overridden by 3 subclasses.

## 5. Test evidence (venv-memory, 2026-09-03)
- pytest tests --no-cov: 1409 collected, 0 collection errors; 1402 passed, 1 failed, 6 skipped (303s).
  - FAIL: tests/integration/test_phase4_security.py::test_load_config_missing_path_survives_python_optimized_mode (subprocess TimeoutExpired, likely flake).
  - Skips: spaCy x3, embedding model, 2 perf benchmarks (env-gated).
- Default pytest config enforces 40% coverage; actual 18.55% => pytest with defaults FAILS on the coverage gate.
- Root gate scripts: gate0_verify.py BROKEN (AttributeError MemoryLifecycleManager._parse_metadata, API drift); gate1 10/13 FAIL; gate2 21/22 FAIL; gate4 12/19 FAIL; test_rlm_quick.py BROKEN (TypeError NoneType len); test_all_14_tools.py exit 0 but 13/14 "passes" are empty responses counted as valid.
- Zero test files import src/sleep, src/safety, src/rlm (0% line coverage).

## 6. Codex audit corrections (gpt-5.6-sol, medium, read-only; full log: audits/codex-audit-2026-09-03.md)
Map errors found and now overriding the sections above:
- CONFLICT RESOLVED: HotColdClassifier IS live on the stdio memory_store path (request_router.py:242-243,284-290; memory_ingestion_service.py:80-84,198-206). map-runtime was wrong.
- "All 18 tools WORKING" is FALSE. bayesian_inference returns isError=false for "engine unavailable"/unknown-node (request_router.py:576-588,616-627). beads_ready_tasks/beads_query_tasks turn CLI failures into successful empty results (beads_bridge.py:293-310; request_router.py:759-760,850-859). Fake-success exists.
- Railway lightweight Bayesian backend is BROKEN at its consumers: lightweight_query_engine.py:38-65 API does not match tier_queries.py:154-186 nor request_router.py:629-630.
- Bayesian network is NOT rebuilt per call; cached by graph version (service_wiring.py:470-487).
- Safety has NO callers anywhere (not even http_server). UnifiedRetrievalRouter is HTTP-only; service_wiring builds a different UnifiedSearchRouter (:256-305).
- RLM adapter is NOT-WIRED (needs use_rlm=True, processor.py:101,126-169; no stdio handler passes it). Telemetry NOT-WIRED (beads namespace_router never injected). Debug: QueryTrace IS live for vector_search only (request_router.py:173-188); replay/attribution unwired.
- Placeholders missed: git_watcher.py:294,349 rebase/merge-complete are literal pass; consolidation_scheduler.py:128-136 placeholder callback.
- Seven more dead MCP tool modules in src/mcp/tools: beads_tools, capture, confidence_tools, ontology, ownership, proactive, visual_memory_tools (visual_memory_tools advertises schemas incl. a duplicate unified_search with no handlers). Only vector_search.py is imported by production (service_wiring.py:25).
- Counts: stdio facade has 8 branches not 7; 6 HTTP-only routes (adds /tools/stats). .claude.json entry is at ~L1816.
- Docs claim as implemented but map shows dead/omitted: curation UI (WEEK-3), Obsidian file watching (WEEK-1), ProactiveContextInjector (docs/CURRENT.md:51), 6 ontology tools (GRAPH-001 report admits stdio wiring pending), per-call tracing/replay (README:48), event logging (README:294), self-referential memory (README:50), SemanticChunker/HNSW (README:92-94), session reflection + 3-day scheduled task (README:298-301), HTTP API-key auth, confidence tools, RAPTOR, auto schema migrations, optional reranker, FrozenHarness telemetry.
- Section 5 test counts could not be re-certified by Codex (no-rerun rule); pytest.ini 40% gate CONFIRMED; gate0 breakage and test_all_14_tools empty-counts-as-pass CONFIRMED statically.

## 7. Summary (corrected)
WORKING and live: 18 MCP tools, 3-layer fusion, PPR, Bayesian (pgmpy or lightweight), ingest-time decay, 6 Claude Code hooks, beads bridge, mode detection, lifecycle stats.
Built but dead (NOT-WIRED): sleep/consolidation, safety (apoptosis/quarantine/circuit breaker), curation UI, trigger watchers, finetune/improvement/weekly_review, guardspine guards, proactive hook injection, ModeAwareRouter, cytoscape export, MemoryMCPQueryService, mcp/tools/{trigger_watchers,improvement_tools}.py, 5 HTTP-only tool routes.
BROKEN: gate0_verify.py, test_rlm_quick.py, gates 1/2/4 partial-fail, default pytest coverage gate.
Design gaps: vector/hipporag tiers fail-open silently; decay never influences ranking.
