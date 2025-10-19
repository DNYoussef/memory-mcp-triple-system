# SPEC v1.0: Memory MCP Triple System

**Project**: Personal Memory System with Multi-Model Portability
**Date**: 2025-10-17
**Version**: 1.0
**Status**: Loop 1 Specification
**Methodology**: SPARC (Specification Phase)

---

## 1. Executive Summary

### 1.1 Project Objective

Build a **portable, multi-model memory system** that:
- Tracks personal information and project context
- Works with multiple LLMs (ChatGPT, Claude, Gemini)
- Uses hybrid RAG architecture (Vector + Graph + Bayesian)
- Integrates with Obsidian for knowledge management
- Implements Model Context Protocol (MCP) for portability
- Self-hosted, privacy-preserving, transferable between models

### 1.2 Core Problem Statement

**The Memory Wall Problem**:
- AI compute capabilities grew **60,000x**
- Memory capabilities only grew **100x**
- Current solutions (ChatGPT memory, Claude recall) are proprietary, non-portable, lossy
- Vendor lock-in prevents multi-model usage
- Passive accumulation creates noise, not memory
- No general solution for relevance, staleness, verification

**Our Solution**: Hybrid triple-layer architecture with active curation, MCP portability, and Obsidian integration.

### 1.3 Success Criteria

**Functional**:
- ✅ Vector search latency <200ms (p95)
- ✅ Graph query latency <500ms (p95)
- ✅ Multi-hop query latency <2s (p95)
- ✅ Retrieval recall@10 ≥85%
- ✅ Multi-hop accuracy ≥85%
- ✅ MCP-compatible (works with ChatGPT, Claude, Gemini)

**Non-Functional**:
- ✅ Self-hosted (no external APIs for core functionality)
- ✅ Privacy-preserving (local embeddings, no data leaving system)
- ✅ Portable (survives vendor/tool/model changes)
- ✅ Obsidian integration (markdown storage)
- ✅ Memory usage <2GB RAM
- ✅ Storage growth <10MB per 1000 docs

---

## 2. Functional Requirements

### 2.1 Memory Types

The system must support **5 distinct memory types**, each with different storage and retrieval patterns:

| ID | Memory Type | Description | Example | Storage | Lifecycle |
|----|-------------|-------------|---------|---------|-----------|
| **FR-01** | Preferences | How user likes things done | Writing style, output format | Key-Value (Redis) | Permanent |
| **FR-02** | Facts | What's true about entities | Client name, project budget | Structured (Neo4j) | Temporary |
| **FR-03** | Episodic Knowledge | Conversational, temporal | "What we discussed last week" | Vector (Qdrant) | Ephemeral |
| **FR-04** | Procedural Knowledge | How we solved problems before | Past solutions, patterns | Graph+Vector | Project |
| **FR-05** | Parametric Knowledge | Domain expertise | Python syntax, API docs | Model weights | N/A (in LLM) |

**Constraints**:
- Each memory type MUST use appropriate storage (principle: match storage to query pattern)
- Memory types MUST NOT be mixed in single storage (prevents lifecycle pollution)
- Update patterns MUST be specific to memory type (preferences=rare, episodic=constant)

### 2.2 Lifecycle Management

The system must separate memory by **three lifecycles**:

| ID | Lifecycle | Duration | Storage Location | Auto-Expire | Update Frequency |
|----|-----------|----------|------------------|-------------|------------------|
| **FR-06** | Permanent | Forever | `obsidian_vault/permanent/` | Never | Rare (manual) |
| **FR-07** | Temporary | Project duration | `obsidian_vault/projects/{id}/` | On project completion | Regular |
| **FR-08** | Ephemeral | 30 days | `obsidian_vault/sessions/{date}/` | After 30 days | Constant |

**Constraints**:
- Lifecycles MUST NOT be mixed (principle: separate by lifecycle, not convenience)
- Ephemeral data MUST decay after 30 days (keep metadata "keys", discard full content)
- Temporary data MUST be scoped to project (prevent cross-project leakage)
- Permanent data MUST be user-curated (no auto-promotion from temporary)

### 2.3 Storage Layers (Triple Hybrid Architecture)

#### 2.3.1 Layer 1: Vector RAG

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-09** | Vector Database | Qdrant (self-hosted, Docker) |
| **FR-10** | Embedding Model | Sentence-Transformers (all-MiniLM-L6-v2, local, free) |
| **FR-11** | Chunking Strategy | Max-Min Semantic (0.90 AMI score, 200-500 tokens/chunk) |
| **FR-12** | Indexing Throughput | ≥100 docs/min (Obsidian sync requirement) |
| **FR-13** | Query Latency | <200ms (p95) for semantic search |
| **FR-14** | Recall Target | ≥85% recall@10 on test set |

**Purpose**: Semantic search over episodic memory ("similar work we've done")

**Constraints**:
- MUST use local embeddings (no OpenAI API for privacy)
- MUST support metadata filtering (date, project, tags, lifecycle)
- MUST integrate with Obsidian file watcher (auto-index on file change)

#### 2.3.2 Layer 2: GraphRAG

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-15** | Graph Database | Neo4j (self-hosted, Docker) |
| **FR-16** | Entity Extraction | spaCy + Relik (NER, no LLM needed) |
| **FR-17** | Multi-Hop Engine | HippoRAG (10-30x faster than iterative RAG) |
| **FR-18** | Query Latency | <500ms (p95) for graph queries |
| **FR-19** | Multi-Hop Accuracy | ≥85% on complex queries (3+ hops) |
| **FR-20** | Graph Schema | Person, Project, Note, Tag, Decision nodes |

**Purpose**: Multi-hop reasoning over facts and procedural knowledge ("what did we decide about X?")

**Constraints**:
- MUST extract entities from markdown (frontmatter + content)
- MUST create bidirectional relationships (Obsidian backlinks → Neo4j edges)
- MUST support temporal queries ("decisions since October 12th")
- MUST verify facts against graph (two-stage retrieval)

#### 2.3.3 Layer 3: Bayesian Network

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-21** | Bayesian Framework | pgmpy or PyMC (probabilistic reasoning) |
| **FR-22** | Neurosymbolic | GNN-RBN (Graph Neural Network + Rule-Based Network) |
| **FR-23** | Uncertainty Scoring | Confidence intervals for retrieved docs |
| **FR-24** | Belief Propagation | Multi-hop probabilistic inference |
| **FR-25** | Query Latency | <2s (p95) for probabilistic queries |

**Purpose**: Uncertainty quantification and decision support ("how confident are we?")

**Constraints**:
- MUST provide probability distributions (not just point estimates)
- MUST integrate with vector/graph layers (fusion of evidence)
- MUST support "what-if" queries (counterfactual reasoning)

### 2.4 MCP Integration (Portability)

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-26** | Protocol | Model Context Protocol (MCP) standard |
| **FR-27** | MCP Server | Python or TypeScript server (localhost) |
| **FR-28** | MCP Tools | `vector_search`, `graph_query`, `probabilistic_query` |
| **FR-29** | Multi-Model Support | ChatGPT, Claude, Gemini (via MCP) |
| **FR-30** | Configuration | MCP config for Claude Desktop integration |

**Purpose**: Portable interface that works with any LLM

**Constraints**:
- MUST be model-agnostic (no OpenAI/Anthropic-specific code)
- MUST abstract storage layer (LLM doesn't know Qdrant/Neo4j details)
- MUST survive vendor changes (switch from ChatGPT to Claude without data migration)

### 2.5 Obsidian Integration

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-31** | Storage Format | Markdown (`.md` files with YAML frontmatter) |
| **FR-32** | Vault Location | `~/Documents/Memory-Vault` (user-configurable) |
| **FR-33** | File Watcher | Auto-index on file create/modify/delete |
| **FR-34** | Frontmatter Parsing | Extract metadata (lifecycle, tags, importance, dates) |
| **FR-35** | Graph Sync | Obsidian backlinks → Neo4j relationships |
| **FR-36** | Sync Latency | <5s from file save to indexed (real-time feel) |

**Purpose**: Obsidian as universal, portable storage layer

**Constraints**:
- MUST preserve Obsidian graph structure in Neo4j
- MUST support `[[wiki-links]]` extraction
- MUST be human-readable (markdown, not binary)
- MUST work without Obsidian app running (direct file access)

### 2.6 Active Curation (Human-in-Loop)

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-37** | Curation UI | Web interface for tagging, updating, archiving |
| **FR-38** | Lifecycle Tagging | Manual assignment: permanent/temporary/ephemeral |
| **FR-39** | Importance Weighting | User marks: critical/high/medium/low |
| **FR-40** | Stale Detection | Alert when fact >180 days old, prompt update |
| **FR-41** | Verification UI | ✅ Verified / ⚠️ Unverified flags for retrieved docs |
| **FR-42** | Compression Workflow | Human writes brief from AI-extracted facts |

**Purpose**: Active curation (principle: compression is curation - human judgment)

**Constraints**:
- MUST NOT assume LLM can auto-curate (passive accumulation fails)
- MUST prompt user for critical facts (legal, financial, policy)
- MUST allow manual override of auto-generated tags
- MUST track curation history (who curated, when, why)

### 2.7 Retrieval & Verification

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-43** | Two-Stage Retrieval | Stage 1: Recall (semantic/graph), Stage 2: Verify (structured) |
| **FR-44** | Recall Strategy | Top-k=20 candidates from vector/graph |
| **FR-45** | Verification Strategy | Check against Neo4j facts (ground truth) |
| **FR-46** | Confidence Scoring | 0.0-1.0 scale (verified=1.0, unverified<0.7) |
| **FR-47** | Hallucination Logging | Log when LLM tries to use unverified facts |
| **FR-48** | Human Override | Allow user to verify facts manually (UI) |

**Purpose**: Prevent $500k hallucination fines (principle: retrieval needs verification)

**Constraints**:
- MUST verify legal/financial/policy facts (always)
- MAY skip verification for brainstorming/drafts (optional)
- MUST log hallucination attempts (audit trail)
- MUST block execution if critical facts unverified

### 2.8 Mode-Aware Context

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-49** | Mode Detection | Automatic from query keywords (planning/execution/default) |
| **FR-50** | Planning Mode | Breadth retrieval (top-k=20, diversity=0.7, threshold=0.65) |
| **FR-51** | Execution Mode | Precision retrieval (top-k=5, diversity=0.2, threshold=0.85) |
| **FR-52** | Manual Override | User can force mode (query parameter) |

**Purpose**: Match retrieval strategy to task type (principle: mode-aware context beats volume)

**Constraints**:
- Planning mode MUST allow diverse results (alternatives, comparables)
- Execution mode MUST enforce precision (high threshold, audit trail)
- Mode detection MUST be fast (<10ms overhead)

### 2.9 Forgetting Mechanism

| ID | Requirement | Specification |
|----|-------------|---------------|
| **FR-53** | Decay Function | Exponential decay (30-day half-life for sessions) |
| **FR-54** | Key Retention | Keep metadata "keys" (date, topic, participants, outcome) |
| **FR-55** | Detail Discarding | Discard full transcript when decay_factor <0.1 |
| **FR-56** | Reconstruction | Reconstruct from keys when user queries old session |

**Purpose**: Structured forgetting (principle: forgetting is a technology)

**Constraints**:
- MUST NOT delete keys (needed for reconstruction)
- MUST compress to summary when decay_factor <0.5
- MUST allow manual override (user can pin important sessions)

---

## 3. Non-Functional Requirements

### 3.1 Performance

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| **NFR-01** | Vector Search Latency | <200ms | p95 |
| **NFR-02** | Graph Query Latency | <500ms | p95 |
| **NFR-03** | Multi-Hop Latency | <2s | p95 |
| **NFR-04** | Indexing Throughput | ≥100 docs/min | Obsidian sync |
| **NFR-05** | Retrieval Recall | ≥85% | recall@10 on test set |
| **NFR-06** | Multi-Hop Accuracy | ≥85% | Complex queries (3+ hops) |
| **NFR-07** | Memory Usage | <2GB RAM | Docker containers |
| **NFR-08** | Storage Growth | <10MB/1000 docs | Vector + graph combined |

### 3.2 Portability

| ID | Requirement | Specification |
|----|-------------|---------------|
| **NFR-09** | Vendor Independence | Works with ChatGPT, Claude, Gemini |
| **NFR-10** | Tool Independence | Works with any MCP-compatible tool |
| **NFR-11** | Model Independence | Survives model version upgrades |
| **NFR-12** | Format Independence | Markdown (human-readable, universal) |
| **NFR-13** | Export | Full memory export to JSON/markdown |
| **NFR-14** | Import | Import from ChatGPT/Claude exports |

### 3.3 Privacy & Security

| ID | Requirement | Specification |
|----|-------------|---------------|
| **NFR-15** | Self-Hosted | All components run locally (Docker) |
| **NFR-16** | No External APIs | No data sent to OpenAI/Anthropic for embeddings |
| **NFR-17** | Local Embeddings | Sentence-Transformers (runs on CPU/GPU locally) |
| **NFR-18** | Secrets Management | Environment variables (never hardcoded) |
| **NFR-19** | Access Control | Optional auth for web UI (basic auth) |
| **NFR-20** | Encryption at Rest | Optional disk encryption (user configurable) |

### 3.4 Reliability

| ID | Requirement | Specification |
|----|-------------|---------------|
| **NFR-21** | Uptime | 99% (Docker restart policies) |
| **NFR-22** | Data Durability | Persistent volumes (Docker) |
| **NFR-23** | Backup | Manual backup via Obsidian sync |
| **NFR-24** | Recovery | Rebuild index from Obsidian vault |
| **NFR-25** | Error Handling | Graceful degradation (if Neo4j down, use vector only) |

### 3.5 Usability

| ID | Requirement | Specification |
|----|-------------|---------------|
| **NFR-26** | Setup Time | <30 minutes (Docker Compose one-command) |
| **NFR-27** | Documentation | User guide, API reference, architecture docs |
| **NFR-28** | Curation UI | Simple web interface (React/FastAPI) |
| **NFR-29** | Query Syntax | Natural language (no Cypher/SQL required) |
| **NFR-30** | Feedback | Clear error messages, logging |

---

## 4. System Architecture

### 4.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
├─────────────────────────────────────────────────────────────┤
│  Obsidian App  │  Web UI (Curation)  │  Claude Desktop (MCP) │
└────────┬────────────────┬──────────────────────┬────────────┘
         │                │                      │
         │                │                      │
┌────────▼────────────────▼──────────────────────▼────────────┐
│                    MCP Server Layer                          │
│  Tools: vector_search, graph_query, probabilistic_query     │
└────────┬────────────────┬──────────────────────┬────────────┘
         │                │                      │
┌────────▼────────┐ ┌────▼────────┐ ┌──────────▼─────────────┐
│  Layer 1:       │ │  Layer 2:   │ │  Layer 3:              │
│  Vector RAG     │ │  GraphRAG   │ │  Bayesian Network      │
│                 │ │             │ │                        │
│  Qdrant         │ │  Neo4j      │ │  pgmpy/PyMC            │
│  Sentence-      │ │  HippoRAG   │ │  GNN-RBN               │
│  Transformers   │ │  spaCy      │ │  Belief Propagation    │
└────────┬────────┘ └────┬────────┘ └──────────┬─────────────┘
         │                │                      │
         │                │                      │
┌────────▼────────────────▼──────────────────────▼────────────┐
│                   Storage Layer                              │
│  Obsidian Vault: ~/Documents/Memory-Vault/                  │
│  - permanent/ (lifecycle: forever)                          │
│  - projects/{id}/ (lifecycle: project duration)             │
│  - sessions/{date}/ (lifecycle: 30 days)                    │
│  - exemplars/ (successful patterns + failures)              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow

#### 4.2.1 Indexing Flow (Obsidian → Storage)

```
User creates note in Obsidian
    ↓
File Watcher detects change
    ↓
Parse frontmatter (lifecycle, tags, importance)
    ↓
Route based on lifecycle:
    ├─ Permanent → Redis (key-value)
    ├─ Temporary → Neo4j (graph) + Qdrant (vector)
    └─ Ephemeral → Qdrant (vector only)
    ↓
Extract entities (spaCy + Relik)
    ↓
Create Neo4j nodes + relationships
    ↓
Generate embedding (Sentence-Transformers)
    ↓
Index in Qdrant with metadata
    ↓
Update graph links (Obsidian [[backlinks]] → Neo4j edges)
```

#### 4.2.2 Query Flow (User → Retrieval → Verification)

```
User query via MCP (ChatGPT/Claude/Gemini)
    ↓
Mode Detection (planning/execution/default)
    ↓
Route to appropriate layer(s):
    ├─ "What's my writing style?" → Layer 1 (key-value)
    ├─ "Similar work we've done?" → Layer 1 (vector)
    ├─ "What did we decide about X?" → Layer 2 (graph + HippoRAG)
    └─ "How confident are we?" → Layer 3 (Bayesian)
    ↓
Stage 1: Recall candidates (top-k=20)
    ↓
Stage 2: Verify (if critical fact)
    ├─ Check Neo4j ground truth
    ├─ Confidence scoring
    └─ Flag unverified (⚠️)
    ↓
Context Fusion (if multiple layers)
    ├─ RRF (Reciprocal Rank Fusion)
    └─ Weighted averaging
    ↓
Return results to LLM via MCP
    ↓
LLM generates response with verified context
```

### 4.3 Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Vector DB** | Qdrant | Best performance (1,238 QPS, 99% recall), self-hosted |
| **Graph DB** | Neo4j | Production-ready, GraphRAG support, Cypher query language |
| **Embeddings** | Sentence-Transformers | Free, local, privacy-preserving, fine-tunable |
| **Multi-Hop** | HippoRAG | 10-30x faster, 20% better accuracy vs iterative RAG |
| **Entity Extract** | spaCy + Relik | Cost-effective, no LLM needed, good accuracy |
| **Chunking** | Max-Min Semantic | 0.90 AMI score (best accuracy) |
| **Bayesian** | pgmpy or PyMC | Mature libraries, probabilistic reasoning |
| **Knowledge Mgmt** | Obsidian | Markdown-native, graph view, plugins, portable |
| **MCP Server** | Python (FastAPI) | Fast, async, type-safe, good MCP support |
| **Curation UI** | React + FastAPI | Modern, responsive, easy integration |
| **Deployment** | Docker Compose | One-command setup, reproducible, portable |

---

## 5. User Stories

### 5.1 Personal Memory (Permanent Lifecycle)

**As a user**, I want to store my writing preferences permanently, so that all LLMs use my preferred style without me repeating it.

**Acceptance Criteria**:
- ✅ Store preferences in `obsidian_vault/permanent/preferences.md`
- ✅ Frontmatter: `lifecycle: permanent`, `type: preference`
- ✅ Indexed in Redis (key-value)
- ✅ MCP tool `get_preference(key)` returns value instantly (<10ms)
- ✅ Works with ChatGPT, Claude, Gemini (same preferences)

**Example**:
```markdown
---
lifecycle: permanent
type: preference
created: 2025-10-17
---

# Writing Preferences

- Style: Technical, concise, bullet points
- Code: Always include examples
- Format: Markdown with syntax highlighting
- NASA Rule 10: Functions ≤60 LOC
```

### 5.2 Project Context (Temporary Lifecycle)

**As a user**, I want to scope memory to specific projects, so that project A facts don't leak into project B queries.

**Acceptance Criteria**:
- ✅ Store project facts in `obsidian_vault/projects/{project_id}/`
- ✅ Frontmatter: `lifecycle: temporary`, `project: {id}`
- ✅ Indexed in Neo4j (scoped to project node)
- ✅ MCP tool `graph_query(query, project_id)` filters by project
- ✅ Auto-archive when project marked complete

**Example**:
```markdown
---
lifecycle: temporary
project: memory-mcp-system
type: decision
created: 2025-10-17
---

# Decision: Use Qdrant for Vector Store

**Rationale**: Best performance (1,238 QPS), self-hosted, low cost
**Alternatives Considered**: Pinecone ($0.096/hr), Weaviate (complex setup)
**Status**: Approved
**Date**: 2025-10-17
```

### 5.3 Multi-Hop Reasoning (GraphRAG)

**As a user**, I want to ask "What decisions relate to people I met last month?" and get accurate multi-hop answers.

**Acceptance Criteria**:
- ✅ Query decomposes into 3 hops:
  - Hop 1: Find people met last month
  - Hop 2: Find projects involving those people
  - Hop 3: Find decisions in those projects
- ✅ HippoRAG retrieves relevant paths (<500ms)
- ✅ Accuracy ≥85% on complex queries
- ✅ Results include source links (which Obsidian notes)

**Example Query**:
```
User: "What decisions relate to people I met last month?"

HippoRAG Hops:
1. MATCH (p:Person)-[:MET_ON]->(date) WHERE date > "2025-09-17"
2. MATCH (p)-[:WORKS_ON]->(project:Project)
3. MATCH (project)-[:HAS_DECISION]->(d:Decision)

Results:
- Decision: "Use Qdrant" (related to Bob from AI meetup)
- Decision: "Implement MCP" (related to Sarah from conference)
```

### 5.4 Verification (Two-Stage Retrieval)

**As a user**, I want to be warned when LLM tries to use unverified facts, so I don't make $500k mistakes.

**Acceptance Criteria**:
- ✅ Stage 1: Semantic search recalls 20 candidates
- ✅ Stage 2: Verify each candidate against Neo4j ground truth
- ✅ Unverified facts flagged with ⚠️ in UI
- ✅ Critical queries (legal/financial) blocked if unverified
- ✅ User can manually verify via curation UI

**Example**:
```
Query: "What's the client budget for Project X?"

Stage 1 (Recall):
- Candidate 1: "Budget is $500k" (similarity: 0.92)
- Candidate 2: "Client requested $500k budget" (similarity: 0.88)

Stage 2 (Verify):
- Candidate 1: ✅ Verified (Neo4j: Project.budget = $500k)
- Candidate 2: ⚠️ Unverified (no Neo4j fact)

Result:
"Client budget: $500k [✅ Verified]"
```

### 5.5 Forgetting (Decay Mechanism)

**As a user**, I want old session data to compress to summaries, so storage doesn't explode but I can still reconstruct if needed.

**Acceptance Criteria**:
- ✅ Sessions >30 days decay to summary + keys
- ✅ Sessions >60 days decay to keys only (discard full transcript)
- ✅ Keys retained: date, topic, participants, outcome, tags
- ✅ User can query old sessions and get reconstruction from keys
- ✅ Manual override: pin important sessions (never decay)

**Example**:
```
Session (Day 1):
- Full transcript: 5,000 words
- Storage: 20KB

Session (Day 40):
- Summary: 200 words
- Keys: date, topic, outcome
- Storage: 2KB (90% reduction)

Session (Day 70):
- Keys only: date, topic, outcome
- Storage: 0.5KB (97.5% reduction)

Query (Day 100):
User: "What did we discuss on Day 1?"
Result: "Session on 2025-10-17 about memory architecture. Outcome: Decided to use 3-layer hybrid RAG. [Full transcript archived - available on request]"
```

### 5.6 Portability (Multi-Model)

**As a user**, I want to switch from ChatGPT to Claude without losing memory, so I'm not vendor-locked.

**Acceptance Criteria**:
- ✅ Same MCP server works with ChatGPT, Claude, Gemini
- ✅ Memory stored in Obsidian (markdown), not vendor API
- ✅ Switch models in <1 minute (update MCP config)
- ✅ All memory types preserved (preferences, facts, episodic)
- ✅ No data migration required

**Example**:
```bash
# Week 1: Using ChatGPT
# config/mcp_config.json points to OpenAI

# Week 2: Switch to Claude
# Edit config/mcp_config.json → point to Anthropic
# Restart MCP server

# Result: Claude has access to all memory from ChatGPT sessions
# No data migration, no loss of context
```

---

## 6. Constraints & Assumptions

### 6.1 Technical Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| **C-01** | Self-hosted only | Privacy requirement (no external APIs) |
| **C-02** | Docker required | Deployment simplicity (one-command setup) |
| **C-03** | Markdown storage | Portability requirement (human-readable) |
| **C-04** | Local embeddings | Privacy (no data to OpenAI) + cost ($0) |
| **C-05** | ≤60 LOC per function | NASA Rule 10 compliance |
| **C-06** | No proprietary APIs | Portability (survive vendor changes) |

### 6.2 Assumptions

| ID | Assumption | Risk if Wrong |
|----|-----------|---------------|
| **A-01** | User has Obsidian installed | Manual install required (docs cover this) |
| **A-02** | User has Docker installed | Setup script can install Docker |
| **A-03** | User willing to curate manually | System falls back to passive (lower quality) |
| **A-04** | User has ≥8GB RAM | Reduce to 4GB (use smaller models) |
| **A-05** | User has ≥20GB disk space | Storage growth monitored, alert user |
| **A-06** | User prefers privacy over cloud | Offer cloud option (Pinecone, etc.) |

### 6.3 Out of Scope (Phase 1)

**Not included in initial 12-week MVP**:
- ❌ Mobile app (desktop/web only)
- ❌ Collaborative features (single-user only)
- ❌ Cloud deployment (self-hosted only)
- ❌ Real-time collaboration (async only)
- ❌ Advanced NLP (LLM-based entity extraction)
- ❌ Custom embedding models (use Sentence-Transformers)
- ❌ Voice interface (text only)
- ❌ Auto-curation (human-in-loop required)

**Deferred to Phase 2** (post-MVP):
- Multi-user support
- Cloud sync (optional)
- Advanced entity extraction (LLM-based)
- Auto-curation experiments
- Mobile companion app
- Plugin ecosystem

---

## 7. Edge Cases & Error Handling

### 7.1 Edge Cases

| ID | Edge Case | Handling Strategy |
|----|-----------|-------------------|
| **E-01** | Obsidian vault deleted | Rebuild from backup (if exists), else start fresh |
| **E-02** | Neo4j crashes during query | Fallback to vector-only retrieval (graceful degradation) |
| **E-03** | Qdrant full (disk space) | Alert user, auto-archive old sessions, compress vectors |
| **E-04** | Duplicate Obsidian note names | Append UUID to filename, warn user |
| **E-05** | Circular graph references | Detect cycles (DFS), limit graph traversal depth to 5 hops |
| **E-06** | Malformed frontmatter | Parse best-effort, log warning, prompt user to fix |
| **E-07** | Query timeout (>10s) | Return partial results, log slow query, suggest optimization |
| **E-08** | Embedding model download failure | Fallback to cached model, retry download in background |

### 7.2 Error Handling Principles

**Graceful Degradation**:
- If Neo4j down → Use vector-only retrieval
- If Qdrant down → Use Neo4j-only retrieval
- If both down → Return cached results (if available)

**User Feedback**:
- Clear error messages (no stack traces to end user)
- Actionable suggestions ("Run `docker-compose up` to start services")
- Logging for debugging (DEBUG level in production)

**Retries**:
- Network errors: 3 retries with exponential backoff
- Database timeouts: 1 retry, then graceful degradation
- File system errors: No retry (likely permission issue), alert user

---

## 8. Testing Requirements

### 8.1 Unit Tests

| Component | Coverage Target | Key Tests |
|-----------|----------------|-----------|
| Chunking | ≥90% | Max-Min Semantic algorithm correctness |
| Embedding | ≥90% | Sentence-Transformers output shape/dtype |
| Entity Extraction | ≥85% | spaCy NER accuracy on test docs |
| Graph Queries | ≥90% | Cypher query correctness, cycle detection |
| Vector Search | ≥90% | Similarity calculation, metadata filtering |
| Bayesian | ≥80% | Belief propagation, confidence scoring |
| Lifecycle Manager | ≥95% | Correct routing by lifecycle tag |
| File Watcher | ≥85% | Detect create/modify/delete events |

### 8.2 Integration Tests

| Workflow | Test Scenario |
|----------|---------------|
| Indexing | Obsidian note → File watcher → Parse → Route → Index (all layers) |
| Retrieval | User query → Mode detect → Recall → Verify → Return |
| Multi-Hop | Complex query → HippoRAG → 3+ hops → Verify → Return |
| Decay | Create session → Wait 30 days (simulated) → Verify compression |
| Portability | ChatGPT query → Switch to Claude → Same results |
| Curation | User tags note → Lifecycle change → Re-index |

### 8.3 E2E Tests

| User Story | E2E Test |
|------------|----------|
| Store preference | Create permanent note → Query via MCP → LLM uses preference |
| Project scope | Create project note → Query with project filter → No leakage |
| Multi-hop | Ask complex question → HippoRAG retrieves path → Verify accuracy |
| Verification | Query critical fact → Two-stage retrieval → Verify flag |
| Forgetting | Create session → Fast-forward 30 days → Verify decay |
| Portability | Use ChatGPT → Switch to Claude → Same memory |

---

## 9. Dependencies

### 9.1 External Dependencies

| Dependency | Version | Purpose | License |
|------------|---------|---------|---------|
| Python | 3.11+ | Core runtime | PSF |
| Docker | 20.10+ | Deployment | Apache 2.0 |
| Docker Compose | 2.0+ | Multi-container orchestration | Apache 2.0 |
| Qdrant | 1.7+ | Vector database | Apache 2.0 |
| Neo4j | 5.0+ | Graph database | GPL/Commercial |
| Sentence-Transformers | 2.2+ | Embeddings | Apache 2.0 |
| spaCy | 3.7+ | Entity extraction | MIT |
| Relik | 1.0+ | Entity linking | Apache 2.0 |
| HippoRAG | 1.0+ | Multi-hop reasoning | MIT |
| pgmpy | 0.1.23+ | Bayesian networks | MIT |
| FastAPI | 0.104+ | API server | MIT |
| React | 18+ | Curation UI | MIT |
| Obsidian | 1.4+ | Knowledge management | Proprietary (free) |

### 9.2 Infrastructure Dependencies

| Component | Resource | Requirement |
|-----------|----------|-------------|
| CPU | Cores | 4+ (8+ recommended) |
| RAM | Memory | 8GB (16GB recommended) |
| Disk | Storage | 20GB (50GB recommended) |
| Network | Bandwidth | 10Mbps (local, no internet needed) |
| OS | Platform | Linux, macOS, Windows (WSL2) |

---

## 10. Success Metrics

### 10.1 Technical Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Vector search latency | <200ms (p95) | Prometheus + Grafana |
| Graph query latency | <500ms (p95) | Prometheus + Grafana |
| Multi-hop latency | <2s (p95) | Prometheus + Grafana |
| Retrieval recall@10 | ≥85% | Offline eval on test set |
| Multi-hop accuracy | ≥85% | Human eval on complex queries |
| Memory usage | <2GB RAM | Docker stats |
| Storage growth | <10MB/1000 docs | Disk usage monitoring |
| Indexing throughput | ≥100 docs/min | File watcher logs |

### 10.2 User Satisfaction Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Setup time | <30 minutes | Timed user test (5 users) |
| Query success rate | ≥90% | User reports "found what I needed" |
| Portability success | 100% | Switch ChatGPT→Claude→Gemini test |
| Curation time | <5 min/day | User self-report (survey) |
| False positive rate | <5% | User flags incorrect results |
| Hallucination rate | <1% | Manual audit of 100 queries |

### 10.3 Business Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Cost | $0/month | Self-hosted, free models (vs $20-30/month SaaS) |
| Privacy score | 100% | No data leaves local system |
| Vendor lock-in | 0% | MCP + markdown = portable |
| Time to value | <1 hour | Setup + first useful query |

---

## 11. Pseudocode Modules

### 11.1 Module: Chunking Pipeline

**File**: `1_chunking_pipeline.md`

**Purpose**: Implement Max-Min Semantic chunking (0.90 AMI score)

**Inputs**:
- `document: str` (markdown content)
- `max_chunk_size: int = 500` (tokens)
- `min_chunk_size: int = 200` (tokens)

**Outputs**:
- `chunks: List[str]` (semantically coherent chunks)

**Pseudocode**:
```python
FUNCTION chunk_document(document: str, max_size: int, min_size: int) -> List[str]:
    # Parse markdown into sections
    sections = parse_markdown_sections(document)

    chunks = []
    current_chunk = ""

    FOR EACH section IN sections:
        # Calculate semantic similarity with current chunk
        similarity = cosine_similarity(
            embed(current_chunk),
            embed(section)
        )

        # If similar, merge; else create new chunk
        IF similarity > 0.7 AND len(current_chunk) < max_size:
            current_chunk += "\n" + section
        ELSE:
            IF len(current_chunk) >= min_size:
                chunks.append(current_chunk)
            current_chunk = section

    # Add final chunk
    IF len(current_chunk) >= min_size:
        chunks.append(current_chunk)

    RETURN chunks
```

**Tests**:
- ✅ Chunk size within [200, 500] tokens
- ✅ Semantic coherence (similarity within chunk >0.7)
- ✅ Edge case: document <200 tokens (return as single chunk)

### 11.2 Module: Lifecycle Router

**File**: `2_lifecycle_router.md`

**Purpose**: Route notes to appropriate storage based on lifecycle

**Inputs**:
- `file_path: str` (Obsidian note path)
- `metadata: dict` (parsed frontmatter)

**Outputs**:
- `storage_actions: List[Action]` (where to index)

**Pseudocode**:
```python
FUNCTION route_by_lifecycle(file_path: str, metadata: dict) -> List[Action]:
    lifecycle = metadata.get("lifecycle", "ephemeral")  # Default
    content = read_file(file_path)

    actions = []

    IF lifecycle == "permanent":
        # Key-value store (Redis)
        actions.append(Action(
            type="redis_set",
            key=metadata["title"],
            value=content
        ))

    ELIF lifecycle == "temporary":
        # Graph + Vector
        actions.append(Action(
            type="neo4j_create_node",
            node_type=metadata.get("type", "Note"),
            properties=metadata,
            content=content
        ))
        actions.append(Action(
            type="qdrant_index",
            collection="temporary",
            embedding=embed(content),
            metadata=metadata
        ))

    ELIF lifecycle == "ephemeral":
        # Vector only
        actions.append(Action(
            type="qdrant_index",
            collection="ephemeral",
            embedding=embed(content),
            metadata={**metadata, "ttl": 30}  # 30-day expiry
        ))

    RETURN actions
```

**Tests**:
- ✅ Permanent → Redis only
- ✅ Temporary → Neo4j + Qdrant
- ✅ Ephemeral → Qdrant only (with TTL)
- ✅ Default (no lifecycle tag) → Ephemeral

### 11.3 Module: Two-Stage Retrieval

**File**: `3_two_stage_retrieval.md`

**Purpose**: Recall + verify to prevent hallucinations

**Inputs**:
- `query: str` (user question)
- `require_verification: bool = True`

**Outputs**:
- `results: List[Result]` (verified documents with confidence scores)

**Pseudocode**:
```python
FUNCTION retrieve_verified(query: str, require_verification: bool) -> List[Result]:
    # Stage 1: Recall candidates (semantic search)
    candidates = qdrant.search(
        query=embed(query),
        limit=20,
        threshold=0.65
    )

    IF NOT require_verification:
        RETURN candidates  # Fast path

    # Stage 2: Verify against ground truth
    verified_results = []

    FOR EACH candidate IN candidates:
        is_verified = verify_fact(candidate)

        verified_results.append(Result(
            content=candidate["content"],
            metadata=candidate["metadata"],
            verified=is_verified,
            confidence=1.0 IF is_verified ELSE 0.6
        ))

    # Sort by confidence (verified first)
    verified_results.sort(key=lambda r: r.confidence, reverse=True)

    RETURN verified_results


FUNCTION verify_fact(candidate: dict) -> bool:
    fact_type = candidate["metadata"].get("type")

    IF fact_type == "decision":
        # Query Neo4j for decision node
        result = neo4j.query(
            "MATCH (d:Decision {title: $title}) RETURN d",
            title=candidate["metadata"]["title"]
        )
        RETURN result IS NOT NULL

    ELIF fact_type == "fact":
        # Query structured database
        result = postgres.query(
            "SELECT * FROM facts WHERE id = %s",
            candidate["metadata"]["id"]
        )
        RETURN result IS NOT NULL

    ELSE:
        # No verification needed (e.g., brainstorming)
        RETURN True
```

**Tests**:
- ✅ Verified facts have confidence=1.0
- ✅ Unverified facts have confidence<0.7
- ✅ Verified facts returned first (sorted)
- ✅ Hallucination logged when verification fails

### 11.4 Module: Mode-Aware Routing

**File**: `4_mode_aware_routing.md`

**Purpose**: Detect mode (planning/execution) and adjust retrieval strategy

**Inputs**:
- `query: str` (user question)
- `mode: str = "auto"` (manual override)

**Outputs**:
- `results: List[Result]` (mode-appropriate retrieval)

**Pseudocode**:
```python
FUNCTION mode_aware_retrieve(query: str, mode: str = "auto") -> List[Result]:
    # Auto-detect mode if not specified
    IF mode == "auto":
        mode = detect_mode(query)

    # Route based on mode
    IF mode == "planning":
        RETURN planning_retrieval(query)
    ELIF mode == "execution":
        RETURN execution_retrieval(query)
    ELSE:
        RETURN default_retrieval(query)


FUNCTION detect_mode(query: str) -> str:
    planning_keywords = ["brainstorm", "explore", "alternatives", "ideas", "research"]
    execution_keywords = ["implement", "deploy", "execute", "build", "create"]

    query_lower = query.lower()

    FOR EACH keyword IN planning_keywords:
        IF keyword IN query_lower:
            RETURN "planning"

    FOR EACH keyword IN execution_keywords:
        IF keyword IN query_lower:
            RETURN "execution"

    RETURN "default"


FUNCTION planning_retrieval(query: str) -> List[Result]:
    # Breadth: diverse results, lower threshold
    RETURN qdrant.search(
        query=embed(query),
        limit=20,
        threshold=0.65,
        diversity_score=0.7
    )


FUNCTION execution_retrieval(query: str) -> List[Result]:
    # Precision: focused results, high threshold
    RETURN qdrant.search(
        query=embed(query),
        limit=5,
        threshold=0.85,
        diversity_score=0.2
    )
```

**Tests**:
- ✅ "Brainstorm ideas" → Planning mode (top-k=20)
- ✅ "Implement feature X" → Execution mode (top-k=5)
- ✅ Manual override works (`mode="planning"`)
- ✅ Default mode for ambiguous queries

### 11.5 Module: Forgetting Mechanism

**File**: `5_forgetting_mechanism.md`

**Purpose**: Structured decay (keep keys, discard details)

**Inputs**:
- `session_id: str`
- `days_old: int`

**Outputs**:
- `decay_action: Action` (compress/archive/keep)

**Pseudocode**:
```python
FUNCTION apply_decay(session_id: str, days_old: int) -> Action:
    # Exponential decay (30-day half-life)
    decay_factor = exp(-days_old / 30)

    session = get_session(session_id)

    IF decay_factor < 0.1:
        # Full decay: keys only
        RETURN compress_to_keys(session)

    ELIF decay_factor < 0.5:
        # Partial decay: summary + keys
        RETURN compress_to_summary(session)

    ELSE:
        # No decay: keep full detail
        RETURN Action(type="keep", session_id=session_id)


FUNCTION compress_to_keys(session: dict) -> Action:
    keys = {
        "date": session["date"],
        "topic": session["topic"],
        "outcome": session["outcome"],
        "tags": session["tags"],
        "participants": session["participants"]
    }

    RETURN Action(
        type="archive",
        session_id=session["id"],
        keep=keys,
        discard=session["transcript"]
    )


FUNCTION compress_to_summary(session: dict) -> Action:
    summary = llm.summarize(
        session["transcript"],
        max_length=200  # words
    )

    keys = compress_to_keys(session)["keep"]

    RETURN Action(
        type="compress",
        session_id=session["id"],
        keep={**keys, "summary": summary},
        discard=session["transcript"]
    )
```

**Tests**:
- ✅ <10 days: Full detail kept
- ✅ 30-45 days: Summary + keys
- ✅ >60 days: Keys only
- ✅ Manual pin prevents decay

---

## 12. Acceptance Criteria (Loop 1 → Loop 2 Handoff)

**Loop 1 is complete when**:
- ✅ Specification document created (`SPEC-v1-MEMORY-MCP-TRIPLE-SYSTEM.md`)
- ✅ Research complete (`hybrid-rag-research.md`, `memory-wall-principles.md`)
- ✅ Pre-mortem generated (risks identified, mitigations planned)
- ✅ All functional requirements documented (FR-01 to FR-56)
- ✅ All non-functional requirements documented (NFR-01 to NFR-30)
- ✅ System architecture diagram created
- ✅ Pseudocode modules outlined (5 core modules)
- ✅ User stories written (6 primary scenarios)
- ✅ Success metrics defined (technical, user, business)
- ✅ GO/NO-GO decision made (based on risk score)

**Handoff to Loop 2**:
- **Input**: This specification document + research + pre-mortem
- **Expected Output**: Implementation (code, tests, deployment)
- **Agents Needed**: devops, backend-dev, coder, ml-developer, frontend-dev, tester
- **Timeline**: 12 weeks (Phase 1: 4 weeks, Phase 2: 4 weeks, Phase 3: 4 weeks)

---

**Version**: 1.0
**Date**: 2025-10-17
**Status**: ✅ COMPLETE - Ready for Pre-Mortem
**Next Step**: Generate pre-mortem risk analysis
**Agent**: spec-writer (Claude Sonnet 4.5)
**Methodology**: SPARC Specification Phase
