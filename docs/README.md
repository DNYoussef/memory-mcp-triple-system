# Memory MCP Triple System Documentation

**Version**: 1.0.0 (Week 13 Complete - Production Ready)
**Last Updated**: 2025-10-19
**Status**: Production Ready

---

## 📁 Documentation Structure

This documentation is organized into logical categories for easy navigation:

### `/api/` - API and Integration Documentation

**Essential API Documentation**:
- [MCP-DEPLOYMENT-GUIDE.md](api/MCP-DEPLOYMENT-GUIDE.md) - MCP server deployment and configuration
- [INGESTION-AND-RETRIEVAL-EXPLAINED.md](api/INGESTION-AND-RETRIEVAL-EXPLAINED.md) - Complete pipeline documentation (400+ lines)

### `/architecture/` - System Architecture

**Architecture Documentation**:
- [SELF-REFERENTIAL-MEMORY.md](architecture/SELF-REFERENTIAL-MEMORY.md) - Self-awareness implementation
- [`processes/`](architecture/processes/) - Visual process diagrams (GraphViz .dot files)
  - `hipporag-retrieval-pipeline.dot` - End-to-end retrieval flow
  - `personalized-pagerank.dot` - PPR algorithm details
  - `multi-hop-bfs-search.dot` - BFS multi-hop traversal
  - `entity-extraction-pipeline.dot` - spaCy NER + graph integration

**How to View Process Diagrams**:
```bash
# Render to PNG
dot -Tpng architecture/processes/hipporag-retrieval-pipeline.dot -o hipporag-pipeline.png

# Render all
for file in architecture/processes/*.dot; do
    dot -Tpng "$file" -o "${file%.dot}.png"
done
```

**VS Code Extension**: Install "Graphviz (dot) language support" for inline preview.

### `/development/` - Development Documentation

**Quality Assurance**:
- [`audits/`](development/audits/) - Code quality audits (theater detection, functionality, style/NASA compliance)
- [`drone-tasks/`](development/drone-tasks/) - Historical task assignments and execution logs

**Development Guides**:
- [`guides/`](development/guides/) - Setup and development guides
  - `DOCKER-FREE-SETUP.md` - Installation without Docker
  - `CHROMADB-QUICKSTART.md` - ChromaDB setup and usage
  - `MCP-SERVER-QUICKSTART.md` - MCP server setup
  - `REVIEW-GUIDE.md` - Code review checklist

### `/project-history/` - Project History and Planning

**Historical Documentation**:
- [`weeks/`](project-history/weeks/) - Weekly implementation summaries (Weeks 1-13)
- [`planning/`](project-history/planning/) - Project planning documents (LOOP1, PLAN v6-v7, SPEC v6-v7)
- [`loop1/`](project-history/loop1/) - Loop 1 summaries
- [`plans/`](project-history/plans/) - Implementation plans
- [`premortem/`](project-history/premortem/) - Pre-mortem risk analyses
- [`specs/`](project-history/specs/) - Specification documents
- [SESSION-COMPLETE-SUMMARY.md](project-history/SESSION-COMPLETE-SUMMARY.md) - Week 13 completion summary

### `/research/` - Research and References

**Research Documentation**:
- Research papers and references
- Technology investigations
- Algorithm studies

---

## 🔑 Key Documents

### Quick Access

**For Users**:
1. [MCP-DEPLOYMENT-GUIDE.md](api/MCP-DEPLOYMENT-GUIDE.md) - Getting started with MCP server
2. [INGESTION-AND-RETRIEVAL-EXPLAINED.md](api/INGESTION-AND-RETRIEVAL-EXPLAINED.md) - How the system works
3. [CHROMADB-QUICKSTART.md](development/guides/CHROMADB-QUICKSTART.md) - Vector database setup

**For Developers**:
1. [REVIEW-GUIDE.md](development/guides/REVIEW-GUIDE.md) - Code review checklist
2. [development/audits/](development/audits/) - Quality audit reports
3. [architecture/processes/](architecture/processes/) - Visual process diagrams

**Project History**:
1. [SESSION-COMPLETE-SUMMARY.md](project-history/SESSION-COMPLETE-SUMMARY.md) - Week 13 completion summary
2. [project-history/weeks/](project-history/weeks/) - All weekly summaries (Weeks 1-13)
3. [project-history/planning/](project-history/planning/) - Planning documents (SPEC, PLAN, PREMORTEM v6-v7)

### Current Status (Week 13 Complete)

**Production Ready**:
- ✅ 27/27 tests passing (100% mode system coverage)
- ✅ 100/100 quality audits (Theater + Functionality + Style/NASA)
- ✅ 85%+ mode detection accuracy
- ✅ Self-referential memory capability
- ✅ MCP server fully functional

---

## 📊 Project Metrics (Week 13)

### Code Quality

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| NASA Rule 10 Compliance | ≥92% | 100% | ✅ |
| Test Coverage (Mode System) | ≥80% | 100% | ✅ |
| Test Pass Rate | 100% | 100% | ✅ |
| Type Safety (mypy strict) | 0 errors | 0 errors | ✅ |
| Theater Detection | 0/100 | 100/100 | ✅ |
| Functionality Audit | 100/100 | 100/100 | ✅ |
| Style/NASA Audit | 100/100 | 100/100 | ✅ |

### Performance (Mode Detection)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Detection Accuracy | ≥85% | 85%+ | ✅ |
| Execution Mode Latency | <500ms | <200ms | ✅ |
| Planning Mode Latency | <1000ms | <500ms | ✅ |
| Brainstorming Mode Latency | <2000ms | <800ms | ✅ |
| Vector Search Latency | <200ms | <150ms | ✅ |

---

## 🏗️ Architecture Overview

### Triple-Layer Memory System

**Three-Tier Storage with Automatic Retention**:
1. **Short-Term Memory** (24-hour retention) - Recent conversation context
2. **Mid-Term Memory** (7-day retention) - Project-specific context
3. **Long-Term Memory** (30-day retention) - System documentation and knowledge

### Mode-Aware Context Adaptation (Week 13)

**Three Interaction Modes**:
1. **Execution Mode** (Default)
   - 5K token budget, 5 core results
   - Fast, precise retrieval (<500ms)
   - 11 detection patterns

2. **Planning Mode**
   - 10K token budget, 10+5 results
   - Balanced exploration (<1000ms)
   - 9 detection patterns

3. **Brainstorming Mode**
   - 20K token budget, 15+10 results
   - Broad exploration (<2000ms)
   - 9 detection patterns

**Mode Detection Pipeline**:
```
User Query
  → Pattern Matching (29 regex patterns)
  → Confidence Scoring (≥0.7 threshold)
  → Mode Selection (Execution/Planning/Brainstorming)
  → Context Adaptation (token budget, result count, verification level)
  → Retrieval with Mode-Specific Configuration
```

### Core Components

**Vector Database** (ChromaDB):
- Embedded vector store with HNSW index
- 384-dimensional embeddings (all-MiniLM-L6-v2)
- Semantic chunking (128-512 tokens at paragraph boundaries)

**Mode Detection System** (Week 13):
- ModeDetector (194 LOC) - Pattern-based query classification
- ModeProfile (145 LOC) - Configuration profiles for each mode
- 27 tests, 100% coverage, 85%+ accuracy

**MCP Server**:
- Model Context Protocol implementation
- stdio-based communication
- Vector search tool integration

---

## 🚀 Quick Start

See the main [README.md](../README.md) in the project root for installation and usage instructions.

**Key Documentation**:
- [MCP-DEPLOYMENT-GUIDE.md](api/MCP-DEPLOYMENT-GUIDE.md) - MCP server setup
- [INGESTION-AND-RETRIEVAL-EXPLAINED.md](api/INGESTION-AND-RETRIEVAL-EXPLAINED.md) - Complete pipeline guide
- [CHROMADB-QUICKSTART.md](development/guides/CHROMADB-QUICKSTART.md) - Vector database setup

---

## 📚 Technologies

- **Python**: 3.10+
- **ChromaDB**: Embedded vector database (HNSW index)
- **Sentence-Transformers**: all-MiniLM-L6-v2 embeddings (384-dim)
- **Model Context Protocol**: MCP server integration
- **pytest**: Testing framework
- **mypy**: Static type checking (strict mode)
- **flake8**: Linting
- **bandit**: Security scanning

---

## 🤝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) in the project root for contribution guidelines.

**Code Standards**:
- NASA Rule 10 compliance (all functions ≤60 LOC)
- Type hints required
- Comprehensive docstrings
- ≥80% test coverage
- Zero TypeScript/Python errors

---

## 📞 Support

For questions or issues:
1. Check the [api/](api/) documentation for usage guides
2. Review [development/guides/](development/guides/) for setup help
3. Browse [project-history/weeks/](project-history/weeks/) for implementation details
4. Open an issue at https://github.com/DNYoussef/memory-mcp-triple-system/issues

---

**Last Updated**: 2025-10-19 (Week 13 Complete)
**Status**: Production Ready (v1.0.0)
**GitHub**: https://github.com/DNYoussef/memory-mcp-triple-system
