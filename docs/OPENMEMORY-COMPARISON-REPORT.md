# OpenMemory vs Memory-MCP-Triple-System Comparison Report

## Executive Summary

This report compares the Memory-MCP-Triple-System with OpenMemory (https://github.com/CaviraOSS/OpenMemory) to identify improvement opportunities and integration strategies.

## Feature Comparison

| Feature | OpenMemory | Memory-MCP | Gap Level |
|---------|------------|------------|-----------|
| **Memory Architecture** |
| Multi-sector memory | 5 sectors (episodic, semantic, procedural, emotional, reflective) | 3 layers (short, mid, long-term) | HIGH |
| Temporal knowledge graphs | Yes (valid_from/valid_to, point-in-time queries) | No | CRITICAL |
| Adaptive forgetting | Built-in decay mechanisms | Hot/Cold classifier | LOW |
| Waypoint graphs | Associative traversal between memories | Graph service (partial) | MEDIUM |
| **Scoring & Ranking** |
| Composite scoring | Salience + Recency + Co-activation | Weighted sum (0.4/0.4/0.2) | MEDIUM |
| Explainable traces | Waypoint traces showing retrieval path | Query traces (partial) | LOW |
| **Infrastructure** |
| Embedding providers | OpenAI, Gemini, Ollama, AWS | sentence-transformers only | HIGH |
| Database backends | SQLite, PostgreSQL with vector indexes | ChromaDB, SQLite | LOW |
| Dashboard UI | Real-time visualization | None | HIGH |
| **Integration** |
| MCP support | HTTP transport at /mcp | Stdio protocol | LOW |
| Data importers | GitHub, Notion, Google Drive, OneDrive, web crawlers | Obsidian only | HIGH |
| Migration tools | Mem0, Zep, Supermemory import | None | MEDIUM |

## Connascence Analysis Results (Current State)

### Critical Issues (9 God Objects)

| Class | File | Cohesion | Context |
|-------|------|----------|---------|
| SemanticChunker | chunking/semantic_chunker.py:19 | 0.57 | business_logic |
| ErrorAttribution | debug/error_attribution.py:36 | 0.26 | config |
| QueryReplay | debug/query_replay.py:20 | 0.22 | config |
| ObsidianMCPClient | mcp/obsidian_client.py:22 | 0.14 | config |
| QueryRouter | routing/query_router.py:33 | 0.35 | api_controller |
| EntityConsolidator | services/entity_service.py:331 | 0.38 | data_model |
| GraphService | services/graph_service.py:17 | 0.28 | config |
| HippoRagService | services/hipporag_service.py:38 | 0.40 | business_logic |
| KVStore | stores/kv_store.py:20 | 0.29 | config |

### High Violations (77 Total)
- Connascence of Position (CoP): 77 functions with >3 positional parameters
- Most common: __init__ methods with too many parameters

### Medium Violations (310 Total)
- Magic literals, missing type annotations, etc.

### Low Violations (2655 Total)
- Style issues, documentation gaps

## Recommended Improvements (Priority Order)

### P0: Critical - Architectural Improvements

1. **Add Temporal Knowledge Graph**
   - Implement valid_from/valid_to timestamps on all memories
   - Add point-in-time query support
   - Track fact evolution and conflicts

2. **Implement Multi-Sector Memory**
   - Extend 3-layer system to 5 cognitive sectors
   - Add sector classification on ingestion
   - Mode-aware sector prioritization

3. **Add Dashboard UI**
   - Real-time memory visualization
   - Query trace exploration
   - Sector distribution analytics

### P1: High - Feature Parity

4. **Multiple Embedding Providers**
   - Add OpenAI, Gemini, Ollama support
   - Configuration-based provider selection
   - Embedding caching with invalidation

5. **Data Importers**
   - GitHub repository ingestion
   - Notion workspace sync
   - Google Drive/Sheets connector

6. **HTTP Transport**
   - Add /mcp endpoint alongside stdio
   - OpenAPI documentation
   - CORS support for web clients

### P2: Medium - Code Quality

7. **Refactor God Objects**
   - Split SemanticChunker into focused components
   - Extract configuration from business logic
   - Apply Single Responsibility Principle

8. **Fix Parameter Bombs**
   - Convert positional args to dataclasses/configs
   - Use builder patterns for complex initialization
   - Add type-safe config objects

### P3: Low - Polish

9. **Migration Tools**
   - Import from other memory systems
   - Export format standardization
   - Backup/restore utilities

## Integration Strategy with Context Cascade Plugin

### Phase 1: Core Integration (Week 1)
- Update MCP configuration in settings.json
- Add memory-mcp to agent MCP requirements
- Configure WHO/WHEN/PROJECT/WHY tagging

### Phase 2: Agent Memory Access (Week 2)
- Update 211 agents with memory access patterns
- Add memory-aware context injection
- Implement session-based memory scoping

### Phase 3: Expertise System Bridge (Week 3)
- Connect expertise files to memory storage
- Auto-sync expertise updates
- Cross-reference with temporal graph

### Phase 4: Quality Loop Integration (Week 4)
- Use connascence analyzer for memory-stored code
- Automated quality gate on stored artifacts
- Feedback loop for pattern learning

## Files Requiring Immediate Fixes

1. `src/services/graph_service.py` - Lowest cohesion (0.14)
2. `src/debug/query_replay.py` - Very low cohesion (0.22)
3. `src/debug/error_attribution.py` - Low cohesion (0.26)
4. `src/services/entity_service.py` - EntityConsolidator too large
5. `src/mcp/obsidian_client.py` - Needs decomposition

## Metrics Targets

| Metric | Current | Target |
|--------|---------|--------|
| God Objects | 9 | 0 |
| High Violations | 77 | < 10 |
| Class Cohesion | 0.14-0.57 | > 0.70 |
| Test Coverage | Unknown | > 80% |
| Memory Sectors | 3 | 5 |
| Embedding Providers | 1 | 4 |

## Next Steps

1. Initialize quality loop with `connascence-quality-gate` skill
2. Fix critical God Objects first (lowest cohesion)
3. Add temporal graph infrastructure
4. Implement multi-embedding provider support
5. Build dashboard UI skeleton
6. Create data importer framework
