# Phase 3: Mock Code Replacement - Specification

## Overview

Replace mock/placeholder implementations with real, functional code to achieve genuine system functionality.

## Requirements

### Functional Requirements

1. **B2.1 - Max-Min Semantic Chunking Algorithm**
   - Replace naive paragraph splitting with semantic chunking
   - Implement sentence embedding similarity detection
   - Find semantic boundaries where similarity drops
   - Merge sentences between boundaries into chunks
   - Respect min/max chunk size constraints

2. **B1.1 - Obsidian Client Real Sync** (Deferred - requires Obsidian setup)
   - Replace fake chunk count with real chunking
   - Actually index chunks via VectorIndexer
   - Track sync state per file
   - Handle incremental updates

3. **B1.6 - Bayesian CPD Real Data** (Deferred - requires historical data)
   - Replace random.choice with frequency-based estimation
   - Use historical query data for CPD estimation
   - Fall back to uniform prior when data insufficient

### Non-Functional Requirements

- Performance: Chunking should complete in <1s for typical documents
- Compatibility: Work with existing VectorIndexer interface
- Reliability: Graceful fallback if embedding model unavailable

## Constraints

- Must maintain backward compatibility
- Must follow NASA Rule 10 (functions <=60 LOC)
- Must use existing sentence-transformers model

## Success Criteria

1. Semantic chunker produces semantically coherent chunks
2. Chunk boundaries align with topic changes
3. No mock code in semantic_chunker.py critical path
4. Tests pass with real implementation

## Priority Order

1. **B2.1 - Semantic Chunking** (Foundation - required by other features)
2. B1.1 - Obsidian Sync (Depends on chunking)
3. B1.6 - Bayesian CPD (Can be done independently)

## Out of Scope for This Phase

- B1.3-B1.5: Query replay (Phase 4)
- B1.7: RAPTOR LLM summaries (Phase 4)
- B1.8-B1.9: Error attribution, lifecycle compression (Phase 4)
