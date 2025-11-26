# Memory MCP Triple System - Error Dependency Tree

**Generated**: 2025-11-25
**Updated**: 2025-11-25 (Post Phase 0 - RC-1 Resolved)
**Purpose**: Identify root causes that cascade into downstream errors

---

## PHASE 0 IMPACT ON DEPENDENCY TREE

```
+-------------------------------------------------------------------+
|                ROOT CAUSE STATUS AFTER PHASE 0                     |
+-------------------------------------------------------------------+
| RC-1: Architecture Conflict     -> RESOLVED (Unified Architecture) |
| RC-2: Missing tenacity          -> OPEN (Phase 1 target)           |
| RC-3: Collection name mismatch  -> OPEN (Phase 1 target)           |
+-------------------------------------------------------------------+
```

**Downstream Unblocked**: 15+ issues that were blocked by RC-1 are now actionable.

---

## DEPENDENCY VISUALIZATION

```
                                    ROOT CAUSES (Fix First)
                                           |
    +--------------------------------------+--------------------------------------+
    |                                      |                                      |
    v                                      v                                      v
+-------------------+          +------------------------+          +-------------------+
| A1. ARCHITECTURE  |          | D1. MISSING            |          | D3. CONFIG        |
| CONFLICT          |          | DEPENDENCIES           |          | MISMATCHES        |
| (Decision Needed) |          | (tenacity missing)     |          | (collection name) |
+--------+----------+          +-----------+------------+          +--------+----------+
         |                                 |                                |
         | blocks                          | blocks                         | causes
         v                                 v                                v
+-------------------+          +------------------------+          +-------------------+
| C3. RUNTIME       |          | B4.1 SERVER            |          | B4.1 EMPTY        |
| WIRING GAPS       |          | CRASH ON START         |          | SEARCH RESULTS    |
+--------+----------+          +-----------+------------+          +--------+----------+
         |                                                                  |
         | causes                                                           | causes
         v                                                                  v
+-------------------+                                              +-------------------+
| B1. MOCK CODE     |                                              | C1. MCP TOOLS     |
| NEVER REPLACED    |                                              | APPEAR BROKEN     |
+--------+----------+                                              +-------------------+
         |
         | causes
         v
+-------------------+
| B2. TODOs NEVER   |
| COMPLETED         |
+-------------------+


                              DETAILED CASCADE CHAINS
                              =======================

CHAIN 1: Architecture -> Everything
----------------------------------
A1.1 (Architecture Conflict)
    |
    +-> A3.1 (Bayesian tier passes None) -- No one knows which arch to implement
    |       |
    |       +-> B4.3 (No prod code builds network) -- Why build if arch unclear?
    |               |
    |               +-> C1.3 (bayesian_inference not exposed) -- Nothing to expose
    |
    +-> C3.1 (NexusProcessor never instantiated) -- Which SOP to follow?
    |       |
    |       +-> C3.3 (Event log never populated) -- No runtime to log
    |       +-> C3.5 (Lifecycle never invoked) -- No flow to trigger it
    |
    +-> B1.* (All mock code) -- "We'll fix it when arch is decided"


CHAIN 2: Missing Dependency -> Server Death
-------------------------------------------
D1.1 (tenacity missing from pyproject.toml)
    |
    +-> vector_indexer.py fails to import
            |
            +-> MCP server crashes before reaching Chroma
                    |
                    +-> No vector search available
                            |
                            +-> ENTIRE SYSTEM DEAD


CHAIN 3: Config Mismatch -> Silent Data Loss
--------------------------------------------
D3.2 (memory_chunks vs memory_embeddings)
    |
    +-> B4.1 (Ingest writes to memory_chunks)
    |       |
    |       +-> B4.2 (Server queries memory_embeddings)
    |               |
    |               +-> EMPTY RESULTS (data in wrong collection)
    |
    +-> Users think system is broken when data exists


CHAIN 4: Hooks Missing -> No Metadata
-------------------------------------
C2.1 (12FA hooks directory missing)
    |
    +-> C2.2 (memory-mcp-tagging-protocol.js missing)
            |
            +-> C2.4 (WHO/WHEN/PROJECT/WHY tagging fails)
                    |
                    +-> Memory stored without context
                            |
                            +-> Retrieval quality degraded
                            +-> Cannot filter by agent/project


CHAIN 5: Mock Code -> Feature Illusion
--------------------------------------
B1.1 (Obsidian sync mock)
    |
    +-> C3.2 (ObsidianClient never imported by prod)
            |
            +-> Users think Obsidian works, it doesn't
                    |
                    +-> Vault files never indexed
                            |
                            +-> Search returns nothing from vault


CHAIN 6: TODO Chain -> Debugging Impossible
-------------------------------------------
B2.3-B2.5 (Query replay TODOs - Week 11)
    |
    +-> B1.4 (Context reconstruction empty)
            |
            +-> Cannot replay queries for debugging
                    |
                    +-> C3.6 (QueryTrace.log never called)
                            |
                            +-> C3.7 (Migration not applied)
                                    |
                                    +-> No query history preserved
```

---

## ROOT CAUSE HIERARCHY

### LEVEL 0: Ultimate Root Causes (Fix These First)

| ID | Root Cause | Status | Downstream Impact |
|----|------------|--------|-------------------|
| **RC-1** | A1.1 Architecture Conflict | **RESOLVED** | 15+ issues UNBLOCKED |
| **RC-2** | D1.1 Missing tenacity dependency | OPEN | Server startup blocked |
| **RC-3** | D3.2 Collection name mismatch | OPEN | Data flow blocked |

**RC-1 Resolution**: Unified Architecture (V/G/B core + time-decay + P/E/S metadata)
**Reference**: docs/ARCHITECTURE-DECISION.md

### LEVEL 1: Primary Blockers (Fix After Level 0)

| ID | Issue | Caused By | Causes |
|----|-------|-----------|--------|
| **L1-1** | C3.1 NexusProcessor not instantiated | RC-1 | 5-step SOP broken |
| **L1-2** | C2.1 Hooks directory missing | Design oversight | Metadata tagging |
| **L1-3** | B1.1 Obsidian mock | RC-1 + time | Vault sync dead |

### LEVEL 2: Secondary Effects (Fix After Level 1)

| ID | Issue | Caused By | Causes |
|----|-------|-----------|--------|
| **L2-1** | B4.3 No network building | L1-1, RC-1 | Bayesian dead |
| **L2-2** | C1.* MCP tools limited | L1-1 | User features missing |
| **L2-3** | B2.* TODOs incomplete | L1-1, RC-1 | Technical debt |

### LEVEL 3: Tertiary Effects (Fix After Level 2)

| ID | Issue | Caused By | Impact |
|----|-------|-----------|--------|
| **L3-1** | C3.3 Event log empty | L2-1 | No audit trail |
| **L3-2** | C3.5 Lifecycle unused | L2-1 | Memory never decays |
| **L3-3** | D4.* Test gaps | L2-3 | Regressions possible |

---

## FIX ORDER (Topological Sort)

Based on dependency analysis, issues must be fixed in this order:

```
PHASE 0: Decision Required [COMPLETE]
======================================
[x] A1.1 - Decide: Vector/Graph/Bayes OR Time-Based OR P/E/S
    - DECISION: Unified Architecture (all 3 merged)
    - COMPLETED: 2025-11-25
    - REFERENCE: docs/ARCHITECTURE-DECISION.md

PHASE 1: Foundation Fixes (Immediate blockers) [READY TO START]
===============================================================
[ ] D1.1 - Add tenacity to pyproject.toml
    - BLOCKS: Server startup
    - EFFORT: 5 minutes
    - STATUS: Ready (unblocked by Phase 0)

[ ] D3.2 - Fix collection name: memory_chunks -> memory_embeddings
    - BLOCKS: All search results
    - EFFORT: 30 minutes (config + code audit)
    - STATUS: Ready (unblocked by Phase 0)

[ ] D2.* - Replace hardcoded paths with os.path.expanduser("~")
    - BLOCKS: Portability
    - EFFORT: 1 hour
    - STATUS: Ready (unblocked by Phase 0)

PHASE 2: Runtime Wiring (Enable execution paths)
================================================
[ ] C3.1 - Wire NexusProcessor into MCP servers
    - BLOCKS: 5-step SOP
    - EFFORT: 4 hours

[ ] C2.1-C2.5 - Create hooks/12fa/ directory and protocol files
    - BLOCKS: Metadata tagging
    - EFFORT: 8 hours

PHASE 3: Mock Code Replacement (Core functionality)
===================================================
[ ] B1.1 - Obsidian client real sync
    - BLOCKED BY: Phase 0, Phase 2
    - EFFORT: 8 hours

[ ] B1.6 - Bayesian CPD from real data
    - BLOCKED BY: Phase 0, Phase 2
    - EFFORT: 16 hours

[ ] B2.1 - Implement Max-Min semantic chunking
    - BLOCKED BY: None (can parallelize)
    - EFFORT: 8 hours

PHASE 4: Feature Completion (Full functionality)
================================================
[ ] B2.3-B2.5 - Query replay Week 11 TODOs
    - BLOCKED BY: Phase 2, Phase 3
    - EFFORT: 16 hours

[ ] C1.2-C1.6 - Add missing MCP tools
    - BLOCKED BY: Phase 2
    - EFFORT: 12 hours

[ ] B1.7 - RAPTOR LLM summaries
    - BLOCKED BY: None
    - EFFORT: 8 hours

PHASE 5: Polish & Testing (Production ready)
============================================
[ ] D4.* - Enable E2E tests, add CI
    - BLOCKED BY: Phase 3, Phase 4
    - EFFORT: 16 hours

[ ] A2.* - Update all documentation
    - BLOCKED BY: Phase 0 decision
    - EFFORT: 8 hours

[ ] B3.* - Fix all algorithm bugs
    - BLOCKED BY: Phase 2
    - EFFORT: 4 hours
```

---

## CRITICAL PATH

The longest dependency chain determines minimum time to production:

```
A1.1 (Decision)
    -> C3.1 (Wire Nexus)
    -> B1.1 (Obsidian real)
    -> B2.3-5 (Query replay)
    -> D4.* (Testing)

CRITICAL PATH LENGTH: 5 phases
MINIMUM CALENDAR TIME: 4-6 weeks (with parallelization)
```

---

## PARALLELIZATION OPPORTUNITIES

These issues have NO dependencies and can be fixed concurrently:

| Issue | Can Start | Parallel With |
|-------|-----------|---------------|
| D1.1 (tenacity) | Immediately | Everything |
| D2.* (paths) | Immediately | Everything |
| B2.1 (Max-Min chunking) | Immediately | Everything |
| B1.7 (RAPTOR LLM) | Immediately | Everything |
| B3.* (algorithm bugs) | After Phase 2 | Phase 3 |
| A2.* (docs) | After Phase 0 | Phase 1-5 |

**Maximum Parallelism**: 4 tracks simultaneously after Phase 0 decision.

---

## NEXT: See VERIFICATION-PLAN.md for validation approach
