# Data Flow Verification Report

**Generated**: 2026-01-18
**Task**: MEM-CLEAN-006
**Status**: VERIFIED

---

## Flow 1: memory_store()

### Entry Point
`src/mcp/request_router.py:handle_memory_store()` (lines 167-252)

### Data Flow Trace

```
Input: {text, metadata}
    |
    v
[1] _normalize_metadata_tags() - Uppercase to lowercase normalization
    |
    v
[2] _validate_metadata() - Check WHO/WHEN/PROJECT/WHY tags
    |
    +-- Missing tags? -> _autofill_metadata() or reject (strict mode)
    |
    v
[3] _enrich_metadata_with_tagging() - Full WHO/WHEN/PROJECT/WHY enrichment
    |
    v
[4] _assign_confidence() - Source-based confidence (0.30-0.95)
    |
    v
[5] hot_cold_classifier.classify() - Lifecycle tier assignment (hot/warm/cold)
    |
    v
[6] embedder.encode([text]) - Generate embedding vector
    |
    v
[7] indexer.index_chunks(chunks, embeddings) - ChromaDB insert
    |
    v
[8] _store_entities_to_graph() - Entity extraction + graph population
    |   |
    |   +-- entity_service.extract_entities()
    |   +-- graph_service.add_chunk_node()
    |   +-- graph_service.add_entity_node()
    |   +-- graph_service.add_relationship()
    |   +-- graph_service.link_similar_entities()
    |   +-- graph_service.save_graph()
    |
    v
[9] lifecycle_manager.demote_stale_chunks() + archive_demoted_chunks()
    |
    v
[10] log_event("memory_store", {...})
    |
    v
Output: {content: [...], isError: false}
```

### Verification Status

| Step | Component | Status | Notes |
|------|-----------|--------|-------|
| 1 | Metadata Normalization | OK | Case-insensitive tag handling |
| 2 | Metadata Validation | OK | Required tags enforced |
| 3 | Tag Enrichment | OK | WHO/WHEN/PROJECT/WHY protocol |
| 4 | Confidence Assignment | OK | Source-type mapping |
| 5 | Hot/Cold Classification | OK | Graceful fallback to 'hot' |
| 6 | Embedding Generation | OK | Validates non-empty result |
| 7 | ChromaDB Insert | OK | Error handling present |
| 8 | Graph Population | OPTIONAL | Only if entity_service available |
| 9 | Lifecycle Management | OK | Silent failure (non-critical) |
| 10 | Event Logging | OK | Async-safe |

### Identified Issues

1. **ISS-040**: Graph population silently fails if entity_service is None
   - **Severity**: Low (feature degrades gracefully)
   - **Location**: `request_router.py:262`

---

## Flow 2: unified_search() (Nexus 5-Step SOP)

### Entry Point
`src/mcp/request_router.py:handle_unified_search()` (lines 477-506)
`src/nexus/processor.py:process()` (lines 75-116)

### Data Flow Trace

```
Input: {query, limit, mode}
    |
    v
[1] RECALL - process() -> _execute_pipeline() -> recall()
    |
    +-- _query_vector_tier()     -> ChromaDB similarity search
    |                               -> Tier: "vector"
    |
    +-- _query_hipporag_tier()   -> Graph multi-hop traversal
    |                               -> Tier: "hipporag"
    |
    +-- _query_bayesian_tier()   -> Probabilistic inference
                                    -> Tier: "bayesian" (optional)
    |
    v
[2] COMBINE - _combine_tier_scores()
    |
    +-- Group by candidate_key (id or file_path::chunk_index)
    +-- Merge vector_score, graph_score, bayesian_score
    +-- Calculate weighted hybrid_score:
        hybrid = 0.4*vector + 0.4*graph + 0.2*bayesian
    |
    v
[3] FILTER - filter_by_confidence()
    |
    +-- Remove candidates with score < 0.3
    |
    v
[4] DEDUPE - deduplicate()
    |
    +-- Exact text match check
    +-- Cosine similarity check (threshold: 0.95)
    +-- Keep first occurrence
    |
    v
[5] RANK - rank()
    |
    +-- Recalculate hybrid_score with weight breakdown
    +-- Sort descending by hybrid_score
    |
    v
[6] COMPRESS - compress()
    |
    +-- Mode config: execution(5K), planning(10K), brainstorm(20K)
    +-- Split: core (top-5) + extended (15-25)
    +-- Enforce token budget
    |
    v
Output: {core: [...], extended: [...], pipeline_stats: {...}}
```

### Verification Status

| Step | Component | Status | Notes |
|------|-----------|--------|-------|
| 1.1 | Vector Recall | OK | ChromaDB query working |
| 1.2 | HippoRAG Recall | CONDITIONAL | Requires graph_query_engine |
| 1.3 | Bayesian Recall | OPTIONAL | May timeout/return None |
| 2 | Score Combination | OK | Weighted merge correct |
| 3 | Confidence Filter | OK | 0.3 threshold enforced |
| 4 | Deduplication | OK | Cosine 0.95 threshold |
| 5 | Ranking | OK | Hybrid score calculation |
| 6 | Compression | OK | Mode-aware token budgets |

### Identified Issues

1. **ISS-041**: HippoRAG tier returns empty if graph_query_engine is None
   - **Severity**: Medium (reduces retrieval quality)
   - **Location**: `nexus/tier_queries.py:_query_hipporag_tier()`

2. **ISS-042**: Bayesian tier may silently timeout
   - **Severity**: Low (graceful degradation)
   - **Location**: `nexus/tier_queries.py:_query_bayesian_tier()`

---

## Flow 3: graph_query() (HippoRAG Multi-Hop)

### Entry Point
`src/mcp/request_router.py:handle_graph_query()` (lines 301-331)

### Data Flow Trace

```
Input: {query, max_hops, limit}
    |
    v
[1] Check nexus_processor.graph_query_engine availability
    |
    +-- Available: graph_query_engine.query(query, top_k, max_hops)
    |       |
    |       +-- Entity extraction from query
    |       +-- Graph traversal (BFS/DFS up to max_hops)
    |       +-- Path scoring and ranking
    |       +-- Result assembly
    |
    +-- Not Available: Fallback to vector search (planning mode)
            |
            +-- tool.execute(query, limit, "planning")
            +-- Add note: "Graph engine not available"
    |
    v
Output: {content: [...], isError: false}
```

### Verification Status

| Step | Component | Status | Notes |
|------|-----------|--------|-------|
| 1 | Engine Check | OK | Safe fallback present |
| 2.1 | Entity Extraction | CONDITIONAL | Requires entity_service |
| 2.2 | Graph Traversal | CONDITIONAL | Requires populated graph |
| 2.3 | Path Ranking | OK | When graph available |
| 3 | Fallback | OK | Vector search substitute |

### Identified Issues

1. **ISS-043**: Graph query degrades to vector search silently
   - **Severity**: Low (user gets results, but not graph-based)
   - **Location**: `request_router.py:316-318`

---

## Summary: Core Path Verification

### Working Paths (Green)

| Path | Test Method | Result |
|------|------------|--------|
| memory_store -> ChromaDB | Index and retrieve | OK |
| memory_store -> Event Log | Check events.db | OK |
| unified_search -> Vector | Basic query | OK |
| unified_search -> 5-step | Full pipeline | OK |

### Conditional Paths (Yellow)

| Path | Condition | Fallback |
|------|-----------|----------|
| memory_store -> Graph | entity_service init | Skip graph |
| unified_search -> HippoRAG | graph_query_engine init | Empty results |
| unified_search -> Bayesian | network build success | Empty results |
| graph_query | graph_query_engine init | Vector fallback |

### Broken Paths (Red)

None identified. All paths have graceful degradation.

---

## Recommendations for MEM-CLEAN-007

1. **Integration Test**: memory_store -> unified_search round-trip
2. **Integration Test**: Graph population + graph_query retrieval
3. **Integration Test**: Mode detection accuracy
4. **Load Test**: Nexus 5-step with 1000+ chunks

---

## Architecture Diagram

```
                              +------------------+
                              |   MCP Protocol   |
                              |  (stdio_server)  |
                              +--------+---------+
                                       |
                              +--------v---------+
                              |  Request Router  |
                              +--------+---------+
                                       |
          +----------------------------+----------------------------+
          |                            |                            |
+---------v---------+      +-----------v-----------+    +-----------v-----------+
|   memory_store    |      |    unified_search     |    |     graph_query       |
+---------+---------+      +-----------+-----------+    +-----------+-----------+
          |                            |                            |
          |                +-----------v-----------+                |
          |                |   NexusProcessor      |                |
          |                |   (5-Step SOP)        |                |
          |                +-----------+-----------+                |
          |                            |                            |
+---------v---------+      +-----------v-----------+    +-----------v-----------+
|  VectorSearchTool |      |   Tier Queries       |    | GraphQueryEngine      |
|    (Embeddings)   |      | Vector/HippoRAG/     |    | (Multi-hop traversal) |
+---------+---------+      | Bayesian             |    +-----------+-----------+
          |                +-----------+-----------+                |
          |                            |                            |
+---------v---------+      +-----------v-----------+    +-----------v-----------+
|     ChromaDB      |      |   Processing Utils   |    |    GraphService       |
|  (Vector Index)   |      | Filter/Dedupe/Rank/  |    |    (NetworkX)         |
+-------------------+      | Compress             |    +-------------------+---+
                           +----------------------+
```

---

## Files Analyzed

- `src/mcp/request_router.py` (680 LOC)
- `src/mcp/service_wiring.py` (316 LOC)
- `src/nexus/processor.py` (484 LOC)
- `src/nexus/tier_queries.py` (referenced)
- `src/nexus/processing_utils.py` (referenced)

---

**Verified By**: MEM-CLEAN-006 automated audit
**Next Steps**: MEM-CLEAN-007 (Integration Tests)
