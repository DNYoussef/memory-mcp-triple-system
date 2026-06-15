# Memory MCP Docs vs Runtime MECE Audit - 2026-06-15

Merged from the documentation/code comparison and the live ground-check.

Source tags:
- [C] code/documentation comparison (intended design vs. wired source)
- [U] live/runtime audit (MCP probe + source-wiring trace)
- [B] both audits converged

Scope:
- Read current README/docs/audits to infer how the project should work.
- Compare that intended model to the actual wired architecture and live behavior.
- Treat `archive/` and project-history material as historical unless a current doc links to it.
- Do not re-litigate already-fixed implementation bugs from `STATUS-2026-06-13.md` (E4-E11, H3-H11, G12).

Findings are MECE: each appears once, in one category, keyed by *kind of defect*.
Severity: High = misleads operators / corrupts data; Medium = real gap, non-corrupting; Low = cosmetic/stale.

---

## 0. Baseline: what is actually true (no action)

- [B] The core is real, not theater: MCP memory with vector retrieval, HippoRAG/NetworkX graph, Bayesian plumbing, Nexus fusion, lifecycle, tagging, tracing, mode-awareness.
- [B] Nexus uses the documented weights: vector 0.4, HippoRAG 0.4, Bayesian 0.2 (`nexus/processor.py:84`; confirmed in a live `score_breakdown`).
- [B] Hot path is RECALL -> COMBINE -> FILTER(0.3) -> DEDUPE(0.95) -> RANK -> pseudo-doc drop -> RERANK -> COMPRESS (`nexus/processor.py:197`).
- [B] WHO/WHEN/PROJECT/WHY tagging is written into stored metadata (`request_router.py:72`; live metadata confirmed).
- [B] Four-stage lifecycle (active/demoted/archived/rehydratable) is wired; `lifecycle_status` live = `{active:1,...}`.
- [B] Mode detection (execution/planning/brainstorming) is live (`detect_mode` -> planning 100%).
- [U] Context-Assembly Debugger / query tracing IS wired through `request_router.py:169/185` into `query_traces.db`.
- [U] `src/routing/query_router.py` EXISTS; the issue is lack of hot-path use, not absence.
- [B] stdio MCP registry exposes 14 tools (`tool_registry.py:15`), not the older doc counts.

---

## A. Code defects (wrong/missing behavior - fix in code)

- **A1 [B] High - Storage split-brain.** Vector index defaults to `CHROMA_PERSIST_DIR` or `/data/chroma`, independent of `MEMORY_MCP_DATA_DIR`; graph/KV/event honor `MEMORY_MCP_DATA_DIR`. A custom data dir relocates graph+KV+event but leaves vectors at `/data/chroma` -> a half-isolated store.
  Evidence: `http_server.py:288` (vector) vs `:334` (graph/KV/event); `service_wiring.py:83`.
  Fix: in `get_indexer()`, default `CHROMA_PERSIST_DIR` to `<MEMORY_MCP_DATA_DIR>/chroma` when unset; keep explicit `CHROMA_PERSIST_DIR` as override (R3). Fail-first test on the derived path.

- **A2 [C] High (added) - Lifecycle never ages under stdio.** `LifecycleScheduler.start()` runs only in the HTTP startup event; the stdio server (the canonical MCP transport) has no scheduler. Running as stdio, demote/archive/cleanup never fire automatically -> memory grows unbounded and never decays, despite docs promising the 4-stage lifecycle.
  Evidence: `http_server.py:693-694` only; absent from `stdio_server.py`/`protocol_handler.py`/`request_router.py`.
  Fix: start the scheduler from a transport-neutral place (or a stdio startup hook), or document that lifecycle maintenance requires the HTTP process / an external cron.

- **A3 [C] Medium (added) - Embedding model/dim unguarded.** The embedding model is a default arg (`all-MiniLM-L6-v2`, 384-dim local; or an API model like `text-embedding-3-small` at a different dim). Nothing asserts the Chroma collection's stored dimension matches the configured model. A model/dim change between ingest and query silently corrupts vector retrieval (cosine over mismatched spaces or a hard dim error).
  Evidence: `indexing/embedding_pipeline.py:21,40`; `indexing/embedding_pipeline_api.py:22`.
  Fix: pin the model in config and validate the collection's dim on startup; refuse/migrate on mismatch.

---

## B. Capability not delivered (exists in tree; inert or degraded at runtime)

- **B1 [B] High - Bayesian tier offline.** Live `bayesian_inference` returns "No Bayesian inference available (no network or timeout)"; fusion gets `bayesian_score: 0.0`. The "triple" runs as a double (vector+graph). Three sources disagree: README says Bayesian *incomplete*, the board says retrieval *closed*, code *wires* all three, runtime returns *nothing*.
  Evidence: live probe; `tier_queries.py:127` (None on timeout, suppressed `:196`); `service_wiring.py:335-337`.
  Decision: bring the pgmpy/lightweight backend up and prove a non-zero contribution, OR declare 2-tier and downgrade weights + docs. Reconcile README/board/code to one truth.

- **B2 [U] Medium - Query Router built, not wired into recall.** `QueryRouter.route()` + lazy `get_router()` exist, but nothing in the Nexus recall path calls it. Docs credit it with skipping Bayesian for ~60% of queries (and the latency targets). Net: every query hits all 3 tiers and Bayesian times out each time (compounds B1).
  Evidence: `routing/query_router.py:33`; `http_server.py:314` accessor has no recall caller.
  Action: wire `route()` into recall (skip dead/slow tiers), OR delete the accessor and drop the doc claim.

- **B3 [C] Medium - Dead subsystems (no live caller).** MemorySweeper, DriftDetector, the Weekly-Review suite, and quality-gate validation are implemented but never instantiated by stdio/HTTP.
  Evidence: `memory/memory_sweeper.py`, `memory/drift_detector.py`, `services/weekly_review/*`, `validation/quality_validator.py` (no wiring).
  Action: per subsystem, wire it or move to `experimental/` and mark docs "not wired."

- **B4 [B] Medium - KV tools documented, not exposed.** README lists `kv_get`/`kv_set`/`kv_delete` as WORKING; they are not in the 14-tool registry (KVStore is internal-only).
  Evidence: `tool_registry.py:15`; `README.md:140`.
  Action: register them or remove from the documented API surface.

- **B5 [B] Low - WHO inferred weakly.** Docs say WHO = agent name; live tagging auto-fills `WHO=unknown:mcp-client` rather than inferring an author.
  Evidence: live metadata; `http_server.py:764` auto-fill.
  Action: improve inference or document WHO as caller-supplied (auto-filled when absent).

---

## C. Documentation accuracy / authority drift (code is right; docs stale or contradictory)

- **C0 [B] High - No single "current" authority.** README, `docs/README.md`, `docs/ARCHITECTURE.md`, deployment/integration docs, and `STATUS-2026-06-13.md` disagree on tool count, maturity, entrypoints, and test/coverage state. This is the umbrella under which C1-C7 sit.
  Action: designate ONE current contract (rewrite README or add `docs/CURRENT.md`); move v1/v7/planning under `docs/project-history/`.

- **C1 [U] High - Deployment/API guide misleads operators.** Guide says `python -m src.mcp.server` and `uvicorn src.mcp.server:create_app` (no such module; real entry is `src.mcp.http_server`); documents `GET /tools` and query-string `POST /tools/vector_search?query=...` (real routes are JSON-body); calls auth "recommended" though tool routes require API-key auth by default.
  Evidence: `docs/api/MCP-DEPLOYMENT-GUIDE.md`; real `http_server.py:709` (routes), `:117` (auth).

- **C2 [U] High - Tool counts/schemas contradictory.** README says "11 MCP tools" (:140) then "6 tools exposed" (:295); actual = 14. HTTP `memory_store` requires `text`; ingestion doc shows `content`.
  Evidence: `README.md:140,295`; `http_server.py:468`; `docs/api/INGESTION-AND-RETRIEVAL-EXPLAINED.md:307`.
  Action: generate the tool list/schemas from `tool_registry.py` + FastAPI routes; stop hand-maintaining counts.

- **C3 [B] Medium - Status/limitations stale.** README says HippoRAG/PPR and Bayesian are incomplete and "Nexus falls back to vector-only"; code wires all three and the board marks retrieval closed. The *vector-only fallback* claim is false (it is vector+graph); the *Bayesian* caveat is partly true (see B1).
  Evidence: `README.md:302`; `service_wiring.py:327`.

- **C4 [U] Medium - "Triple-layer" overloaded.** Docs mix short/mid/long-term *retention* language with the triple *retrieval tiers*. Code stores `lifecycle_tier`/`decay_score`/`stage`, not a short/mid/long primary architecture.
  Evidence: `memory_ingestion_service.py:80`.
  Action: rename - "triple retrieval tiers" (vector/graph/bayesian) + "lifecycle stages" (active/demoted/archived/rehydratable).

- **C5 [U] Medium - Beads docs written as a plan.** Manifest says "ready for implementation"; code ships `UnifiedRetrievalRouter` with the documented 80/50/20 weights and live beads tools.
  Evidence: `docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:5`; `routing/unified_router.py:25`.

- **C6 [C] Low - Compression ratio claim false.** Docs claim 100:1 (5000->50 tokens). Code uses a flat `SUMMARY_MAX_LEN = 200` chars (<=200 verbatim; larger truncated to 200) after the E9 fix.
  Evidence: `lifecycle_manager.py` SUMMARY_MAX_LEN.

- **C7 [U] Low - Quality/coverage claims stale.** README claims 100% coverage, 27/27 tests, perfect audits; board says 1342 passed, coverage gate excluded, ruff sweep + manifest drift open.
  Evidence: `README.md`; `STATUS-2026-06-13.md:19,343`.
  Action for C3/C6/C7: replace hardcoded claims with current numbers or a link to the live board.

---

## D. Self-referential ingestion hygiene (the system stores its own docs as memory)

- **D1 [U] Medium - Self-doc ingest targets stale paths/claims.** `ingest_documentation.py` points at `docs/INGESTION-AND-RETRIEVAL-EXPLAINED.md` (real file is under `docs/api/`); `SELF-REFERENTIAL-MEMORY.md` says only 4 docs ingested and still calls graph/Bayesian "planned." Stale docs become bad retrieval data about the system itself.
  Evidence: `scripts/ingest_documentation.py:54`; `docs/architecture/SELF-REFERENTIAL-MEMORY.md:102`.
  Action: ingest current docs only, tag with authority metadata, exclude `project-history/` unless requested.

---

## E. Corrections (raised then disproven - recorded so they are not re-flagged)

- **E1 [U]** Context-Assembly Debugger IS wired (an earlier code-map wrongly called it absent): `request_router.py:169/185` -> `query_traces.db`; `debug/error_attribution.py` reads them.
- **E2 [U]** `entity_extraction` and `hipporag_retrieve` are NOT stubs (docs mark them STUBBED/PARTIAL); both returned real results live. Docs under-sell.

---

## Rollup

| Category | High | Medium | Low | Total |
|----------|------|--------|-----|-------|
| A. Code defects | 2 | 1 | 0 | 3 |
| B. Capability not delivered | 1 | 3 | 1 | 5 |
| C. Doc accuracy / authority | 3 | 3 | 2 | 8 |
| D. Self-ingestion hygiene | 0 | 1 | 0 | 1 |
| E. Corrections | - | - | - | 2 |
| **Total findings (A-D)** | **6** | **8** | **3** | **17** |

**Must-fix-in-code:** A1 (storage split-brain), A2 (stdio never ages), A3 (embedding-dim guard).
B is "wire or honestly declare." C/D is documentation/ingestion accuracy.

Recommended order: A1 -> A2 -> A3 (code, each via the fail-first loop) -> C0/C1/C2 (operator-facing docs, regenerate from source) -> B1/B2 decision (true triple or honest double) -> remainder.

### Recommended next steps (from the audit discussion)

1. **Fix the storage mismatch (A1):** `get_indexer()` derives `CHROMA_PERSIST_DIR` from `<MEMORY_MCP_DATA_DIR>/chroma` when `CHROMA_PERSIST_DIR` is unset.
2. **One current contract:** create `docs/CURRENT.md` or rewrite README - entrypoints, 14 stdio tools, HTTP routes, auth, storage env vars.
3. **Demote history:** mark old deployment/history/planning docs as historical, or move under `docs/project-history/`.
4. **Generate, don't hand-maintain:** regenerate API docs (tool list/schemas/counts) from `tool_registry.py` + FastAPI routes.
5. **Clean self-ingestion (D1):** ingest only current docs with authority metadata; exclude stale history unless requested.

---

## F. Live runtime evidence (2026-06-15 MCP probe)

Single stored chunk `a1cc8fbc...`, then probed every tool. Grounds the Baseline and B1.

| Tool / layer | Result | Reads as |
|---|---|---|
| `memory_store` | chunk created; `WHO=unknown:mcp-client`, `PROJECT=memory-mcp-triple-system`, `lifecycle=hot` | store + tagging live (B5: WHO default) |
| `vector_search` | hit, `vector_score 0.32` (hybrid 0.639) | Vector tier live |
| `hipporag_retrieve` | entity `GuardSpine (ORG)`, `graph_score 1.0` | HippoRAG tier live |
| `bayesian_inference` | "No Bayesian inference available (no network or timeout)" (x2) | **Bayesian tier offline (B1)** |
| `unified_search` | `source_tiers=[hipporag, vector]`, `bayesian_score 0.0`, `final_score 0.76`, all stage timings present | fusion live as 2-of-3; pseudo-doc filter holding (no Bayesian VAR=state leak) |
| `graph_query` | thin result | graph multi-hop live (sparse output) |
| `entity_extraction` | 3 entities (PERSON/ORG/GPE) | live (E2: not a stub) |
| `detect_mode` | `planning`, 100% confidence | mode detection live |
| `lifecycle_status` | `{active:1, demoted:0, archived:0, rehydratable:0, total:1}` | lifecycle reporting live (but never ages under stdio - A2) |

---

## Operational note

Worktree at audit time had 6 uncommitted reviewer/smoke-test files (`raptor_clusterer.py`,
`http_server.py`, `consolidation.py`, `test_http_server_auth.py`, `test_lifecycle_manager.py`,
`test_raptor_clusterer.py`). A1's fix touches `http_server.py` - sequence around those edits to avoid collision.

Status: all open. Not yet promoted onto `STATUS-2026-06-13.md`; promote there if adopted.
