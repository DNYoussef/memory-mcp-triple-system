# Memory MCP Triple-System - Merged MECE Issue List

**Date:** 2026-06-12
**Sources:** [Y] = Codex runtime audit, [M] = user-provided static deep-trace, [B] = both independently.
**Method:** Each issue assigned to exactly one category (mutually exclusive); categories cover all known defects (collectively exhaustive). Root causes are placed once; downstream symptoms reference them.

Severity: C=Critical, H=High, Md=Medium, L=Low.

---

## A. Security & Exposure
- **A1 [Y] (C)** HTTP tool routes fail OPEN when `MCP_API_KEY` is empty - `http_server.py:116` returns `True`. Running server confirms `tool_routes_protected: false`; unauthenticated `GET /tools/stats` succeeds.
- **A2 [Y] (C)** Server binds `0.0.0.0` (`scripts/startup/start-memory-mcp.ps1:30`) and the tunnel script can expose `localhost:8080` publicly - combined with A1, unauthenticated public exposure.
- **A3 [M] (H)** ConfigGuard fails OPEN on Windows - `configguard.py:374` writes to hardcoded `/tmp/`; on failure the bare `except` returns `passed=True, ALLOW`, waving unscanned secret-bearing diffs through.

## B. Identity & Cross-Tier Integrity  (ROOT-CAUSE CLUSTER)
- **B1 [Y] (C) ROOT** `VectorIndexer.index_chunks` discards provided IDs - signature `(chunks, embeddings)` has no id param; `vector_indexer.py:233` does `ids=[uuid4() ...]`. Ingestion computes a stable `chunk_id` (`memory_ingestion_service.py:101`) used for graph + event log, but the vector row gets a UUID. Breaks cross-tier lookup, lifecycle updates, archive/rehydrate, event-log correlation.
  - **B1a [M]** symptom: HippoRAG `retrieve()` returns `[]` for UUID-keyed graphs (`hipporag_service.py:215-244`).
  - **B1b [M]** symptom: rekindle/promotion re-indexes with a new UUID, so lifecycle updates target the wrong vector (`lifecycle_manager.py:184-191`).
  - **B1c [B]** symptom: stage update writes only lifecycle fields, dropping file_path/source, then rehydrate reinserts under a new UUID (`stage_transitions.py:65`) - your #7 + my #17.

## C. Write-Path & API Consistency
- **C1 [Y] (H)** HTTP and stdio use different ingestion paths - HTTP -> `MemoryIngestionService.ingest`; stdio -> bespoke `handle_memory_store` (`request_router.py:193`). Different chunking, metadata, IDs, graph behavior, lifecycle by client.
- **C2 [Y/B] (Md)** Arbitrary nested metadata breaks Chroma - HTTP accepts `Dict[str,Any]` (`http_server.py:464`), passed straight into Chroma (`vector_indexer.py:235`) which requires scalar values.
- **C3 [Y] (Md)** stdio protocol framing inconsistent - current server reads newline-delimited JSON (`protocol_handler.py:104`); Codex wrapper uses Content-Length framing against the stale API.

## D. Retrieval Correctness (fusion + tiers)
- **D1 [M] (H)** 40/40/20 fusion not scale-normalized - `processing_utils.py:50-54` weighted-sums cosine [0,1], raw PPR sum (~0.0-0.05), and posterior (~0.5). Graph tier effectively dead; Bayesian noise dominates.
- **D2 [M] (H)** Reranker blends normalized rerank score with un-normalized hybrid score (`reranker_service.py:204-211`) - "50/50" is really ~70/30.
- **D3 [M] (H)** Bayesian feedback looks up state `"true"` but lightweight net uses `"0"/"1"`/`VAR=state` -> posterior=0.5 every time, dragging edge confidences to 0.5 (`bayesian_graph_sync.py:109`).
- **D4 [B] (H)** Bayesian fallback signature incompatible - `tier_queries.py:149` passes `query_vars=`; lightweight engine expects `query_variables` (`lightweight_query_engine.py:39`) -> TypeError on no-pgmpy path. (your #6)
- **D5 [M] (Md)** pgmpy `query_marginal`/`get_most_probable_explanation` lack the `network or self._network` fallback that `query_conditional` has (`probabilistic_query_engine.py:110-165`) -> crash when `network=None`. (my #14; complements D4)
- **D6 [M] (Md)** Cosine collection scored with L2 formula `1 - d/2` (`tier_queries.py:62-63`) - orthogonal/irrelevant docs score 0.5 and pass the 0.3 filter. Correct: `1 - d`.
- **D7 [M] (Md)** Bayesian tier injects `VAR=state` rows as document chunks (`tier_queries.py:175-192`) that get fused/reranked against real docs.
- **D8 [M] (Md)** `_get_edge_posterior` reads wrong CPD cell and `.flatten()` crashes on lightweight `List[List[float]]` CPDs (`bayesian_graph_sync.py:273-275`).

## E. Lifecycle, Decay & Consolidation
- **E1 [M] (C)** "rehydratable" stage never fires - gated on `archived_at` (`stage_transitions.py:186`) which archival never writes; `threshold_days` computed but unused. Archived entries accumulate forever.
- **E2 [M] (H)** Timezone basis split - `datetime.now()` (local) in stage transitions + vector indexer vs `utcnow()` in drift/dedup/sweeper/sleep; decay/staleness boundaries skew by host UTC offset, non-reproducible across regions.
- **E3 [M] (H)** Merge/rekindle never re-embeds - `consolidation.py:112-119` keeps the old vector after merging text; `lifecycle_manager.py:184-191` re-indexes with the *query* embedding.
- **E4 [M] (H)** Rekindled chunks lose `last_accessed_ts`, so `demote_stale_chunks`' `$lt` predicate can never re-select them - they pin active forever.
- **E5 [M] (Md)** Dedup reports merges/bytes-freed that never happen - `tier_deduplication.py:373-374` sets `merged_count=len(all_pairs)` with no actual merge.
- **E6 [M] (Md)** KV expired-entry cleanup only runs at wall-clock hour 0 (`lifecycle_scheduler.py:67-73`); skipped if process not alive then. Stage stats include unswept rows.
- **E7 [M] (Md)** Three schedulers mutate the same Chroma chunks with no cross-subsystem lock (Lifecycle/Sweeper/Consolidation) - delete-after-read / double-delete races; phantom archive entries.
- **E8 [M] (Md)** Archived rehydrate parses `file_path` from `str(dict)` string-splitting with a silent `/default/path.md` fallback (`lifecycle_manager.py:152-161`) - unrecoverable on any parse miss.
- **E9 [M] (H)** `_summarize` lossy bound miscalibrated (`lifecycle_manager.py:295`); since archival keeps only the summary, this is irreversible loss.
- **E10 [M] (Md)** Hash-duplicate tiebreaker never uses recency - `(1 if c.created_at else 0)` is always 1; "oldest wins" not implemented.
- **E11 [M] (L)** `get_candidates_for_cleanup` can `ValueError` - `severity_order` omits `DriftSeverity.NONE` which detectors can emit (`drift_detector.py:438-472`).

## F. Config, Environment & Deployment
- **F1 [Y] (H)** Env override broken - `service_wiring.py:136` reads config `data_dir` before env, and `config/memory-mcp.yaml` hardcodes `/data`, so `MEMORY_MCP_DATA_DIR` is ignored; backup script may target the wrong dir.
- **F2 [Y] (H)** Codex and Claude point at different codebases - Codex `.codex/memory_mcp_wrapper.py:80` -> stale `.claude-worktrees` (6 tools, broken `.git`); Claude -> current repo (14 tools).
- **F3 [M] (H)** WoundHealer hardcodes `C:/Users/17175/...` and `D:/Projects/...` (`woundhealer/rlm_client.py:137-138`, `woundhealer_core.py:175-176`); off-machine returns zero matches silently; ignores `MEMORY_MCP_DATA_DIR`.
- **F4 [M] (Md)** RLM codebase indexer hardcodes `D:/Projects/...` defaults (`rlm_codebase_env.py:35-51`).
- **F5 [M] (Md)** `requirements.txt` (pinned) vs `pyproject.toml` (floating) out of sync for 10+ packages; live env already drifted. Not a hard conflict (pins are satisfiable) but two manifests resolve differently.
- **F6 [M] (C-for-module)** Flask imported but undeclared in any manifest (`ui/curation_app.py:8`) -> ModuleNotFoundError on clean install.
- **F7 [M] (C-for-module)** `curation_app.py` opens a ChromaDB client at import time (`:37`), creating `./data/chroma` as a side effect during pytest collection.

## G. Reliability & Silent Failure (broad excepts, dying loops, leaks)
- **G1 [M] (C)** `@lru_cache` on instance method `_cached_pagerank` (`ppr_algorithms.py:96-106`) pins every engine+graph forever and recomputes a full graph signature per query (slower than no cache).
- **G2 [M] (C)** PPR fallback raises `UnboundLocalError` - `personalization` referenced in `except` but assigned in `try` (`graph_query_engine.py:104-106`); safety net becomes a second failure.
- **G3 [M] (C)** Bidirectional Obsidian sync fully non-functional - `bidirectional_sync.py:345/400/435/464` call `file_manager.write_file()`, which does not exist; AttributeError swallowed. No file ever written.
- **G4 [M] (Md)** File-event watcher drops every event on Py3.10+ - `get_event_loop()` from watchdog thread raises, caught and `pass`ed (`file_watcher.py:278-288`).
- **G5 [M] (Md)** `add_watch_path` schedules a second handler -> events double-fire (`file_watcher.py:406-409`).
- **G6 [M] (H)** Time scheduler loop has no exception guard (`time_scheduler.py:193-202`) - one bad schedule kills the task and stops ALL scheduling; `_running` left True so no restart.
- **G7 [M] (H)** Activity-detector cooldown added only after successful injection (`activity_detector.py:403-455`) - on injector failure the pattern re-fires every 60s unbounded.
- **G8 [M] (H)** SessionStart hook can crash on Windows via `print()` of non-ASCII memory content (`session_start_handler.py:191`); exception escapes `main()`, no context injected.
- **G9 [M] (H)** `handle_bayesian_inference` forces `network=None` (`request_router.py:496-499`) and has no try/except -> every call returns generic `isError`.
- **G10 [M] (Md)** `_format_result_full` uses direct key indexing (`request_router.py:143-148`) -> KeyError on the fallback vector-search path; the most-used tool returns `isError`.
- **G11 [M] (Md)** Beads calls spin a fresh event loop per call in a daemon thread, `join()` with no timeout (`request_router.py:452-473`) - a hung `bd` blocks the tool call indefinitely; priority index has no lower bound.
- **G12 [Y] (Md)** Startup/tunnel automation unreliable - duplicate server starts, health-check failures, saved Cloudflare URL doesn't resolve, `cloudflared` not in PATH.

## H. Validation & Data Quality
- **H1 [M] (C-for-validator)** Schema validator marks valid schemas INVALID on warnings - `valid = len(errors)==0` counts `severity="warning"` (`schema_validator.py:119-123`).
- **H2 [M] (C-for-validator)** Schema validator crashes on non-dict tier config - `field not in tier_config` assumes dict (`schema_validator.py:153-156`).
- **H3 [M] (H)** Quality gate `weighted_min` discards weighting - returns unweighted raw score (`quality_gate.py:248-254`).
- **H4 [M] (H)** `rule_deployment._apply_change` "remove" unguarded - `replace(current_value,"")` no-ops or strips file-wide (`:396-399`).
- **H5 [M] (Md)** Category-drift detector fabricates drift from a 0.5 default (`pattern_detection.py:441-446`) -> false rule proposals.
- **H6 [M] (Md)** Usage aggregator labels each daily bucket one day early (`usage_aggregator.py:175-187`).
- **H7 [M] (Md)** Quality-trends mixes statistics - trend uses half-means, warning/critical use single `values[-1]` (`quality_trends.py:154-194`).
- **H8 [M] (Md)** `build_namespace_key` `break`s on first missing segment, dropping later segments (`namespace_router.py:152-157`).
- **H9 [M] (Md)** Approval-gate `approval_rate` can exceed 1.0 - auto-approvals counted in numerator but not denominator (`approval_gate.py:475-478`).
- **H10 [M] (L)** `get_outcomes_by_category` pre-truncates scan to `limit*2` before the `since` filter (`outcome_measurement.py:265`).
- **H11 [M] (L)** Tag scorer returns shared cached dict; caller mutation corrupts cache; key only `content[:300]` (`tag_scorer.py:177-195`).

## I. Code Health (non-functional)
- **I1 [Y] (Md)** Focused pytest: 3 failed / 46 passed (config-exception + chunk_id vs chunk_ids).
- **I2 [Y] (Md)** Ruff: 72 lint issues; mypy: broad type-health problems.
- **I3 [M] (L)** `stdio_server.py __all__` lists undefined names (`tagger`, `memory_client`, ...) -> `import *` raises AttributeError.
- **I4 [M] (L)** ~60 unused imports (pyflakes); `apoptosis` health-score divisions unguarded against zero config.

---

## Highest-priority fix order (merged)
1. **A1+A2** require auth by default; stop binding `0.0.0.0` behind a public tunnel.
2. **B1** make `index_chunks` honor provided IDs - collapses B1a/B1b/B1c and unblocks cross-tier integrity.
3. **C1** route stdio `memory_store` through `MemoryIngestionService.ingest` (one write path).
4. **F1+F2** fix env>config precedence; point Codex and Claude at one current codebase.
5. **G1+G2+G3** PPR leak, PPR crash, dead Obsidian sync.
6. **D1+D3+D4+D6** make the fusion real: normalize tiers, fix Bayesian state-name + signature, fix cosine formula.
7. **E1+E2+E3+E4** rehydratable stage, UTC basis, re-embed on merge, preserve `last_accessed_ts`.
8. **H1+H2+C2** validator correctness + Chroma scalar-metadata guard.
