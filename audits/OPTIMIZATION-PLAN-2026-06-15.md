# Memory-MCP Optimization Plan (crucible) - 2026-06-15

Goal: make the triple-system FASTER, LESS BUGGY, LESS FRAGILE, and SIMPLER
without changing tool contracts or stored-data formats. Method: crucible
(Claude builds, Codex audits; reproducible gate first; one logical change per
commit; both models verify). Torvalds lens: data structures first, kill special
cases, delete code, never break the user.

This is a PLAN. No code has been changed. Nothing proceeds without go-ahead.

---

## 0. What was verified from code (not opinion)

Resolved a direct contradiction between two audit agents using runtime + source:

- The Bayesian network is built by a LAZY property `NexusSearchTool.nexus_processor`
  (service_wiring.py:321-325) -> `_init_nexus_processor` (327) -> `_build_bayesian_network`
  (335/387) -> `network_builder.build_network` (network_builder.py:150). It builds
  ONCE per process, on the FIRST fused read (first vector_search / unified_search),
  and is cached in `self._nexus_processor`. NOT rebuilt per call.
- It IS on the first-read hot path: that first search blocks for minutes.
- Root cause of the minutes + the "Unable to allocate 128 GiB / 2 TiB / 16 TiB"
  warnings: NO parent-cardinality cap. Nodes default to 2 states
  (network_builder.py:167-170), so CPD table size = 2 x 2^(num_parents).
  `BayesianNetwork(edges)` (142) takes every filtered edge; a node with 12-15
  parents -> 2^12..2^15 columns -> MLE `estimate_cpd` (292-295) tries a giant
  alloc, throws, the node is SKIPPED (297-298). Then `check_model()` RAISES on
  the missing CPD (300-304), `_build_bayesian_network` catches it and returns
  None (service_wiring.py:387-397). Net effect: the build burns minutes on
  doomed allocations and then the Bayesian tier contributes NOTHING (None).
  Latency sink AND silent dead-tier in one bug.
  NOTE: the SAME explosion exists in the lightweight fallback builder
  (lightweight_network_builder.py:95-120 enumerates 2^parents). F1 must cap BOTH.

  (Correction from Codex audit: an earlier draft said "cached invalid model" -
  wrong; check_model raises, build returns None. Fixed above.)

---

## 1. Acceptance gate - BUILD FIRST (Phase 0, the second method)

Before any fix. Three existing gates stay green throughout; one new gate added.

Existing (regression net - prove "not broken"):
- `scripts/acceptance_all_parts.py` : 12/12 capabilities PASS.
- `scripts/check_docs.py` : docs match code.
- full pytest suite : 1349 passed / 6 skipped baseline.

NEW (prove "faster" + "less fragile" with numbers - Phase 0 deliverable):
- `scripts/bench_tools.py` : hermetic (fresh temp MEMORY_MCP_DATA_DIR +
  CHROMA_PERSIST_DIR), seeds a known corpus whose texts share entities so the
  graph/bayesian path is actually exercised, then drives each MCP tool through
  `handle_call_tool` and records: cold (first-call) latency, warm p50/p95, and
  asserts (a) zero tool errors, (b) a unique canary still retrieves, (c) the
  Bayesian model is valid after build. Emits a before/after latency table.
  Wire a loose perf-regression guard into the suite (fail only on large
  regressions, not noise).

No optimizing without the BEFORE number. Measure, then cut.

---

## 2. Findings, deduped and triaged

Severity x (1 / risk-to-functionality). Each carries its proof obligation.
Confidence: [C]=code-confirmed this session, [A]=agent-reported, verify in phase.

### TIER 1 - high impact, low risk (do first)

- F1 [C] SPEED+BUG+FRAGILITY - Bayesian CPD parent explosion (BOTH builders).
  network_builder.py:142 (no in-degree cap) + estimate_cpds:292 (MLE), AND
  lightweight_network_builder.py:95-120 (same 2^parents enumeration).
  Fix: cap in-degree (start at <=4, keep highest-confidence parents) before
  `BayesianNetwork(edges)` in both builders; consider BayesianEstimator +
  Dirichlet prior for regularized CPDs. Kills the TiB allocations, the
  minutes-long first query, the warning spam, and lets `check_model()` pass so
  the tier returns a real net instead of None. Risk: low (a 4-parent Markov
  blanket preserves signal; tool output shape unchanged). Proof: bench
  cold-latency before/after; assert check_model() True / build != None;
  bayesian_inference tool still returns; 12/12 + suite.

- F2b [C] SPEED - `bayesian_inference` tool REBUILDS the network on EVERY call
  (request_router.py:513-520; this is the rebuild-from-current-graph added for
  correctness). After F1 the build is cheap, but a fresh rebuild per call is
  still waste. Fix: cache the net keyed by a cheap graph version/hash; rebuild
  only when the graph changed. Risk: low. Proof: 2nd identical bayesian_inference
  call is ~free; result identical to a fresh build.

- F2 [C] SPEED+FRAGILITY - Bayesian build sits on the first fused-read hot path
  (service_wiring.py:335), CONTRACT-SENSITIVE. Recall always queries the
  Bayesian tier (processor.py:429-459) and scoring weights it
  (processing_utils.py:39-53), so it cannot simply be removed from fused reads
  without breaking the 0.4/0.4/0.2 contract. Fix options (decide explicitly):
  (a) after F1 the build is fast enough to stay inline; (b) make the tier
  degrade cleanly to weight 0 when the net is None/not-yet-built and build it
  lazily in the background; NOT a silent removal. Risk: med (touches fusion
  contract). Proof: cold vector_search latency drops; fused ranking unchanged
  on a fixed corpus (golden compare); 12/12 + suite.

- F3 [C] FRAGILITY/data-integrity - silent wrong-store, CONTRACT-SENSITIVE.
  vector_indexer.py:53-72: default `persist_directory="/data/chroma"` ignores
  MEMORY_MCP_DATA_DIR; http_server.py:278-290/682-689 and
  obsidian_client.py:46-50/111-116 pass explicit "/data/chroma" fallbacks that
  bypass any resolver. The "/data/chroma" default is INTENTIONAL for the Railway
  volume and is ASSERTED by tests (test_gate4_regression.py:70-82, 146-157) - do
  NOT change it. Fix: one `_resolve_persist_dir` with precedence explicit-arg >
  CHROMA_PERSIST_DIR > MEMORY_MCP_DATA_DIR/chroma > "/data/chroma"; route
  VectorIndexer + http_server + obsidian_client through it. Risk: low-med
  (preserve prod default + existing tests). Proof: VectorIndexer() with
  MEMORY_MCP_DATA_DIR set and CHROMA_PERSIST_DIR unset opens the configured dir;
  with neither set it still defaults to /data/chroma; gate4 tests stay green.

### TIER 2 - medium impact, low risk

- F4 [C] FRAGILITY - cp1252 stdout -> UnicodeEncodeError on import under pipes
  (Windows). Fix: force utf-8 on stdout/log handlers at server entry. Proof:
  drive a tool through a pipe, no UnicodeEncodeError.

- F5 [C] SPEED - deduplicate() re-encodes candidate texts to vectors
  (processor.py:544-546 -> _batch_encode_texts 583-594 -> embedding_pipeline.encode);
  candidates do NOT carry embeddings (tier_queries.py:63-69; search_similar
  returns id/doc/metadata/distance only, vector_indexer.py:562-572). Confirmed by
  Codex. Tradeoff: reusing embeddings means fetching them from Chroma at recall
  (larger read payload) and only helps vector-tier candidates. Fix only if the
  bench shows dedup is a real cost after F1/F2. Proof: bench dedup; identical
  dedup output.

- F6 [C] SPEED - trivial tools (kv_get, detect_mode) pay heavy startup: not just
  graph + spaCy, but the vector indexer + SentenceTransformer embedder are
  eagerly built via lifecycle wiring (service_wiring.py:156-160 ->
  vector_search.py:70-95). Fix: split minimal init (EventLog/KVStore) from lazy
  vector/graph/embedder init. Risk: med (init ordering deps - trace SessionStart
  hooks). Proof: kv_get cold latency drops; all tools still work.

- F7 [C] FRAGILITY - stale Bayesian net (cached forever, never invalidated on
  graph mutation). Lower priority once F1/F2 reshape the path; otherwise add
  invalidation on graph change or document a TTL.

### TIER 3 - low impact, opportunistic (simplify / debt)

- F8 [A] SIMPLIFY - request_router: ~15 handlers duplicate try/except + result
  formatting; `_text_result` exists but only KV tools use it. Route all handlers
  through one helper. Pure DRY, no contract change.
- F9 [A] SPEED - consolidation.py O(n^2) pairwise similarity -> vectorize
  (matrix / cdist). Large-store speedup, identical pairs.
- F10 [A] SPEED/FRAGILITY - graph_persistence full-JSON dump per mutation
  (write amplification) -> debounce / batch saves.
- F11 [A] BUG - stage_transitions archived_at_ts=0.0 fallback on parse failure
  is always < cutoff -> false-positive rehydration of corrupted metadata. Use
  far-future or skip.
- F12 [A] SPEED - graph loads 2660 nodes then prunes to 1000; prune-before-load.
- F13 [A] misc small: set-based entity dedup (ingestion), bounded LRU for the
  network-builder cache, drop misleading @staticmethod, replace -OO-fragile
  module asserts in mode_detector, PPR/degree caching, sqlite connection
  cleanup in kv_store/event_log.

---

## 3. Execution order (each = one commit, crucible loop)

Reordered per Codex audit (F3 must precede the bench, or the bench seeds/measures
the wrong Chroma dir - the exact footgun we hit this session).

Phase 0: F3 (store-path resolver) FIRST - so the bench can't measure the wrong
         store. Preserve /data/chroma default + gate4 tests.
Phase 1: build `scripts/bench_tools.py` + capture baseline (cold timings for
         kv_get, detect_mode, vector_search, unified_search, bayesian_inference;
         + path test with MEMORY_MCP_DATA_DIR set, CHROMA_PERSIST_DIR unset).
Phase 2: F1 (CPD parent cap) across BOTH builders - biggest single win.
Phase 3: F2b (cache bayesian_inference net by graph version).
Phase 4: F2 (fused-read Bayesian: explicit contract decision, golden-compare
         ranking unchanged).
Phase 5: F4 (utf-8 stdout) - small fragility fix.
Phase 6: F6 then F5 - measured individually, only if bench still shows cost.
Phase 7+: F8-F13 each as its OWN commit (not a batch - one logical change per
          commit per the rule).

Each phase: fail-first proof -> minimal fix (ponytail) -> focused test + bench
delta + 12/12 + full suite -> Codex zero-trust audit of the diff -> commit ->
reconcile board. Cross-model parity at the end (both run bench + gate green).

## 4. Explicitly OUT of scope (no rewrites; protect the user)

- No fusion-engine rewrite. No change to the 0.4/0.4/0.2 contract.
- No change to stored-data formats (chroma metadata, graph.json, event_log).
- The `_is_bayesian_pseudo_doc` filter (processor.py:221/235) stays: it is a
  carefully-guarded special case (checks source_tiers == ["bayesian"]), not a
  sloppy hack. Revisit only if F2 removes the need for it.
