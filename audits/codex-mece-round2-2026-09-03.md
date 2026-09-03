## A. Triage rule

1. [MAJOR] Test coverage alone incorrectly means KEEP. Section 1 says any exercised test makes code KEEP (`audits/COMPLETION-PLAN-2026-09-03.md:31`), but H2-H4 delete test-covered, non-live subsystems (`:208-210`). Examples include `tests/unit/test_configguard.py:13`, `tests/unit/test_curation_service.py:10`, and `tests/test_proactive_context_injector.py:13`. The rule must distinguish tests of live paths from isolated tests deleted with dead code.

## B. Gate-script design

2. [BLOCKER] The baseline is mutable during later reverification. P0 runs `baseline.py --write audits/baseline-2026-09-03.json` (`audits/GATES-2026-09-03.md:16-18`), while P3 consumes that same file (`:56-58`). Re-running P0 after deletion can overwrite the pre-change baseline with post-change numbers and erase the comparison point.

3. [MAJOR] The baseline EXPECT omits both benchmark measurements required by the plan. The plan requires p95 for `memory_store` and `unified_search` (`audits/COMPLETION-PLAN-2026-09-03.md:42-44`), but the EXPECT checks only acceptance, pytest count, and coverage (`audits/GATES-2026-09-03.md:18`). A baseline without either p95 passes.

4. [BLOCKER] The self-test contract is not coupled to the normal probe. A script can implement `if --self-test: exit(1)` and print its success token otherwise, satisfying `audits/COMPLETION-PLAN-2026-09-03.md:54-55`. The aggregate EXPECT also accepts `0/0` (`audits/GATES-2026-09-03.md:21-24`). Require a fixed non-empty script manifest and prove the same probe rejects the planted input.

5. [MAJOR] Several EXPECTs still accept vacuous measurements. For example, `tools=0 rows=0` satisfies the backreference in `audits/GATES-2026-09-03.md:48`; `deleted=0 kept=0 tools=0 passed=0 failed=0` matches `:58`. Plain success tokens such as `STALE_ORACLES_GONE` (`:11-13`) rely entirely on the under-specified self-test mechanism.

6. [MAJOR] `deleted_test_count` is implementer-controlled. The plan says the deletion commit writes it (`audits/COMPLETION-PLAN-2026-09-03.md:180-182`) but never binds it to independently measured collection counts. Inflating it weakens the P3 pass-count floor.

7. [MINOR] The fixed interpreter currently exists, but the CHECK contract is machine-specific (`audits/GATES-2026-09-03.md:3-6`). The venv does not install `src`; gate scripts must explicitly put the worktree root on `sys.path`. Merely setting `PYTHONPATH` after Python starts is insufficient.

## C. P1c tuple and all-down handling

8. [BLOCKER] `context_retrieve` cannot receive degradation metadata as designed. It calls `tool.execute()` (`src/mcp/request_router.py:1010-1022`), whose public contract returns only a list (`src/mcp/service_wiring.py:492-505`) after discarding every `process()` field except `core` and `extended` (`:507-529`). P1c needs an explicit request-local result-bearing API for this path.

9. [MAJOR] The plan names `_recall`, but the actual public method is `recall()` (`src/nexus/processor.py:428-464`). Changing it to return `(candidates, degraded)` breaks direct callers at `tests/unit/test_nexus_processor.py:102-110,398-415`, `tests/integration/test_nexus_search.py:99-107`, and `tests/integration/test_pipeline_integration.py:173-178`.

10. [MAJOR] Changing each tier function to a tuple also breaks tests and monkeypatches not listed in P1c. Old list assertions occur at `tests/unit/test_error_injection.py:46-73`; list-returning replacements occur at `tests/unit/test_nexus_processor.py:133-135,162-164,189-191`.

11. [MAJOR] "Degraded" is undefined for an unavailable tier. Vector, HippoRAG, and Bayesian currently return empty values when their service is absent before entering exception handling (`src/nexus/tier_queries.py:39-41,85-87,136-138`). If only exceptions set `error`, three unavailable tiers still produce false success.

12. [MAJOR] HTTP remains dishonest when all tiers fail. `/tools/vector_search` and `/tools/search` discard `degraded_tiers` and return normal success payloads (`src/mcp/http_server.py:771-793,887-905`). The P1c gate covers only the two stdio handlers (`audits/GATES-2026-09-03.md:41-44`).

## D. P2a facade routing

13. [MAJOR] The tracing gate does not exercise the facade it claims to verify. The plan calls every tool only through `protocol_handler` (`audits/COMPLETION-PLAN-2026-09-03.md:123-126`), and that path imports `request_router.handle_call_tool` directly (`src/mcp/protocol_handler.py:42-57`). All facade branches can remain unmodified while the gate passes.

No named test must break if each branch retains its literal `tool_name == "..."` line and delegates to `_handle_call_tool`. Unit behavior assertions are at `tests/unit/test_stdio_server.py:135-227,382-467`; the integration test checks only seven source strings at `tests/integration/test_phase4_mcp_tools.py:130-147`.

## E. P2b cleanup throttle

14. [MAJOR] The gate proves only "first call runs, immediate second call skips" (`audits/COMPLETION-PLAN-2026-09-03.md:134-136`; `audits/GATES-2026-09-03.md:51-53`). A permanent `lifecycle:last_cleanup` marker that suppresses cleanup forever passes. It needs a controlled-clock check after 24 hours and preferably a new service instance to prove persistence.

15. [MAJOR] A `get` then `set` throttle is not atomic under concurrent HTTP ingestion. `MemoryIngestionService` has no maintenance lock (`src/services/memory_ingestion_service.py:265-273`); `KVStore.get` and `set` lock separate transactions (`src/stores/kv_store.py:211-248,248-289`). Two requests can both observe no marker and run cleanup. The gate tests only sequential ingestion.

## F. DELETE closure

16. [MAJOR] H1 misses collection-breaking unit files: `test_approval_gate.py:3`, `test_outcome_measurement.py:5`, `test_pattern_detection_drift.py:14`, `test_quality_trends.py:5`, `test_rule_deployment.py:15`, and `test_usage_aggregator_buckets.py:13` all import deleted services.

17. [MAJOR] H1 also misses mixed consumers. `tests/unit/test_phase5_memory_mcp_tail.py:8` imports deleted `BeadsTools`, but unrelated KEEP tests occupy `:18-53,88-119`; remove only the Beads import and tests at `:56-85`. Mixed scripts include `scripts/test_capture003_real_data.py:141,484-546,549-586` and `scripts/test_confidence_scoring_dry_run.py:638-733`.

18. [MAJOR] Additional H1 script closure is absent: `scripts/test_capture_dry_run.py:59`, `scripts/test_improve001_real_data.py:33-61`, `scripts/test_improve002_real_data.py:31-57`, `scripts/test_improve003_real_data.py:30-56`, and `scripts/test_mcp005_beads_tools.py:51-71`.

19. [MAJOR] H3 omits two entire test consumers: `tests/unit/test_curation_service.py:10` and `tests/integration/test_curation_workflow.py:15-16`. Deleting the service/UI while retaining either causes collection failure. The plan lists only the app unit test and performance test (`audits/COMPLETION-PLAN-2026-09-03.md:160-162`).

20. [MAJOR] Deleting `curation_service.py` does not break `resolve_persist_dir` or `src/mcp`. The resolver lives in `src/indexing/vector_indexer.py:25`; HTTP imports and uses it at `src/mcp/http_server.py:42,310-312`. Only the "curation UI" phrase in `docs/CURRENT.md:18-21` must be removed, not the shared precedence description.

21. [MAJOR] H4 omits `tests/test_proactive_context_injector.py`, which imports the deleted service at `:13-15`. The other two H4 tests and dry-run script are listed correctly at `audits/COMPLETION-PLAN-2026-09-03.md:163-164`.

22. [MAJOR] H5 misses six script consumers: `scripts/exoskeleton_doc_audit.py:26`, `scripts/rlm_codebase_analysis.py:18-26`, `scripts/test_rlm_implementations.py:63-97`, `scripts/test_rlm_phase2.py:24-81`, `scripts/test_rlm006_search_tools.py:24-68`, and `scripts/test_rlm007_recursive_query.py:23-76`.

23. [MAJOR] H5's processor closure is incomplete. Removing only `use_rlm` and the branch leaves the `rlm_adapter` constructor contract (`src/nexus/processor.py:45,63,77`) and `_process_rlm`, including an import of the deleted package (`:154-177`). The mixed test function at `tests/unit/test_nexus_processor.py:670-687` must be removed, not the file.

24. [MAJOR] Deleting all of `scripts/test_bead_implementations.py` for one ModeAwareRouter check deletes five checks for retained components. The six distinct checks are enumerated at `:21,58,110,157,211,235` and invoked at `:267-282`. Remove only the mode-router function and invocation.

25. [MAJOR] The Beads namespace surgery is ambiguous. `namespace_router` belongs to `BeadsMemoryBridge` (`src/integrations/beads_bridge.py:530-559`); `store_task_completion` depends on it throughout `:647-707`, and `_query_related` depends on it at `:732-748`. Deleting only the named guards leaves broken dead methods. Ponytail's smaller closure is to delete the uncalled `BeadsMemoryBridge` class or explicitly remove all namespace-dependent methods.

No Beads or namespace-router test breaks from deleting that dead class: `tests/unit/test_namespace_router.py:3-45` tests telemetry only, while Beads tests instantiate `BeadsBridge`, not `BeadsMemoryBridge` (`tests/unit/test_beads_bridge.py:28,46,65`).

The remaining listed targets had no unaccounted external runtime importer: `src/safety`, `src/sleep`, visual tools, MCP trigger tools, Claude hooks, H2 GuardSpine, ownership, and ontology. Their internal or already-listed closure references were the only hits.

## G. Phase 4 docs

26. [MAJOR] The procedure miscounts its scope. `CURRENT_DOCS` contains ten files (`scripts/check_docs.py:16-27`), so after README and CURRENT there are eight, not "the other seven" (`audits/COMPLETION-PLAN-2026-09-03.md:190`). The referenced SYSTEM-MAP section 6 is corrections, not a ten-doc checklist (`audits/SYSTEM-MAP-2026-09-03.md:90-101`).

27. [MAJOR] The proposed path rule can leave a known current-facing document stale. `docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md` is gated (`scripts/check_docs.py:25`) but names deleted `public_api.py` through a Windows path and bare imports (`docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:232,341,668`). A rule limited to literal `src/<path>` will not necessarily match either form.

28. [MINOR] The negative control is useful but must call the same validator used for all ten real files. The current checker hardcodes `ROOT` and `CURRENT_DOCS` (`scripts/check_docs.py:13-27,73-77`), so `docs_truth.py` needs an explicit validator seam or controlled module invocation for its temporary README.

## H. Railway smoke

29. [BLOCKER] The smoke is not hermetic outside Railway. The image hardcodes `EMBEDDING_API_BASE=http://litellm.railway.internal:4000/v1` (`Dockerfile.railway:10-15`). Canary storage and search call the embedding API (`src/services/memory_ingestion_service.py:109-126`; `src/indexing/embedding_pipeline_api.py:43-75`). A local container or GitHub runner has no such service, so `/tools/memory_store` fails before the canary can be retrieved.

30. [MAJOR] The wrong-key self-test can pass for the wrong reason. The contract merely requires a nonzero gate exit (`audits/COMPLETION-PLAN-2026-09-03.md:234-235`); connection failure, startup failure, or the missing embedding service also qualifies. It must specifically observe HTTP 401 while `/health` is already healthy.

31. [MINOR] The request contract should be explicit in P6. Tool auth accepts `Authorization: Bearer <key>` or `X-MCP-API-Key` (`src/mcp/http_server.py:118-147`). `/tools/search` requires JSON `{"query": "...", "limit": optional_int, "mode": optional_string}` (`:516-521`); `/tools/unified_retrieve` uses `query`, optional `mode`, and optional `token_budget` (`:524-532`).

The `/health` route is real and public (`src/mcp/http_server.py:583-608`). It currently reports the backend only inside `components.bayesian`, not as `bayesian_backend`. Absence of pgmpy itself does not prevent module startup: `src/bayesian/__init__.py:17-32` catches the import failure and selects lightweight; a blocked-pgmpy import check loaded `http_server` with `BAYESIAN_BACKEND=lightweight`. Full Docker startup was not run, as requested.

```text
Verdict: NO - v3 is not safe to start Phase 0 unchanged.
Primary blockers: mutable baseline, unbound self-tests, lost P1c status, incomplete closure, and non-hermetic P6.
Phase 0 prerequisite: make the baseline immutable and bind self-tests to a fixed non-empty manifest and the real probes.
Before product phases: close the listed callers/tests/docs and provide a local embedding stub or override for P6.
Audit execution: read-only; no pytest, Docker, acceptance scripts, or repository writes were performed.
```
