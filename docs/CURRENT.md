# Memory MCP - Current Contract (2026-06-16)

The single source of truth for how the running system actually works. Verified by
`scripts/acceptance_all_parts.py` (hermetic, canary-asserted) on both Claude (in-process
stdio dispatch) and Codex (`codex exec`): **12 capabilities PASS / 0 FAIL** on both.

Older `README` / `docs/api/*` / planning specs describe earlier or aspirational states;
prefer this file. History lives under `docs/project-history/`.

## Entry points
- **stdio** (canonical MCP transport): `src/mcp/stdio_server.py` -> `protocol_handler` -> `request_router.handle_call_tool`.
- **HTTP**: `uvicorn src.mcp.http_server:app` (FastAPI). Tool routes require an API key by default.
- In-process (tests/harness): `NexusSearchTool(load_config())` + `handle_call_tool(name, args, tool)`.

## Storage (env)
- `MEMORY_MCP_DATA_DIR` (default `/data`) - root for graph.json, kv_store.db, events.db, query_traces.db.
- `CHROMA_PERSIST_DIR` - vector store override.
- **Path resolution (one resolver, `resolve_persist_dir`)**: every caller - the
  stdio + HTTP servers, the curation UI, and the maintenance scripts - resolves
  the ChromaDB dir with a single precedence:
  `explicit arg > CHROMA_PERSIST_DIR > MEMORY_MCP_DATA_DIR/chroma > /data/chroma`.
  So setting `MEMORY_MCP_DATA_DIR` alone is enough; the `/data/chroma` default is
  kept for the Railway volume when nothing is set. (Was item A1 - now fixed.)
- Embeddings: `all-MiniLM-L6-v2` (local, 384-dim) by default. The model loads
  lazily on first use, NOT at server boot (the stdio handshake stays fast).
- `MEMORY_MCP_SYNC_BAYESIAN=1` forces the Bayesian network to build synchronously
  instead of in the background (tests / deterministic startup).
- `OBSIDIAN_VAULT_PATH` - absolute path to an Obsidian vault. When set (or
  `storage.obsidian_vault` in config), `obsidian_sync` ingests the vault's `.md`
  notes (chunked + embedded + entity-extracted) into the same tiers as
  `memory_store`. Unset by default; the tool returns "not configured" until it
  is set. It is read from the env, so it lives in the MCP client config (e.g.
  the server's `env` block), not in this repo.

## Tools (18)
vector_search, unified_search, memory_store, graph_query, bayesian_inference,
entity_extraction, hipporag_retrieve, detect_mode, lifecycle_status, obsidian_sync,
beads_ready_tasks, beads_task_detail, beads_query_tasks, observation_timeline,
**kv_get, kv_set, kv_delete** (B4), **context_retrieve** (P5).

## How each part works (and how to exercise it)
- **Store** (`memory_store`): tags WHO/WHEN/PROJECT/WHY, stamps numeric `last_accessed_ts` + `stage`, chunks, embeds -> ChromaDB, extracts entities -> NetworkX graph, logs an event.
- **Vector** (`vector_search`): query embedded, cosine over the HNSW index; score = 1 - distance.
- **HippoRAG graph** (`hipporag_retrieve` / `graph_query`): entity extraction -> graph nodes -> multi-hop retrieval of connected chunks.
- **Bayesian** (`bayesian_inference`): builds a Bayesian network from the CURRENT stored-memory graph (CPDs estimated from real co-occurrence), resolves the query entity to the graph's node naming - including multi-word entities that NER stored under a single token (e.g. "Wilhelmina Ashgrove" -> `wilhelmina`) - and returns a probability distribution. Honest message when the entity has no node/edges yet. Real inference over real data, not synthetic. Three properties matter for performance/safety: (1) node **in-degree is capped** (`MAX_PARENTS`, default 4) so a hub entity cannot produce a 2^parents CPD table that tries to allocate hundreds of GiB; (2) the network is **cached** by graph version on one reused builder, so a repeated query on an unchanged graph is a cache hit; (3) for fused reads the network builds in a **background thread** off the hot path - the Bayesian tier simply contributes nothing until it is ready (the same graceful state it reaches on a query timeout), so vector/HippoRAG are never blocked.
- **Unified fusion** (`unified_search`): RECALL all tiers -> COMBINE (vector 0.4 / graph 0.4 / bayesian 0.2) -> FILTER(0.3) -> DEDUPE(0.95) -> RANK -> drop Bayesian pseudo-docs -> RERANK -> COMPRESS. Degrades cleanly if a tier returns nothing.
- **Mode** (`detect_mode`): execution / planning / brainstorming via regex; sets result count + token budget.
- **Creative / broader-recall**: `unified_search mode=brainstorming` returns a wider set (>= execution).
- **Lifecycle** (`lifecycle_status` + aging): stages active->demoted->archived->rehydratable. Demotion filters `last_accessed_ts < cutoff`; ingestion now writes that numeric ts (A2), so chunks actually age. (Background scheduler runs under HTTP; under stdio, run maintenance on demand - follow-up.)
- **KV** (`kv_get/set/kv_delete`): direct key-value store (preferences, archival keys), TTL on set.
- **Context injection** (`context_retrieve`): surfaces the relevant stored memory to inject for a query (server side; the client performs the actual prompt injection). The richer `ProactiveContextInjector` adds trigger automation + ontology on top of the same retrieval.
- **Tracing**: every tool call records a `QueryTrace` to `query_traces.db`; `ErrorAttribution` reads them.

## Robustness notes
- **UTF-8 I/O**: `src/mcp/_utf8_io` reconfigures stdout/stderr to UTF-8 before any
  heavy import, so a non-cp1252 glyph printed at import time can't crash the
  process on a Windows pipe (the MCP stdio transport).
- **Fast boot**: the embedder (and reranker, graph, spaCy, nexus processor) load
  lazily; constructing the server no longer blocks on the ~8s model load.

## Verification
- Acceptance: `PYTHONPATH=. python scripts/acceptance_all_parts.py` -> `12 PASS | 0 XFAIL | 0 FAIL`. Runs on both models.
- Per-tool latency + functional gate: `PYTHONPATH=. python scripts/bench_tools.py`
  (hermetic; records cold + warm p50/p95 per tool, asserts zero errors + canary present).
- Doc accuracy: `PYTHONPATH=. python scripts/check_docs.py` (this file and the other
  current docs must match the code; wired into the test suite).

## Known remaining (tracked in audits/MECE-docs-vs-code-2026-06-15.md)
- Lifecycle scheduler trigger under stdio.
- Bayesian query-time variable elimination in the lightweight backend is bounded
  by the engine's 1.0s timeout, not by structure; node cardinality (vs parents)
  is not capped (all nodes are 2-state today).
- Doc cleanup of older README/api/planning files (C-cluster); this file supersedes them.
