# Scripts Directory

Utility scripts for the Memory MCP Triple System.

## Available Scripts

### `ingest_documentation.py` - Documentation Self-Ingestion

**Purpose**: Ingest system documentation into the memory system itself, enabling AI models to retrieve information about how the system works.

**Usage**:
```bash
cd /path/to/memory-mcp-triple-system
python scripts/ingest_documentation.py
```

**What it does**:
1. Collects all documentation files (markdown)
2. Chunks each file semantically (128-512 tokens)
3. Generates embeddings (384-dim vectors)
4. Indexes in ChromaDB with metadata
5. Tests self-referential retrieval

**Files ingested**:
- `docs/INGESTION-AND-RETRIEVAL-EXPLAINED.md` - Pipeline explanation
- `docs/MCP-DEPLOYMENT-GUIDE.md` - Deployment instructions
- `docs/weeks/WEEK-13-COMPLETE-SUMMARY.md` - Mode-aware context
- `docs/weeks/WEEK-13-IMPLEMENTATION-PLAN.md` - Implementation details

**Requirements**:
- ChromaDB installed (`pip install chromadb`)
- Sentence-transformers installed (`pip install sentence-transformers`)
- Internet connection (first run only, to download embedding model)

**Expected output**:
```
Files processed: 4/4
Total chunks created: 173
Storage location: ./chroma_data/
Collection: memory_embeddings

✅ Documentation ingestion complete!
```

**After ingestion**, AI models can query:
- "How does the ingestion pipeline work?"
- "How do I deploy the MCP server?"
- "What is mode-aware context?"
- "How do I troubleshoot ChromaDB errors?"

See [docs/SELF-REFERENTIAL-MEMORY.md](../docs/SELF-REFERENTIAL-MEMORY.md) for full details.

---

## Future Scripts (Planned)

### `ingest_vault.py` - Obsidian Vault Ingestion

Ingest an entire Obsidian vault into the memory system.

**Status**: Not yet implemented
**Target**: Week 14-15

### `reindex_collection.py` - Collection Reindexing

Re-index existing chunks with updated embeddings or metadata.

**Status**: Not yet implemented
**Target**: Week 16-17

### `cleanup_old_chunks.py` - Lifecycle Management

Clean up old or low-value chunks based on access patterns.

**Status**: Not yet implemented
**Target**: Week 16-17

---

## Development

### Adding New Scripts

1. Create script in `scripts/` directory
2. Add shebang: `#!/usr/bin/env python3`
3. Include docstring explaining purpose
4. Add usage example
5. Update this README

### Script Conventions

- **Error handling**: Always use try/except for external operations
- **Logging**: Use loguru for structured logging
- **Progress**: Show progress for long-running operations
- **Testing**: Include dry-run mode where applicable
- **Documentation**: Update README when adding scripts
