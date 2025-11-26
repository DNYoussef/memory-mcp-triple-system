# Memory MCP Triple System - Production Remediation Plan

**Generated**: 2025-11-25
**Updated**: 2025-11-25 (Post Phase 0)
**Goal**: Fix ALL issues and achieve production-ready status
**Approach**: Work backwards from dependency tree, fix root causes first

---

## EXECUTIVE SUMMARY

```
+-------------------------------------------------------------------+
|                    REMEDIATION OVERVIEW (UPDATED)                  |
+-------------------------------------------------------------------+
| Total Issues:        40 -> 35 (5 A1.* resolved)                   |
| Critical Issues:     18 -> 13 (5 A1.* were critical)              |
| Estimated Effort:    156-196 developer hours (4-8 hrs saved)      |
| Calendar Time:       4-6 weeks (with 2 developers)                |
| Phases:              6 (0-5) - Phase 0 COMPLETE                   |
+-------------------------------------------------------------------+
```

---

## PHASE 0: ARCHITECTURE DECISION [COMPLETE - 2025-11-25]

**Status**: COMPLETE
**Decision Date**: 2025-11-25
**Decision**: Unified Architecture (A + B + C features)
**Reference**: docs/ARCHITECTURE-DECISION.md (ADR-001)

### Decision Made: Unified Architecture

| Component | Source | Implementation |
|-----------|--------|----------------|
| **Core Retrieval** | Option A | Vector/Graph/Bayesian tiers (existing code) |
| **Time Decay** | Option B | Metadata feature: `decay_score`, `retention_tier` |
| **P/E/S Categories** | Option C | Metadata field: `category: procedural|episodic|semantic` |
| **Tagging** | All | WHO/WHEN/PROJECT/WHY protocol preserved |

### Completed Actions

```
[x] Architecture decision meeting (2025-11-25)
[x] Document chosen architecture in ARCHITECTURE-DECISION.md
[x] Update all conflicting documentation:
    - MEMORY-MCP-TRUE-ARCHITECTURE.md -> ARCHIVED
    - MEMORY-MCP-OBSIDIAN-INTEGRATION.md -> ARCHIVED
    - src/__init__.py banner -> FIXED (Chroma/NetworkX, v1.1.0)
[x] Create ARCHITECTURE.md with canonical truth
```

### Issues Resolved by Phase 0

| Issue ID | Description | Resolution |
|----------|-------------|------------|
| A1.1 | THREE competing architecture definitions | Unified architecture chosen |
| A1.2 | Codebase: Vector/Graph/Bayesian | KEPT as core |
| A1.3 | True Architecture Doc: Time-Based | MERGED as metadata feature |
| A1.4 | Obsidian Doc: P/E/S | MERGED as metadata category |
| A1.5 | Backend/frontend mismatch | Unified model resolves |

**Effort Saved**: 4-8 hours (no more architecture debates)
**Issues Resolved**: 5 (A1.1-A1.5)
**Downstream Unblocked**: 15+ issues now actionable

---

## PHASE 1: FOUNDATION FIXES [WEEK 1]

### P1.1: Add Missing Dependency (D1.1)
**Effort**: 15 minutes
**Blocks**: All runtime functionality

```toml
# pyproject.toml - Add to dependencies:
[project]
dependencies = [
    # ... existing ...
    "tenacity>=8.2.0",  # ADD THIS
]
```

**Verification**:
```bash
pip install -e .
python -c "from tenacity import retry; print('OK')"
```

### P1.2: Fix Collection Name Mismatch (D3.2)
**Effort**: 1 hour
**Blocks**: All search results

```python
# Option A: Change config to match code
# config/memory-mcp.yaml
vector:
  collection_name: memory_chunks  # Was: memory_embeddings

# Option B: Change code to match config
# src/indexing/vector_indexer.py AND src/services/curation_service.py
COLLECTION_NAME = "memory_embeddings"  # Standardize
```

**Verification**:
```python
# Both should return same value
grep -r "collection" config/memory-mcp.yaml
grep -r "collection" src/indexing/vector_indexer.py
```

### P1.3: Fix Hardcoded Paths (D2.*)
**Effort**: 2 hours
**Blocks**: Portability

```python
# Before (BAD):
path = "C:\\Users\\17175\\Desktop\\memory-mcp-triple-system"

# After (GOOD):
import os
path = os.path.expanduser("~/Desktop/memory-mcp-triple-system")
# OR
path = os.environ.get("MEMORY_MCP_HOME", os.path.expanduser("~"))
```

**Files to Fix**:
- scripts/populate_knowledge_base.py
- scripts/ingest_complete_system_knowledge.py
- Any other scripts/ files

**Playbook**: simple-feature-implementation
**Skill**: sparc-methodology
**Agent**: coder

---

## PHASE 2: RUNTIME WIRING [WEEKS 1-2]

### P2.1: Wire NexusProcessor into MCP Servers (C3.1)
**Effort**: 8 hours
**Blocks**: 5-step SOP, all tiers

```python
# src/mcp/stdio_server.py - CURRENT (BAD):
from src.mcp.tools.vector_search import VectorSearchTool
tool = VectorSearchTool(collection)  # Direct to Chroma

# src/mcp/stdio_server.py - FIXED (GOOD):
from src.nexus.processor import NexusProcessor
from src.indexing.vector_indexer import VectorIndexer
from src.hipporag.graph_query_engine import GraphQueryEngine
from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine

# Initialize all tiers
vector_indexer = VectorIndexer(collection)
graph_engine = GraphQueryEngine(graph_path)
bayes_engine = ProbabilisticQueryEngine()

# Create Nexus processor with all tiers
nexus = NexusProcessor(
    vector_indexer=vector_indexer,
    graph_query_engine=graph_engine,
    probabilistic_query_engine=bayes_engine
)

# Route MCP calls through Nexus
@tool
async def vector_search(query: str, limit: int = 10):
    return await nexus.process(query, limit)
```

### P2.2: Create Hooks Directory and Files (C2.1-C2.5)
**Effort**: 16 hours
**Blocks**: Metadata tagging, context preservation

```bash
# Create directory structure
mkdir -p ~/.claude/hooks/12fa
```

```javascript
// ~/.claude/hooks/12fa/memory-mcp-tagging-protocol.js
module.exports = {
  taggedMemoryStore: async function(agent, content, metadata = {}) {
    const enrichedMetadata = {
      // WHO
      agent_name: agent,
      agent_category: getAgentCategory(agent),

      // WHEN
      timestamp_iso: new Date().toISOString(),
      timestamp_unix: Date.now(),
      timestamp_readable: new Date().toLocaleString(),

      // PROJECT
      project: process.env.MEMORY_MCP_PROJECT || 'memory-mcp-triple-system',

      // WHY
      intent: metadata.intent || 'storage',

      // Custom
      ...metadata
    };

    return await memoryStore(content, enrichedMetadata);
  }
};
```

**Playbook**: three-loop-system
**Skill**: research-driven-planning, parallel-swarm-implementation
**Agents**: system-architect, coder, tester

---

## PHASE 3: MOCK CODE REPLACEMENT [WEEKS 2-3]

### P3.1: Obsidian Client Real Sync (B1.1, B1.2)
**Effort**: 16 hours
**Blocks**: Vault integration

```python
# src/mcp/obsidian_client.py - CURRENT (MOCK):
def _sync_file(self, file_path: str) -> int:
    content = file_path.read_text()
    chunks = max(1, len(content) // 500)  # FAKE
    return chunks

# src/mcp/obsidian_client.py - FIXED (REAL):
def _sync_file(self, file_path: str) -> int:
    content = file_path.read_text()

    # Real chunking
    from src.chunking.semantic_chunker import SemanticChunker
    chunker = SemanticChunker()
    chunks = chunker.chunk(content)

    # Real indexing
    from src.indexing.vector_indexer import VectorIndexer
    indexer = VectorIndexer(self.collection)

    for i, chunk in enumerate(chunks):
        metadata = {
            "source": str(file_path),
            "chunk_index": i,
            "total_chunks": len(chunks),
            "synced_at": datetime.now().isoformat()
        }
        indexer.index(chunk, metadata)

    return len(chunks)
```

### P3.2: Semantic Chunker Max-Min Algorithm (B2.1)
**Effort**: 8 hours
**Blocks**: Chunk quality

```python
# src/chunking/semantic_chunker.py - CURRENT (NAIVE):
# TODO: Implement Max-Min semantic chunking algorithm
paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

# src/chunking/semantic_chunker.py - FIXED (MAX-MIN):
def max_min_chunk(self, text: str, target_size: int = 500) -> List[str]:
    """
    Max-Min semantic chunking:
    1. Split into sentences
    2. Compute embeddings for each sentence
    3. Find semantic boundaries where similarity drops
    4. Merge sentences between boundaries into chunks
    """
    sentences = self._split_sentences(text)
    embeddings = self.model.encode(sentences)

    # Find semantic boundaries
    boundaries = [0]
    for i in range(1, len(embeddings)):
        similarity = cosine_similarity(embeddings[i-1], embeddings[i])
        if similarity < self.boundary_threshold:
            boundaries.append(i)
    boundaries.append(len(sentences))

    # Create chunks from boundaries
    chunks = []
    for i in range(len(boundaries) - 1):
        chunk_sentences = sentences[boundaries[i]:boundaries[i+1]]
        chunks.append(' '.join(chunk_sentences))

    return chunks
```

### P3.3: Bayesian CPD from Real Data (B1.6)
**Effort**: 16 hours
**Blocks**: Bayesian inference quality

```python
# src/bayesian/network_builder.py - CURRENT (RANDOM):
import random
row[node] = random.choice(states)  # MOCK

# src/bayesian/network_builder.py - FIXED (REAL DATA):
def estimate_cpd_from_history(self, node: str, history_store) -> TabularCPD:
    """
    Estimate CPD from historical query data.
    """
    # Fetch historical data
    history = history_store.get_node_observations(node)

    if len(history) < self.min_samples:
        # Fall back to uniform prior
        return self._uniform_cpd(node)

    # Compute frequencies from real data
    state_counts = Counter(history)
    total = sum(state_counts.values())
    probabilities = [state_counts[s] / total for s in self.states[node]]

    return TabularCPD(node, len(self.states[node]), [probabilities])
```

**Playbook**: three-loop-system
**Skill**: parallel-swarm-implementation
**Agents**: coder, tester, reviewer

---

## PHASE 4: FEATURE COMPLETION [WEEKS 3-4]

### P4.1: Add Missing MCP Tools (C1.2-C1.6)
**Effort**: 16 hours

```python
# src/mcp/stdio_server.py - Add tools:

@tool
async def graph_query(entity: str, depth: int = 2):
    """Query the HippoRAG knowledge graph."""
    return await nexus.graph_query_engine.query(entity, depth)

@tool
async def bayesian_inference(query: str, evidence: dict = None):
    """Perform Bayesian inference on memory graph."""
    return await nexus.probabilistic_query_engine.query_conditional(
        query, evidence, nexus.bayesian_network
    )

@tool
async def entity_extraction(text: str):
    """Extract entities from text using NER."""
    from src.extraction.entity_extractor import EntityExtractor
    extractor = EntityExtractor()
    return extractor.extract(text)

@tool
async def hipporag_retrieve(query: str, k: int = 10):
    """HippoRAG retrieval with PPR reranking."""
    return await nexus.hipporag_retrieve(query, k)

@tool
async def mode_detect(query: str):
    """Detect memory mode from query intent."""
    return await nexus.detect_mode(query)
```

### P4.2: Query Replay v0.9.0 Deferred TODOs (B2.3-B2.5)
**Effort**: 16 hours

```python
# src/debug/query_replay.py - CURRENT (TODO):
# TODO: Fetch from memory store (v0.9.0 deferred)
# TODO: Fetch from KV store (v0.9.0 deferred)
# TODO: Fetch from session store (v0.9.0 deferred)
return {}

# src/debug/query_replay.py - FIXED:
async def reconstruct_context(self, trace_id: str) -> dict:
    """Reconstruct full context for query replay."""
    trace = await self.trace_store.get(trace_id)

    return {
        "memory_snapshot": await self.memory_store.get_snapshot(
            trace.timestamp
        ),
        "preferences": await self.kv_store.get_user_preferences(
            trace.user_id
        ),
        "session": await self.session_store.get_session(
            trace.session_id
        ),
        "active_memories": await self.memory_store.get_active_at(
            trace.timestamp
        )
    }
```

### P4.3: RAPTOR LLM Summaries (B1.7)
**Effort**: 8 hours

```python
# src/clustering/raptor_clusterer.py - CURRENT (EXTRACTIVE):
# Week 9: Simple extractive summary (first 200 chars)
summary = concatenation[:200]

# src/clustering/raptor_clusterer.py - FIXED (LLM):
async def generate_cluster_summary(self, chunks: List[str]) -> str:
    """Generate abstractive summary using LLM."""
    concatenation = "\n\n".join(chunks)

    prompt = f"""Summarize these related text chunks into a single coherent summary:

{concatenation}

Summary (2-3 sentences):"""

    # Use local model or API
    response = await self.llm.complete(prompt, max_tokens=200)
    return response.text.strip()
```

**Playbook**: feature-dev-complete
**Skill**: ai-dev-orchestration
**Agents**: coder, tester, reviewer, api-docs

---

## PHASE 5: ALGORITHM FIXES & POLISH [WEEK 4]

### P5.1: Fix Distance-to-Similarity Bug (B3.1)
**Effort**: 1 hour

```python
# src/mcp/tools/vector_search.py - CURRENT (BUG):
'score': 1.0 - search_results['distances'][0][i]  # Can be negative!

# src/mcp/tools/vector_search.py - FIXED:
'score': 1.0 / (1.0 + search_results['distances'][0][i])  # Always [0, 1]
```

### P5.2: Fix Entity Extraction (B3.3)
**Effort**: 4 hours

```python
# src/nexus/processor.py - CURRENT (BUG):
query_entity = query.split()[0] if query.split() else "unknown"

# src/nexus/processor.py - FIXED:
from src.extraction.entity_extractor import EntityExtractor

def extract_query_entities(self, query: str) -> List[str]:
    """Extract entities using NER model."""
    extractor = EntityExtractor()
    entities = extractor.extract(query)
    return [e.text for e in entities] if entities else ["unknown"]
```

### P5.3: Update All Documentation (A2.*)
**Effort**: 8 hours

```markdown
Files to update:
- [ ] src/__init__.py - Change banner from Qdrant/Neo4j to Chroma/NetworkX
- [ ] README.md - Update architecture description
- [ ] docs/ARCHITECTURE.md - Create canonical truth
- [ ] tests/integration/*.py - Update comments about infrastructure
- [ ] Archive or align conflicting docs
```

### P5.4: Enable E2E Tests (D4.*)
**Effort**: 16 hours

```python
# tests/integration/test_end_to_end_search.py
# Remove pytest.skip decorators, add proper fixtures

@pytest.fixture
def memory_system():
    """Create real memory system for E2E tests."""
    # Use embedded Chroma, no Docker required
    return create_test_memory_system()

def test_full_pipeline(memory_system):
    # Index document
    memory_system.index("Test document about AI")

    # Query through all tiers
    results = memory_system.query("What is AI?")

    # Verify results include vector, graph, and bayesian
    assert results.vector_results
    assert results.graph_results
    # Bayesian optional until fully implemented
```

**Playbook**: testing-quality
**Skill**: functionality-audit, cicd-intelligent-recovery
**Agents**: tester, cicd-engineer

---

## PHASE 6: PRODUCTION HARDENING [WEEKS 5-6]

### P6.1: File Watcher Deletion Sync (B2.2)
**Effort**: 4 hours

```python
# src/utils/file_watcher.py - CURRENT (TODO):
# TODO: Implement deletion from vector DB

# src/utils/file_watcher.py - FIXED:
def on_deleted(self, event):
    """Handle file deletion - remove from vector DB."""
    file_path = event.src_path

    # Find and delete all chunks from this file
    self.vector_indexer.delete_by_metadata(
        {"source": file_path}
    )

    # Also remove from graph
    self.graph_engine.remove_document(file_path)

    logger.info(f"Deleted {file_path} from all indices")
```

### P6.2: Apply Database Migrations (C3.7)
**Effort**: 4 hours

```bash
# Create migration runner
# scripts/apply_migrations.py

import sqlite3
import glob

def apply_migrations(db_path: str):
    conn = sqlite3.connect(db_path)

    # Get applied migrations
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    applied = {row[0] for row in conn.execute("SELECT name FROM _migrations")}

    # Apply new migrations
    for migration_file in sorted(glob.glob("migrations/*.sql")):
        name = os.path.basename(migration_file)
        if name not in applied:
            with open(migration_file) as f:
                conn.executescript(f.read())
            conn.execute("INSERT INTO _migrations (name) VALUES (?)", (name,))
            print(f"Applied: {name}")

    conn.commit()
```

### P6.3: Wire Event Log and Lifecycle (C3.3, C3.5)
**Effort**: 8 hours

```python
# src/nexus/processor.py - Add event logging:
async def process(self, query: str, limit: int = 10):
    # Log query event
    await self.event_log.log({
        "type": "query",
        "query": query,
        "timestamp": datetime.now().isoformat()
    })

    results = await self._execute_pipeline(query, limit)

    # Log results event
    await self.event_log.log({
        "type": "results",
        "query": query,
        "result_count": len(results),
        "timestamp": datetime.now().isoformat()
    })

    # Trigger lifecycle check
    await self.lifecycle_manager.check_and_demote()

    return results
```

**Playbook**: production-readiness
**Skill**: deployment-readiness
**Agents**: cicd-engineer, production-validator

---

## REMEDIATION TIMELINE

```
WEEK 1:
+------------------+------------------+------------------+
| Phase 0          | Phase 1          | Phase 2 (Start)  |
| Arch Decision    | Foundation       | Runtime Wiring   |
| (4-8 hrs)        | (3 hrs)          | (8 hrs)          |
+------------------+------------------+------------------+

WEEK 2:
+------------------+------------------+------------------+
| Phase 2 (Cont)   | Phase 3 (Start)                     |
| Runtime Wiring   | Mock Code Replacement               |
| (16 hrs)         | (40 hrs)                            |
+------------------+------------------+------------------+

WEEK 3:
+------------------+------------------+------------------+
| Phase 3 (Cont)   | Phase 4 (Start)                     |
| Mock Code        | Feature Completion                  |
| (remaining)      | (40 hrs)                            |
+------------------+------------------+------------------+

WEEK 4:
+------------------+------------------+------------------+
| Phase 4 (Cont)   | Phase 5                             |
| Features         | Algorithm Fixes & Polish            |
| (remaining)      | (29 hrs)                            |
+------------------+------------------+------------------+

WEEKS 5-6:
+------------------+------------------+------------------+
| Phase 6                                               |
| Production Hardening                                  |
| (16 hrs)                                              |
+------------------+------------------+------------------+
```

---

## RESOURCE REQUIREMENTS

| Resource | Quantity | Duration |
|----------|----------|----------|
| Senior Backend Developer | 1 | 6 weeks |
| ML/NLP Engineer | 1 | 3 weeks (Phases 3-4) |
| QA Engineer | 1 | 2 weeks (Phases 5-6) |
| Architect | 0.25 FTE | Week 1 |

**Total Effort**: 160-200 developer hours
**Calendar Time**: 4-6 weeks (with 2 FTE average)

---

## SUCCESS CRITERIA

### Phase Gates

| Phase | Gate Criteria |
|-------|---------------|
| Phase 0 | Architecture documented, conflicts resolved |
| Phase 1 | Server starts, basic search returns results |
| Phase 2 | NexusProcessor used, hooks work |
| Phase 3 | No mock code in critical paths |
| Phase 4 | All MCP tools functional |
| Phase 5 | All tests pass, docs accurate |
| Phase 6 | Production metrics green |

### Production Ready Checklist

```
[ ] All 40 issues resolved or documented as won't-fix
[ ] No CRITICAL issues remaining
[ ] E2E tests pass without skips
[ ] Documentation matches implementation
[ ] All three tiers (Vector/Graph/Bayesian) functional
[ ] MCP exposes all advertised tools
[ ] Hooks integrate with Claude Code
[ ] Lifecycle management active
[ ] Event logging operational
[ ] Query replay functional for debugging
[ ] No hardcoded paths
[ ] All dependencies in pyproject.toml
```

---

## RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Architecture decision delayed | Medium | High | Set deadline, escalate |
| Bayesian tier too complex | Medium | Medium | Can ship with V+G only |
| LLM integration costs | Low | Medium | Use local models initially |
| Test environment setup | Medium | Low | Document requirements clearly |

---

## NEXT STEPS

1. **Immediate**: Get architecture decision (Phase 0)
2. **Day 1**: Fix D1.1 (tenacity) and D3.2 (collection)
3. **Week 1**: Complete Phase 1 + start Phase 2
4. **Ongoing**: Daily standup on progress, weekly phase gate reviews

---

**Generated by**: Claude Opus 4.5
**Methodology**: MECE analysis, dependency tree, topological sort
**Sources**: Opus 4.5, Gemini 3, GPT-5 Codex remediation reports
