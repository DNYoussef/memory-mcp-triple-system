# Memory MCP Triple System - MECE Consolidated Issues Analysis

**Generated**: 2025-11-25
**Updated**: 2025-11-25 (Post Phase 0 - Architecture Decision)
**Sources**: Opus 4.5, Gemini 3, GPT-5 Codex
**Framework**: MECE (Mutually Exclusive, Collectively Exhaustive)

---

## POST-PHASE 0 STATUS UPDATE

```
+-------------------------------------------------------------------+
|                    ISSUE STATUS AFTER PHASE 0                      |
+-------------------------------------------------------------------+
| Original Total:      40 issues                                    |
| Resolved (Phase 0):   5 issues (A1.1-A1.5)                        |
| Remaining:           35 issues                                    |
| Critical Remaining:  13 (was 18)                                  |
+-------------------------------------------------------------------+
```

**Architecture Decision**: Unified (Vector/Graph/Bayesian + Time-Decay + P/E/S metadata)
**Reference**: docs/ARCHITECTURE-DECISION.md, docs/ARCHITECTURE.md

---

## MECE CATEGORY MATRIX

```
+-----------------------------------------------------------------------------------+
|                    MEMORY MCP TRIPLE SYSTEM - ISSUE TAXONOMY                       |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  1. ARCHITECTURE       2. CORE              3. INTEGRATION    4. CONFIG/DEPS      |
|     & DESIGN              FUNCTIONALITY        LAYER             & TESTING        |
|                                                                                   |
|  +---------------+    +---------------+    +---------------+  +---------------+   |
|  | A1. Arch      |    | B1. Mock Code |    | C1. MCP Tools |  | D1. Missing   |   |
|  |    Conflict   |    |    Inventory  |    |    Limited    |  |    Deps       |   |
|  +---------------+    +---------------+    +---------------+  +---------------+   |
|  | A2. Doc vs    |    | B2. TODO/     |    | C2. Hooks     |  | D2. Hardcoded |   |
|  |    Code Drift |    |    Incomplete |    |    Missing    |  |    Paths      |   |
|  +---------------+    +---------------+    +---------------+  +---------------+   |
|  | A3. Layer     |    | B3. Algorithm |    | C3. Runtime   |  | D3. Config    |   |
|  |    Mismatch   |    |    Bugs       |    |    Wiring     |  |    Mismatches |   |
|  +---------------+    +---------------+    +---------------+  +---------------+   |
|                       | B4. Data Flow |    | C4. External  |  | D4. Test      |   |
|                       |    Broken     |    |    Systems    |  |    Coverage   |   |
|                       +---------------+    +---------------+  +---------------+   |
+-----------------------------------------------------------------------------------+
```

---

## 1. ARCHITECTURE & DESIGN (Category A)

### A1. Architecture Conflict [RESOLVED - PHASE 0 COMPLETE]

**Status**: RESOLVED (2025-11-25)
**Resolution**: Unified Architecture adopted (ADR-001)

| ID | Issue | Status | Resolution |
|----|-------|--------|------------|
| A1.1 | THREE competing architecture definitions | RESOLVED | Unified architecture chosen |
| A1.2 | Codebase: Vector/Graph/Bayesian | RESOLVED | KEPT as core retrieval tiers |
| A1.3 | True Architecture Doc: Time-Based (24h/7d/30d) | RESOLVED | MERGED as metadata feature (decay_score) |
| A1.4 | Obsidian Doc: Procedural/Episodic/Semantic | RESOLVED | MERGED as metadata category field |
| A1.5 | Backend doesn't support frontend data structures | RESOLVED | Unified model provides consistency |

**Documents Created**:
- `docs/ARCHITECTURE-DECISION.md` - ADR-001 formal decision
- `docs/ARCHITECTURE.md` - Canonical architecture reference

**Documents Archived**:
- `docs/archive/MEMORY-MCP-TRUE-ARCHITECTURE-ARCHIVED.md`
- `docs/archive/MEMORY-MCP-OBSIDIAN-INTEGRATION-ARCHIVED.md`

### A2. Documentation vs Code Drift [PARTIALLY RESOLVED]
| ID | Issue | Source | Status |
|----|-------|--------|--------|
| A2.1 | Banner claims Qdrant/Neo4j but code uses Chroma/NetworkX | Codex | RESOLVED - src/__init__.py fixed (v1.1.0) |
| A2.2 | Integration tests reference Dockerized Qdrant | Codex | OPEN - needs test update |
| A2.3 | Week N references never completed | All 3 | OPEN - needs cleanup |

### A3. Layer Mismatch [HIGH - ALL]
| ID | Issue | Source | Evidence |
|----|-------|--------|----------|
| A3.1 | Bayesian tier always passes network=None | Opus, Codex | src/nexus/processor.py:216-565 |
| A3.2 | Nexus/HippoRAG 5-step SOP never executed | Codex | stdio_server.py bypasses to VectorSearchTool |
| A3.3 | Only 2 of 3 tiers actually functional | All 3 | Vector works, Graph partial, Bayesian broken |

---

## 2. CORE FUNCTIONALITY (Category B)

### B1. Mock Code Inventory [CRITICAL - ALL]
| ID | File | Line | Issue | Source |
|----|------|------|-------|--------|
| B1.1 | src/mcp/obsidian_client.py | 167 | Sync returns fake chunk count, no API call | Opus |
| B1.2 | src/mcp/obsidian_client.py | 150-174 | _sync_file reads markdown but doesn't index | Codex |
| B1.3 | src/debug/query_replay.py | 31,83 | Week 8 mock implementation | Opus |
| B1.4 | src/debug/query_replay.py | 160-178 | Context reconstruction returns empty dicts | Opus |
| B1.5 | src/debug/query_replay.py | 188-219 | Query re-run creates dummy trace | Opus |
| B1.6 | src/bayesian/network_builder.py | 145-156 | CPD uses random.choice instead of real data | Opus |
| B1.7 | src/clustering/raptor_clusterer.py | 277-278 | First 200 chars instead of LLM summary | Opus |
| B1.8 | src/debug/error_attribution.py | 200, 232 | Placeholder implementations | Opus |
| B1.9 | src/memory/lifecycle_manager.py | 530 | Compression placeholder | Opus |

### B2. TODO/Incomplete Implementations [HIGH - ALL]
| ID | File | Line | TODO | Week |
|----|------|------|------|------|
| B2.1 | src/chunking/semantic_chunker.py | 116 | Max-Min semantic chunking algorithm | - |
| B2.2 | src/utils/file_watcher.py | 63 | Implement deletion from vector DB | - |
| B2.3 | src/debug/query_replay.py | 176 | Fetch from memory store | Week 11 |
| B2.4 | src/debug/query_replay.py | 177 | Fetch from KV store | Week 11 |
| B2.5 | src/debug/query_replay.py | 178 | Fetch from session store | Week 11 |
| B2.6 | src/services/curation_service.py | 317 | TODO/FIXME detection for lifecycle | - |

### B3. Algorithm Bugs [CRITICAL - ALL]
| ID | File | Line | Bug | Impact |
|----|------|------|-----|--------|
| B3.1 | src/mcp/tools/vector_search.py | 140 | Distance-to-similarity assumes [0,1] range | Wrong similarity scores |
| B3.2 | src/nexus/processor.py | 587-590 | Jaccard instead of cosine similarity | Reduced accuracy |
| B3.3 | src/nexus/processor.py | 529 | Entity extraction uses first word only | Broken entity logic |
| B3.4 | src/debug/query_replay.py | 201 | Import inside function, unused uuid4 | Dead code |

### B4. Data Flow Broken [CRITICAL - CODEX]
| ID | Issue | Evidence | Impact |
|----|-------|----------|--------|
| B4.1 | Collection mismatch: memory_chunks vs memory_embeddings | curation_service.py vs config | Empty search results |
| B4.2 | Ingestion writes to wrong collection | vector_indexer.py:38-44 | Data goes to void |
| B4.3 | No production code builds Bayesian network | Only tests import NetworkBuilder | Tier 3 dead |
| B4.4 | HotColdClassifier only in tests | tests/unit/test_hotcold_classifier.py | No lifecycle demote |

---

## 3. INTEGRATION LAYER (Category C)

### C1. MCP Tools Limited [HIGH - ALL]
| ID | Issue | Source | Evidence |
|----|-------|--------|----------|
| C1.1 | Only 2 tools exposed: vector_search, memory_store | Opus, Codex | src/mcp/stdio_server.py |
| C1.2 | Missing: graph_query | Opus | Not in server |
| C1.3 | Missing: bayesian_inference | Opus | Not in server |
| C1.4 | Missing: entity_extraction | Opus | Not in server |
| C1.5 | Missing: hipporag_retrieve | Opus | Not in server |
| C1.6 | Missing: MODE detection, routing, event log, lifecycle | Codex | src/mcp/server.py:58-103 |

### C2. Hooks Missing [CRITICAL - GEMINI]
| ID | Issue | Expected Location | Status |
|----|-------|-------------------|--------|
| C2.1 | 12FA hooks directory missing | .claude/hooks/12fa/ | Directory DNE |
| C2.2 | memory-mcp-tagging-protocol.js missing | hooks/12fa/ | File DNE |
| C2.3 | agent-mcp-access-control.js missing | hooks/12fa/ | File DNE |
| C2.4 | WHO/WHEN/PROJECT/WHY tagging fails | Automatic | No hook to invoke |
| C2.5 | Terminal Manager hooks missing | .claude/hooks/ | Only basic PS1 scripts |

### C3. Runtime Wiring Gaps [CRITICAL - CODEX]
| ID | Issue | Evidence | Impact |
|----|-------|----------|--------|
| C3.1 | NexusProcessor never instantiated by MCP servers | src/mcp/server.py:58-101 | 5-step SOP bypassed |
| C3.2 | ObsidianClient never imported by production code | Only tests import | Vault sync dead |
| C3.3 | Event log never populated at runtime | src/stores/*.py | No audit trail |
| C3.4 | KV store never used at runtime | src/stores/kv_store.py | State storage dead |
| C3.5 | Lifecycle manager never invoked | src/memory/lifecycle_manager.py | No memory decay |
| C3.6 | QueryTrace.log never called by service | src/debug/query_trace.py:73-151 | No debugging |
| C3.7 | Migration 007_query_traces_table.sql not auto-applied | migrations/ | Table missing |

### C4. External Systems [MEDIUM - OPUS]
| ID | Issue | Status | Impact |
|----|-------|--------|--------|
| C4.1 | Terminal Manager integration | NOT PRESENT | No coordination |
| C4.2 | Claude Code hook integration | NOT INTEGRATED | No session sync |
| C4.3 | Obsidian vault path may not exist | Config issue | Sync fails |
| C4.4 | Gemini model disabled | config/memory-mcp.yaml:35-36 | Feature unavailable |

---

## 4. CONFIGURATION, DEPENDENCIES & TESTING (Category D)

### D1. Missing Dependencies [CRITICAL - CODEX]
| ID | Package | File | Impact |
|----|---------|------|--------|
| D1.1 | tenacity | pyproject.toml missing | MCP server crashes |
| D1.2 | requests | Imported but logic mock | No actual HTTP calls |

### D2. Hardcoded Paths [HIGH - GEMINI]
| ID | File | Issue |
|----|------|-------|
| D2.1 | scripts/populate_knowledge_base.py | C:\Users\17175 hardcoded |
| D2.2 | scripts/ingest_complete_system_knowledge.py | C:\Users\17175 hardcoded |
| D2.3 | Various scripts | Absolute paths not portable |

### D3. Configuration Mismatches [HIGH - ALL]
| ID | Issue | Evidence |
|----|-------|----------|
| D3.1 | Strategy: max_min_semantic but code uses paragraph split | config vs semantic_chunker.py |
| D3.2 | Collection: memory_chunks vs memory_embeddings | config vs code |
| D3.3 | Backend: Qdrant/Neo4j docs vs Chroma/NetworkX code | All docs outdated |

### D4. Test Coverage Gaps [MEDIUM - ALL]
| ID | Issue | Evidence |
|----|-------|----------|
| D4.1 | E2E tests skipped (Docker/Qdrant/Claude prereqs) | test_end_to_end_search.py |
| D4.2 | Embedding pipeline tests skip if model unavailable | test_embedding_pipeline.py |
| D4.3 | No CI job for migrations | No script |
| D4.4 | Only unit tests pass, integration broken | tests/integration/* |

---

## ISSUE COUNTS BY SEVERITY (UPDATED POST-PHASE 0)

| Severity | Original | Resolved | Remaining | Categories |
|----------|----------|----------|-----------|------------|
| CRITICAL | 18 | 5 (A1.*) | 13 | B1, B3, B4, C2, C3, D1 |
| HIGH | 14 | 1 (A2.1) | 13 | A2, A3, B2, C1, D2, D3 |
| MEDIUM | 8 | 0 | 8 | C4, D4 |
| **TOTAL** | **40** | **6** | **34** | Phase 0 resolved 6 issues |

**Phase 0 Resolved**:
- A1.1, A1.2, A1.3, A1.4, A1.5 (Architecture Conflict) - 5 CRITICAL
- A2.1 (Banner drift) - 1 HIGH

---

## UNIQUE CONTRIBUTIONS BY MODEL

| Model | Unique Findings | Key Contribution |
|-------|-----------------|------------------|
| **Opus 4.5** | Line-level precision, Bug identification | B1.6, B1.7, B1.8, B3.1-B3.4 |
| **Gemini 3** | Architecture conflict discovery | A1.1-A1.5, C2.1-C2.5, D2.* |
| **Codex** | Runtime wiring analysis, Dependency issues | B4.*, C3.*, D1.*, A2.1-A2.2 |

---

## OVERLAP MATRIX

Issues discovered by multiple models:

| Issue | Opus | Gemini | Codex |
|-------|------|--------|-------|
| Obsidian client mock | X | X | X |
| Query replay mock | X | X | X |
| Semantic chunker TODO | X | | X |
| File watcher deletion | X | | X |
| MCP tools limited | X | | X |
| Hooks missing | X | X | |
| Bayesian tier broken | X | | X |
| Doc vs code drift | | X | X |

**Consensus Issues (3/3 models)**: 2
**Majority Issues (2/3 models)**: 6
**Single-source Issues**: 32

---

## NEXT: DEPENDENCY TREE & VERIFICATION PLAN

See: DEPENDENCY-TREE.md and VERIFICATION-PLAN.md
