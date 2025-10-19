# Memory MCP Triple System - SPEC v6.0

**Version**: 6.0 (Loop 1 Iteration 1)
**Date**: 2025-10-18
**Status**: Draft - Awaiting Review
**Methodology**: SPARC Loop 1 Planning Phase

---

## Executive Summary

The Memory MCP Triple System is a **portable, architecture-first AI memory solution** that addresses the "memory wall" problem through intelligent 3-tier retrieval, lifecycle-aware storage, and vendor-independent design. Building on Weeks 1-6 foundation (321 tests passing, 85% coverage), this specification defines Weeks 7-14 implementation to deliver a production-ready system aligned with 8 Memory Wall principles.

**Core Innovation**: Parallel 3-tier RAG (Vector + HippoRAG + Bayesian) with Obsidian MCP portability layer and SOP-enforced context curation.

**Target Users**: AI power users, developers building agentic systems, teams requiring multi-model memory portability.

---

## 1. Foundation Status (Weeks 1-6 Complete)

### 1.1 Completed Infrastructure ✅

**Week 1-2: Vector RAG Foundation**
- **ChromaDB**: Embedded vector database (SQLite backend, no Docker)
- **VectorIndexer**: Full CRUD operations (add, delete, update, search)
- **Embedding Pipeline**: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- **Performance**: Batch size 100, HNSW optimized (construction_ef=100, M=16)
- **Tests**: 16 tests passing (11 unit + 5 integration), 92% coverage

**Week 3: Curation UI**
- **Flask/React Interface**: Lifecycle tagging (temporary, keep, archive)
- **Performance**: 300ms average retrieval
- **Tests**: 40 tests passing (28 unit + 12 integration)

**Week 4: Graph Services**
- **NetworkX**: In-memory directed graph knowledge representation
- **EntityService**: spaCy NER integration (en_core_web_sm)
- **GraphService**: Node/edge management, JSON persistence
- **Tests**: 65 tests passing

**Week 5-6: HippoRAG + ChromaDB Completion**
- **HippoRagService**: Multi-hop graph-based retrieval (321 LOC)
- **GraphQueryEngine**: Personalized PageRank (<50ms), BFS multi-hop (<100ms)
- **ChromaDB Migration**: Qdrant fully replaced, Docker eliminated
- **Performance**: 3-hop queries <100ms, PPR convergence <50ms
- **Tests**: 321 tests passing, 12 skipped, 85% coverage

**Total Baseline**:
- **LOC**: 1,653 production + 388 test (Week 5-6 alone)
- **Tests**: 321 passing across all components
- **Coverage**: 85-92% across modules
- **NASA Rule 10**: 99-100% compliance

### 1.2 Technology Stack ✅

**Storage Layer**:
- ChromaDB 1.0.20+ (embedded, file-based)
- NetworkX 3.2+ (in-memory graph)
- SQLite (via ChromaDB backend)

**NLP/AI**:
- spaCy 3.7+ (en_core_web_sm for NER)
- Sentence-Transformers 2.2+ (all-MiniLM-L6-v2)
- HippoRAG (NeurIPS'24 implementation)

**API/Interface**:
- Flask 3.0+ (REST API)
- React 18+ (curation UI)
- MCP (Model Context Protocol) server

**Testing**:
- pytest 7.4+ with fixtures/mocking
- 85% coverage target (achieved: 85-92%)

---

## 2. Memory Wall Principles (Architecture Foundation)

The specification is architected around 8 principles from Simon Willison's "Memory Wall" framework:

### Principle 1: Memory is Architecture, Not a Feature
**Requirement**: Memory MUST be a standalone, portable layer that survives vendor changes.

**Implementation**:
- **MCP Server as Portability Layer**: Standardized protocol for ChatGPT, Claude, Gemini
- **Obsidian Vault as Universal Store**: Markdown-based, vendor-independent
- **No Vendor Lock-In**: Memory persists regardless of LLM provider

**Acceptance Criteria**:
- ✅ MCP server can serve any LLM client (ChatGPT, Claude, Gemini)
- ✅ Obsidian vault readable by humans without AI
- ✅ Migration to new LLM takes <30 minutes (documented process)

### Principle 2: Separate by Lifecycle, Not Convenience
**Requirement**: Personal (permanent), Project (temporary), Session (ephemeral) data MUST have distinct storage and retrieval.

**Implementation**:
- **Personal Memory**: Obsidian vault `/personal/` (never expires)
- **Project Memory**: Obsidian vault `/projects/[project-name]/` (30-day retention after project close)
- **Session Memory**: ChromaDB with TTL tags (auto-expire after 7 days)

**Storage Separation**:
```
obsidian-vault/
├── personal/           # Permanent (user preferences, style guides)
│   ├── preferences.md
│   ├── style-guide.md
│   └── domain-knowledge/
├── projects/           # Temporary (project-specific facts)
│   ├── project-a/
│   │   ├── decisions.md
│   │   ├── entities.md
│   │   └── context.md
│   └── project-b/
└── sessions/           # Ephemeral (7-day TTL)
    ├── 2025-10-18-session-1.md
    └── 2025-10-18-session-2.md
```

**Acceptance Criteria**:
- ✅ ChromaDB metadata tags: `lifecycle: [personal|project|session]`
- ✅ Automatic expiration: Sessions purged after 7 days
- ✅ Query filtering: Can restrict search to lifecycle (e.g., "only personal memory")

### Principle 3: Match Storage to Query Pattern
**Requirement**: Different questions require different retrieval mechanisms.

**3-Tier RAG Implementation** (Parallel Retrieval):

**Tier 1: Vector RAG (Semantic Similarity)**
- **Engine**: ChromaDB with cosine similarity
- **Use Case**: "What did we discuss about X?" (broad semantic search)
- **Query Pattern**: Embedding-based nearest neighbors
- **Performance**: <200ms for top-10 results

**Tier 2: HippoRAG (Graph Traversal)**
- **Engine**: NetworkX + Personalized PageRank
- **Use Case**: "What decisions led to Y?" (multi-hop reasoning)
- **Query Pattern**: Entity extraction → BFS multi-hop → PPR ranking
- **Performance**: <500ms for 3-hop queries

**Tier 3: Bayesian Graph RAG (Probabilistic Reasoning)** 🆕 WEEK 7-10
- **Engine**: pgmpy belief networks
- **Use Case**: "What's the probability X given Y?" (uncertainty quantification)
- **Query Pattern**: Bayesian inference on knowledge graph
- **Performance**: <1s for probabilistic queries

**Tier Integration** (Nexus Processor):
- All 3 tiers query simultaneously (parallel execution)
- Nexus Processor consolidates results (5-step SOP pipeline)
- Ranking algorithm: Weighted sum (Vector: 0.4, HippoRAG: 0.4, Bayesian: 0.2)

**Acceptance Criteria**:
- ✅ Each tier queries in parallel (total latency = max(Tier1, Tier2, Tier3))
- ✅ Nexus Processor merges results within 100ms
- ✅ User can query individual tiers (e.g., "vector-only search")

### Principle 4: Mode-Aware Context Beats Volume
**Requirement**: Planning (breadth) vs Execution (precision) contexts require different retrieval strategies.

**Implementation**:
- **Planning Mode**: Return top-20 diverse results (maximize coverage)
- **Execution Mode**: Return top-5 precise results (minimize noise)
- **Brainstorming Mode**: Return top-30 with randomness (encourage exploration)

**Mode Detection**:
- **Explicit**: User specifies mode in query (e.g., `mode=planning`)
- **Implicit**: Nexus Processor detects mode from query structure
  - Planning: "What are all the options for X?"
  - Execution: "What is the exact value of X?"
  - Brainstorming: "What are some creative ideas for X?"

**Acceptance Criteria**:
- ✅ Planning mode returns 20+ results (recall-optimized)
- ✅ Execution mode returns ≤5 results (precision-optimized)
- ✅ Mode detection accuracy ≥85% (validated on 100 test queries)

### Principle 5: Portable First-Class
**Requirement**: Memory layer MUST survive vendor changes, tool changes, model changes.

**Portability Design**:
1. **Obsidian Vault**: Human-readable markdown (no vendor format)
2. **MCP Server**: Standardized protocol (ChatGPT, Claude, Gemini compatible)
3. **Export/Import**: JSON, CSV, Markdown formats
4. **Migration Scripts**: Automated migration from ChatGPT memory, Claude Projects

**Portability Testing**:
- Test MCP server with ChatGPT (OpenAI API)
- Test MCP server with Claude (Anthropic API)
- Test MCP server with Gemini (Google API)
- Validate Obsidian vault readable by humans (no AI required)

**Acceptance Criteria**:
- ✅ MCP server responds to all 3 LLM clients
- ✅ Obsidian vault 100% human-readable (markdown only, no binary)
- ✅ Migration from ChatGPT memory <30 minutes (documented script)

### Principle 6: Compression is Curation (Active, Not Passive)
**Requirement**: Memory MUST be actively curated with human judgment, not passively accumulated.

**Nexus Processor 5-Step SOP Pipeline** 🆕 WEEK 11:
1. **Recall**: Query all 3 tiers, collect candidate results (top-50 total)
2. **Filter**: Remove low-confidence results (confidence <0.3)
3. **Deduplicate**: Merge semantically identical results (cosine >0.95)
4. **Rank**: Weighted ranking (Vector: 0.4, HippoRAG: 0.4, Bayesian: 0.2)
5. **Compress**: Return top-K (K=5 execution, K=20 planning, K=30 brainstorming)

**Curation Workflow**:
- **Weekly Review**: User tags chunks as `keep`, `archive`, or `delete`
- **Time Estimate**: <5 minutes/day (35 minutes/week target)
- **Smart Suggestions**: ML-based auto-tagging (user can override)
- **Batch Operations**: Tag 10+ chunks at once (not one-by-one)

**Acceptance Criteria**:
- ✅ Nexus Processor executes 5 steps in <100ms
- ✅ Weekly curation takes <35 minutes (measured via analytics)
- ✅ Smart suggestions ≥70% accuracy (validated on 1000 chunks)

### Principle 7: Retrieval Needs Verification (Two-Stage)
**Requirement**: Semantic search recalls candidates, but facts must be verified against ground truth.

**Two-Stage Retrieval**:
1. **Stage 1 (Recall)**: Semantic search (ChromaDB) → Top-50 candidates
2. **Stage 2 (Verify)**:
   - **Facts** (legal, financial, policy): Verify against Obsidian ground truth
   - **Brainstorm** (creative, exploratory): Skip verification
   - **Mixed**: Verify critical fields only (e.g., dates, names)

**Ground Truth Database**:
- **Storage**: Obsidian `/personal/ground-truth/` (structured YAML)
- **Schema**:
  ```yaml
  facts:
    - id: fact-001
      type: policy
      content: "NASA Rule 10: All functions ≤60 LOC"
      source: "nasa-compliance.md"
      confidence: 1.0
  ```
- **Verification**: Exact string match or semantic similarity >0.98

**Acceptance Criteria**:
- ✅ Facts verified against ground truth (100% for `type: policy`)
- ✅ Verification adds <50ms latency (parallel with ranking)
- ✅ False positive rate <2% (hallucination detection)

### Principle 8: Memory Compounds Through Structure
**Requirement**: Structured memory (evergreen, versioned, tagged) compounds value. Random accumulation creates noise.

**Structured Memory Design**:
- **Evergreen**: Personal preferences, domain knowledge (never expires)
- **Versioned**: Project decisions (v1.0, v2.0, deprecated)
- **Tagged**: Metadata tags (topic, priority, lifecycle, project)

**Obsidian Tagging Convention**:
```markdown
---
title: "Decision: Use ChromaDB for Vector Store"
tags: [decision, architecture, vector-db, project-memory-mcp]
lifecycle: project
version: 2.0
created: 2025-10-18
updated: 2025-10-18
confidence: high
---

# Decision: Use ChromaDB for Vector Store

**Context**: Need embedded vector database without Docker.

**Decision**: Use ChromaDB (embedded, SQLite backend).

**Rationale**: No Docker, 3x faster indexing (batch_size=100).

**Alternatives Considered**: Qdrant (rejected: requires Docker).

**Supersedes**: v1.0 (Qdrant decision)
```

**Acceptance Criteria**:
- ✅ All Obsidian notes have YAML frontmatter (tags, lifecycle, version)
- ✅ Versioned notes linked (v2.0 references "Supersedes: v1.0")
- ✅ Tag-based search works (e.g., "show all `decision` tags")

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LLM Clients                             │
│  (ChatGPT, Claude, Gemini via MCP protocol)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP Server (Flask)                         │
│  - /query endpoint (3-tier retrieval)                        │
│  - /curate endpoint (lifecycle tagging)                      │
│  - /health endpoint (system status)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 Nexus Processor (SOP Pipeline)               │
│  1. Recall (query all 3 tiers)                               │
│  2. Filter (confidence >0.3)                                 │
│  3. Deduplicate (cosine >0.95)                               │
│  4. Rank (weighted sum)                                      │
│  5. Compress (return top-K)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         ▼           ▼           ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │ Tier 1 │  │ Tier 2 │  │ Tier 3 │
    │ Vector │  │HippoRAG│  │Bayesian│
    │  RAG   │  │  RAG   │  │  RAG   │
    └───┬────┘  └───┬────┘  └───┬────┘
        │           │           │
        ▼           ▼           ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │ChromaDB│  │NetworkX│  │ pgmpy  │
    │ (SQLite)│ │ DiGraph│  │ Belief │
    └───┬────┘  └───┬────┘  └───┬────┘
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
        ┌────────────────────────┐
        │   Obsidian Vault       │
        │   (Markdown + YAML)    │
        │   - /personal/         │
        │   - /projects/         │
        │   - /sessions/         │
        └────────────────────────┘
```

### 3.2 Data Flow

**Query Path** (Read):
```
LLM → MCP Server → Nexus Processor
  → [Tier 1: ChromaDB semantic search (parallel)]
  → [Tier 2: HippoRAG multi-hop (parallel)]
  → [Tier 3: Bayesian inference (parallel)]
  → Nexus Merge (5-step SOP)
  → Return top-K to LLM
```

**Indexing Path** (Write):
```
Obsidian File Save
  → File Watcher detects change
  → Semantic Chunker (512 tokens max)
  → Embedding Pipeline (all-MiniLM-L6-v2)
  → [Tier 1: ChromaDB batch add (parallel)]
  → [Tier 2: NetworkX entity extraction + graph update (parallel)]
  → [Tier 3: Bayesian network update (parallel)]
  → Indexing Complete (<2s target)
```

**Curation Path** (Update):
```
User → Curation UI → Tag chunks (keep/archive/delete)
  → Update ChromaDB metadata (`lifecycle` tag)
  → Update Obsidian YAML frontmatter
  → Propagate to NetworkX graph (optional entity re-extraction)
  → Curation Complete
```

### 3.3 Component Details

**Tier 1: Vector RAG (ChromaDB)**
- **Purpose**: Fast semantic similarity search
- **Storage**: Embedded SQLite (no server)
- **Indexing**: Batch size 100, HNSW (construction_ef=100, M=16)
- **Query**: Cosine similarity, top-K results
- **Performance**: <200ms for top-10

**Tier 2: HippoRAG (NetworkX + PPR)**
- **Purpose**: Multi-hop graph reasoning
- **Storage**: In-memory DiGraph, JSON persistence
- **Algorithm**: Personalized PageRank (alpha=0.85), BFS multi-hop (max 3 hops)
- **Entity Extraction**: spaCy NER (PERSON, ORG, GPE, PRODUCT, EVENT)
- **Performance**: <500ms for 3-hop queries

**Tier 3: Bayesian Graph RAG (pgmpy)** 🆕 WEEK 7-10
- **Purpose**: Probabilistic reasoning with uncertainty
- **Storage**: Bayesian belief network (JSON serialization)
- **Algorithm**: Variable elimination, belief propagation
- **Use Cases**: "What's P(X|Y)?", "What's most likely cause of Z?"
- **Performance**: <1s for inference

**Nexus Processor** 🆕 WEEK 11
- **Purpose**: Consolidate 3-tier results with SOP-enforced curation
- **Pipeline**: Recall → Filter → Deduplicate → Rank → Compress
- **Ranking**: Weighted sum (Vector: 0.4, HippoRAG: 0.4, Bayesian: 0.2)
- **Performance**: <100ms for pipeline execution

**MCP Server** (Flask REST API)
- **Endpoints**:
  - `POST /query`: 3-tier retrieval
  - `POST /curate`: Lifecycle tagging
  - `GET /health`: System status
  - `POST /export`: Export memory (JSON/CSV/Markdown)
- **Authentication**: Optional JWT tokens (configurable)
- **Performance**: <50ms overhead (excluding retrieval)

**Obsidian Integration** 🆕 WEEK 7
- **Bidirectional Sync**:
  - **Read**: File watcher → Auto-indexing (<2s from save to indexed)
  - **Write**: AI conversations → Auto-save to `/sessions/` (timestamped markdown)
- **Frontmatter**: YAML metadata (tags, lifecycle, version, confidence)
- **Portability**: 100% human-readable markdown (no binary)

---

## 4. Functional Requirements

### 4.1 Core Features

**FR-1: 3-Tier Parallel Retrieval**
- **Description**: Query Vector, HippoRAG, and Bayesian RAG simultaneously
- **Priority**: P0 (critical path)
- **Acceptance Criteria**:
  - ✅ All 3 tiers query in parallel (total latency = max latency)
  - ✅ Nexus Processor merges results within 100ms
  - ✅ User can query individual tiers (tier override parameter)

**FR-2: Lifecycle-Aware Storage**
- **Description**: Separate personal, project, session memory with distinct lifecycles
- **Priority**: P0
- **Acceptance Criteria**:
  - ✅ ChromaDB metadata tags: `lifecycle: [personal|project|session]`
  - ✅ Automatic expiration: Sessions purged after 7 days
  - ✅ Query filtering: Can restrict to lifecycle (e.g., `lifecycle=personal`)

**FR-3: Obsidian Bidirectional Sync**
- **Description**: Auto-index Obsidian vault changes, auto-save AI conversations
- **Priority**: P0
- **Acceptance Criteria**:
  - ✅ File watcher detects changes within 1s
  - ✅ Indexing completes within 2s of file save
  - ✅ AI conversations auto-saved to `/sessions/` with timestamp

**FR-4: Mode-Aware Context**
- **Description**: Planning (breadth), Execution (precision), Brainstorming (exploration) modes
- **Priority**: P1
- **Acceptance Criteria**:
  - ✅ Planning mode returns top-20 (recall-optimized)
  - ✅ Execution mode returns top-5 (precision-optimized)
  - ✅ Mode detection ≥85% accuracy (100 test queries)

**FR-5: Nexus Processor 5-Step SOP**
- **Description**: Active curation pipeline (Recall → Filter → Deduplicate → Rank → Compress)
- **Priority**: P0
- **Acceptance Criteria**:
  - ✅ Pipeline executes in <100ms
  - ✅ Deduplication removes cosine >0.95 duplicates
  - ✅ Ranking uses weighted sum (configurable weights)

**FR-6: Two-Stage Verification**
- **Description**: Verify facts against ground truth, skip for brainstorming
- **Priority**: P1
- **Acceptance Criteria**:
  - ✅ Facts (`type: policy`) verified against Obsidian ground truth
  - ✅ Verification adds <50ms latency
  - ✅ False positive rate <2% (hallucination detection)

**FR-7: Memory Forgetting & Decay** 🆕 WEEK 12
- **Description**: Exponential decay for session memory, preserve important chunks
- **Priority**: P2
- **Acceptance Criteria**:
  - ✅ Decay formula: `score = base_score * exp(-decay_rate * days_old)`
  - ✅ Important chunks (`priority: high`) exempt from decay
  - ✅ Manual override: User can mark "never forget"

**FR-8: Memory Consolidation** 🆕 WEEK 12
- **Description**: Weekly batch summarization (compress 100+ session chunks → 1 summary)
- **Priority**: P2
- **Acceptance Criteria**:
  - ✅ Auto-trigger: Every Sunday at 2am
  - ✅ Compression ratio: 100:1 (100 chunks → 1 summary chunk)
  - ✅ Summary stored in `/projects/` (permanent if project active)

**FR-9: MCP Server Portability**
- **Description**: Standardized MCP protocol for ChatGPT, Claude, Gemini
- **Priority**: P0
- **Acceptance Criteria**:
  - ✅ MCP server responds to all 3 LLM clients
  - ✅ Client switching takes <5 minutes (update config only)
  - ✅ Migration script from ChatGPT memory (<30 minutes)

**FR-10: Curation UI with Smart Suggestions**
- **Description**: Weekly review workflow with ML-based auto-tagging
- **Priority**: P1
- **Acceptance Criteria**:
  - ✅ Weekly curation takes <35 minutes
  - ✅ Smart suggestions ≥70% accuracy (1000 chunks validation)
  - ✅ Batch operations: Tag 10+ chunks at once

### 4.2 Performance Requirements

**PR-1: Query Latency**
- **Tier 1 (Vector RAG)**: <200ms for top-10
- **Tier 2 (HippoRAG)**: <500ms for 3-hop queries
- **Tier 3 (Bayesian RAG)**: <1s for inference
- **Nexus Processor**: <100ms for 5-step pipeline
- **Total (95th percentile)**: <1s for end-to-end query

**PR-2: Indexing Latency**
- **File Watcher Detection**: <1s from file save
- **Embedding Generation**: <100ms per chunk (batch size 100)
- **ChromaDB Indexing**: <50ms per chunk (batch size 100)
- **NetworkX Graph Update**: <200ms per file (entity extraction + graph insert)
- **Total**: <2s from file save to indexed

**PR-3: Curation Workflow**
- **Weekly Review Time**: <35 minutes (5 minutes/day average)
- **Smart Suggestion Latency**: <500ms per chunk
- **Batch Tag Operation**: <100ms for 10 chunks

**PR-4: Storage Growth**
- **Embeddings**: <10MB per 1000 chunks (384-dimensional vectors)
- **Graph**: <5MB per 1000 entities (NetworkX JSON)
- **Bayesian Network**: <20MB per 1000 nodes (pgmpy serialization)
- **Total**: <35MB per 1000 chunks

**PR-5: Concurrent Queries**
- **Throughput**: ≥10 queries/second (production target)
- **Horizontal Scaling**: ChromaDB supports read replicas (future enhancement)

### 4.3 Quality Requirements

**QR-1: NASA Rule 10 Compliance**
- **Target**: ≥95% of functions ≤60 LOC
- **Current**: 99-100% (Weeks 1-6)
- **Enforcement**: AST-based checking in CI/CD

**QR-2: Test Coverage**
- **Target**: ≥85% for all new code
- **Current**: 85-92% (Weeks 1-6)
- **Components**:
  - Unit tests: ≥80%
  - Integration tests: ≥70%
  - E2E tests: ≥60%

**QR-3: Type Safety**
- **Target**: 100% type hints, 0 mypy errors
- **Enforcement**: mypy --strict in CI/CD

**QR-4: Linting**
- **Target**: 0 ruff issues (Python)
- **Target**: 0 ESLint issues (JavaScript/React)

**QR-5: Security**
- **Target**: 0 critical vulnerabilities (Bandit, Semgrep)
- **Authentication**: Optional JWT tokens for MCP server
- **Secrets**: Environment variables only (no hardcoded keys)

---

## 5. Non-Functional Requirements

### 5.1 Portability

**NFR-1: Vendor Independence**
- **Requirement**: Memory layer survives ChatGPT, Claude, Gemini API changes
- **Implementation**: MCP server + Obsidian vault (no vendor-specific format)
- **Testing**: Validate with all 3 LLM clients

**NFR-2: Export/Import**
- **Formats**: JSON, CSV, Markdown
- **Use Cases**: Backup, migration, data analysis
- **Performance**: Export 10,000 chunks in <10s

**NFR-3: Migration Scripts**
- **From ChatGPT Memory**: Automated script (<30 minutes)
- **From Claude Projects**: Automated script (<30 minutes)
- **From Notion**: Manual guide (1-2 hours)

### 5.2 Usability

**NFR-4: Setup Time**
- **Target**: <15 minutes from git clone to first query
- **Dependencies**: Python 3.11+, pip install, spaCy model download
- **Documentation**: Step-by-step quickstart guide

**NFR-5: Curation UX**
- **Weekly Review**: <35 minutes
- **Smart Suggestions**: ≥70% accuracy
- **Batch Operations**: ≥10 chunks at once

**NFR-6: Error Messages**
- **User-Friendly**: No stack traces in UI
- **Actionable**: Clear next steps (e.g., "Install spaCy model: python -m spacy download en_core_web_sm")

### 5.3 Maintainability

**NFR-7: Modular Architecture**
- **Components**: Tier 1, Tier 2, Tier 3, Nexus, MCP Server (independently testable)
- **Interfaces**: Clear API contracts (Python Protocol classes)

**NFR-8: Logging**
- **Library**: loguru (structured logging)
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Performance**: Log all queries (latency, tier used, top-K results)

**NFR-9: Monitoring**
- **Metrics**: Query latency, indexing latency, storage growth
- **Alerts**: Latency >2s (95th percentile), storage >80% disk

### 5.4 Scalability

**NFR-10: Data Volume**
- **Target**: Support 100,000 chunks without performance degradation
- **ChromaDB**: Embedded mode supports 1M+ vectors
- **NetworkX**: In-memory graph (consider Neo4j for >100k entities)

**NFR-11: Horizontal Scaling**
- **Phase 1** (Weeks 1-14): Single-node deployment
- **Phase 2** (Future): ChromaDB read replicas, distributed graph

---

## 6. User Stories

### 6.1 Core User Stories (P0)

**US-1: As a power user, I want to query my memory across ChatGPT, Claude, and Gemini**
- **Scenario**: Switch from ChatGPT to Claude without losing memory
- **Acceptance**:
  - MCP server configured with Claude API key
  - Previous ChatGPT conversations accessible from Claude
  - Switch takes <5 minutes (update config only)

**US-2: As a developer, I want multi-hop reasoning for "What led to decision X?"**
- **Scenario**: Trace decision history across 3+ linked notes
- **Acceptance**:
  - HippoRAG finds 3-hop path (Entity A → Decision B → Rationale C → Decision X)
  - Query completes in <500ms
  - Top-5 results ranked by PageRank relevance

**US-3: As a user, I want automatic Obsidian sync without manual indexing**
- **Scenario**: Save note in Obsidian, query immediately
- **Acceptance**:
  - File watcher detects change within 1s
  - Indexing completes within 2s
  - New note appears in query results

**US-4: As a user, I want weekly curation to take <35 minutes**
- **Scenario**: Review 100+ session chunks from past week
- **Acceptance**:
  - Smart suggestions pre-tag 70% correctly
  - Batch tag 10 chunks at once
  - Total time <35 minutes (measured via analytics)

**US-5: As a user, I want personal memory to never expire**
- **Scenario**: Store personal preferences (e.g., "I prefer Python over JavaScript")
- **Acceptance**:
  - Stored in `/personal/` with `lifecycle: personal`
  - Never purged by auto-expiration
  - Queryable across all projects/sessions

### 6.2 Advanced User Stories (P1)

**US-6: As a user, I want probabilistic queries ("What's P(X|Y)?")**
- **Scenario**: "What's the probability decision X was caused by constraint Y?"
- **Acceptance**:
  - Bayesian RAG infers from knowledge graph
  - Returns probability (e.g., "P(X|Y) = 0.73")
  - Query completes in <1s

**US-7: As a user, I want to verify facts against ground truth**
- **Scenario**: Query policy ("What's NASA Rule 10?")
- **Acceptance**:
  - Semantic search recalls candidates
  - Verification stage checks Obsidian `/personal/ground-truth/`
  - Returns exact match (100% confidence) or marks as unverified

**US-8: As a user, I want session memory to decay over time**
- **Scenario**: Old brainstorming sessions become less relevant
- **Acceptance**:
  - Decay formula: `score = base_score * exp(-0.05 * days_old)`
  - 30-day-old sessions have 0.22x original score
  - Important chunks (`priority: high`) exempt

**US-9: As a user, I want to export my memory for backup**
- **Scenario**: Backup before major system upgrade
- **Acceptance**:
  - Export 10,000 chunks to JSON in <10s
  - Import restores 100% of data (verified via hash)

**US-10: As a user, I want mode-aware context (planning vs execution)**
- **Scenario**: "What are all options for database?" (planning) vs "What database did we choose?" (execution)
- **Acceptance**:
  - Planning mode returns top-20 (diverse options)
  - Execution mode returns top-5 (precise answer)
  - Mode detection ≥85% accuracy

---

## 7. Weeks 7-14 Roadmap (High-Level)

### Week 7: Obsidian MCP Integration + Lifecycle Separation
**Deliverables**:
- Obsidian file watcher (auto-indexing <2s)
- MCP server bidirectional sync (read vault + write sessions)
- Lifecycle tagging (personal, project, session) in ChromaDB metadata
- 15 tests (file watcher, sync, lifecycle filtering)

**Acceptance Criteria**:
- ✅ File save → indexed in <2s
- ✅ AI conversations auto-saved to `/sessions/`
- ✅ Lifecycle filtering works (e.g., `lifecycle=personal`)

### Week 8: GraphRAG Entity Consolidation (Leiden Algorithm)
**Deliverables**:
- Entity deduplication ("Tesla" = "Tesla Inc")
- Community detection (Leiden algorithm from GraphRAG paper)
- Hierarchical entity clustering
- 20 tests (entity consolidation, community detection)

**Acceptance Criteria**:
- ✅ Synonyms merged (90% accuracy on 1000 entities)
- ✅ Communities detected (modularity >0.4)
- ✅ Query "Tesla" returns all variants

### Week 9: RAPTOR Hierarchical Clustering
**Deliverables**:
- Recursive summarization (100 chunks → 10 summaries → 1 abstract)
- Bayesian Information Criterion (BIC) for cluster quality
- Multi-level retrieval (query at chunk, summary, or abstract level)
- 25 tests (clustering, summarization, multi-level retrieval)

**Acceptance Criteria**:
- ✅ 3-level hierarchy (chunks → summaries → abstracts)
- ✅ BIC score validates clusters (lower = better)
- ✅ Multi-level retrieval returns relevant results at all levels

### Week 10: Bayesian Graph RAG (pgmpy Belief Networks)
**Deliverables**:
- Bayesian network construction from knowledge graph
- Probabilistic inference (variable elimination, belief propagation)
- Uncertainty quantification ("P(X|Y) = 0.73")
- 30 tests (network construction, inference, uncertainty)

**Acceptance Criteria**:
- ✅ Bayesian network built from 1000+ entity graph
- ✅ Inference completes in <1s
- ✅ Probability queries return valid distributions (sum to 1.0)

### Week 11: Nexus Processor 5-Step SOP Pipeline
**Deliverables**:
- 5-step pipeline (Recall → Filter → Deduplicate → Rank → Compress)
- Weighted ranking (Vector: 0.4, HippoRAG: 0.4, Bayesian: 0.2)
- Parallel tier execution (latency = max tier latency)
- 15 tests (pipeline, ranking, parallel execution)

**Acceptance Criteria**:
- ✅ Pipeline executes in <100ms
- ✅ Parallel execution (total latency ≤ slowest tier + 100ms)
- ✅ Ranking weights configurable (YAML config)

### Week 12: Memory Forgetting & Consolidation
**Deliverables**:
- Exponential decay for session memory
- Weekly batch summarization (100 chunks → 1 summary)
- Manual override ("never forget" flag)
- 20 tests (decay, consolidation, override)

**Acceptance Criteria**:
- ✅ Decay formula applied (30-day chunks = 0.22x score)
- ✅ Weekly consolidation auto-triggers (Sunday 2am)
- ✅ Important chunks (`priority: high`) exempt

### Week 13: Mode-Aware Context (Planning vs Execution)
**Deliverables**:
- Mode detection (planning, execution, brainstorming)
- Mode-specific retrieval (top-K varies by mode)
- Explicit mode override (query parameter)
- 10 tests (mode detection, retrieval, override)

**Acceptance Criteria**:
- ✅ Planning returns top-20 (recall-optimized)
- ✅ Execution returns top-5 (precision-optimized)
- ✅ Mode detection ≥85% accuracy (100 test queries)

### Week 14: Two-Stage Retrieval Verification + Integration Testing
**Deliverables**:
- Ground truth database (Obsidian `/personal/ground-truth/`)
- Verification stage (facts only, skip brainstorming)
- E2E integration tests (all 3 tiers + Nexus + MCP)
- 50 tests (verification, E2E, performance benchmarks)

**Acceptance Criteria**:
- ✅ Facts verified against ground truth (100% for `type: policy`)
- ✅ Verification adds <50ms latency
- ✅ E2E tests pass (100% success rate)
- ✅ Performance benchmarks meet targets (95th percentile <1s)

---

## 8. Success Criteria

### 8.1 Technical Success

**Tier 1 Metrics**:
- ✅ 321+ tests passing (baseline: 321 from Weeks 1-6)
- ✅ ≥85% test coverage (all modules)
- ✅ NASA Rule 10: ≥95% compliance
- ✅ 0 critical security vulnerabilities

**Tier 2 Metrics**:
- ✅ Query latency (95th percentile): <1s
- ✅ Indexing latency: <2s from file save
- ✅ Curation time: <35 minutes/week
- ✅ Storage growth: <35MB per 1000 chunks

**Tier 3 Metrics**:
- ✅ MCP server responds to 3 LLM clients (ChatGPT, Claude, Gemini)
- ✅ Obsidian vault 100% human-readable (markdown only)
- ✅ Migration from ChatGPT memory <30 minutes

### 8.2 Functional Success

**Memory Wall Principles** (8/8 implemented):
- ✅ **P1**: Memory is architecture (MCP + Obsidian portability)
- ✅ **P2**: Lifecycle separation (personal, project, session)
- ✅ **P3**: Storage matches query pattern (3-tier RAG)
- ✅ **P4**: Mode-aware context (planning vs execution)
- ✅ **P5**: Portable first-class (vendor-independent)
- ✅ **P6**: Compression is curation (Nexus SOP pipeline)
- ✅ **P7**: Retrieval verification (two-stage)
- ✅ **P8**: Memory compounds through structure (tags, versions)

**User Stories** (10/10 validated):
- ✅ US-1: Multi-model query (ChatGPT, Claude, Gemini)
- ✅ US-2: Multi-hop reasoning (HippoRAG 3-hop)
- ✅ US-3: Auto Obsidian sync (<2s indexing)
- ✅ US-4: Weekly curation (<35 minutes)
- ✅ US-5: Personal memory never expires
- ✅ US-6: Probabilistic queries (Bayesian RAG)
- ✅ US-7: Fact verification (ground truth)
- ✅ US-8: Session decay (exponential formula)
- ✅ US-9: Export/backup (JSON, CSV, Markdown)
- ✅ US-10: Mode-aware context (≥85% detection)

### 8.3 Quality Gates

**Gate 1: All Tests Passing**
- **Criteria**: 400+ tests (baseline 321 + Weeks 7-14 additions)
- **Validation**: `pytest -v` (100% success rate)

**Gate 2: Performance Benchmarks**
- **Criteria**: 95th percentile <1s (end-to-end query)
- **Validation**: 1000 query load test

**Gate 3: NASA Compliance**
- **Criteria**: ≥95% functions ≤60 LOC
- **Validation**: AST-based checking script

**Gate 4: Security Audit**
- **Criteria**: 0 critical vulnerabilities
- **Validation**: Bandit + Semgrep scans

**Gate 5: Portability Testing**
- **Criteria**: MCP server works with 3 LLM clients
- **Validation**: Integration tests (ChatGPT, Claude, Gemini)

**Gate 6: Curation UX**
- **Criteria**: Weekly review <35 minutes
- **Validation**: 10 user testing sessions (average time)

---

## 9. Risks & Mitigation

### 9.1 Technical Risks

**Risk 1: Bayesian Network Complexity Explosion**
- **Probability**: 40%
- **Impact**: High (Week 10 delivery at risk)
- **Mitigation**:
  - Limit network size: Max 1000 nodes per graph
  - Use sparse belief propagation (skip low-probability edges)
  - Fallback: Skip Bayesian tier if >1s latency, rely on Vector + HippoRAG

**Risk 2: Obsidian Sync Latency >2s**
- **Probability**: 30%
- **Impact**: Medium (user experience degraded)
- **Mitigation**:
  - Incremental indexing (update single file, not full reindex)
  - Debouncing (wait 500ms after last file change before indexing)
  - Background indexing (queue files, process async)

**Risk 3: Mode Detection Accuracy <85%**
- **Probability**: 25%
- **Impact**: Low (user can override mode explicitly)
- **Mitigation**:
  - Rule-based fallback (keywords: "all options" → planning, "exact value" → execution)
  - User feedback loop (log misclassifications, retrain)

**Risk 4: MCP Server Performance Overhead >50ms**
- **Probability**: 20%
- **Impact**: Low (increases total latency but not critical)
- **Mitigation**:
  - Async Flask (use asyncio for parallel tier queries)
  - Connection pooling (reuse HTTP connections)

### 9.2 Usability Risks

**Risk 5: Curation Time >35 minutes/week**
- **Probability**: 35%
- **Impact**: High (defeats active curation principle)
- **Mitigation**:
  - Improve smart suggestions (aim for 80% accuracy, not 70%)
  - Batch operations: Tag 20+ chunks at once (not 10)
  - Auto-archive: Low-confidence chunks auto-tagged for deletion

**Risk 6: Setup Time >15 minutes**
- **Probability**: 25%
- **Impact**: Medium (adoption barrier)
- **Mitigation**:
  - One-command install: `pip install memory-mcp-system` (bundle dependencies)
  - Pre-download spaCy model in Docker image (optional Dockerfile)
  - Video tutorial (YouTube walkthrough <5 minutes)

### 9.3 Portability Risks

**Risk 7: MCP Protocol Changes (Breaking API)**
- **Probability**: 15%
- **Impact**: High (all LLM clients break)
- **Mitigation**:
  - Version MCP server API (v1, v2 with backward compatibility)
  - Monitor MCP spec updates (monthly check)
  - Fallback: REST API without MCP (direct HTTP)

**Risk 8: Obsidian Plugin API Changes**
- **Probability**: 10%
- **Impact**: Medium (file watcher breaks)
- **Mitigation**:
  - Use native filesystem watcher (not Obsidian plugin API)
  - Fallback: Manual indexing button (user-triggered)

---

## 10. Dependencies

### 10.1 Software Dependencies

**Python Libraries**:
- chromadb>=1.0.20 (embedded vector DB)
- networkx>=3.2 (graph algorithms)
- pgmpy>=0.1.25 (Bayesian networks) 🆕
- spacy>=3.7 (NER, requires en_core_web_sm)
- sentence-transformers>=2.2 (embeddings)
- flask>=3.0 (REST API)
- loguru>=0.7 (logging)
- pytest>=7.4 (testing)
- ruff (linting)
- mypy (type checking)

**JavaScript Libraries** (Curation UI):
- react>=18 (UI framework)
- axios>=1.6 (HTTP client)
- react-query>=3.39 (data fetching)

**External Services**:
- Obsidian vault (markdown notes)
- LLM APIs: ChatGPT (OpenAI), Claude (Anthropic), Gemini (Google)

### 10.2 Data Dependencies

**Pre-existing Data** (Weeks 1-6):
- ChromaDB collection (321 tests passing)
- NetworkX graph (entities + relations)
- Obsidian vault structure (`/personal/`, `/projects/`, `/sessions/`)

**New Data** (Weeks 7-14):
- Ground truth database (YAML in Obsidian)
- Bayesian network serialization (JSON)
- RAPTOR summaries (3-level hierarchy)

---

## 11. Out of Scope

**Explicitly NOT in Scope for v6.0**:

1. **Multi-user support**: Single-user system (no authentication, no collaboration)
2. **Distributed deployment**: Single-node only (no horizontal scaling)
3. **Real-time collaboration**: No conflict resolution for concurrent Obsidian edits
4. **Mobile app**: Web UI only (no iOS/Android native apps)
5. **Video/audio indexing**: Text-only (PDFs converted to text, no video transcription)
6. **Custom LLM fine-tuning**: Use pre-trained models only (no LoRA, no RLHF)
7. **Blockchain/Web3**: No decentralized storage (centralized Obsidian vault)

---

## 12. Appendices

### Appendix A: Memory Wall Principles Summary

| Principle | Implementation | Weeks |
|-----------|----------------|-------|
| **P1**: Memory is architecture | MCP Server + Obsidian vault | Week 7 |
| **P2**: Lifecycle separation | ChromaDB `lifecycle` tags | Week 7 |
| **P3**: Storage matches query | 3-tier RAG (Vector, HippoRAG, Bayesian) | Weeks 8-10 |
| **P4**: Mode-aware context | Planning/Execution modes | Week 13 |
| **P5**: Portable first-class | MCP protocol + Markdown | Week 7 |
| **P6**: Compression is curation | Nexus 5-step SOP | Week 11 |
| **P7**: Retrieval verification | Two-stage (recall + verify) | Week 14 |
| **P8**: Memory compounds | Structured tags, versions | Week 12 |

### Appendix B: 3-Tier RAG Comparison

| Tier | Engine | Use Case | Latency | Accuracy | Complexity |
|------|--------|----------|---------|----------|------------|
| **Tier 1** | ChromaDB | Semantic search ("What about X?") | <200ms | Good | Low |
| **Tier 2** | HippoRAG | Multi-hop ("What led to X?") | <500ms | Better | Medium |
| **Tier 3** | Bayesian | Probabilistic ("P(X\|Y)?") | <1s | Best | High |

**Ranking**: Weighted sum (0.4 + 0.4 + 0.2 = 1.0)

### Appendix C: Performance Budget

| Component | Latency Budget | Allocation |
|-----------|----------------|------------|
| Tier 1 (Vector) | 200ms | 20% |
| Tier 2 (HippoRAG) | 500ms | 50% |
| Tier 3 (Bayesian) | 1000ms | 100% |
| Nexus Processor | 100ms | 10% |
| MCP Server | 50ms | 5% |
| **Total (95th %)** | **<1s** | **Parallel** |

**Parallel Execution**: Total latency = max(Tier1, Tier2, Tier3) + Nexus + MCP

### Appendix D: Test Coverage Matrix

| Component | Unit Tests | Integration Tests | E2E Tests | Total |
|-----------|-----------|-------------------|-----------|-------|
| Tier 1 (Vector) | 16 | 5 | 0 | 21 |
| Tier 2 (HippoRAG) | 68 | 0 | 0 | 68 |
| Tier 3 (Bayesian) | 30 🆕 | 10 🆕 | 0 | 40 🆕 |
| Nexus Processor | 15 🆕 | 5 🆕 | 0 | 20 🆕 |
| MCP Server | 11 | 12 | 5 🆕 | 28 |
| Obsidian Sync | 15 🆕 | 5 🆕 | 5 🆕 | 25 🆕 |
| Curation UI | 28 | 12 | 0 | 40 |
| GraphRAG (Week 8) | 20 🆕 | 10 🆕 | 0 | 30 🆕 |
| RAPTOR (Week 9) | 25 🆕 | 10 🆕 | 0 | 35 🆕 |
| Forgetting (Week 12) | 20 🆕 | 5 🆕 | 0 | 25 🆕 |
| Mode-Aware (Week 13) | 10 🆕 | 5 🆕 | 0 | 15 🆕 |
| Verification (Week 14) | 20 🆕 | 10 🆕 | 20 🆕 | 50 🆕 |
| **Total** | **278** | **89** | **30** | **397** |

**Weeks 1-6 Baseline**: 321 tests
**Weeks 7-14 Additions**: 76 tests
**Total Target**: 397 tests (24% increase)

---

## 13. Version History

**v6.0 (2025-10-18)**: Initial Loop 1 Iteration 1 draft
- Integrated Weeks 1-6 completion status (321 tests, 85% coverage)
- Embedded 8 Memory Wall principles as architectural requirements
- Defined 3-tier RAG architecture (Vector + HippoRAG + Bayesian)
- Specified Nexus Processor 5-step SOP pipeline
- Added Obsidian MCP portability layer
- Detailed Weeks 7-14 roadmap (8 weeks, 76 new tests)
- Identified 8 risks with mitigation strategies
- Total: 397 tests target, <1s query latency, <35min weekly curation

**Next Iteration (v6.1)**: Risk mitigation refinement
- Address top P0/P1 risks from PREMORTEM v6.0
- Refine Bayesian network complexity limits
- Optimize Obsidian sync latency (<2s target)
- Improve mode detection accuracy (>85% target)

---

**Receipt**:
- **Run ID**: loop1-iter1-spec-v6.0
- **Timestamp**: 2025-10-18T18:30:00Z
- **Agent**: Strategic Planning (Loop 1)
- **Inputs**: Weeks 1-6 docs, Memory Wall transcript, user vision
- **Tools Used**: Read (7 files), Write (1 file), TodoWrite (2 updates)
- **Changes**: Created SPEC-v6.0.md (397 tests target, 8 Memory Wall principles, 3-tier RAG)
- **Status**: Ready for PLAN v6.0 creation
