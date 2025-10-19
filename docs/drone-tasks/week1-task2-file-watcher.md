# Week 1, Task 2: Obsidian File Watcher & Embedding Pipeline

**Assigned To**: coder Drone
**Priority**: P0 (Blocking Week 1 milestone)
**Estimated Time**: 6 hours
**Loop**: Loop 2 (Implementation)

## Objective

Implement a file watcher that monitors an Obsidian vault for changes and automatically generates embeddings using Sentence-Transformers, then indexes them in Qdrant.

## Requirements (From SPEC v4.0)

**FR-01**: Obsidian markdown storage
**FR-02**: Real-time indexing (<2s from save to searchable)
**FR-13**: Max-Min semantic chunking
**FR-78**: Vendored ML models (bundled Sentence-Transformers)

## Deliverables

1. **src/storage/file_watcher.py** (Obsidian vault monitor)
   - Watch directory for .md file changes (create, modify, delete)
   - Debounce rapid changes (wait 500ms after last change)
   - Parse markdown frontmatter (YAML metadata)
   - Extract content and metadata
   - Emit events to embedding pipeline

2. **src/embeddings/chunker.py** (Semantic chunking)
   - Implement Max-Min semantic chunking algorithm
   - Parameters: max_chunk_size=512, min_chunk_size=128, overlap=50
   - Preserve markdown structure (headings, lists, code blocks)
   - Return List[Chunk] with text, metadata, position

3. **src/embeddings/encoder.py** (Sentence-Transformers wrapper)
   - Load model: sentence-transformers/all-MiniLM-L6-v2 (384 dim)
   - Batch encoding (batch_size=32)
   - GPU support (if available, fallback to CPU)
   - Cache model in memory (singleton pattern)

4. **src/storage/qdrant_client.py** (Qdrant indexer)
   - Connect to Qdrant (from config)
   - Create collection (if not exists)
   - Upsert embeddings with metadata
   - Delete embeddings (on file delete)
   - Health check method

5. **src/pipeline/indexing_pipeline.py** (Orchestrator)
   - Coordinate: file watcher → chunker → encoder → Qdrant
   - Async processing (non-blocking)
   - Error handling and retry (3 attempts)
   - Logging (INFO level)

## Acceptance Criteria

- [ ] File watcher detects .md file changes within 500ms
- [ ] Chunking produces 128-512 token chunks with 50 token overlap
- [ ] Embeddings are 384-dimensional vectors
- [ ] Qdrant indexing completes within 2s of file save
- [ ] Deleted files are removed from Qdrant
- [ ] Pipeline handles 100 files/minute (performance target)
- [ ] No crashes on malformed markdown
- [ ] All functions ≤60 LOC (NASA Rule 10)

## Technical Constraints

**NASA Rule 10**: ≤60 LOC per function
**Performance**: <2s end-to-end (file save → indexed)
**Memory**: <500MB for 10k documents
**Type Safety**: Full type hints (mypy compliant)

## Architecture

```
Obsidian Vault (.md files)
    ↓
FileWatcher (watchdog)
    ↓
Chunker (Max-Min semantic)
    ↓
Encoder (Sentence-Transformers)
    ↓
QdrantClient (vector indexing)
```

## Testing Plan

**Unit Tests** (create these in `tests/unit/`):
1. `test_file_watcher.py`: Test file change detection, debouncing
2. `test_chunker.py`: Test chunking algorithm, edge cases
3. `test_encoder.py`: Test embedding generation, batching
4. `test_qdrant_client.py`: Test Qdrant operations (mock)
5. `test_indexing_pipeline.py`: Test end-to-end pipeline

**Integration Test** (create in `tests/integration/`):
1. `test_full_indexing.py`: Create .md file → verify in Qdrant

## Files to Create

1. `src/storage/file_watcher.py` (~150 LOC)
2. `src/embeddings/chunker.py` (~120 LOC)
3. `src/embeddings/encoder.py` (~80 LOC)
4. `src/storage/qdrant_client.py` (~180 LOC)
5. `src/pipeline/indexing_pipeline.py` (~200 LOC)
6. `src/storage/__init__.py` (exports)
7. `src/embeddings/__init__.py` (exports)
8. `src/pipeline/__init__.py` (exports)

**Total**: ~730 LOC

## Dependencies (Add to requirements.txt)

```
watchdog>=3.0.0  # File watching
sentence-transformers>=2.2.2  # Embeddings
qdrant-client>=1.7.0  # Vector database
pyyaml>=6.0  # YAML frontmatter
torch>=2.0.0  # PyTorch (for transformers)
```

## Example Usage

```python
from src.pipeline.indexing_pipeline import IndexingPipeline
from src.config import load_config

config = load_config()
pipeline = IndexingPipeline(config)
pipeline.start()  # Start watching vault

# Pipeline runs in background
# When user saves note.md in Obsidian:
# 1. FileWatcher detects change
# 2. Chunker splits into semantic chunks
# 3. Encoder generates embeddings
# 4. QdrantClient indexes in <2s
```

## References

- SPEC v4.0: FR-01, FR-02, FR-13, FR-78
- Research: Max-Min semantic chunking paper
- Config: config/memory-mcp.yaml (chunking parameters)

## Notes

- Use `watchdog` library for cross-platform file watching
- Sentence-Transformers model should be downloaded during Docker build (not runtime)
- Handle partial file writes (wait for file close event)
- Respect .gitignore patterns in vault (don't index .git/, .obsidian/)

---

**Status**: Ready for implementation
**Created**: 2025-10-17
**Princess-Dev**: Coordinating
