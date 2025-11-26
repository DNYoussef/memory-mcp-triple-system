# Architecture Decision Record: Memory MCP Triple System

**ADR-001**: Unified Architecture Selection
**Date**: 2025-11-25
**Status**: APPROVED
**Decision Maker**: User + AI Analysis

---

## Context

The Memory MCP Triple System had THREE competing architecture definitions causing confusion and blocking development:

| Option | Name | Location | Status |
|--------|------|----------|--------|
| A | Vector/Graph/Bayesian | `src/nexus/processor.py`, `src/bayesian/` | Implemented (660+ LOC) |
| B | Time-Based (24h/7d/30d) | `MEMORY-MCP-TRUE-ARCHITECTURE.md` | Documented only |
| C | Procedural/Episodic/Semantic | `MEMORY-MCP-OBSIDIAN-INTEGRATION.md` | Documented only |

This conflict was identified as **Root Cause RC-1** blocking 15+ downstream issues.

---

## Decision

**ADOPT: Unified Architecture (A + B + C features)**

- **Core**: Vector/Graph/Bayesian retrieval tiers (Option A code)
- **Feature Addition**: Time-based decay as metadata (Option B)
- **Feature Addition**: P/E/S categories as chunk metadata (Option C)

---

## Rationale

### Why Keep Option A Core

1. **Code Exists**: 660+ LOC in NexusProcessor, 300+ LOC in NetworkBuilder
2. **Research-Backed**: HippoRAG (multi-hop graph reasoning) is proven
3. **Unique Value**: Bayesian tier adds probabilistic inference
4. **Effort Saved**: Rewriting to B or C discards ~80% of implementation

### Why Add Option B Features

1. **Temporal Decay**: Memory should decay over time (biological model)
2. **Retention Tiers**: Short/Mid/Long term useful for lifecycle management
3. **Implementation**: Add `decay_score` field to chunk metadata, not new architecture

### Why Add Option C Features

1. **Semantic Categories**: P/E/S classification helps retrieval
2. **Obsidian Integration**: Valuable for knowledge workers
3. **Implementation**: Add `category` field to chunk metadata, not new layers

---

## Architecture Overview

```
+------------------------------------------------------------------+
|               MEMORY MCP UNIFIED ARCHITECTURE v1.0                |
+------------------------------------------------------------------+
|                                                                  |
|  LAYER 1: RETRIEVAL TIERS (Core from Option A)                   |
|  +----------------+------------------+------------------+        |
|  | VECTOR TIER    | HIPPORAG TIER    | BAYESIAN TIER    |        |
|  | (ChromaDB)     | (NetworkX Graph) | (pgmpy Network)  |        |
|  | Weight: 0.4    | Weight: 0.4      | Weight: 0.2      |        |
|  | Dense vectors  | Multi-hop PPR    | Probabilistic    |        |
|  +----------------+------------------+------------------+        |
|                           |                                      |
|  LAYER 2: NEXUS PROCESSOR (5-Step SOP)                           |
|  +----------------------------------------------------------+    |
|  | 1. RECALL    - Query all 3 tiers (top-50 candidates)     |    |
|  | 2. FILTER    - Confidence threshold (>0.3)                |    |
|  | 3. DEDUPE    - Cosine similarity (>0.95)                  |    |
|  | 4. RANK      - Weighted scoring (V:0.4 + H:0.4 + B:0.2)   |    |
|  | 5. COMPRESS  - Curated core (mode-aware)                  |    |
|  +----------------------------------------------------------+    |
|                           |                                      |
|  LAYER 3: METADATA FEATURES                                      |
|  +----------------------------------------------------------+    |
|  | TIME DECAY (from Option B):                               |    |
|  |   - created_at: ISO timestamp                             |    |
|  |   - decay_score: e^(-days/30)                             |    |
|  |   - retention_tier: short|mid|long                        |    |
|  |                                                           |    |
|  | CATEGORY (from Option C):                                 |    |
|  |   - category: procedural|episodic|semantic                |    |
|  |   - Auto-detected from content type                       |    |
|  |                                                           |    |
|  | TAGGING PROTOCOL (WHO/WHEN/PROJECT/WHY):                  |    |
|  |   - agent: Who stored this                                |    |
|  |   - timestamp: When stored                                |    |
|  |   - project: Which project                                |    |
|  |   - intent: Why stored                                    |    |
|  +----------------------------------------------------------+    |
|                           |                                      |
|  LAYER 4: QUERY MODES                                            |
|  +------------------+------------------+------------------+       |
|  | EXECUTION        | PLANNING         | BRAINSTORMING    |       |
|  | 5 results        | 20 results       | 30 results       |       |
|  | Threshold: 0.85  | Threshold: 0.65  | Threshold: 0.50  |       |
|  | Precise answers  | Decision support | Creative explore |       |
|  +------------------+------------------+------------------+       |
|                                                                  |
+------------------------------------------------------------------+
```

---

## Migration Plan

### Phase 0 (This Decision) - COMPLETE
- [x] Analyze all 3 architectures
- [x] Make architecture decision
- [x] Create this ADR document

### Phase 1 (Foundation Fixes)
- [ ] Fix banner in `src/__init__.py` (Qdrant/Neo4j -> Chroma/NetworkX)
- [ ] Add tenacity dependency
- [ ] Fix collection name mismatch

### Phase 2 (Wire NexusProcessor)
- [ ] Update `src/mcp/server.py` to use NexusProcessor
- [ ] Enable all 3 tiers through MCP tools
- [ ] Add decay and category metadata fields

### Phase 3-6 (Implementation)
- See REMEDIATION-PLAN.md for detailed phases

---

## Consequences

### Positive
- Preserves 80% of existing code
- Unified mental model for team
- Clear path forward for all 40 issues
- No blocking architecture conflicts

### Negative
- Bayesian tier needs significant work (currently mock)
- Documentation cleanup required
- Some Option B/C concepts become "features" not "core"

### Neutral
- Obsidian integration remains valuable (from Option C)
- Time decay becomes metadata feature (from Option B)

---

## Documents to Update

### Archive (Move to `docs/archive/`)
1. `MEMORY-MCP-TRUE-ARCHITECTURE.md` - Superseded by this ADR
2. `MEMORY-MCP-OBSIDIAN-INTEGRATION.md` - Merge relevant parts into ARCHITECTURE.md

### Update
1. `src/__init__.py` - Fix banner (Chroma/NetworkX, not Qdrant/Neo4j)
2. `README.md` - Reference this ADR and ARCHITECTURE.md
3. `config/memory-mcp.yaml` - Add decay and category config sections

### Create
1. `docs/ARCHITECTURE.md` - Canonical architecture reference

---

## Signatures

- **Analysis**: Claude Opus 4.5
- **Decision**: User (2025-11-25)
- **Implementation**: Pending Phase 1-6

---

**Status**: PHASE 0 COMPLETE - Architecture conflict resolved
