# Memory MCP Triple System - Canonical Architecture

**Version**: 1.0.0
**Last Updated**: 2025-11-25
**ADR Reference**: ARCHITECTURE-DECISION.md

---

## Overview

Memory MCP Triple System is a unified multi-model RAG memory system that combines:

1. **Vector RAG** - Dense semantic search (ChromaDB)
2. **HippoRAG** - Multi-hop graph reasoning (NetworkX)
3. **Bayesian RAG** - Probabilistic inference (pgmpy)

With metadata features for:
- **Time-based decay** - Memories fade over time
- **P/E/S categories** - Procedural/Episodic/Semantic classification
- **WHO/WHEN/PROJECT/WHY** - Rich tagging protocol

---

## System Architecture

```
+------------------------------------------------------------------+
|                     MEMORY MCP TRIPLE SYSTEM                      |
+------------------------------------------------------------------+
|                                                                  |
|  +--------------------+                                          |
|  |   MCP INTERFACE    |  <-- Claude Desktop / Claude Code        |
|  |   (stdio_server)   |                                          |
|  +--------+-----------+                                          |
|           |                                                      |
|           v                                                      |
|  +--------------------+                                          |
|  |  NEXUS PROCESSOR   |  <-- 5-Step SOP Pipeline                 |
|  |  (src/nexus/)      |                                          |
|  +--------+-----------+                                          |
|           |                                                      |
|     +-----+-----+---------------------+                          |
|     |           |                     |                          |
|     v           v                     v                          |
|  +------+    +--------+    +----------+                          |
|  |VECTOR|    |HIPPORAG|    | BAYESIAN |                          |
|  | TIER |    |  TIER  |    |   TIER   |                          |
|  +------+    +--------+    +----------+                          |
|  Chroma      NetworkX       pgmpy                                |
|  Weight:0.4  Weight:0.4     Weight:0.2                           |
|                                                                  |
+------------------------------------------------------------------+
```

---

## Core Components

### 1. Retrieval Tiers

#### Vector Tier (Weight: 0.4)

**Purpose**: Dense semantic similarity search

**Technology**: ChromaDB (embedded)

**How it works**:
1. Query text -> Embedding (sentence-transformers)
2. Cosine similarity search in vector space
3. Returns top-K most similar chunks

**File**: `src/indexing/vector_indexer.py`

```python
# Example usage
results = vector_indexer.search_similar(
    query_embedding=embed("What is memory?"),
    top_k=50
)
```

#### HippoRAG Tier (Weight: 0.4)

**Purpose**: Multi-hop graph reasoning

**Technology**: NetworkX (in-memory graph)

**How it works**:
1. Extract entities from query
2. Find entity nodes in knowledge graph
3. Run Personalized PageRank (PPR) from seed nodes
4. Retrieve chunks connected to high-PPR nodes

**File**: `src/services/graph_query_engine.py`

```python
# Example usage
results = graph_engine.retrieve_multi_hop(
    query="How does memory decay?",
    top_k=50,
    max_hops=3
)
```

#### Bayesian Tier (Weight: 0.2)

**Purpose**: Probabilistic inference and uncertainty

**Technology**: pgmpy (Bayesian networks)

**How it works**:
1. Build Bayesian network from knowledge graph
2. Extract query variables
3. Run probabilistic inference (Variable Elimination)
4. Return probability distributions

**File**: `src/bayesian/probabilistic_query_engine.py`

**Status**: Partially implemented (CPD estimation needs real data)

```python
# Example usage
results = bayes_engine.query_conditional(
    network=bayesian_network,
    query_vars=["memory_type"],
    evidence={"context": "long_term"}
)
```

---

### 2. Nexus Processor (5-Step SOP)

**File**: `src/nexus/processor.py`

The Nexus Processor orchestrates all 3 tiers through a 5-step pipeline:

```
Step 1: RECALL
  - Query all 3 tiers
  - Collect top-50 candidates per tier
  - ~150 total candidates

Step 2: FILTER
  - Remove low-confidence results
  - Threshold: 0.3
  - Typically 60-100 candidates remain

Step 3: DEDUPLICATE
  - Remove near-duplicates
  - Cosine similarity threshold: 0.95
  - Typically 40-60 unique candidates

Step 4: RANK
  - Weighted scoring
  - hybrid_score = (V * 0.4) + (H * 0.4) + (B * 0.2)
  - Sort by hybrid_score descending

Step 5: COMPRESS
  - Mode-aware selection
  - Execution: 5 core, 0 extended
  - Planning: 5 core, 15 extended
  - Brainstorming: 5 core, 25 extended
  - Enforce 10K token budget
```

---

### 3. Query Modes

| Mode | Core | Extended | Threshold | Use Case |
|------|------|----------|-----------|----------|
| **Execution** | 5 | 0 | 0.85 | Factual retrieval ("What is X?") |
| **Planning** | 5 | 15 | 0.65 | Decision support ("How should X?") |
| **Brainstorming** | 5 | 25 | 0.50 | Creative exploration ("What if X?") |

**Auto-detection**: Query keywords determine mode automatically.

---

### 4. Metadata Features

#### Time-Based Decay (from Architecture Option B)

Every chunk has temporal metadata:

```python
{
    "created_at": "2025-11-25T12:00:00Z",
    "retention_tier": "short",  # short|mid|long
    "decay_score": 1.0  # Calculated: e^(-days/30)
}
```

**Retention Tiers**:
- **Short-term**: 0-24 hours, full content, decay_score ~1.0
- **Mid-term**: 1-7 days, full content, decay_score ~0.8
- **Long-term**: 7+ days, compressed, decay_score < 0.8

#### P/E/S Categories (from Architecture Option C)

Chunks are categorized by content type:

```python
{
    "category": "semantic"  # procedural|episodic|semantic
}
```

**Category Definitions**:
- **Procedural**: How-to, instructions, steps (execution state)
- **Episodic**: Events, history, timeline (what happened)
- **Semantic**: Concepts, definitions, facts (meaning)

#### WHO/WHEN/PROJECT/WHY Tagging

Every memory storage includes:

```python
{
    "agent": {
        "name": "coder",
        "category": "code-quality"
    },
    "timestamp": {
        "iso": "2025-11-25T12:00:00Z",
        "unix": 1732536000,
        "readable": "2025-11-25 12:00:00"
    },
    "project": "memory-mcp-triple-system",
    "intent": "implementation"
}
```

---

## MCP Tools

### Available Tools

| Tool | Description | Status |
|------|-------------|--------|
| `vector_search` | Semantic similarity search | WORKING (v1.4.0) |
| `memory_store` | Store with metadata tagging | WORKING (v1.4.0) |
| `detect_mode` | Query mode detection | WORKING (v1.4.0) |
| `graph_query` | HippoRAG multi-hop query | PARTIAL (GraphService exists, PPR incomplete) |
| `bayesian_inference` | Probabilistic query | PARTIAL (NetworkBuilder exists, CPD needs data) |
| `entity_extraction` | NER from text | STUBBED (interface defined, implementation pending) |
| `hipporag_retrieve` | Full HippoRAG pipeline | STUBBED (depends on graph_query completion) |

### Usage Examples

```python
# Vector search
results = await mcp__memory-mcp__vector_search(
    query="What is semantic memory?",
    limit=10
)

# Store with tagging
await mcp__memory-mcp__memory_store(
    text="Semantic memory stores concepts and facts.",
    metadata={
        "agent": {"name": "coder"},
        "project": "memory-mcp",
        "intent": "documentation"
    }
)
```

---

## Directory Structure

```
memory-mcp-triple-system/
|-- config/
|   |-- memory-mcp.yaml       # Main configuration
|-- src/
|   |-- __init__.py           # Package init
|   |-- nexus/
|   |   |-- processor.py      # 5-Step SOP pipeline
|   |-- indexing/
|   |   |-- vector_indexer.py # ChromaDB indexing
|   |   |-- embedding_pipeline.py
|   |-- bayesian/
|   |   |-- network_builder.py    # Graph -> BN conversion
|   |   |-- probabilistic_query_engine.py
|   |-- services/
|   |   |-- graph_query_engine.py # HippoRAG retrieval
|   |   |-- hipporag_service.py
|   |-- mcp/
|   |   |-- server.py         # FastAPI MCP server
|   |   |-- stdio_server.py   # stdio MCP server
|   |   |-- tools/
|   |       |-- vector_search.py
|   |-- chunking/
|   |   |-- semantic_chunker.py
|   |-- memory/
|   |   |-- lifecycle_manager.py
|   |-- modes/
|       |-- mode_detector.py
|       |-- mode_profile.py
|-- tests/
|   |-- unit/
|   |-- integration/
|-- docs/
|   |-- ARCHITECTURE.md       # This file
|   |-- ARCHITECTURE-DECISION.md
|   |-- REMEDIATION-PLAN.md
|-- migrations/
|-- scripts/
```

---

## Configuration

**File**: `config/memory-mcp.yaml`

```yaml
# Vector Tier
vector:
  collection_name: memory_chunks
  embedding_model: all-MiniLM-L6-v2
  dimension: 384

# HippoRAG Tier
hipporag:
  graph_path: data/knowledge_graph.gpickle
  max_hops: 3
  ppr_alpha: 0.85

# Bayesian Tier
bayesian:
  max_nodes: 1000
  min_edge_confidence: 0.3
  cache_ttl_hours: 1

# Nexus Processor
nexus:
  weights:
    vector: 0.4
    hipporag: 0.4
    bayesian: 0.2
  confidence_threshold: 0.3
  dedup_threshold: 0.95

# Query Modes
modes:
  execution:
    core_k: 5
    extended_k: 0
    threshold: 0.85
  planning:
    core_k: 5
    extended_k: 15
    threshold: 0.65
  brainstorming:
    core_k: 5
    extended_k: 25
    threshold: 0.50

# Time Decay
decay:
  formula: exponential  # e^(-days/30)
  short_term_hours: 24
  mid_term_days: 7
  long_term_days: 30

# MCP Server
mcp:
  server:
    host: localhost
    port: 8080
```

---

## Key Differences from Previous Documentation

| Previous Doc | Claimed | Actual |
|--------------|---------|--------|
| `src/__init__.py` | Qdrant + Neo4j | ChromaDB + NetworkX |
| `TRUE-ARCHITECTURE.md` | Time-based only | Time-based is FEATURE |
| `OBSIDIAN-INTEGRATION.md` | P/E/S layers | P/E/S is METADATA |

**Canonical Truth**: This document (ARCHITECTURE.md)

---

## References

- **ADR**: `docs/ARCHITECTURE-DECISION.md`
- **Remediation Plan**: `docs/REMEDIATION-PLAN.md`
- **Issues Tracker**: `docs/MECE-CONSOLIDATED-ISSUES.md`
- **HippoRAG Paper**: https://arxiv.org/abs/2402.02713

---

**Status**: CANONICAL - This is the authoritative architecture reference.
