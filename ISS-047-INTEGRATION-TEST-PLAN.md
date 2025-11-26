# ISS-047: Integration Test Implementation Plan

## Overview
Replace mock-heavy tests with real integration tests for ChromaDB, NetworkX, and MCP tools.

## Current State
- 28 unit tests (heavily mocked)
- 11 integration tests (partial coverage)
- 3 performance tests

## Target State
- Real ChromaDB integration tests
- Real NetworkX graph integration tests
- End-to-end MCP tool execution tests
- Shared test fixtures with real services

---

## Execution Streams (Parallel)

### Stream A: ChromaDB Integration Tests
**Files to create:**
- `tests/integration/test_real_chromadb.py`

**Test cases:**
1. `test_vector_indexer_real_chromadb_add_and_search`
2. `test_vector_search_tool_real_chromadb`
3. `test_embedding_pipeline_real_encode`
4. `test_memory_store_real_persistence`
5. `test_chunk_deduplication_real_vectors`

### Stream B: NetworkX Graph Integration Tests
**Files to create:**
- `tests/integration/test_real_networkx.py`

**Test cases:**
1. `test_graph_service_real_networkx_add_nodes`
2. `test_graph_query_engine_real_ppr`
3. `test_hipporag_service_real_graph`
4. `test_multi_hop_traversal_real_graph`
5. `test_entity_linking_real_graph`

### Stream C: End-to-End MCP Tool Tests
**Files to create:**
- `tests/integration/test_mcp_tools_e2e.py`

**Test cases:**
1. `test_vector_search_e2e_real_data`
2. `test_memory_store_e2e_real_persistence`
3. `test_graph_query_e2e_real_graph`
4. `test_hipporag_retrieve_e2e_full_pipeline`
5. `test_detect_mode_e2e_real_patterns`
6. `test_nexus_processor_e2e_all_tiers`

### Stream D: Test Fixtures and Utilities
**Files to create:**
- `tests/fixtures/real_services.py`

**Fixtures:**
1. `real_chromadb_client` - Ephemeral ChromaDB for tests
2. `real_vector_indexer` - Real VectorIndexer with test collection
3. `real_graph_service` - Real NetworkX graph
4. `real_embedding_pipeline` - Real sentence-transformers
5. `sample_documents` - Test documents for indexing
6. `cleanup_after_test` - Cleanup fixture

---

## Execution Order
1. Stream D (fixtures) - FIRST (others depend on it)
2. Streams A, B, C - PARALLEL (use fixtures)
3. Verification - Run all tests

## Success Criteria
- All new tests pass
- No mocks in integration tests
- Real ChromaDB operations verified
- Real NetworkX operations verified
- MCP tools work end-to-end
