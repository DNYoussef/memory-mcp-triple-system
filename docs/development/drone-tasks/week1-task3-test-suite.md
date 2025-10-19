# Week 1, Task 3: Test Suite Setup (TDD)

**Assigned To**: tester Drone
**Priority**: P0 (Must write tests BEFORE code implementation)
**Estimated Time**: 5 hours
**Loop**: Loop 2 (Implementation)
**Methodology**: Test-Driven Development (TDD - London School)

## Objective

Write comprehensive test suites for Week 1 components BEFORE they are implemented. This ensures all code is testable and meets requirements from day 1.

## Requirements (From SPEC v4.0)

**FR-86**: Test coverage ≥90% (unit + integration)
**FR-87**: Performance benchmarks (documented baselines)

## Deliverables

### 1. Test Infrastructure

**File**: `tests/conftest.py`
- Pytest fixtures for:
  - Mock Obsidian vault (temp directory with .md files)
  - Mock Qdrant client (in-memory)
  - Mock file watcher events
  - Sample embeddings (384-dim vectors)
  - Test config (from config/memory-mcp.yaml)

**File**: `tests/builders.py`
- Test data builders:
  - `MarkdownFileBuilder`: Generate test .md files
  - `ChunkBuilder`: Generate test chunks
  - `EmbeddingBuilder`: Generate test embeddings
  - `QdrantPointBuilder`: Generate test Qdrant points

### 2. Unit Tests (20+ tests)

**File**: `tests/unit/test_file_watcher.py` (6 tests)
```python
def test_file_watcher_detects_new_file()
def test_file_watcher_detects_modified_file()
def test_file_watcher_detects_deleted_file()
def test_file_watcher_debounces_rapid_changes()
def test_file_watcher_parses_yaml_frontmatter()
def test_file_watcher_ignores_non_markdown_files()
```

**File**: `tests/unit/test_chunker.py` (5 tests)
```python
def test_chunker_respects_max_chunk_size()
def test_chunker_respects_min_chunk_size()
def test_chunker_applies_overlap()
def test_chunker_preserves_markdown_structure()
def test_chunker_handles_empty_content()
```

**File**: `tests/unit/test_encoder.py` (4 tests)
```python
def test_encoder_generates_384_dim_embeddings()
def test_encoder_batches_encoding()
def test_encoder_uses_gpu_if_available()
def test_encoder_caches_model()
```

**File**: `tests/unit/test_qdrant_client.py` (6 tests)
```python
def test_qdrant_client_creates_collection()
def test_qdrant_client_upserts_embeddings()
def test_qdrant_client_deletes_embeddings()
def test_qdrant_client_health_check()
def test_qdrant_client_handles_connection_error()
def test_qdrant_client_handles_duplicate_points()
```

**File**: `tests/unit/test_indexing_pipeline.py` (4 tests)
```python
def test_pipeline_processes_file_end_to_end()
def test_pipeline_retries_on_failure()
def test_pipeline_logs_errors()
def test_pipeline_handles_async_processing()
```

### 3. Integration Tests (3 tests)

**File**: `tests/integration/test_full_indexing.py` (3 tests)
```python
@pytest.mark.integration
def test_full_pipeline_obsidian_to_qdrant():
    """Create .md file → verify in Qdrant (<2s)"""

@pytest.mark.integration
def test_pipeline_handles_100_files():
    """Performance: Index 100 files within 1 minute"""

@pytest.mark.integration
def test_pipeline_deletion_removes_from_qdrant():
    """Delete .md file → verify removed from Qdrant"""
```

### 4. Performance Benchmarks

**File**: `tests/benchmarks/test_performance.py` (3 benchmarks)
```python
@pytest.mark.benchmark
def benchmark_chunking_speed():
    """Target: ≥1000 chunks/second"""

@pytest.mark.benchmark
def benchmark_encoding_speed():
    """Target: ≥100 docs/second (batch_size=32)"""

@pytest.mark.benchmark
def benchmark_end_to_end_latency():
    """Target: <2s from file save to indexed"""
```

### 5. Test Configuration

**File**: `pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests (fast, no external dependencies)
    integration: Integration tests (require Docker)
    benchmark: Performance benchmarks
addopts = -v --cov=src --cov-report=html --cov-report=term
```

**File**: `.coveragerc`
```ini
[run]
source = src
omit = */tests/*, */__pycache__/*

[report]
precision = 2
show_missing = True
skip_covered = False

[html]
directory = htmlcov
```

## Acceptance Criteria

- [ ] ≥25 unit tests written (before code implementation)
- [ ] ≥3 integration tests written
- [ ] ≥3 performance benchmarks written
- [ ] All tests have clear docstrings explaining what they test
- [ ] Fixtures and builders enable easy test data creation
- [ ] Tests cover happy path + error cases + edge cases
- [ ] pytest.ini configured for coverage ≥90%
- [ ] Tests pass with mocks (code not implemented yet)

## Technical Constraints

**TDD Principle**: Write tests FIRST, then implement code to pass tests
**Coverage**: ≥90% for Week 1 code
**Speed**: Unit tests run in <5 seconds total
**Isolation**: Unit tests don't require Docker/external services

## Testing Strategy

1. **Red**: Write failing tests (no implementation yet)
2. **Green**: Implement minimal code to pass tests
3. **Refactor**: Clean up code while keeping tests green

## Files to Create

1. `tests/conftest.py` (~150 LOC)
2. `tests/builders.py` (~120 LOC)
3. `tests/unit/test_file_watcher.py` (~180 LOC)
4. `tests/unit/test_chunker.py` (~150 LOC)
5. `tests/unit/test_encoder.py` (~120 LOC)
6. `tests/unit/test_qdrant_client.py` (~180 LOC)
7. `tests/unit/test_indexing_pipeline.py` (~150 LOC)
8. `tests/integration/test_full_indexing.py` (~200 LOC)
9. `tests/benchmarks/test_performance.py` (~150 LOC)
10. `pytest.ini` (~20 LOC)
11. `.coveragerc` (~20 LOC)

**Total**: ~1,440 LOC (tests)

## Dependencies (Add to requirements.txt)

```
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.1
pytest-asyncio>=0.21.0
pytest-benchmark>=4.0.0
```

## Example Test (TDD Style)

```python
# tests/unit/test_chunker.py

def test_chunker_respects_max_chunk_size():
    """
    Given: A document with 1000 tokens
    When: Chunking with max_chunk_size=512
    Then: All chunks have ≤512 tokens
    """
    from src.embeddings.chunker import MaxMinChunker

    # Arrange
    chunker = MaxMinChunker(max_chunk_size=512, min_chunk_size=128)
    long_text = "word " * 1000  # 1000 tokens

    # Act
    chunks = chunker.chunk(long_text)

    # Assert
    assert len(chunks) > 0
    for chunk in chunks:
        assert len(chunk.tokens) <= 512
        assert len(chunk.tokens) >= 128  # Also check min
```

## References

- SPEC v4.0: FR-86, FR-87
- TDD London School methodology
- pytest documentation
- SPEK Platform test examples (139 tests, 85% coverage)

## Notes

- Write tests as if code already exists (TDD mindset)
- Use pytest fixtures liberally (DRY principle)
- Mock external dependencies (Qdrant, file system where appropriate)
- Integration tests require Docker (mark with `@pytest.mark.integration`)

---

**Status**: Ready for implementation (WRITE TESTS FIRST)
**Created**: 2025-10-17
**Princess-Dev**: Coordinating
