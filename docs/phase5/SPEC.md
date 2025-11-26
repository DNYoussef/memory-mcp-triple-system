# Phase 5: Algorithm Fixes & Polish - Specification

## Overview

Fix algorithm bugs, improve accuracy, and polish documentation to prepare for production.

## Requirements

### Algorithm Fixes (B3.*)

1. **B3.1 - Negative Similarity Scores**
   - File: `src/mcp/tools/vector_search.py:140`
   - Bug: `1.0 - distance` assumes distance in [0,1] but L2 can be > 1
   - Fix: Normalize to [0,1] range using `max(0, 1 - distance)` or sigmoid

2. **B3.2 - Jaccard vs Cosine Similarity**
   - File: `src/nexus/processor.py:587-590`
   - Bug: Uses word-based Jaccard as "fast approximation"
   - Fix: Use embedding-based cosine similarity for accuracy

3. **B3.3 - Entity Extraction Uses First Word Only**
   - File: `src/nexus/processor.py:529-530`
   - Bug: `query.split()[0]` extracts only first word
   - Fix: Use proper entity extraction (NER or capitalized phrase detection)

4. **B3.4 - Query Replay Dead Code**
   - File: `src/debug/query_replay.py:201`
   - Bug: Import inside function, mock implementation
   - Fix: Clean up imports, add TODO for real implementation

### Documentation Cleanup (A2.*)

1. **A2.2 - Integration Tests Reference Dockerized Qdrant**
   - Update tests to use ChromaDB (current backend)

2. **A2.3 - Week N References Never Completed**
   - Replace "Week N" comments with permanent documentation

### Test Coverage (D4.*)

1. **D4.1 - E2E Tests Skipped**
   - Remove Docker/Qdrant prereqs, use in-memory ChromaDB

2. **D4.4 - Integration Tests Broken**
   - Fix integration tests to work with current architecture

## Success Criteria

1. All similarity scores in [0, 1] range
2. Cosine similarity replaces Jaccard approximation
3. Entity extraction handles multi-word entities
4. No "Week N" comments remaining
5. E2E tests run without Docker prereqs

## Priority Order

1. B3.1 - Critical (negative scores break ranking)
2. B3.3 - High (broken entity logic)
3. B3.2 - Medium (accuracy improvement)
4. A2.*, D4.* - Low (polish)
