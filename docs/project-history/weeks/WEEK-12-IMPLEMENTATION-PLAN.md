# Week 12 Implementation Plan: Memory Forgetting + 4-Stage Lifecycle

**Version**: 1.0
**Date**: 2025-10-18
**Status**: Ready to Implement
**Methodology**: Loop 2 (Queen implements directly)

---

## Overview

Week 12 implements the **4-stage memory lifecycle** with **rekindling** capability. This addresses the memory forgetting problem by providing gradual degradation from Active → Demoted → Archived → Rehydratable, with the ability to restore archived chunks when they become relevant again.

**Source**: PLAN v7.0 lines 930-1057, SPEC v7.0 COMPLETE lines 2124-2134

---

## Deliverables

### Production Code (360 LOC)

**src/memory/__init__.py** (12 LOC):
- Module initialization
- Export MemoryLifecycleManager

**src/memory/lifecycle_manager.py** (348 LOC):
- `MemoryLifecycleManager` class (NASA Rule 10 compliant)
- 4-stage lifecycle implementation:
  - Active (100% score, <7 days)
  - Demoted (50% score, 7-30 days, decay applied)
  - Archived (10% score, 30-90 days, compressed 100:1)
  - Rehydratable (1% score, >90 days, lossy key only)
- Methods:
  - `demote_stale_chunks()` - Active → Demoted (7 days)
  - `archive_demoted_chunks()` - Demoted → Archived (30 days, compress)
  - `make_rehydratable()` - Archived → Rehydratable (90 days, lossy key)
  - `rekindle_archived()` - Archived/Rehydratable → Active (query match)
  - `consolidate_similar()` - Merge similar chunks (cosine >0.95)
  - `_summarize()` - LLM-based summarization (100:1 compression)
  - `_calculate_similarity()` - Cosine similarity helper
  - `_merge_chunks()` - Merge logic for consolidation
  - `get_stage_stats()` - Statistics for dashboard

### Test Code (320 LOC)

**tests/unit/test_lifecycle_manager.py** (320 LOC, 20 tests):
1. **Initialization Tests** (2 tests):
   - `test_initialization` - Verify stage configuration
   - `test_stage_multipliers` - Verify score multipliers

2. **Demotion Tests** (4 tests):
   - `test_demote_stale_chunks` - Active → Demoted after 7 days
   - `test_demote_threshold_configurable` - Custom thresholds
   - `test_demote_preserves_recent` - Recent chunks unchanged
   - `test_demote_batch_performance` - <100ms for 1000 chunks

3. **Archival Tests** (5 tests):
   - `test_archive_demoted_chunks` - Demoted → Archived after 30 days
   - `test_archive_compression` - 100:1 compression ratio
   - `test_archive_lossy_key_storage` - Summary stored in KV
   - `test_archive_deletes_from_vector` - Vector store cleanup
   - `test_archive_threshold_configurable` - Custom thresholds

4. **Rehydration Tests** (5 tests):
   - `test_make_rehydratable` - Archived → Rehydratable (90 days)
   - `test_rekindle_archived` - Query match → Active
   - `test_rekindle_rehydratable` - Rekindle from lossy key
   - `test_rekindle_file_not_found` - Handle missing files
   - `test_rekindle_promotes_to_active` - Stage set to active

5. **Consolidation Tests** (3 tests):
   - `test_consolidate_similar_chunks` - Merge cosine >0.95
   - `test_consolidate_preserves_metadata` - Metadata merged
   - `test_consolidate_performance` - <200ms for 100 chunks

6. **Statistics Tests** (1 test):
   - `test_get_stage_stats` - Dashboard stats aggregation

---

## Architecture

### 4-Stage Lifecycle Flow

```
Active (100%) ──7 days──> Demoted (50%) ──30 days──> Archived (10%) ──90 days──> Rehydratable (1%)
    ^                                            |                           |
    |                                            |                           |
    +────────────────rekindle()─────────────────+───────────────────────────+
```

### Storage Strategy

**Active Stage**:
- Stored in: Vector store (full embeddings)
- Metadata: `{stage: 'active', score_multiplier: 1.0, last_accessed: timestamp}`

**Demoted Stage**:
- Stored in: Vector store (full embeddings)
- Metadata: `{stage: 'demoted', score_multiplier: 0.5, last_accessed: timestamp}`

**Archived Stage**:
- Stored in: KV store (lossy key = summary only)
- Metadata: `{stage: 'archived', score_multiplier: 0.1, file_path: original_path}`
- Compression: Full text → 1-sentence summary (100:1 ratio)

**Rehydratable Stage**:
- Stored in: KV store (lossy key only)
- Metadata: `{stage: 'rehydratable', score_multiplier: 0.01, file_path: original_path}`
- Compression: Summary only, full text discarded

### Rekindling Logic

When a query matches an archived/rehydratable chunk:
1. Retrieve lossy key (summary) from KV store
2. Check if original file exists
3. Re-read full text from Obsidian
4. Re-index in vector store with new embedding
5. Promote to Active stage (score_multiplier = 1.0)
6. Update last_accessed timestamp

### Consolidation Logic

Periodically merge similar chunks (cosine similarity >0.95):
1. Query all Active chunks
2. Calculate pairwise cosine similarity
3. Merge chunks with similarity >0.95:
   - Combine text: `chunk1 + "\n\n" + chunk2`
   - Merge metadata: Union of tags, max scores
   - Keep newer timestamp
4. Delete duplicate from vector store
5. Log consolidation action

---

## Implementation Phases

### Phase 1: Core Lifecycle (12 hours)

**Files**:
- `src/memory/__init__.py` (12 LOC)
- `src/memory/lifecycle_manager.py` (200 LOC core)

**Methods**:
1. `__init__()` - Initialize with dependencies
2. `demote_stale_chunks()` - Active → Demoted
3. `archive_demoted_chunks()` - Demoted → Archived
4. `make_rehydratable()` - Archived → Rehydratable
5. `get_stage_stats()` - Statistics

**Success Criteria**:
- All methods ≤60 LOC (NASA Rule 10)
- 100% type hints
- Full docstrings

### Phase 2: Rekindling (4 hours)

**Files**:
- `src/memory/lifecycle_manager.py` (80 LOC added)

**Methods**:
1. `rekindle_archived()` - Restore archived chunk
2. `_summarize()` - LLM summarization helper

**Success Criteria**:
- Rehydration from both archived and rehydratable stages
- File not found handled gracefully
- Promotion to active verified

### Phase 3: Consolidation (4 hours)

**Files**:
- `src/memory/lifecycle_manager.py` (68 LOC added)

**Methods**:
1. `consolidate_similar()` - Merge similar chunks
2. `_calculate_similarity()` - Cosine similarity
3. `_merge_chunks()` - Merge logic

**Success Criteria**:
- Cosine >0.95 threshold
- Metadata preservation
- Performance <200ms for 100 chunks

### Phase 4: Testing (4 hours)

**Files**:
- `tests/unit/test_lifecycle_manager.py` (320 LOC)

**Tests**: 20 comprehensive tests covering all methods

**Success Criteria**:
- 100% test pass rate
- ≥80% code coverage
- All edge cases covered

---

## Integration Points

### Dependencies

**Vector Indexer** (`src/indexing/vector_indexer.py`):
- `collection.get()` - Query chunks by stage/timestamp
- `collection.update()` - Update stage metadata
- `collection.delete()` - Remove archived chunks
- `index_chunks()` - Re-index rekindled chunks

**KV Store** (`src/storage/kv_store.py`):
- `set()` - Store lossy keys (summaries)
- `get()` - Retrieve summaries for rekindling

**Embedding Pipeline** (`src/indexing/embedding_pipeline.py`):
- `encode()` - Generate embeddings for rekindled chunks
- `calculate_similarity()` - Cosine similarity for consolidation

### Usage Example

```python
from src.memory.lifecycle_manager import MemoryLifecycleManager
from src.indexing.vector_indexer import VectorIndexer
from src.storage.kv_store import KeyValueStore

# Initialize
indexer = VectorIndexer(collection_name="memory")
kv_store = KeyValueStore(db_path="memory.db")
lifecycle = MemoryLifecycleManager(indexer, kv_store)

# Run lifecycle management (e.g., daily cron job)
lifecycle.demote_stale_chunks(threshold_days=7)     # Active → Demoted
lifecycle.archive_demoted_chunks(threshold_days=30) # Demoted → Archived
lifecycle.make_rehydratable(threshold_days=90)      # Archived → Rehydratable

# Consolidate similar chunks weekly
lifecycle.consolidate_similar(threshold=0.95)

# Rekindle on query match
query_embedding = embedding_pipeline.encode(["relevant query"])[0]
lifecycle.rekindle_archived(query_embedding, chunk_id="archived_123")

# Get statistics
stats = lifecycle.get_stage_stats()
# {
#   'active': 1250,
#   'demoted': 340,
#   'archived': 180,
#   'rehydratable': 95,
#   'total': 1865
# }
```

---

## Performance Targets

| Operation | Target | Rationale |
|-----------|--------|-----------|
| Demote batch (1000 chunks) | <100ms | Metadata update only |
| Archive batch (100 chunks) | <5s | LLM summarization bottleneck |
| Make rehydratable (100 chunks) | <50ms | KV store write only |
| Rekindle single chunk | <1s | File read + re-index |
| Consolidate (100 chunks) | <200ms | Pairwise similarity + merge |
| Get stats | <50ms | Metadata aggregation |

---

## Quality Assurance

### 3-Part Audit (Correct Order)

1. **Theater Detection** (target: 100/100):
   - 0 TODO comments
   - 0 mock data
   - 0 placeholder implementations
   - 0 fake summarization

2. **Functionality** (target: 100/100):
   - 20/20 tests passing
   - All lifecycle transitions work
   - Rekindling functional
   - Consolidation accurate

3. **Style (NASA Rule 10)** (target: 100/100):
   - All methods ≤60 LOC
   - 100% type hints
   - Full docstrings
   - Target: ≥95% compliance

### Risk Mitigation

**Risk**: Summarization quality degradation (100:1 compression)
- **Mitigation**: Use structured prompt: "Summarize in 1 sentence, preserving key entities and concepts"
- **Validation**: Manual review of 20 random summaries

**Risk**: Rehydration file not found (Obsidian file moved/deleted)
- **Mitigation**: Graceful fallback, log warning, keep lossy key
- **Validation**: Test `test_rekindle_file_not_found()`

**Risk**: Consolidation false positives (merge unrelated chunks with high similarity)
- **Mitigation**: Threshold 0.95 (very high), metadata validation
- **Validation**: Manual review of 10 merged pairs

---

## Timeline

**Total**: 24 hours (3 working days)

- **Day 1** (8 hours): Phase 1 (Core Lifecycle) + Phase 2 (Rekindling)
- **Day 2** (8 hours): Phase 3 (Consolidation) + Phase 4 (Testing start)
- **Day 3** (8 hours): Phase 4 (Testing complete) + Audits + Documentation

**Checkpoint**: After Day 1, verify:
- ✅ 4 lifecycle methods implemented
- ✅ Rekindling functional
- ✅ All methods ≤60 LOC

**Checkpoint**: After Day 2, verify:
- ✅ Consolidation working
- ✅ 15/20 tests passing

**Checkpoint**: After Day 3, verify:
- ✅ 20/20 tests passing
- ✅ 3-part audit passed (100/100 each)
- ✅ Documentation complete

---

## Success Criteria

**Production Code**:
- ✅ 360 LOC implemented (lifecycle_manager.py)
- ✅ All methods ≤60 LOC (NASA Rule 10)
- ✅ 100% type hints
- ✅ Full docstrings

**Test Code**:
- ✅ 320 LOC tests
- ✅ 20 tests passing (100%)
- ✅ ≥80% code coverage

**Quality**:
- ✅ Theater: 100/100 (0 violations)
- ✅ Functionality: 100/100 (20/20 tests)
- ✅ Style: 100/100 (≥95% NASA compliance)

**Integration**:
- ✅ Vector indexer integration verified
- ✅ KV store integration verified
- ✅ Embedding pipeline integration verified
- ✅ Ready for Week 13 (Mode-Aware Context)

---

**Plan Created**: 2025-10-18
**Agent**: Claude Code (Queen)
**Loop**: Loop 2 (Direct Implementation)
**Status**: Ready to Execute
