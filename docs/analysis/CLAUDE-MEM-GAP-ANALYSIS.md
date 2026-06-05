# claude-mem Gap Analysis Report

**Date**: 2026-02-05
**Analyst**: Claude Opus 4.5 (6-agent parallel research + sequential thinking synthesis)
**Source**: `thedotmack/claude-mem` (GitHub, ~250 files, 77K lines)
**Target**: `DNYoussef/memory-mcp-triple-system` (+ Beads + Obsidian integration)
**Standard**: Linus Torvalds A- (3.7/4.0)
**Method**: Gap Reconnaissance 7-Phase Workflow (adapted)

---

## Executive Summary

claude-mem is a TypeScript/Bun tool that hooks into Claude Code's lifecycle events (SessionStart, UserPromptSubmit, PostToolUse, Stop) to automatically capture observations and proactively inject relevant context. It uses SQLite for structured storage and ChromaDB (via MCP subprocess) for semantic search.

**The core insight**: Our retrieval pipeline is far superior (triple-tier fusion vs single-tier vector). But their automatic capture loop means their memory fills itself while ours stays empty without explicit `memory_store` calls. **Capture is the prerequisite for retrieval value.**

**Verdict**: 10 capability gaps identified. 8 files to adapt (TS -> Python). 5-phase plan. ~48 hours estimated effort. No architectural rewrites needed -- our foundation is stronger; we just need the auto-capture and proactive injection layers on top.

---

## Section 1: Capability Comparison Matrix

### What claude-mem Has That We Lack

| # | Capability | Impact | Their Implementation | Our Gap |
|---|-----------|--------|---------------------|---------|
| 1 | **Proactive context injection** | CRITICAL | SessionStart hook queries memory, outputs via `hookSpecificOutput` | We have no SessionStart hook. Memory is passive -- only returns results when explicitly queried via MCP tools. |
| 2 | **Automatic observation capture** | CRITICAL | PostToolUse hook captures every tool invocation as a structured observation without user action | We require explicit `memory_store` calls. Nothing is captured automatically. |
| 3 | **Session summaries** | HIGH | Stop hook generates structured summary (request/investigated/learned/completed/next_steps) | We have no Stop hook. Session context is lost between conversations. |
| 4 | **ChromaDB graceful fallback** | HIGH | ChromaDB accessed via MCP subprocess; 5-layer fallback if unavailable | Our `vector_indexer.py` has a hard `import chromadb` at top level. Catches wrong exception type (ValueError/KeyError instead of NotFoundError). 28 tests fail. |
| 5 | **Progressive disclosure** | HIGH | 3-layer search: compact index (~50 tok/result) -> timeline -> full details (~500 tok/result) | We always return full chunks. No compact mode. ~10x more tokens consumed per query. |
| 6 | **Observation type taxonomy** | MEDIUM | 6 types (tool_use, code_change, error, decision, discovery, conversation) x 7 concept categories | We store flat text blobs. No structured typing or categorization. |
| 7 | **Timeline navigation** | MEDIUM | Anchor timestamp + depth parameter for chronological browsing of session history | We have no temporal browsing. Search is purely semantic. |
| 8 | **Privacy tags** | MEDIUM | `<private>` tag stripping before storage -- marked content never enters memory | We store everything. No mechanism to exclude sensitive content. |
| 9 | **Token economics tracking** | MEDIUM | Logs tokens injected vs tokens that led to useful follow-up actions | We have no ROI tracking for injected context. |
| 10 | **Session tracking entity** | MEDIUM | Dual-ID lifecycle: session_id (UUID) + Claude session reference, with start/end/tool_count | We have no concept of a "session" as a first-class entity. |

### What We Have That They Lack (Our Advantages)

| Capability | Our Implementation | Their Gap |
|-----------|-------------------|-----------|
| **Triple-tier retrieval** | 40% Vector + 40% HippoRAG + 20% Bayesian | Vector-only search |
| **HippoRAG graph reasoning** | NetworkX multi-hop entity traversal | No graph tier |
| **Bayesian inference** | pgmpy probabilistic reasoning | No probabilistic tier |
| **Entity extraction (NER)** | spaCy + regex fallback | No entity extraction |
| **Memory lifecycle decay** | `e^(-days/30)` temporal decay formula | No decay -- all memories equal weight |
| **Nexus 5-step pipeline** | RECALL/FILTER/DEDUP/RANK/COMPRESS | Simple ChromaDB `query()` |
| **13 MCP tools** | vector_search, graph_query, bayesian_inference, entity_extraction, hipporag_retrieve, detect_mode, obsidian_sync, unified_search, memory_store, lifecycle_status, beads_ready_tasks, beads_task_detail, beads_query_tasks | 4 MCP tools (search, timeline, get_observations, __IMPORTANT) |
| **Obsidian vault sync** | Bidirectional markdown sync with chunking | Not present |
| **Beads task integration** | Task management with dependency tracking | Not present |
| **Mode-aware retrieval** | execution (5K) / planning (10K) / brainstorming (20K) token budgets | Single mode |

---

## Section 2: Files to Adapt from claude-mem

All files require TypeScript -> Python translation. We adapt patterns, not direct copies.

### File 1: `src/cli/handlers/context.ts` -> `src/hooks/session_start_handler.py`

**What it does**: SessionStart hook handler. Queries memory for recent observations and session summaries relevant to current working directory/project. Formats results as a context injection block and outputs via `hookSpecificOutput`.

**What to keep**:
- hookSpecificOutput pattern for injecting context into Claude's prompt
- Project-based filtering (current working directory)
- Recency weighting for observation selection

**What to change**:
- Replace their simple ChromaDB query with our Nexus 5-step pipeline
- Use our mode detection (execution/planning/brainstorming) to set token budget
- Use our decay formula for temporal relevance
- Add HippoRAG graph context alongside vector results

**Integration point**: `.claude/hooks/memory-mcp/session-start.py` (new file)

### File 2: `src/cli/handlers/observation.ts` -> `src/hooks/post_tool_handler.py`

**What it does**: PostToolUse hook handler. Parses the tool name and result from Claude's tool invocation. Creates a structured observation record. Stores in SQLite and indexes into ChromaDB.

**What to keep**:
- Tool name + result parsing from hook payload
- Auto-categorization logic (tool_use type by default, code_change if Write/Edit, error if tool failed)
- Deduplication check (don't store duplicate observations within same session)

**What to change**:
- Map observations to our WHO/WHEN/PROJECT/WHY tagging protocol
- Index into all 3 tiers (vector + graph entities + probabilistic)
- Use our KVStore for structured storage instead of raw SQLite
- Add concept extraction via our NER service

**Integration point**: `.claude/hooks/memory-mcp/post-tool.py` (new file)

### File 3: `src/services/context/ContextBuilder.ts` -> `src/services/context_builder.py`

**What it does**: Orchestrator that assembles the injection context block. Takes available observations, summaries, and search results. Applies token budget constraints. Produces the final formatted output.

**What to keep**:
- Priority ordering (recent session summary > recent observations > historical matches)
- Token-aware truncation (never exceed budget)
- Structured output format with section headers

**What to change**:
- Use our mode detection for budget (5K/10K/20K)
- Integrate our Nexus pipeline output format (core + extended results)
- Add Beads task context (currently active tasks)
- Add Obsidian daily note context if available

**Integration point**: `src/services/context_builder.py` (new file in memory-mcp)

### File 4: `src/services/context/ObservationCompiler.ts` -> `src/services/observation_compiler.py`

**What it does**: Selects which observations to include in context injection. Applies recency bias, type diversity (include at least one of each type), and relevance scoring.

**What to keep**:
- Type diversity constraint (at least 1 observation per type if available)
- Recency bias algorithm
- Relevance scoring based on current query/project context

**What to change**:
- Use our `e^(-days/30)` decay formula for recency weighting
- Integrate with our graph tier for entity-based relevance
- Add Beads task correlation (observations linked to active tasks get boost)

**Integration point**: `src/services/observation_compiler.py` (new file in memory-mcp)

### File 5: `src/services/context/TokenCalculator.ts` -> `src/services/token_calculator.py`

**What it does**: Estimates token count for text chunks. Enforces mode-based budget limits. Tracks cumulative tokens across injection sections.

**What to keep**:
- Token estimation algorithm (chars/4 approximation + safety margin)
- Cumulative tracking across sections
- Budget enforcement with graceful truncation

**What to change**:
- Align budgets with our mode system: execution=5K, planning=10K, brainstorming=20K
- Add optional tiktoken integration for precise counting
- Track token economics (injected vs utilized)

**Integration point**: `src/services/token_calculator.py` (new file in memory-mcp)

### File 6: `src/services/sqlite/transactions.ts` -> patterns in `src/stores/kv_store.py`

**What it does**: Atomic transaction wrapper for SQLite operations. Ensures observation writes are atomic (either fully committed or fully rolled back).

**What to keep**:
- Transaction wrapper pattern with automatic rollback on failure
- Retry logic for SQLITE_BUSY errors (concurrent access)

**What to change**:
- Enhance our existing KVStore with transaction support (it currently lacks it)
- Use Python's `sqlite3` context manager pattern
- Keep our existing KVStore API surface, just add atomicity

**Integration point**: `src/stores/kv_store.py` (modify existing file)

### File 7: `src/services/sqlite/observations/types.ts` -> `src/models/observation_types.py`

**What it does**: Defines the observation type enum, concept categories, and schema for structured observation storage.

**What to keep**:
- 6 observation types: tool_use, code_change, error, decision, discovery, conversation
- 7 concept categories: architecture, implementation, debugging, testing, configuration, documentation, planning
- Structured fields: session_id, type, concept, content, metadata, timestamp

**What to change**:
- Add our WHO/WHEN/PROJECT/WHY tagging as required fields
- Add confidence field (from our VERIX system)
- Add graph_entities field (extracted NER entities for graph indexing)
- Use Python dataclasses or Pydantic models

**Integration point**: `src/models/observation_types.py` (new file in memory-mcp)

### File 8: `plugin/hooks/hooks.json` -> `.claude/hooks/memory-mcp/hooks.json`

**What it does**: Hook wiring configuration. Maps Claude Code lifecycle events to handler scripts.

**What to keep**:
- Event-to-handler mapping pattern
- SessionStart, PostToolUse, Stop event types

**What to change**:
- Use our hook infrastructure paths (`.claude/hooks/memory-mcp/`)
- Point to Python handlers instead of TypeScript
- Add our enforcement integration (5-phase workflow compatibility)

**Integration point**: `.claude/hooks/memory-mcp/hooks.json` (new file)

---

## Section 3: ChromaDB Fix (28 Test Failures)

### Root Cause

`D:\Projects\memory-mcp-triple-system\src\indexing\vector_indexer.py`, line 100:

```python
try:
    self.collection = self.client.get_collection(self.collection_name)
except (ValueError, KeyError):  # BUG: wrong exception types
    self.collection = self.client.create_collection(...)
```

ChromaDB v1.3.5 throws `chromadb.errors.NotFoundError` when a collection doesn't exist, not `ValueError` or `KeyError`. This causes the exception to propagate up, crashing the 28 tests that depend on collection initialization.

### Fix Plan

**P0.1**: Change the except clause to catch the correct exception:
```python
try:
    import chromadb.errors
    _CHROMA_NOT_FOUND = chromadb.errors.NotFoundError
except (ImportError, AttributeError):
    _CHROMA_NOT_FOUND = Exception  # fallback

# In create_collection():
try:
    self.collection = self.client.get_collection(self.collection_name)
except (ValueError, KeyError, _CHROMA_NOT_FOUND):
    self.collection = self.client.create_collection(...)
```

**P0.2**: Make ChromaDB import optional:
```python
try:
    import chromadb
    import chromadb.errors
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
```

When unavailable, the vector tier returns empty results and the Nexus processor redistributes weights to graph (57%) and Bayesian (43%).

**P0.3**: Verify all 28 tests pass with the fix.

**P0.4**: Add a health check endpoint to report ChromaDB availability status.

---

## Section 4: Contradictions Resolved

| # | Contradiction | Report A | Report B | Resolution |
|---|--------------|----------|----------|------------|
| 1 | ChromaDB import strategy | Agent 3: "never import chromadb directly" | Agent 1: "ChromaDB IS used for storage" | claude-mem accesses ChromaDB through a separate MCP subprocess, never importing the library directly. Our approach: fix direct import AND add optional fallback. Both strategies are valid. |
| 2 | Daemon model recommendation | Agent 5: "daemon model NO" | Agent 2: "worker is core to injection" | We don't need a persistent daemon. Our hooks fire on-demand (SessionStart/PostToolUse/Stop). The worker pattern is only needed for background processing, which Claude Code's hook model doesn't require. |
| 3 | Number of MCP tools | Agent 6: "4 MCP tools" | Agent 1: "many more features" | claude-mem exposes 4 tools via MCP but has many more features through its hook/worker system. We should focus on hook-side features (auto-capture, proactive injection), not expanding MCP tool count. |
| 4 | Web UI recommendation | Agent 5: "Web UI NO" | Agent 6: "React viewer is useful" | The web viewer is nice-to-have but not a memory system feature. We already have Life OS Dashboard for visualization. Skip the web UI. |

---

## Section 5: Full Sequenced Implementation Plan

### Dependency Graph

```
Phase 0 (ChromaDB Fix) -----+
                             |
                             v
                      Phase 1 (Schema) ----+----> Phase 3 (Search)
                             |             |            |
                             v             |            v
                      Phase 2 (Hooks) -----+----> Phase 4 (Polish)
```

**Critical Path**: Phase 0 -> Phase 1 -> Phase 2 -> Phase 4 (28-46 hours)
**Parallel Path**: Phase 1 -> Phase 3 (can run alongside Phase 2)

---

### Phase 0: ChromaDB Resilience
**Effort**: 4-6 hours | **Blockers**: None | **Risk**: Low

| Task | Description | Hours | Depends On |
|------|-------------|-------|------------|
| P0.1 | Fix `vector_indexer.py:100` to catch `NotFoundError` | 1 | - |
| P0.2 | Make `import chromadb` optional with `CHROMADB_AVAILABLE` flag | 2 | - |
| P0.3 | Verify all 28 previously-failing tests pass | 1 | P0.1, P0.2 |
| P0.4 | Add ChromaDB availability health check to lifecycle_status | 1 | P0.2 |

**GATE 0**: All 28 tests pass. `CHROMADB_AVAILABLE=False` gracefully returns empty vector results with weight redistribution.

---

### Phase 1: Observation Schema & Storage
**Effort**: 8-12 hours | **Blockers**: Phase 0 (for test stability) | **Risk**: Low

| Task | Description | Hours | Depends On |
|------|-------------|-------|------------|
| P1.1 | Create `src/models/observation_types.py` with 6 types + 7 concepts | 1 | - |
| P1.2 | Add observations table to KVStore (session_id, type, concept, content, metadata, timestamp) | 2 | P1.1 |
| P1.3 | Create session tracking entity (session_id UUID, started_at, ended_at, tool_count, summary) | 2 | P1.1 |
| P1.4 | Create structured summary generator (request/investigated/learned/completed/next_steps) | 3 | P1.3 |
| P1.5 | Add observation-to-memory bridge: auto-index observations into vector + graph tiers | 2 | P1.2 |

**GATE 1**: Unit tests for all new entities. Observation round-trip (create -> store -> retrieve) works. Summary generation produces structured output.

---

### Phase 2: Hooks Integration (Proactive Injection)
**Effort**: 12-18 hours | **Blockers**: Phase 1 | **Risk**: Medium

| Task | Description | Hours | Depends On |
|------|-------------|-------|------------|
| P2.1 | Create `src/hooks/session_start_handler.py` - SessionStart hook querying Nexus | 4 | P1.2, P1.3 |
| P2.2 | Create `src/hooks/post_tool_handler.py` - PostToolUse auto-capture to observations | 4 | P1.1, P1.2 |
| P2.3 | Create `src/hooks/stop_handler.py` - Stop session summarizer | 3 | P1.4 |
| P2.4 | Create `src/services/context_builder.py` - Orchestrate injection context assembly | 3 | P2.1 |
| P2.5 | Create `src/services/token_calculator.py` - Token estimation + budget enforcement | 2 | - |
| P2.6 | Wire hooks into `.claude/hooks/memory-mcp/` configuration | 2 | P2.1-P2.5 |

**GATE 2**: SessionStart injects relevant context (verified by hook output). PostToolUse creates observations (verified by KVStore query). Stop generates session summary (verified by summary content).

---

### Phase 3: Search Enhancements
**Effort**: 8-12 hours | **Blockers**: Phase 1 | **Risk**: Low
**Note**: Can run in parallel with Phase 2.

| Task | Description | Hours | Depends On |
|------|-------------|-------|------------|
| P3.1 | Progressive disclosure - compact index mode (~50 tokens/result) | 3 | P1.2 |
| P3.2 | Progressive disclosure - full detail mode (~500 tokens/result) | 2 | P3.1 |
| P3.3 | Timeline query support (anchor timestamp + depth for chronological browsing) | 3 | P1.3 |
| P3.4 | Search filters: by observation type, session, date range, project | 2 | P1.1, P1.2 |
| P3.5 | Update MCP tools (vector_search, unified_search) with new search parameters | 2 | P3.1-P3.4 |

**GATE 3**: Progressive disclosure saves >60% tokens on initial queries. Timeline browsing returns chronologically ordered observations. Filters work correctly.

---

### Phase 4: Polish & Integration
**Effort**: 6-10 hours | **Blockers**: Phases 2 and 3 | **Risk**: Low

| Task | Description | Hours | Depends On |
|------|-------------|-------|------------|
| P4.1 | Privacy tag support: `<private>` stripping before storage | 2 | P2.2 |
| P4.2 | Token economics tracking: log injected tokens vs follow-up utility | 2 | P2.4 |
| P4.3 | Beads integration: link observations to active Beads tasks via project/context | 2 | P1.2 |
| P4.4 | Obsidian sync enhancement: include observations in vault sync | 2 | P1.2 |
| P4.5 | End-to-end integration test suite: capture -> store -> inject -> verify | 2 | P4.1-P4.4 |

**GATE 4**: Privacy tags work (tagged content never stored). Token economics logs exist. Beads tasks include observation references. Obsidian sync includes observations. E2E test passes.

---

## Section 6: Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Hook latency adds perceptible delay to SessionStart | Medium | Medium | Token budget limits + async observation indexing |
| PostToolUse capture creates too much noise | Medium | Low | Observation dedup + type filtering + configurable capture rules |
| ChromaDB optional mode degrades search quality | Low | Medium | Weight redistribution ensures graph+Bayesian compensate |
| Session summary generation fails on complex sessions | Low | Medium | Fallback to simple observation list if structured generation fails |
| Hook script errors break Claude Code workflow | Medium | High | All hooks wrapped in try/except with silent failure + error logging |

---

## Section 7: Metrics & Success Criteria

### Quantitative Gates

| Metric | Current | Target | Phase |
|--------|---------|--------|-------|
| Test failures (ChromaDB) | 28 | 0 | Phase 0 |
| Auto-captured observations per session | 0 | >10 | Phase 2 |
| Context injection at session start | Never | Every session | Phase 2 |
| Tokens per search query (compact mode) | ~2000 | ~200 | Phase 3 |
| Privacy tag compliance | N/A | 100% stripped | Phase 4 |

### Qualitative Success

1. A user starting a new Claude Code session in a project automatically sees relevant prior context
2. Tool usage is silently captured and available for future retrieval without explicit memory_store calls
3. Session endings produce structured summaries that appear in the next session's context
4. Search supports both "give me a quick overview" and "give me full details" modes
5. Beads tasks and Obsidian notes are woven into the observation context

---

## Section 8: What NOT to Adopt

| claude-mem Feature | Reason to Skip |
|-------------------|----------------|
| Daemon worker process (port 37777) | Our hook model is on-demand; daemon adds complexity + failure modes |
| React web viewer | We already have Life OS Dashboard for visualization |
| SSE streaming | Not needed for hook-based capture pattern |
| Multi-model agent routing (SDK/Gemini/OpenRouter) | We already have multi-model routing via Context Cascade |
| HTTP API (50 endpoints) | Overkill; our MCP tools are the API surface |
| `__IMPORTANT` MCP tool | Gimmick; our Nexus pipeline handles importance ranking |

---

## Appendix A: Agent Research Summary

| Agent | Domain | Key Finding |
|-------|--------|-------------|
| 1 - Architecture | README, CLAUDE.md, PLAN.md | 19 features total; proactive injection is the standout differentiator |
| 2 - Context Injection | Hooks, handlers, ContextBuilder | 5-step injection flow; hookSpecificOutput is the mechanism |
| 3 - Search/ChromaDB | ChromaDB, search services | MCP subprocess pattern; 5-layer fallback; our bug is exception type mismatch |
| 4 - Storage | SQLite, observations, sessions | 6 entities; structured summaries; concept taxonomy is well-designed |
| 5 - Worker | Daemon, health, shutdown | Health monitoring YES; graceful shutdown YES; daemon NO |
| 6 - MCP/Plugin | Plugin hooks, SDK, modes | 4 MCP tools; progressive disclosure and timeline are key search gaps |

---

## Appendix B: Commit Integration Plan

**Branch**: `feature/claude-mem-integration`
**Base**: Current `vx39/pipeline-forge-stabilize` after existing commits

| Commit | Phase | Description |
|--------|-------|-------------|
| 1 | P0 | fix: ChromaDB exception handling and optional import |
| 2 | P1 | feat: observation types, session tracking, structured summaries |
| 3 | P2 | feat: SessionStart/PostToolUse/Stop hook handlers |
| 4 | P2 | feat: ContextBuilder and TokenCalculator services |
| 5 | P3 | feat: progressive disclosure and timeline search |
| 6 | P4 | feat: privacy tags, token economics, Beads/Obsidian integration |
| 7 | P4 | test: end-to-end integration test suite |

Each commit must pass its phase gate before the next phase begins.

---

*Report generated by 6-agent parallel research + 3-step sequential thinking synthesis.*
*Method: Gap Reconnaissance 7-Phase adapted workflow.*
*Standard: Linus Torvalds A- (3.7/4.0)*
