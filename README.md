# Memory MCP Triple System

**A sophisticated multi-layer memory system for AI assistants with mode-aware context adaptation**

The Memory MCP Triple System is a production-ready Model Context Protocol (MCP) server that provides intelligent, multi-layered memory management for AI assistants like Claude and ChatGPT. It automatically detects query intent, adapts context based on interaction modes, and retrieves relevant information from a semantic vector database.

## 🔗 Integration with AI Development Systems

The Memory MCP Triple System integrates seamlessly with intelligent code analysis and development systems:

**Context Cascade Cognitive Architecture** - [https://github.com/DNYoussef/context-cascade](https://github.com/DNYoussef/context-cascade)
- **Four-Loop Integration**: Loop 1.5 (Reflect) and Loop 3 (Meta-Optimization) fully wired
- **FrozenHarness Telemetry**: Evaluation metrics stored with WHO/WHEN/PROJECT/WHY tags
- **Session Learnings**: reflect_to_memory.py stores corrections and patterns
- **Meta-Loop Optimization**: meta_loop_runner.py aggregates and optimizes every 3 days
- **Library Catalog**: 25 components indexed for pre-coding guard

**Connascence Safety Analyzer** - [https://github.com/DNYoussef/connascence-safety-analyzer](https://github.com/DNYoussef/connascence-safety-analyzer)
- 7+ code quality violation types with NASA compliance
- 0.018s analysis performance
- Real-time code quality tracking and pattern detection

**ruv-SPARC Three-Loop System** - [https://github.com/DNYoussef/ruv-sparc-three-loop-system](https://github.com/DNYoussef/ruv-sparc-three-loop-system)
- 86+ specialized agents (ALL have Memory MCP access)
- Automatic tagging protocol (WHO/WHEN/PROJECT/WHY)
- Complete agent coordination framework
- Evidence-based prompting techniques

### New Integration Scripts (2026-01-09)

| Script | Location | Purpose |
|--------|----------|---------|
| `reflect_to_memory.py` | `scripts/` | Store session learnings from Loop 1.5 |
| `meta_loop_runner.py` | `scripts/` | Aggregate learnings, run every 3 days |
| `migrate_library_to_memory_mcp.py` | `cognitive-architecture/scripts/` | Library catalog migration |

**Scheduled Task**: `MemoryMCP-MetaLoop-3Day` runs meta_loop_runner.py every 3 days at 3:00 AM.

**MCP Integration Guide**: See [docs/MCP-INTEGRATION.md](docs/MCP-INTEGRATION.md) for complete setup instructions.

---

## Key Features

- **Triple retrieval tiers, fused**: Vector (ChromaDB, 384-dim) + HippoRAG knowledge graph (NetworkX multi-hop) + Bayesian inference (built from the live stored-memory graph) are fused by the Nexus pipeline (RECALL → FILTER → DEDUPE → RANK → RERANK → COMPRESS) at 0.4 / 0.4 / 0.2. (Not to be confused with the lifecycle *stages* below.)
- **Mode-aware retrieval**: detects Execution / Planning / Brainstorming via 29 patterns and adapts result count + token budget; brainstorming gives broader recall.
- **Four-stage lifecycle**: active → demoted → archived → rehydratable, with real aging — chunks carry a numeric `last_accessed_ts` and demote/archive/clean up on an elapsed-time schedule.
- **WHO/WHEN/PROJECT/WHY tagging** on every stored memory, plus per-call query tracing for replay and error attribution.
- **18 MCP tools** — semantic/graph/bayesian/unified search, entity extraction, mode detection, lifecycle status, a key-value store (`kv_get` / `kv_set` / `kv_delete`), and **`context_retrieve`** (surface relevant memory to inject as context). Full current list in [docs/CURRENT.md](docs/CURRENT.md).
- **Self-referential memory**: the system stores and retrieves its own documentation.
- **MCP-compatible**: stdio (canonical transport) + HTTP (FastAPI, API-key auth); works with Claude Desktop, Continue, and other MCP clients.
- **Verified end to end**: `scripts/acceptance_all_parts.py` exercises all 12 capabilities (store + every retrieval tier + lifecycle + injection) and passes on both Claude and Codex. Status: [audits/STATUS-2026-06-13.md](audits/STATUS-2026-06-13.md).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Assistant (Claude/ChatGPT)            │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Memory MCP Server                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Mode Detection Engine (29 patterns)                │   │
│  │  • Execution Mode (11 patterns)                     │   │
│  │  • Planning Mode (9 patterns)                       │   │
│  │  • Brainstorming Mode (9 patterns)                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Context Adaptation Layer                           │   │
│  │  • Token Budget (5K/10K/20K)                        │   │
│  │  • Core Size (5/10/15 results)                      │   │
│  │  • Extended Size (0/5/10 results)                   │   │
│  │  • Verification (on/conditional/off)                │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Triple retrieval tiers (fused 0.4/0.4/0.2)         │   │
│  │  • Vector (ChromaDB)                                │   │
│  │  • HippoRAG graph (NetworkX)                        │   │
│  │  • Bayesian (from the live graph)                  │   │
│  │  Lifecycle stages: active→demoted→archived→rehydr.  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Vector Database (ChromaDB)                         │   │
│  │  • Semantic chunking (128-512 tokens)               │   │
│  │  • 384-dim embeddings (all-MiniLM-L6-v2)            │   │
│  │  • HNSW index for fast similarity search            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/DNYoussef/memory-mcp-triple-system.git
cd memory-mcp-triple-system

# Install dependencies
pip install -e .

# Run tests to verify installation
pytest tests/unit/test_mode_detector.py tests/unit/test_mode_profile.py -v
```

### Configuration (Optional)

Copy `.env.example` to `.env` and configure as needed:

```bash
cp .env.example .env
```

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_MCP_DATA_DIR` | `./data` | Data storage directory |
| `HF_HOME` | `~/.cache/huggingface` | HuggingFace model cache |
| `OBSIDIAN_VAULT_PATH` | (none) | Optional Obsidian integration |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

All paths support `~` expansion for cross-platform compatibility.

### Running the MCP Server

```bash
# Start the MCP server (Stdio protocol - canonical)
python -m src.mcp.stdio_server

# The server listens on stdio for MCP protocol messages
# Current MCP tool list: see docs/CURRENT.md, including context_retrieve:
# - vector_search: Semantic similarity search with mode-aware context adaptation
# - memory_store: Store information with automatic layer assignment
# - kv_get/kv_set/kv_delete: Key-value storage operations
# - graph_query: HippoRAG multi-hop reasoning
# - entity_extraction: Named entity extraction
# - hipporag_retrieve: Full HippoRAG pipeline
# - detect_mode: Query mode detection (execution/planning/brainstorming)
```

### Claude Desktop Integration

Add to your Claude Desktop MCP configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "src.mcp.stdio_server"],
      "cwd": "/path/to/memory-mcp-triple-system"
    }
  }
}
```

For more details, see [docs/MCP-DEPLOYMENT-GUIDE.md](docs/MCP-DEPLOYMENT-GUIDE.md).

## Basic Usage

### Storing Memories

```python
from src.indexing.embedding_pipeline import EmbeddingPipeline
from src.indexing.vector_indexer import VectorIndexer

# Initialize components
embedder = EmbeddingPipeline()
indexer = VectorIndexer(persist_directory="./chroma_data")
indexer.create_collection()

# Store a memory
chunks = [{
    'text': 'The project uses React 18 with TypeScript',
    'file_path': 'notes.md',
    'chunk_index': 0,
    'metadata': {'category': 'tech_stack', 'layer': 'mid_term'}
}]

embeddings = embedder.encode([c['text'] for c in chunks])
indexer.index_chunks(chunks, embeddings.tolist())
```

### Retrieving Memories with Mode Detection

```python
from src.modes.mode_detector import ModeDetector

detector = ModeDetector()

# Execution mode: Fast, precise (5K tokens, 5 results)
profile, confidence = detector.detect("What is the tech stack?")
print(f"Mode: {profile.name}, Confidence: {confidence:.2f}")

# Planning mode: Balanced (10K tokens, 10+5 results)
profile, confidence = detector.detect("What should I consider for auth?")

# Brainstorming mode: Exploratory (20K tokens, 15+10 results)
profile, confidence = detector.detect("What if we used microservices?")
```

See [docs/INGESTION-AND-RETRIEVAL-EXPLAINED.md](docs/INGESTION-AND-RETRIEVAL-EXPLAINED.md) for complete pipeline documentation.

## Interaction Modes

### Execution Mode (Default)
- **Use Case**: Factual queries, specific information retrieval
- **Pattern Examples**: "What is X?", "How do I Y?", "Show me Z"
- **Configuration**: 5K tokens, 5 core results, verification enabled, <500ms latency

### Planning Mode
- **Use Case**: Decision-making, comparison, strategy
- **Pattern Examples**: "What should I do?", "Compare X and Y"
- **Configuration**: 10K tokens, 10+5 results, conditional verification, <1000ms latency

### Brainstorming Mode
- **Use Case**: Ideation, exploration, creative thinking
- **Pattern Examples**: "What if?", "Imagine...", "Explore all..."
- **Configuration**: 20K tokens, 15+10 results, verification disabled, <2000ms latency

## Triple-Layer Memory System

### Short-Term Memory (24-hour retention)
- Recent conversation context
- Temporary working data
- Current task information

### Mid-Term Memory (7-day retention)
- Project-specific context
- Recent decisions and rationales
- Active work artifacts

### Long-Term Memory (30-day retention)
- System documentation
- Best practices and patterns
- Historical decisions
- Important project knowledge

## Self-Referential Memory

The system can retrieve information about its own capabilities:

```python
from scripts.ingest_documentation import ingest_all_documentation

# Ingest system documentation
stats = ingest_all_documentation()
print(f"Ingested {stats['total_chunks']} chunks from {stats['files_processed']} files")

# Now the system can answer questions about itself
results = indexer.search_similar(
    query_embedding=embedder.encode_single("How does mode detection work?"),
    where={"category": "system_documentation"}
)
```

See [docs/SELF-REFERENTIAL-MEMORY.md](docs/SELF-REFERENTIAL-MEMORY.md) for details.

## Project Status

**Current Version**: v1.5.0
**Status**: Production Ready (Cognitive Architecture Integrated)
**Last Updated**: 2026-01-09

### Remediation Progress
- **Total Issues**: 52 identified
- **Issues Resolved**: 36/52 (69%)
- **Critical Issues Fixed**: 13/13 (100%)
- **Phases Completed**: 0-4 (Foundation, Features, Integration, Hardening)

### Quality Metrics (Current)
- **Tests**: 40+ passing (core functionality verified)
- **NASA Rule 10**: Compliant (all functions ≤60 LOC, assertions replaced with ValueError)
- **Error Handling**: Robust exception handling across 70+ handlers
- **Type Safety**: Full type annotations with mypy compliance
- **Mode Detection**: 3 modes with 29 regex patterns

### Working Features
- ✅ Vector search with ChromaDB (semantic similarity)
- ✅ Mode-aware context adaptation (execution/planning/brainstorming)
- ✅ Triple-layer memory architecture (short/mid/long-term)
- ✅ WHO/WHEN/PROJECT/WHY metadata tagging protocol
- ✅ Memory storage with automatic layer assignment
- ✅ Event logging and query tracing
- ✅ Lifecycle management with TTL support
- ✅ MCP stdio server (current tool set documented in docs/CURRENT.md)
- ✅ Self-referential memory capability
- ✅ **Loop 1.5 Integration**: Session reflection storage (reflect_to_memory.py)
- ✅ **Loop 3 Integration**: Meta-optimization aggregation (meta_loop_runner.py)
- ✅ **Telemetry Bridge**: FrozenHarness evaluation metrics storage
- ✅ **Scheduled Automation**: Windows Task Scheduler for 3-day meta-loop cycle

### Known Limitations
- Current runtime contract and known remaining items are tracked in [docs/CURRENT.md](docs/CURRENT.md).
- Retrieval is vector+graph fused, with Bayesian inference rebuilt from the live stored-memory graph.
- Live test/audit status is tracked in [audits/STATUS-2026-06-13.md](audits/STATUS-2026-06-13.md).

See [docs/REMEDIATION-PLAN.md](docs/REMEDIATION-PLAN.md) for detailed remediation roadmap and [docs/MECE-CONSOLIDATED-ISSUES.md](docs/MECE-CONSOLIDATED-ISSUES.md) for complete issue tracking.

## Documentation

### Core Documentation
- [MCP-DEPLOYMENT-GUIDE.md](docs/api/MCP-DEPLOYMENT-GUIDE.md) - MCP server deployment guide
- [INGESTION-AND-RETRIEVAL-EXPLAINED.md](docs/api/INGESTION-AND-RETRIEVAL-EXPLAINED.md) - Complete pipeline documentation
- [SELF-REFERENTIAL-MEMORY.md](docs/architecture/SELF-REFERENTIAL-MEMORY.md) - Self-awareness implementation
- [SESSION-COMPLETE-SUMMARY.md](docs/project-history/SESSION-COMPLETE-SUMMARY.md) - v1.0.0 completion summary

### Documentation Structure
- [docs/api/](docs/api/) - API and integration guides
- [docs/architecture/](docs/architecture/) - System architecture and process diagrams
- [docs/development/](docs/development/) - Development guides, audits, and quality reports
- [docs/project-history/](docs/project-history/) - Weekly summaries and planning documents
- [docs/research/](docs/research/) - Research papers and references
- [scripts/README.md](scripts/README.md) - Utility scripts documentation

See [docs/README.md](docs/README.md) for complete documentation index.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run mode detection tests
pytest tests/unit/test_mode_detector.py -v

# Run mode profile tests
pytest tests/unit/test_mode_profile.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Architecture Principles

### NASA Rule 10 Compliance
- All functions ≤60 lines of code
- No recursion (iterative alternatives only)
- Fixed loop bounds
- ≥2 assertions for critical paths

### Code Quality Gates
- Zero compilation errors
- ≥80% test coverage (≥90% for critical paths)
- Zero critical security vulnerabilities
- <60 theater detection score

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Mode detection accuracy | ≥85% | ✅ 85%+ |
| Execution mode latency | <500ms | ✅ <200ms |
| Planning mode latency | <1000ms | ✅ <500ms |
| Brainstorming latency | <2000ms | ✅ <800ms |
| Vector search latency | <200ms | ✅ <150ms |
| Test coverage | ≥80% | ✅ 100% |

## Technology Stack

- **Language**: Python 3.10+
- **Vector Database**: ChromaDB (embedded, Docker-free v5.0)
- **Graph Database**: NetworkX (in-memory, Docker-free v5.0)
- **Bayesian Inference**: pgmpy (probabilistic graphical models)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 (384-dim)
- **Protocol**: Model Context Protocol (MCP) stdio
- **Testing**: pytest, pytest-cov
- **Type Checking**: mypy (strict mode)
- **Linting**: flake8, bandit
- **Index**: HNSW (Hierarchical Navigable Small World)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt

# Run pre-commit checks
flake8 src/ tests/
mypy src/ --strict
bandit -r src/
pytest tests/ -v --cov=src
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [ChromaDB](https://www.trychroma.com/) for vector storage
- Uses [sentence-transformers](https://www.sbert.net/) for semantic embeddings
- Implements [Model Context Protocol](https://modelcontextprotocol.io/) for AI integration
- Follows [NASA Power of 10 Rules](https://en.wikipedia.org/wiki/The_Power_of_10:_Rules_for_Developing_Safety-Critical_Code)

## Contact

For questions or support, please open an issue on GitHub:
https://github.com/DNYoussef/memory-mcp-triple-system/issues

---

**Version**: v1.5.0 (Cognitive Architecture Integrated)
**Status**: Production Ready (Four-Loop System Complete)
**Remediation Tracking**: 36/52 issues resolved (69%)
**Last Updated**: 2026-01-09
---

## Obsidian Vault Integration

Memory MCP supports bidirectional sync with Obsidian vaults.

### Configuration

Add to your `.env` file:

```bash
OBSIDIAN_VAULT_PATH=C:\Users\17175\Documents\Obsidian Vault
OBSIDIAN_SYNC_ENABLED=true
OBSIDIAN_SYNC_INTERVAL=300
OBSIDIAN_SYNC_EXTENSIONS=.md
```

### Quick Start

```bash
# Check vault statistics
python scripts/obsidian_sync.py --stats

# Scan vault files
python scripts/obsidian_sync.py

# Use custom vault path
python scripts/obsidian_sync.py --vault "/path/to/vault" --stats
```

### Programmatic Usage

```python
from src.mcp import ObsidianMCPClient

client = ObsidianMCPClient(vault_path="/path/to/vault")

# Get vault statistics
stats = client.get_vault_stats()
print(f"Found {stats['markdown_files']} markdown files")

# Sync vault to memory system
result = client.sync_vault()
print(f"Synced {result['files_processed']} files")

# Export memories back to vault
client.export_to_vault(chunks, output_file="memories.md")
```

### Components

| Component | Purpose |
|-----------|---------|
| `ObsidianMCPClient` | Facade coordinating all vault operations |
| `VaultFileManager` | File discovery, metadata, and filtering |
| `VaultSyncService` | Sync operations, chunking, embedding |

