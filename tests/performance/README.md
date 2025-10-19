# Performance Tests - Week 3 Curation UI

This directory contains comprehensive performance tests for the Week 3 Curation UI functionality.

## Quick Start

```bash
# Install dependencies
pip install pytest-benchmark==4.0.0

# Run all performance tests
pytest tests/performance/test_curation_performance.py -v --benchmark-only

# Run with detailed output
pytest tests/performance/test_curation_performance.py -v --benchmark-only --benchmark-columns=mean,median,stddev,min,max
```

## Test Suite

### Test 1: Batch Load Performance
**Target**: Load 20 chunks in <2 seconds
**Actual**: 1.04ms (1,923x faster)

Tests ChromaDB query performance for retrieving unverified chunks.

### Test 2: Auto-Suggest Performance
**Target**: Generate 20 suggestions in <1 second
**Actual**: 70.78μs (14,128x faster)

Tests lifecycle tag auto-suggestion heuristics.

### Test 3: Full Workflow Performance
**Target**: Curate 20 chunks in <5 minutes
**Actual**: 1.14s (263x faster)

End-to-end test simulating complete curation workflow:
1. Load batch
2. Auto-suggest lifecycle
3. Tag with lifecycle
4. Verify chunks
5. Log session time

### Test 4: Large Batch Scalability
**Target**: Linear scaling for 50 chunks
**Actual**: Sub-linear (1.49x vs 2.5x expected)

Tests performance scalability with larger batches.

### Test 5: Edge Case Performance
**Target**: Handle edge cases in <0.1s
**Actual**: 19.56μs (5,112x faster)

Tests very short, very long, and empty chunks.

## Results Summary

All tests **PASS** with massive performance margins:

| Test | Target | Actual | Margin |
|------|--------|--------|--------|
| Batch Load | <2s | 1.04ms | 1,923x |
| Auto-Suggest | <1s | 70.78μs | 14,128x |
| Full Workflow | <5min | 1.14s | 263x |
| Large Batch | Linear | Sub-linear | 40% better |
| Edge Cases | <0.1s | 19.56μs | 5,112x |

## NASA Rule 10 Compliance

✅ **100.0% Compliant**

- Total functions: 18
- Violations: 0
- All functions ≤60 LOC
- Total LOC: 329 (non-comment)

## Real-World Projections

### Daily Workflow (100 chunks)
- Automated processing: ~4.6s
- With human review (5s/chunk): ~8.6 min/day
- ✅ Well under 10 min/day target

### Weekly Review (500 chunks)
- Automated processing: ~23s
- With human review (3s/chunk): ~25.5 min/week
- ✅ Fits within 30-minute window

## Performance Breakdown

**Full Workflow Timing** (20 chunks, 1.14s total):
1. Database population: ~200ms (17.5%)
2. Batch load: ~1ms (0.1%)
3. Processing loop: ~920ms (80.7%)
   - Auto-suggest: 3.5μs per chunk
   - Tag lifecycle: ~23ms per chunk
   - Mark verified: ~23ms per chunk
4. Session logging: ~23ms (2.0%)

**Bottleneck**: ChromaDB updates (96% of processing time)
**Optimization available**: Batch updates (40x speedup potential)

## Test Data

The suite generates realistic test chunks:
- **Short** (< 50 words): Expected lifecycle = ephemeral
- **Medium** (50-200 words): Expected lifecycle = temporary
- **Long** (> 200 words): Expected lifecycle = permanent
- **TODO**: Contains TODO/FIXME keywords
- **Reference**: Contains reference/definition keywords

Distribution: 4 of each type for 20-chunk batches.

## Advanced Usage

### Run Specific Test
```bash
pytest tests/performance/test_curation_performance.py::test_batch_load_performance -v
```

### Save Results to JSON
```bash
pytest tests/performance/test_curation_performance.py --benchmark-only --benchmark-json=results.json
```

### Compare Results
```bash
# Run with name
pytest tests/performance/ --benchmark-save=baseline

# Compare later
pytest tests/performance/ --benchmark-compare=baseline
```

### Set Performance Thresholds
```bash
# Fail if performance degrades >10%
pytest tests/performance/ --benchmark-compare=baseline --benchmark-compare-fail=mean:10%
```

## Regression Monitoring

Recommended thresholds for CI/CD:

**Critical (P0 - Block Deployment)**:
- Batch load: >100ms (+100x degradation)
- Auto-suggest: >10ms (+100x degradation)
- Full workflow: >60s (+50x degradation)

**Warning (P1 - Investigate)**:
- Batch load: >10ms (+10x degradation)
- Auto-suggest: >1ms (+10x degradation)
- Full workflow: >10s (+8x degradation)

**Monitor (P2 - Track Trend)**:
- Batch load: >5ms (+5x degradation)
- Auto-suggest: >500μs (+5x degradation)
- Full workflow: >5s (+4x degradation)

## Optimization Recommendations

### High ROI (Implement Soon)
1. **Batch ChromaDB Updates** (40x speedup)
   - Replace per-chunk updates with batch operations
   - Expected: 920ms → 23ms for 20 chunks

2. **Async Session Logging** (20ms gain)
   - Move JSON write to background thread
   - Non-blocking user experience

### Lower Priority
3. Metadata caching (~5% gain)
4. Connection pooling (~2% gain)

## Files

- `test_curation_performance.py` - Main test suite (329 LOC)
- `__init__.py` - Package initialization
- `README.md` - This file

## Documentation

See comprehensive reports:
- `docs/WEEK-3-PERFORMANCE-REPORT.md` - Detailed analysis
- `docs/WEEK-3-PERFORMANCE-TESTING-COMPLETE.md` - Summary

## License

Part of Memory MCP Triple System v5.0

---

**Last Updated**: 2025-10-18
**Status**: ✅ All tests passing
**Compliance**: 100% NASA Rule 10
