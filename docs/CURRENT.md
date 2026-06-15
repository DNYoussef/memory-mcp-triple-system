# Memory MCP - Current Contract (2026-06-15)

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
- `CHROMA_PERSIST_DIR` - vector store. (Known item A1: when unset it still defaults to `/data/chroma` instead of `<MEMORY_MCP_DATA_DIR>/chroma`; set it explicitly for a custom data dir until A1 lands.)
- Embeddings: `all-MiniLM-L6-v2` (local, 384-dim) by default.

## Tools (18)
vector_search, unified_search, memory_store, graph_query, bayesian_inference,
entity_extraction, hipporag_retrieve, detect_mode, lifecycle_status, obsidian_sync,
beads_ready_tasks, beads_task_detail, beads_query_tasks, observation_timeline,
**kv_get, kv_set, kv_delete** (B4), **context_retrieve** (P5).

## How each part works (and how to exercise it)
- **Store** (`memory_store`): tags WHO/WHEN/PROJECT/WHY, stamps numeric `last_accessed_ts` + `stage`, chunks, embeds -> ChromaDB, extracts entities -> NetworkX graph, logs an event.
- **Vector** (`vector_search`): query embedded, cosine over the HNSW index; score = 1 - distance.
- **HippoRAG graph** (`hipporag_retrieve` / `graph_query`): entity extraction -> graph nodes -> multi-hop retrieval of connected chunks.
- **Bayesian** (`bayesian_inference`): builds a Bayesian network from the CURRENT stored-memory graph at query time (CPDs estimated from real co-occurrence), normalizes the query entity to the graph's node naming, returns a probability distribution. Honest message when the entity has no node/edges yet. Calibration is bounded by the chunk<->entity graph; it is real inference over real data, not synthetic.
- **Unified fusion** (`unified_search`): RECALL all tiers -> COMBINE (vector 0.4 / graph 0.4 / bayesian 0.2) -> FILTER(0.3) -> DEDUPE(0.95) -> RANK -> drop Bayesian pseudo-docs -> RERANK -> COMPRESS. Degrades cleanly if a tier returns nothing.
- **Mode** (`detect_mode`): execution / planning / brainstorming via regex; sets result count + token budget.
- **Creative / broader-recall**: `unified_search mode=brainstorming` returns a wider set (>= execution).
- **Lifecycle** (`lifecycle_status` + aging): stages active->demoted->archived->rehydratable. Demotion filters `last_accessed_ts < cutoff`; ingestion now writes that numeric ts (A2), so chunks actually age. (Background scheduler runs under HTTP; under stdio, run maintenance on demand - follow-up.)
- **KV** (`kv_get/set/kv_delete`): direct key-value store (preferences, archival keys), TTL on set.
- **Context injection** (`context_retrieve`): surfaces the relevant stored memory to inject for a query (server side; the client performs the actual prompt injection). The richer `ProactiveContextInjector` adds trigger automation + ontology on top of the same retrieval.
- **Tracing**: every tool call records a `QueryTrace` to `query_traces.db`; `ErrorAttribution` reads them.

## Acceptance
`PYTHONPATH=. python scripts/acceptance_all_parts.py` -> `12 PASS | 0 XFAIL | 0 FAIL`. Runs on both models.

## Known remaining (tracked in audits/MECE-docs-vs-code-2026-06-15.md)
- A1 storage resolver (vector dir should derive from MEMORY_MCP_DATA_DIR).
- Lifecycle scheduler trigger under stdio.
- Doc cleanup of older README/api/planning files (C-cluster); this file supersedes them.
