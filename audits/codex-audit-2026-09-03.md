Audit method: read-only source tracing, positive-controlled caller searches, and permitted import checks. I did not run pytest, gate scripts, or the persistent system-map indexer because the latter writes cache state.

## Section 0: Production truth

Live local entrypoint is venv Python running src.mcp.stdio_server | CONFIRMED | C:/Users/17175/.claude.json:1816-1825

Map citation "~L1842" for the local entrypoint | WRONG | C:/Users/17175/.claude.json:1816

Stdio constructs one lazy NexusSearchTool and routes calls through request_router | CONFIRMED | src/mcp/protocol_handler.py:47-57

Railway launches http_server | CONFIRMED | railway.toml:9,17; Dockerfile.railway:56

http_server is never started locally | UNVERIFIABLE | no local launcher appears in Dockerfile:38-39 or C:/Users/17175/.claude.json:1816-1825, but historical/manual starts cannot be disproved

HTTP-only features are unreachable through the configured Claude Code stdio deployment | CONFIRMED | C:/Users/17175/.claude.json:1816-1825; src/mcp/request_router.py:1032-1050

Default Docker entrypoint is stdio_server | CONFIRMED | Dockerfile:38-39

Docker/Railway entrypoints do not launch UI, finetune, improvement, weekly review, or watcher services | CONFIRMED | Dockerfile:39; Dockerfile.railway:56; railway.toml:17

chroma is active, chroma_data is stale, and agent_kv.db has a live WAL | CONFIRMED at inspection time | C:/Users/17175/.claude/memory-mcp-data/chroma:n/a; C:/Users/17175/.claude/memory-mcp-data/chroma_data:n/a; C:/Users/17175/.claude/memory-mcp-data/agent_kv.db-wal:n/a

## Section 1: MCP tools

Exactly 18 stdio tools are registered | CONFIRMED | src/mcp/tool_registry.py:15-36

Exactly 18 stdio handler mappings exist | CONFIRMED | src/mcp/request_router.py:1032-1050

All 18 stdio tools are WORKING | WRONG | src/mcp/request_router.py:576-588,616-634; src/integrations/beads_bridge.py:293-310

vector_search is WORKING | CONFIRMED | src/mcp/request_router.py:161-208

unified_search is WORKING and falls back to vector search | CONFIRMED | src/mcp/request_router.py:644-699

memory_store is WORKING | CONFIRMED | src/mcp/request_router.py:211-272; src/services/memory_ingestion_service.py:105-160

graph_query is WORKING with a disclosed vector fallback | CONFIRMED | src/mcp/request_router.py:354-385

bayesian_inference is WORKING | WRONG | unavailable and unknown-node states return isError false at src/mcp/request_router.py:576-588,616-627; the Railway backend fails at :629-634

The Bayesian network is rebuilt per call | WRONG | the builder is called per request but reused and graph-version cached at src/mcp/service_wiring.py:470-487

entity_extraction is WORKING with regex fallback | CONFIRMED | src/mcp/request_router.py:388-428

hipporag_retrieve is WORKING | CONFIRMED | src/mcp/request_router.py:431-479; src/services/hipporag_service.py:276

detect_mode is WORKING | CONFIRMED | src/mcp/request_router.py:482-498

lifecycle_status is WORKING | CONFIRMED | src/mcp/request_router.py:542-547; src/memory/lifecycle_manager.py:309

obsidian_sync is config-gated and reports missing configuration as an error | CONFIRMED | src/mcp/request_router.py:702-743

All three Beads tools are WORKING with a 35-second timeout | WRONG | timeout wiring exists at src/mcp/request_router.py:501-516, but CLI failures collapse to [] at src/integrations/beads_bridge.py:293-310 and ready/query report successful empty results at src/mcp/request_router.py:759-760,850-859

beads_task_detail reports a missing task as an error | CONFIRMED | src/mcp/request_router.py:782-826

observation_timeline is WORKING | CONFIRMED | src/mcp/request_router.py:883-955

kv_get, kv_set, and kv_delete are WORKING | CONFIRMED | src/mcp/request_router.py:966-992

context_retrieve is WORKING | CONFIRMED | src/mcp/request_router.py:995-1022

stdio_server has seven explicit dispatch branches | WRONG | it has eight branches at src/mcp/stdio_server.py:147-163

The facade's double dispatch is redundant but functionally delegates unmatched tools | CONFIRMED | src/mcp/stdio_server.py:144-163

There are five HTTP-only tool routes | WRONG | there are six: stats, raptor_cluster, consolidate, consolidate_entities, search, and unified_retrieve at src/mcp/http_server.py:611,662,697,711,873,938

trigger_watchers.py and improvement_tools.py are NOT-WIRED | CONFIRMED | src/mcp/service_wiring.py:25; src/mcp/request_router.py:1032-1050

No handler converts failures to fake success | WRONG | Bayesian returns isError false for unavailable states at src/mcp/request_router.py:576-588,616-627; Beads ready/query turn CLI failures into successful empty results at :759-760,850-859

_store_entities_to_graph soft-fails to zero and logs the outer failure | CONFIRMED | src/mcp/request_router.py:298-351

## Section 2: Retrieval

40/40/20 fusion is implemented and used | CONFIRMED | src/nexus/processing_utils.py:40-55; src/nexus/processor.py:263-317,600-652

Exponential decay is computed as exp(-days/30) | CONFIRMED | src/lifecycle/hotcold_classifier.py:120-131

Decay and hot/warm/cold classification run during stdio memory_store ingestion | CONFIRMED | src/mcp/request_router.py:242-243,284-290; src/services/memory_ingestion_service.py:80-84,198-206

Decay does not affect retrieval ranking | CONFIRMED | src/nexus/processor.py:600-645

pgmpy Bayesian inference uses VariableElimination | CONFIRMED | src/bayesian/probabilistic_query_engine.py:238,267,293

Railway's lightweight Bayesian fallback is WORKING | WRONG | its API accepts query_variables and returns a flat dictionary at src/bayesian/lightweight_query_engine.py:38-65; fused retrieval expects a results wrapper at src/nexus/tier_queries.py:154-186, while the direct tool passes query_vars at src/mcp/request_router.py:629-630

BAYESIAN_BACKEND identifies the selected backend | CONFIRMED | src/bayesian/__init__.py:17-39

HippoRAG performs real Personalized PageRank | CONFIRMED | src/services/graph_query_engine.py:65-108; src/services/ppr_algorithms.py:35-50,105-114

Vector tier is implemented and fail-open | CONFIRMED | src/nexus/tier_queries.py:43-72

HippoRAG tier is implemented and fail-open | CONFIRMED | src/nexus/tier_queries.py:89-118

Tier failures can silently produce successful empty searches | CONFIRMED | src/nexus/processor.py:445-464; src/mcp/request_router.py:208,683,698

HotColdClassifier is reachable only through http_server | WRONG | src/mcp/protocol_handler.py:50-57; src/mcp/service_wiring.py:181-205; src/mcp/request_router.py:275-294; src/services/memory_ingestion_service.py:198-206

## Section 3: Runtime and hooks

The six listed Claude Code hooks are installed | CONFIRMED | C:/Users/17175/.claude/settings.json:12-17,36-45,50-56,61-67,72-77

The six hooks import cleanly | CONFIRMED | source entrypoints at src/hooks/session_start_handler.py:1, prompt_marker_handler.py:1, user_prompt_memory_handler.py:1, pre_tool_memory_gate.py:1, post_tool_handler.py:1, stop_handler.py:1

The six hooks' runtime behavior is WORKING | UNVERIFIABLE | configuration and imports were verified, but execution was explicitly not exercised

NexusProcessor.process is the unified_search core | CONFIRMED | src/nexus/processor.py:95-152; src/mcp/request_router.py:644-683

MemoryMCPQueryService is NOT-WIRED | CONFIRMED | src/nexus/public_api.py:21; src/nexus/__init__.py:17-21

ModeDetector and mode profiles are live | CONFIRMED | src/mcp/request_router.py:482-498

MemoryLifecycleManager is live | CONFIRMED | src/mcp/service_wiring.py:205-209; src/mcp/request_router.py:542-547

BeadsBridge is fully WORKING | WRONG | production construction is live at src/mcp/service_wiring.py:249-252, but errors are hidden at src/integrations/beads_bridge.py:293-310

src/sleep has zero production callers | CONFIRMED | src/sleep/sleep_cycle.py:102; src/sleep/consolidation_scheduler.py:79; src/sleep/activity_monitor.py:52

src/safety is NOT-WIRED only through http_server | WRONG | it is NOT-WIRED everywhere; no HTTP references exist, and definitions are isolated at src/safety/apoptosis.py:129, quarantine.py:160, circuit_breaker_metrics.py:93

ModeAwareRouter is NOT-WIRED | CONFIRMED | src/routing/mode_aware_router.py:80

UnifiedRetrievalRouter is constructed by service_wiring | WRONG | service_wiring constructs the different visual UnifiedSearchRouter at src/mcp/service_wiring.py:256-305; UnifiedRetrievalRouter is HTTP-only at src/mcp/http_server.py:475-485,938-961

QueryMode is likely NOT-WIRED | CONFIRMED, with high confidence | src/routing/query_router.py:27; its only production consumer is the HTTP QueryRouter module itself

CytoscapeExporter is NOT-WIRED | CONFIRMED | src/bridges/cytoscape_exporter.py:55; src/bridges/__init__.py:9

ClaudeCodeHooksIntegration and install_proactive_hooks are NOT-WIRED | CONFIRMED | src/integrations/claude_code_hooks.py:286,470-494

ProactiveContextInjector is unreachable through the installed hooks | CONFIRMED | installed hooks point to src/hooks at C:/Users/17175/.claude/settings.json:12-77; the unused generated integration references the injector at src/integrations/claude_code_hooks.py:82-97

RLM adapter reachability is UNKNOWN | WRONG | it is definitively NOT-WIRED from stdio because it requires use_rlm=True at src/nexus/processor.py:101,126-169, and no stdio handler supplies that argument

All src/debug reachability is UNKNOWN | WRONG | QueryTrace is live at src/mcp/request_router.py:173-188 and src/mcp/service_wiring.py:364-368; replay and attribution remain unwired

src/telemetry reachability is UNKNOWN | WRONG | it is resolvable as NOT-WIRED from stdio; Beads requires an injected namespace_router at src/integrations/beads_bridge.py:638,667,734-743, but production constructors omit it at src/mcp/service_wiring.py:249-251 and src/mcp/http_server.py:470-472

## Section 4: Services, UI, and guardspine

The curation UI is not launched by production entrypoints | CONFIRMED | Dockerfile:39; Dockerfile.railway:56; railway.toml:17

WatcherManager and individual watcher services are NOT-WIRED | CONFIRMED | src/services/trigger_watchers/watcher_manager.py:54; src/mcp/tools/trigger_watchers.py:12

The watcher services' only callers are "the two dead files above" | WRONG | improvement_tools.py does not use watchers; WatcherManager's dead MCP consumer is src/mcp/tools/trigger_watchers.py:12

FineTuneCoordinator has zero non-test callers | CONFIRMED | src/services/finetune/finetune_coordinator.py:134,387

ImprovementCoordinator is called only by dead improvement_tools.py | CONFIRMED | src/services/improvement/improvement_coordinator.py:86,460; src/mcp/tools/improvement_tools.py:284

WeeklyReviewCoordinator is NOT-WIRED | CONFIRMED | src/services/weekly_review/weekly_coordinator.py:50,388

Guardspine guards are NOT-WIRED | CONFIRMED | src/guardspine/configguard/configguard.py:121; src/guardspine/promptguard/promptguard.py:120; src/guardspine/hookguard/hookguard.py:121

Repository scripts are manual-only and there is no cron | UNVERIFIABLE | production entrypoints do not launch scripts at Dockerfile:39, Dockerfile.railway:56, and railway.toml:17, but README claims an external Windows scheduled task at README.md:301

No stub markers exist in src/services or src/guardspine | CONFIRMED narrowly | the activity detector's abstract method is at src/services/trigger_watchers/activity_detector.py:79

No placeholder behavior was missed | WRONG | rebase-complete and merge-complete are literal pass operations at src/services/trigger_watchers/git_watcher.py:294,349; the sleep scheduler has a placeholder callback at src/sleep/consolidation_scheduler.py:128-136

## Section 5: Test evidence

1409 collected, 1402 passed, 1 failed, and 6 skipped | UNVERIFIABLE | prohibited from rerunning pytest and no machine-verifiable result artifact was supplied

The phase4 security test timed out and was likely flaky | UNVERIFIABLE | tests/integration/test_phase4_security.py:n/a

The six skips have the stated causes | UNVERIFIABLE | no fresh pytest result was permitted

Default pytest enforces 40 percent coverage | CONFIRMED | pytest.ini:6-13

Actual coverage is 18.55 percent and therefore default pytest fails | UNVERIFIABLE | the 40 percent threshold is confirmed at pytest.ini:13, but the reported measurement was not rerun

gate0_verify.py is broken by _parse_metadata API drift | CONFIRMED statically | gate0_verify.py:34-58; src/memory/lifecycle_manager.py:n/a

Gate 1, 2, and 4 have the listed failure counts | UNVERIFIABLE | gate1_verify.py:n/a; gate2_verify.py:n/a; gate4_verify.py:n/a

test_rlm_quick.py fails on len(None) | CONFIRMED statically as a possible failure path | test_rlm_quick.py:10-16

test_all_14_tools.py counts empty responses as success | CONFIRMED | test_all_14_tools.py:189-198

Zero tests import src/sleep, src/safety, or src/rlm | CONFIRMED by positive-controlled source scan | tests:n/a

Those packages have exactly 0 percent line coverage | UNVERIFIABLE | coverage was not rerun

## Documentation conflicts and omissions

Curation UI is documented as production-ready but mapped NOT-WIRED | CONFIRMED | docs/project-history/weeks/WEEK-3-COMPLETE-SUMMARY.md:30; audits/SYSTEM-MAP-2026-09-03.md:72

Obsidian file watching is documented implemented but watcher services are mapped NOT-WIRED | CONFIRMED | docs/project-history/weeks/WEEK-1-IMPLEMENTATION-COMPLETE.md:13; audits/SYSTEM-MAP-2026-09-03.md:73

ProactiveContextInjector is documented as the richer trigger and ontology layer but mapped dead | CONFIRMED | docs/CURRENT.md:51; audits/SYSTEM-MAP-2026-09-03.md:65

Ontology bridge and six implemented but unregistered ontology tools are absent from the map | CONFIRMED | GRAPH-001-COMPLETION-REPORT.md:23-32,68-74; its own report admits stdio wiring remains at :89

Per-call tracing, replay, and error attribution are documented but not accurately mapped | CONFIRMED | README.md:48; docs/CURRENT.md:52; only vector_search creates a trace at src/mcp/request_router.py:173-188

Event logging is documented but omitted as a component | CONFIRMED | README.md:294; src/mcp/service_wiring.py:191-197,335-353

Self-referential memory is documented but omitted | CONFIRMED | README.md:50,297; docs/architecture/SELF-REFERENTIAL-MEMORY.md:8

SemanticChunker, 384-dimensional embedding, and HNSW indexing are documented but omitted as component statuses | CONFIRMED | README.md:92-94

Session reflection, meta-loop aggregation, and three-day scheduled automation are documented but omitted | CONFIRMED | README.md:298-301

HTTP API-key authentication is documented but omitted | CONFIRMED | README.md:51; docs/CURRENT.md:12

Confidence services and tools are documented in the architecture but omitted | CONFIRMED | docs/README.md:162; src/mcp/tools/confidence_tools.py:1

RAPTOR clustering is documented as implemented, but the map only names its HTTP route and gives no component status | CONFIRMED | docs/project-history/weeks/WEEK-9-COMPLETE-SUMMARY.md:37,420

Automatic schema migrations are documented as wired but omitted | CONFIRMED | docs/phase6/WIRING-QUICK-REFERENCE.md:9

The optional reranker is documented as part of current unified fusion but omitted | CONFIRMED | docs/CURRENT.md:46,58; src/mcp/service_wiring.py:396-405

FrozenHarness telemetry is documented working while the map leaves src/telemetry UNKNOWN | CONFIRMED | README.md:300; audits/SYSTEM-MAP-2026-09-03.md:67

Older documentation is explicitly allowed to be stale or aspirational | CONFIRMED | docs/CURRENT.md:7-8

## Additional missing findings

Seven additional unregistered MCP tool modules are absent from the map | CONFIRMED | src/mcp/tools/beads_tools.py:29; capture.py:664; confidence_tools.py:462; ontology.py:282; ownership.py:311; proactive.py:227; visual_memory_tools.py:190

visual_memory_tools advertises schemas, including a duplicate unified_search, but contains no executable handlers | CONFIRMED | src/mcp/tools/visual_memory_tools.py:12-197

Only vector_search.py from src/mcp/tools is imported by production MCP wiring | CONFIRMED | src/mcp/service_wiring.py:25

No broken imports were found in the six hooks, dead MCP tool modules, routing modules, RLM adapter, sleep, safety, UI, or coordinators | CONFIRMED for the inspected modules | source module anchors listed above

## Map errors

- HotColdClassifier is live on stdio memory_store.
- "All 18 tools WORKING" is false because Bayesian and two Beads paths can report fake success.
- Railway lightweight Bayesian is incompatible with both direct and fused consumers.
- Stdio has eight explicit facade branches, not seven.
- There are six HTTP-only tool routes, not five.
- UnifiedRetrievalRouter is HTTP-only; service_wiring constructs a different router.
- Safety is not HTTP-only; it has no production callers at all.
- RLM and telemetry reachability can be resolved as NOT-WIRED from stdio.
- Debug is not wholly unknown because QueryTrace is live.
- Seven dead MCP tool modules and several placeholder paths were omitted.
- Section 5's historical execution counts cannot be independently certified under the no-test rule.

Corrected summary: the configured stdio server exposes 18 real handlers, with vector, storage, graph, mode, lifecycle, Obsidian, timeline, KV, and context paths statically wired. Hot/cold classification runs during stdio ingestion, and vector plus HippoRAG fusion is real but silently fail-open. The pgmpy Bayesian implementation is real, but the Railway lightweight backend is broken at its consumer interfaces, while Beads ready/query can disguise CLI failures as empty success. Large feature families remain unwired, including sleep, safety, UI, coordinators, guardspine, RLM, telemetry, proactive integration, ontology tools, and most standalone MCP tool modules.
