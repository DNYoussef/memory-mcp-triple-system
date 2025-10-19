# Week 11 Implementation Plan: Nexus Processor + Error Attribution

**Date**: 2025-10-18
**Phase**: Loop 2 (Implementation)
**Methodology**: Queen (Claude Code) direct implementation
**Estimated Duration**: 26 hours (24 Nexus + 2 Error Attribution)
**Priority**: P0 (Critical Path + Risk #13 Mitigation)

---

## Executive Summary

Week 11 delivers the **Nexus Processor** - the final integration layer that combines all three RAG tiers (Vector + HippoRAG + Bayesian) with **Error Attribution** logic to distinguish context bugs from model bugs.

**Deliverables**:
1. ✅ Nexus Processor (5-step SOP pipeline: Recall → Filter → Deduplicate → Rank → Compress)
2. ✅ Curated Core Pattern (top-5 core + 15-25 extended based on mode)
3. ✅ Error Attribution Logic (classify context bugs vs model bugs)

**Total**: 520 LOC production + 400 LOC tests (20 tests)

---

## Week 11 Requirements (from PLAN v7.0 FINAL)

### 1. Nexus Processor (440 LOC production, 300 LOC tests, 15 tests)

**Purpose**: Unified retrieval pipeline that integrates all three RAG tiers.

**5-Step SOP Pipeline**:
1. **Recall**: Query all tiers (Vector, HippoRAG, Bayesian), top-50 candidates
2. **Filter**: Confidence >0.3 threshold
3. **Deduplicate**: Cosine similarity >0.95
4. **Rank**: Weighted sum (Vector 0.4 + HippoRAG 0.4 + Bayesian 0.2)
5. **Compress**: Curated core pattern (mode-aware)

**Curated Core Pattern** (from Insight #1: Bigger windows make you dumber):
- **Execution mode**: 5 core + 0 extended = 5 total (precision only)
- **Planning mode**: 5 core + 15 extended = 20 total
- **Brainstorming mode**: 5 core + 25 extended = 30 total

**Token Budget**: Hard limit of 10,000 tokens

**Files to Create**:
- `src/nexus/processor.py` (440 LOC)
- `tests/unit/test_nexus_processor.py` (300 LOC, 15 tests)

### 2. Error Attribution (80 LOC production, 100 LOC tests, 5 tests)

**Purpose**: Classify failures to distinguish context bugs (70%) from model bugs (20%) or system errors (10%).

**Error Types**:
- **CONTEXT_BUG** (70% of failures):
  - Wrong store queried (40%)
  - Wrong mode detected (30%)
  - Wrong lifecycle filter (20%)
  - Retrieval ranking error (10%)
- **MODEL_BUG** (20% of failures): Correct context, wrong output
- **SYSTEM_ERROR** (10% of failures): Timeout, exception, crash

**Risk Mitigation**: Addresses PREMORTEM Risk #13 (Context-Assembly Bugs)
- Current: 160 points
- Target: 80 points (-80 points, 50% reduction)

**Files to Create**:
- `src/debug/error_attribution.py` (80 LOC)
- `tests/unit/test_error_attribution.py` (100 LOC, 5 tests)

---

## Implementation Phases

### Phase 1: Nexus Processor Core (12 hours)

**Tasks**:
1. Create `src/nexus/__init__.py` module
2. Implement `NexusProcessor` class with 5-step pipeline
   - `recall()` method: Query all 3 tiers (50 LOC)
   - `filter_by_confidence()` method: Threshold filtering (20 LOC)
   - `deduplicate()` method: Cosine similarity (40 LOC)
   - `rank()` method: Weighted scoring (50 LOC)
   - `compress()` method: Curated core pattern (60 LOC)
3. Implement helper methods:
   - `_query_vector_tier()` (30 LOC)
   - `_query_hipporag_tier()` (30 LOC)
   - `_query_bayesian_tier()` (30 LOC)
   - `_calculate_cosine_similarity()` (20 LOC)
   - `_enforce_token_budget()` (30 LOC)

**Success Criteria**:
- All 5 steps implemented
- Mode-aware compression working
- Token budget enforced
- NASA Rule 10 compliant (all methods ≤60 LOC)

### Phase 2: Nexus Processor Tests (6 hours)

**Tasks**:
1. Create test fixtures:
   - Sample Vector results
   - Sample HippoRAG results
   - Sample Bayesian results
   - Mock tier services

2. Implement 15 unit tests:
   - `test_recall_from_all_tiers()` - Verify all 3 tiers queried
   - `test_filter_low_confidence()` - Confidence <0.3 filtered
   - `test_deduplicate_similar_chunks()` - Cosine >0.95 removed
   - `test_rank_weighted_sum()` - Vector 0.4 + HippoRAG 0.4 + Bayesian 0.2
   - `test_compress_execution_mode()` - 5 core + 0 extended
   - `test_compress_planning_mode()` - 5 core + 15 extended
   - `test_compress_brainstorming_mode()` - 5 core + 25 extended
   - `test_token_budget_enforcement()` - Truncate extended to stay under 10k tokens
   - `test_empty_results()` - Handle no results gracefully
   - `test_single_tier_results()` - One tier returns empty
   - `test_recall_performance()` - Query latency <500ms
   - `test_compression_ratio()` - Calculate compression metrics
   - `test_mode_invalid()` - Default to execution mode
   - `test_duplicate_removal_threshold()` - Cosine =0.95 boundary
   - `test_nasa_rule_10_compliance()` - All methods ≤60 LOC

**Success Criteria**:
- 15/15 tests passing
- Test coverage ≥80%

### Phase 3: Error Attribution (4 hours)

**Tasks**:
1. Create `ErrorType` and `ContextBugType` enums
2. Implement `ErrorAttribution` class:
   - `classify_failure()` method (30 LOC)
   - `classify_context_bug()` method (20 LOC)
   - `_is_wrong_store()` helper (20 LOC)
   - `_is_wrong_mode()` helper (15 LOC)
   - `_is_wrong_lifecycle()` helper (10 LOC)
   - `get_statistics()` method (20 LOC)

3. Implement 5 unit tests:
   - `test_classify_wrong_store()` - "What's my X?" should use KV
   - `test_classify_wrong_mode()` - "P(X)" should be planning mode
   - `test_classify_model_bug()` - Correct context, wrong output
   - `test_classify_system_error()` - Timeout exception
   - `test_get_statistics()` - Aggregate 30-day error stats

**Success Criteria**:
- All 5 tests passing
- Context bug detection working
- Statistics aggregation functional

### Phase 4: Integration & Audits (4 hours)

**Tasks**:
1. Integration testing:
   - Test Nexus Processor with real Week 8-10 results
   - Verify ranking weights correct (0.4 + 0.4 + 0.2 = 1.0)
   - Verify mode-aware compression working

2. Run 3-part audit system:
   - **Audit 1: Functionality** - All 20 tests passing
   - **Audit 2: Style (NASA Rule 10)** - All methods ≤60 LOC
   - **Audit 3: Theater Detection** - No TODO/FIXME/mock data

3. Performance validation:
   - Recall latency <500ms (query all 3 tiers in parallel)
   - Filter + Deduplicate + Rank <100ms
   - Compress <50ms
   - **Total pipeline latency <650ms**

4. Create Week 11 completion summary

**Success Criteria**:
- All audits passing
- Performance targets met
- Documentation complete

---

## Files to Create

### Production Code (520 LOC)

```
src/nexus/
├── __init__.py                    (NEW, 14 LOC)
└── processor.py                   (NEW, 440 LOC)

src/debug/
└── error_attribution.py           (NEW, 80 LOC)
```

### Unit Tests (400 LOC)

```
tests/unit/
├── test_nexus_processor.py        (NEW, 300 LOC, 15 tests)
└── test_error_attribution.py      (NEW, 100 LOC, 5 tests)
```

### Documentation

```
docs/weeks/
├── WEEK-11-IMPLEMENTATION-PLAN.md (this file)
└── WEEK-11-COMPLETE-SUMMARY.md    (to be created)
```

---

## Dependencies

### External Libraries

**Already Installed** (from Weeks 1-10):
- `numpy` (1.24+) - Cosine similarity
- `loguru` - Logging
- `typing` - Type hints

**From Week 8-10** (Integration Dependencies):
- `src/services/graph_query_engine.py` (Week 8 - HippoRAG)
- `src/indexing/vector_indexer.py` (Week 6 - Vector search)
- `src/bayesian/probabilistic_query_engine.py` (Week 10 - Bayesian)
- `src/debug/query_trace.py` (Week 7 - Query logging)

**No New Dependencies Required** ✅

---

## Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Recall latency | <500ms | Query all 3 tiers in parallel |
| Filter + Deduplicate + Rank | <100ms | Lightweight operations |
| Compress | <50ms | Mode-aware slicing |
| **Total pipeline latency** | **<650ms** | End-to-end Nexus processing |
| Memory usage | <500MB | Results held in memory temporarily |
| Token budget enforcement | 100% | Hard limit at 10,000 tokens |

---

## Success Criteria

### Pre-Testing Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Production LOC | 520 | Nexus (440) + Attribution (80) |
| Test LOC | 400 | Nexus tests (300) + Attribution tests (100) |
| NASA Compliance | ≥95% | All methods ≤60 LOC |
| Type Hints | 100% | All public methods annotated |
| Docstrings | 100% | All classes and public methods |
| Theater Score | <60 | No TODO/FIXME/mock data |

### Post-Testing Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Unit Tests | 20 | 15 Nexus + 5 Attribution |
| Tests Passing | 100% | All 20 tests passing |
| Test Coverage | ≥80% | Line coverage metric |
| Recall Latency | <500ms | Parallel tier queries |
| Pipeline Latency | <650ms | End-to-end processing |
| Token Budget | 100% | Always ≤10,000 tokens |

---

## Risk Mitigation

### Risk #13: Context-Assembly Bugs (PREMORTEM)

**Current Score**: 160 points
**Target Score**: 80 points (-80 points, 50% reduction)

**Mitigation Strategy**:
1. **Error Attribution** → Know if context bugs or model bugs
2. **Statistics Aggregation** → Track failure patterns over 30 days
3. **Context Bug Classification** → Identify root causes (wrong store, wrong mode, wrong lifecycle)

**Evidence of Mitigation**:
- Error classification accuracy ≥85% (based on query trace analysis)
- Context bug detection finds 70% of failures (expected distribution)
- Dashboard shows error breakdown (context vs model vs system)

---

## Integration Points

### With Week 8 (HippoRAG + Query Router)

**Status**: Ready for integration

**Integration Point**: Nexus Processor uses GraphQueryEngine (Week 8) for HippoRAG tier

**Example**:
```python
from src.services.graph_query_engine import GraphQueryEngine

# In Nexus Processor recall() method
hipporag_results = self.graph_query_engine.retrieve_multi_hop(
    query=query,
    top_k=50,
    max_hops=3
)
```

### With Week 6 (Vector Indexer)

**Status**: Ready for integration

**Integration Point**: Nexus Processor uses VectorIndexer (Week 6) for Vector tier

**Example**:
```python
from src.indexing.vector_indexer import VectorIndexer
from src.indexing.embedding_pipeline import EmbeddingPipeline

# In Nexus Processor recall() method
query_embedding = self.embedding_pipeline.encode([query])[0]
vector_results = self.vector_indexer.search_similar(
    query_embedding=query_embedding,
    top_k=50
)
```

### With Week 10 (Bayesian Graph RAG)

**Status**: Ready for integration

**Integration Point**: Nexus Processor uses ProbabilisticQueryEngine (Week 10) for Bayesian tier

**Example**:
```python
from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine
from src.bayesian.network_builder import NetworkBuilder

# In Nexus Processor recall() method
bayesian_results = self.probabilistic_query_engine.query_conditional(
    network=self.bayesian_network,
    query_vars=[query_entity],
    evidence=context_evidence
)
```

### With Week 7 (Query Logging)

**Status**: Ready for integration

**Integration Point**: Error Attribution uses QueryTrace (Week 7) to classify failures

**Example**:
```python
from src.debug.query_trace import QueryTrace

# In Error Attribution classify_failure() method
trace = QueryTrace.load(query_id)
error_type = self.classify_failure(trace)
context_bug_type = self.classify_context_bug(trace) if error_type == ErrorType.CONTEXT_BUG else None
```

---

## Next Steps

### Week 12 (After Week 11 Complete)

**Memory Forgetting + 4-Stage Lifecycle**:
1. 4-stage lifecycle (Active → Demoted → Archived → Rehydratable)
2. Compression (100:1 for archived, 1000:1 for rehydratable)
3. Rekindling logic (query matches archived → rehydrate)

**Integration with Week 11**:
- Nexus Processor will filter by lifecycle stage
- Curated core pattern will prioritize Active > Demoted > Archived

---

## Conclusion

Week 11 is the **final integration layer** that unifies all three RAG tiers (Vector + HippoRAG + Bayesian) with comprehensive error attribution.

**Key Achievements**:
- ✅ 5-step SOP pipeline (Recall → Filter → Deduplicate → Rank → Compress)
- ✅ Curated core pattern (mode-aware compression)
- ✅ Error attribution logic (context bugs vs model bugs)
- ✅ Risk #13 mitigation (160 → 80 points, 50% reduction)

**Production Readiness**: ✅ **READY FOR IMPLEMENTATION**

---

**Plan Created**: 2025-10-18
**Agent**: Claude Code (Queen)
**Methodology**: Loop 2 (Implementation)
**Status**: Week 11 plan complete, ready for implementation
**Next Milestone**: Phase 1 implementation (Nexus Processor core)
