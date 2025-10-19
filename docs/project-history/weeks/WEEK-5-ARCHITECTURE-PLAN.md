# Week 5-6 Architecture Plan: HippoRAG + Two-Stage Verification

**Project**: Memory MCP Triple System v5.0
**Date**: 2025-10-18
**Weeks**: 5-6 of 8 (HippoRAG Implementation)
**Methodology**: SPARC - Architecture Phase
**Research Agent**: Claude Sonnet 4.5

---

## Executive Summary

### Objective

Implement **HippoRAG (NeurIPS'24)** - a neurobiologically-inspired retrieval framework that combines knowledge graphs with Personalized PageRank for **multi-hop reasoning** and **context-aware retrieval**. Integrate with existing ChromaDB vector search to create a **two-stage verification system**.

### Design Principles

1. **Research-Backed**: Based on NeurIPS'24 paper (OSU-NLP-Group/HippoRAG)
2. **Pragmatic Integration**: Reuse existing GraphService (NetworkX) + EntityService (spaCy)
3. **Performance First**: <100ms graph queries, 10-30x faster than iterative retrieval
4. **NASA Rule 10**: All functions ≤60 LOC (maintain 95%+ compliance)

### Key Innovation

HippoRAG **mimics human hippocampal memory** by using:
- **Neocortex** = LLM for entity extraction (we use spaCy NER instead)
- **Parahippocampal Regions** = Retrieval encoders for synonymy detection (ChromaDB embeddings)
- **Hippocampus** = Knowledge Graph + Personalized PageRank for context-based recall

**Performance Target**: Up to **20% improvement** on multi-hop QA vs. standard RAG

---

## 1. HippoRAG Overview

### 1.1 What is HippoRAG?

**HippoRAG** (Hippocampal Indexing for Retrieval-Augmented Generation) is a novel RAG framework inspired by the **hippocampal indexing theory** of human long-term memory. Published at NeurIPS'24 by OSU-NLP-Group, it enables LLMs to continuously integrate knowledge across external documents through graph-based reasoning.

**Core Innovation**: Instead of flat vector similarity (standard RAG), HippoRAG uses a **knowledge graph + Personalized PageRank** to capture multi-hop relationships between entities, mimicking how the human hippocampus indexes and retrieves episodic memories.

**Example Multi-Hop Question**:
```
Query: "What company did the founder of Tesla previously start?"

Standard RAG:
1. Find chunks mentioning "Tesla founder" → Returns Elon Musk
2. STOP (requires iterative retrieval or chain-of-thought)

HippoRAG:
1. Extract entity: "Tesla" → Graph node
2. Run Personalized PageRank from "Tesla" node
3. Graph traversal finds: Tesla --founded_by--> Elon Musk --founded--> PayPal/Zip2
4. Returns all connected passages in ONE step (no iteration)
```

### 1.2 Why HippoRAG is Better Than Standard RAG

| Aspect | Standard RAG | HippoRAG | Improvement |
|--------|-------------|----------|-------------|
| **Multi-hop QA** | Requires iterative retrieval | Single-step graph traversal | **10-30x faster** |
| **Context awareness** | Flat similarity matching | Graph relationships preserved | **+20% accuracy** |
| **Computational cost** | Multiple LLM calls for hops | One PageRank computation | **10-30x cheaper** |
| **Knowledge integration** | Independent chunks | Connected knowledge graph | **Continuous learning** |
| **Synonymy handling** | Embedding similarity only | Explicit synonymy edges | **Better recall** |

**Benchmark Results (NeurIPS'24 Paper)**:
- Multi-hop QA: +20% over standard RAG
- Single-step retrieval: Comparable to iterative IRCoT
- Speed: 6-13x faster than iterative methods
- Cost: 10-30x cheaper (fewer LLM calls)

### 1.3 How HippoRAG Uses Knowledge Graphs

**Graph Structure** (schemaless):
```
Nodes:
- Entities (PERSON, ORG, GPE, etc.) - extracted by spaCy NER
- Chunks (memory passages) - from Obsidian vault

Edges (4 types):
- MENTIONS: Chunk → Entity (e.g., chunk_123 --mentions--> "Elon Musk")
- RELATED_TO: Entity → Entity (e.g., "Tesla" --related_to--> "SpaceX")
- SIMILAR_TO: Entity → Entity (semantic similarity from embeddings)
- SYNONYMY: Entity → Entity (e.g., "USA" --synonymy--> "United States")
```

**Key Advantage**: Graph captures **relational context** that embeddings alone cannot:
- "Steve Jobs founded Apple" + "Apple is a tech company" + "iPhone is Apple product"
- Query: "What phone did Steve Jobs create?" → Graph traversal finds connection via Apple

**Personalized PageRank Role**:
- Standard PageRank: Global importance (like Google's original algorithm)
- **Personalized PageRank**: Importance **relative to query entities**
- Biases random walk to start from query-relevant nodes → surfaces connected facts

---

## 2. Architecture Design

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  HippoRAG Two-Stage Retrieval                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              STAGE 1: Vector Retrieval                    │  │
│  │  (Existing ChromaDB - Week 2)                             │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  Query → EmbeddingPipeline → ChromaDB.query()            │  │
│  │  Returns: Top-K chunks (K=20) with similarity scores      │  │
│  └───────────────────┬──────────────────────────────────────┘  │
│                      │                                           │
│                      ↓                                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │       STAGE 2: Graph-Based Verification (HippoRAG)        │  │
│  │  (NEW - Week 5-6)                                         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  1. Extract query entities (EntityService + spaCy NER)   │  │
│  │  2. Match entities to graph nodes (embedding similarity) │  │
│  │  3. Run Personalized PageRank from query nodes           │  │
│  │  4. Rank chunks by PPR scores                            │  │
│  │  5. Combine with Stage 1 scores (weighted fusion)        │  │
│  └───────────────────┬──────────────────────────────────────┘  │
│                      │                                           │
│                      ↓                                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Final Ranked Results                         │  │
│  │  - Verified chunks (graph + vector agreement)            │  │
│  │  - Confidence scores (0.0-1.0)                           │  │
│  │  - Multi-hop context (connected entities)                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Supporting Services (Weeks 1-4):
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ GraphService │  │EntityService │  │VectorIndexer │
│ (NetworkX)   │  │ (spaCy NER)  │  │ (ChromaDB)   │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 Component Responsibilities

#### 2.2.1 HippoRagService (NEW)

**Purpose**: Core HippoRAG retrieval orchestrator

**Responsibilities**:
1. Extract entities from query (via EntityService)
2. Match query entities to graph nodes (embedding similarity)
3. Run Personalized PageRank from query nodes
4. Rank passages by PPR scores
5. Fuse with Stage 1 vector scores

**Key Methods**:
```python
class HippoRagService:
    def __init__(
        self,
        graph_service: GraphService,
        entity_service: EntityService,
        vector_indexer: VectorIndexer
    )

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        alpha: float = 0.85
    ) -> List[RetrievalResult]

    def _extract_query_entities(self, query: str) -> List[str]
    def _match_entities_to_nodes(self, entities: List[str]) -> List[str]
    def _run_personalized_pagerank(
        self,
        query_nodes: List[str],
        alpha: float
    ) -> Dict[str, float]
    def _rank_chunks_by_ppr(
        self,
        ppr_scores: Dict[str, float]
    ) -> List[Tuple[str, float]]
    def _fuse_scores(
        self,
        vector_results: List[Dict],
        graph_results: List[Tuple[str, float]]
    ) -> List[RetrievalResult]
```

**LOC Estimate**: ~250 LOC (6 methods × ~40 LOC each)

---

#### 2.2.2 GraphQueryEngine (NEW)

**Purpose**: Specialized graph query operations for retrieval

**Responsibilities**:
1. Multi-hop path finding (2-3 hop queries)
2. Entity neighborhood extraction
3. Subgraph relevance scoring
4. Synonymy edge traversal

**Key Methods**:
```python
class GraphQueryEngine:
    def __init__(self, graph_service: GraphService)

    def find_multihop_paths(
        self,
        source_nodes: List[str],
        max_hops: int = 3
    ) -> List[List[str]]

    def get_entity_neighborhood(
        self,
        entity_id: str,
        depth: int = 2
    ) -> Dict[str, Any]

    def find_connecting_paths(
        self,
        entity_a: str,
        entity_b: str
    ) -> List[List[str]]

    def expand_via_synonymy(
        self,
        entity_id: str
    ) -> Set[str]
```

**LOC Estimate**: ~180 LOC (4 methods × ~45 LOC each)

---

#### 2.2.3 TwoStageCoordinator (NEW)

**Purpose**: Orchestrate Stage 1 (vector) + Stage 2 (graph) retrieval

**Responsibilities**:
1. Call Stage 1 vector search (existing VectorSearchTool)
2. Call Stage 2 graph retrieval (HippoRagService)
3. Score fusion (weighted combination)
4. Confidence calculation
5. Result deduplication and ranking

**Key Methods**:
```python
class TwoStageCoordinator:
    def __init__(
        self,
        vector_search_tool: VectorSearchTool,
        hipporag_service: HippoRagService
    )

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.4,
        graph_weight: float = 0.6
    ) -> List[RetrievalResult]

    def _stage1_vector_retrieval(
        self,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]

    def _stage2_graph_retrieval(
        self,
        query: str,
        limit: int
    ) -> List[Tuple[str, float]]

    def _fuse_scores(
        self,
        vector_results: List[Dict],
        graph_results: List[Tuple[str, float]],
        vector_weight: float,
        graph_weight: float
    ) -> List[RetrievalResult]

    def _calculate_confidence(
        self,
        vector_score: float,
        graph_score: float,
        agreement_level: float
    ) -> float
```

**LOC Estimate**: ~220 LOC (5 methods × ~44 LOC each)

---

### 2.3 Data Flow: Query → Vector Retrieval → Graph Reasoning → Response

**Step-by-Step Workflow**:

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT: User Query                                               │
│ Example: "What company did Elon Musk start before Tesla?"      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: Vector Retrieval (ChromaDB)                           │
├─────────────────────────────────────────────────────────────────┤
│ 1. Query embedding: EmbeddingPipeline.encode_single(query)     │
│ 2. Similarity search: ChromaDB.query(embedding, n_results=20)  │
│ 3. Returns: Top-20 chunks with cosine similarity scores        │
│                                                                 │
│ Example Results:                                                │
│ - Chunk A: "Elon Musk founded Tesla in 2003" (score: 0.85)    │
│ - Chunk B: "PayPal was started by Musk in 1999" (score: 0.72) │
│ - Chunk C: "Zip2 was Musk's first company" (score: 0.68)      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Graph-Based Verification (HippoRAG)                   │
├─────────────────────────────────────────────────────────────────┤
│ Step 2.1: Extract query entities (EntityService)               │
│   - Input: "What company did Elon Musk start before Tesla?"    │
│   - spaCy NER output: ["Elon Musk" (PERSON), "Tesla" (ORG)]   │
│                                                                 │
│ Step 2.2: Match entities to graph nodes                        │
│   - "Elon Musk" → node "elon_musk" (exact match)              │
│   - "Tesla" → node "tesla" (exact match)                       │
│   - Query nodes: ["elon_musk", "tesla"]                        │
│                                                                 │
│ Step 2.3: Run Personalized PageRank                            │
│   - personalization = {"elon_musk": 0.5, "tesla": 0.5}        │
│   - nx.pagerank(graph, personalization=...)                    │
│   - PPR scores (node importance relative to query):            │
│     • elon_musk: 0.25                                          │
│     • tesla: 0.20                                              │
│     • paypal: 0.15 (connected via elon_musk)                  │
│     • zip2: 0.12 (connected via elon_musk)                    │
│     • spacex: 0.10 (connected via elon_musk)                  │
│                                                                 │
│ Step 2.4: Rank chunks by PPR scores                            │
│   - Aggregate PPR scores for entities mentioned in chunks:     │
│     • Chunk A (Tesla): 0.20                                    │
│     • Chunk B (PayPal): 0.15                                   │
│     • Chunk C (Zip2): 0.12                                     │
│                                                                 │
│ Step 2.5: Multi-hop context extraction                         │
│   - Path: elon_musk --founded--> zip2 --timeline--> paypal    │
│   - Path: elon_musk --founded--> paypal --timeline--> tesla   │
│   - Context: Zip2 (1995) → PayPal (1999) → Tesla (2003)      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ SCORE FUSION (Weighted Combination)                            │
├─────────────────────────────────────────────────────────────────┤
│ Formula: final_score = α × vector_score + β × graph_score      │
│ Default weights: α=0.4 (vector), β=0.6 (graph)                │
│                                                                 │
│ Chunk A (Tesla):                                               │
│   - Vector: 0.85, Graph: 0.20                                  │
│   - Final: 0.4×0.85 + 0.6×0.20 = 0.46                         │
│                                                                 │
│ Chunk B (PayPal):                                              │
│   - Vector: 0.72, Graph: 0.15                                  │
│   - Final: 0.4×0.72 + 0.6×0.15 = 0.38                         │
│                                                                 │
│ Chunk C (Zip2):                                                │
│   - Vector: 0.68, Graph: 0.12                                  │
│   - Final: 0.4×0.68 + 0.6×0.12 = 0.34                         │
│                                                                 │
│ Confidence calculation:                                         │
│ - High confidence: Vector + Graph agree (both high scores)     │
│ - Medium: Vector high, Graph low OR vice versa                 │
│ - Low: Both scores low                                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT: Final Ranked Results                                   │
├─────────────────────────────────────────────────────────────────┤
│ Result 1 (Chunk A - Tesla):                                    │
│   - Text: "Elon Musk founded Tesla in 2003..."                │
│   - Final Score: 0.46                                          │
│   - Confidence: 0.82 (high - both stages agree)               │
│   - Context: Connected to PayPal, Zip2 (timeline)             │
│                                                                 │
│ Result 2 (Chunk B - PayPal):                                   │
│   - Text: "PayPal was started by Musk in 1999..."            │
│   - Final Score: 0.38                                          │
│   - Confidence: 0.75 (high - both stages agree)               │
│   - Context: Between Zip2 and Tesla (timeline)                │
│                                                                 │
│ Result 3 (Chunk C - Zip2):                                     │
│   - Text: "Zip2 was Musk's first company..."                 │
│   - Final Score: 0.34                                          │
│   - Confidence: 0.71 (medium-high)                            │
│   - Context: First company, before PayPal                      │
│                                                                 │
│ Multi-hop Answer: "Zip2 (1995) and PayPal (1999) were both    │
│ founded before Tesla (2003)"                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insights**:
1. Stage 1 (vector) finds semantically similar chunks
2. Stage 2 (graph) adds relational context via PPR
3. Fusion balances lexical similarity + structural relationships
4. Confidence scores reflect vector-graph agreement
5. Multi-hop paths provide explanatory context

---

### 2.4 Integration with Existing Services

#### 2.4.1 GraphService Integration

**Existing API (from Week 4)**:
```python
class GraphService:
    def add_chunk_node(chunk_id, metadata) -> bool
    def add_entity_node(entity_id, entity_type, metadata) -> bool
    def add_relationship(source, target, relationship_type, metadata) -> bool
    def get_neighbors(node_id, relationship_type=None) -> List[str]
    def find_path(source, target) -> Optional[List[str]]
    def get_subgraph(node_id, depth=2) -> Dict[str, Any]
    def save_graph(file_path) -> bool
    def load_graph(file_path) -> bool
```

**HippoRAG Usage**:
- **Add synonymy edges**: `add_relationship(entity_a, entity_b, "similar_to")`
- **Find multi-hop paths**: `find_path(source, target)`
- **Get entity neighborhoods**: `get_subgraph(node_id, depth=2)`
- **PageRank input**: `graph_service.graph` (NetworkX DiGraph object)

**New Enhancement Required**:
- Add `get_graph()` method to expose underlying NetworkX graph for PageRank:
  ```python
  def get_graph(self) -> nx.DiGraph:
      """Return underlying NetworkX graph for advanced algorithms."""
      return self.graph
  ```

---

#### 2.4.2 EntityService Integration

**Existing API (from Week 4)**:
```python
class EntityService:
    def extract_entities(text: str) -> List[Dict[str, Any]]
    def extract_entities_by_type(text, entity_types) -> List[Dict]
    def add_entities_to_graph(chunk_id, text, graph_service) -> Dict
    def batch_extract_entities(texts: List[str]) -> List[List[Dict]]
```

**HippoRAG Usage**:
- **Query entity extraction**: `extract_entities(query)` → spaCy NER
- **Entity normalization**: `_normalize_entity_text(entity)` → lowercase, no spaces
- **Batch processing**: `batch_extract_entities([query])` for efficiency

**No changes required** - existing API sufficient for HippoRAG

---

#### 2.4.3 VectorIndexer Integration

**Existing API (from Week 2)**:
```python
class VectorIndexer:
    def add_chunk(chunk_id, text, embedding, metadata) -> bool
    def collection.query(query_embeddings, n_results) -> Dict
```

**HippoRAG Usage**:
- **Stage 1 retrieval**: `collection.query(query_embedding, n_results=20)`
- **Entity similarity**: Use embeddings to find synonymy (cosine similarity >0.9)

**Enhancement for Synonymy Detection**:
- Add method to retrieve entity embeddings by ID:
  ```python
  def get_embedding_by_id(self, entity_id: str) -> Optional[np.ndarray]:
      """Retrieve embedding for entity by ID."""
      result = self.collection.get(ids=[entity_id])
      if result['embeddings']:
          return np.array(result['embeddings'][0])
      return None
  ```

---

## 3. Implementation Checklist

### Week 5 Deliverables (Core HippoRAG)

#### Module 1: HippoRagService Class (Day 1-2)
- [ ] Create `src/services/hipporag_service.py`
- [ ] Implement `__init__(graph_service, entity_service, vector_indexer)`
- [ ] Implement `retrieve(query, top_k, alpha)` (main entry point)
- [ ] Implement `_extract_query_entities(query)` (use EntityService)
- [ ] Implement `_match_entities_to_nodes(entities)` (embedding similarity)
- [ ] Implement `_run_personalized_pagerank(query_nodes, alpha)` (NetworkX)
- [ ] Implement `_rank_chunks_by_ppr(ppr_scores)` (aggregate scores)
- [ ] Unit tests (15 tests): Entity extraction, node matching, PPR execution
- [ ] **LOC Target**: 250 LOC implementation + 180 LOC tests

#### Module 2: GraphQueryEngine (Day 2-3)
- [ ] Create `src/services/graph_query_engine.py`
- [ ] Implement `__init__(graph_service)`
- [ ] Implement `find_multihop_paths(source_nodes, max_hops=3)` (BFS/DFS)
- [ ] Implement `get_entity_neighborhood(entity_id, depth=2)` (reuse GraphService)
- [ ] Implement `find_connecting_paths(entity_a, entity_b)` (all simple paths)
- [ ] Implement `expand_via_synonymy(entity_id)` (follow similar_to edges)
- [ ] Unit tests (12 tests): Multi-hop queries, neighborhoods, synonymy
- [ ] **LOC Target**: 180 LOC implementation + 150 LOC tests

#### Module 3: Personalized PageRank Wrapper (Day 3)
- [ ] Create `src/algorithms/personalized_pagerank.py`
- [ ] Implement `run_ppr(graph, personalization, alpha=0.85, max_iter=100)`
- [ ] Implement `create_personalization_vector(query_nodes, graph)` (uniform distribution)
- [ ] Implement `aggregate_node_scores(ppr_scores, chunk_entities)` (sum scores)
- [ ] Unit tests (8 tests): PPR convergence, personalization, score aggregation
- [ ] **LOC Target**: 120 LOC implementation + 100 LOC tests

#### Module 4: Integration Tests (Day 4)
- [ ] Create `tests/integration/test_hipporag_retrieval.py`
- [ ] Test full retrieval workflow (query → entities → PPR → ranking)
- [ ] Test multi-hop question answering (3-hop paths)
- [ ] Test synonymy edge usage (USA = United States)
- [ ] Test performance (<100ms for graphs with <100k nodes)
- [ ] **Test Target**: 10 integration tests

#### Module 5: Performance Benchmarks (Day 5)
- [ ] Create `tests/performance/test_hipporag_performance.py`
- [ ] Benchmark PPR on 1k, 10k, 100k node graphs
- [ ] Measure query latency (target: <100ms for <100k nodes)
- [ ] Compare HippoRAG vs. vector-only retrieval (accuracy + speed)
- [ ] Profile memory usage (target: <500MB for 100k nodes)
- [ ] **Benchmark Target**: 5 performance tests

---

### Week 6 Deliverables (Two-Stage Coordinator + Integration)

#### Module 6: TwoStageCoordinator (Day 1-2)
- [ ] Create `src/services/two_stage_coordinator.py`
- [ ] Implement `__init__(vector_search_tool, hipporag_service)`
- [ ] Implement `retrieve(query, top_k, vector_weight, graph_weight)`
- [ ] Implement `_stage1_vector_retrieval(query, limit)` (call VectorSearchTool)
- [ ] Implement `_stage2_graph_retrieval(query, limit)` (call HippoRagService)
- [ ] Implement `_fuse_scores(vector_results, graph_results, weights)` (weighted sum)
- [ ] Implement `_calculate_confidence(vector_score, graph_score, agreement)`
- [ ] Unit tests (12 tests): Score fusion, confidence calculation, deduplication
- [ ] **LOC Target**: 220 LOC implementation + 160 LOC tests

#### Module 7: Synonymy Detection (Day 2-3)
- [ ] Create `src/services/synonymy_detector.py`
- [ ] Implement `detect_synonyms(entity_a, entity_b, threshold=0.9)` (cosine similarity)
- [ ] Implement `build_synonymy_edges(graph_service, vector_indexer)` (batch processing)
- [ ] Implement `expand_query_with_synonyms(query_entities, graph_service)` (query expansion)
- [ ] Unit tests (8 tests): Synonymy detection, edge creation, query expansion
- [ ] **LOC Target**: 150 LOC implementation + 100 LOC tests

#### Module 8: MCP Tool Integration (Day 3-4)
- [ ] Create `src/mcp/tools/hipporag_search.py`
- [ ] Implement `HippoRagSearchTool` class (MCP-compatible interface)
- [ ] Implement `execute(query, top_k, use_graph=True)` (two-stage retrieval)
- [ ] Update `src/mcp/server.py` to register HippoRAG tool
- [ ] Add tool metadata (name, description, parameters)
- [ ] Unit tests (6 tests): MCP tool execution, parameter validation
- [ ] **LOC Target**: 100 LOC implementation + 80 LOC tests

#### Module 9: End-to-End Testing (Day 4-5)
- [ ] Create `tests/integration/test_two_stage_retrieval.py`
- [ ] Test complete workflow (Obsidian vault → indexing → two-stage retrieval)
- [ ] Test confidence scoring accuracy (verified vs. unverified chunks)
- [ ] Test multi-hop reasoning (3+ hop questions)
- [ ] Test real-world queries (sample from Obsidian vault)
- [ ] **Test Target**: 15 integration tests

#### Module 10: Documentation (Day 5)
- [ ] Create `docs/HIPPORAG-IMPLEMENTATION.md` (architecture details)
- [ ] Create `docs/TWO-STAGE-RETRIEVAL-GUIDE.md` (user guide)
- [ ] Update `docs/MCP-SERVER-QUICKSTART.md` (add HippoRAG tool)
- [ ] Add code examples and usage patterns
- [ ] Document performance characteristics and tuning parameters
- [ ] **Documentation Target**: 3 comprehensive guides

---

## 4. Week 5 Scope (Specific Deliverables)

### What to Implement in Week 5

**Core Focus**: HippoRAG retrieval engine (graph-only, no vector fusion yet)

**Day-by-Day Breakdown**:

#### Day 1 (6 hours): HippoRagService Foundation
- **Morning** (3 hours):
  - Create `hipporag_service.py` skeleton
  - Implement `__init__` and `retrieve` (main entry point)
  - Implement `_extract_query_entities` (EntityService integration)
- **Afternoon** (3 hours):
  - Implement `_match_entities_to_nodes` (embedding similarity)
  - Unit tests (8 tests): Initialization, entity extraction, node matching
- **Deliverables**: 150 LOC + 8 tests

#### Day 2 (6 hours): Personalized PageRank
- **Morning** (3 hours):
  - Create `personalized_pagerank.py` algorithm wrapper
  - Implement `run_ppr` (NetworkX integration)
  - Implement `create_personalization_vector`
- **Afternoon** (3 hours):
  - Implement `_run_personalized_pagerank` in HippoRagService
  - Implement `_rank_chunks_by_ppr` (score aggregation)
  - Unit tests (10 tests): PPR convergence, score aggregation
- **Deliverables**: 200 LOC + 10 tests

#### Day 3 (6 hours): GraphQueryEngine
- **Morning** (3 hours):
  - Create `graph_query_engine.py`
  - Implement `find_multihop_paths` (BFS-based)
  - Implement `get_entity_neighborhood`
- **Afternoon** (3 hours):
  - Implement `find_connecting_paths` (all simple paths)
  - Implement `expand_via_synonymy`
  - Unit tests (12 tests): Multi-hop queries, synonymy expansion
- **Deliverables**: 180 LOC + 12 tests

#### Day 4 (6 hours): Integration Testing
- **Morning** (3 hours):
  - Create `test_hipporag_retrieval.py` (integration tests)
  - Test full workflow (query → PPR → ranking)
  - Test multi-hop reasoning (3-hop questions)
- **Afternoon** (3 hours):
  - Test synonymy handling (USA = United States)
  - Test edge cases (no entities in query, empty graph)
  - Bug fixes and refinements
- **Deliverables**: 10 integration tests passing

#### Day 5 (6 hours): Performance Benchmarking
- **Morning** (3 hours):
  - Create `test_hipporag_performance.py`
  - Benchmark PPR on 1k, 10k, 100k node graphs
  - Measure query latency (target: <100ms)
- **Afternoon** (3 hours):
  - Profile memory usage (target: <500MB)
  - Optimize bottlenecks (if needed)
  - Documentation (WEEK-5-IMPLEMENTATION-SUMMARY.md)
- **Deliverables**: 5 performance benchmarks + documentation

---

### Success Criteria (Week 5)

**Functional Requirements**:
- [ ] HippoRagService retrieves top-K chunks using PPR
- [ ] Query entity extraction works (spaCy NER integration)
- [ ] Personalized PageRank runs successfully (NetworkX)
- [ ] Multi-hop paths are found (2-3 hop queries)
- [ ] Synonymy edges are traversed correctly

**Performance Requirements**:
- [ ] Query latency <100ms for graphs with <100k nodes
- [ ] PPR convergence in <100 iterations (typically 20-30)
- [ ] Memory usage <500MB for 100k node graphs
- [ ] Multi-hop queries complete in <200ms

**Quality Requirements**:
- [ ] 45 unit tests passing (15+12+8+10 across 4 modules)
- [ ] 10 integration tests passing
- [ ] 5 performance benchmarks complete
- [ ] NASA Rule 10 compliance ≥95% (all functions ≤60 LOC)
- [ ] Code coverage ≥85%
- [ ] Zero critical bugs

**Documentation**:
- [ ] WEEK-5-IMPLEMENTATION-SUMMARY.md complete
- [ ] Code docstrings for all methods (Google style)
- [ ] Performance benchmark results documented

---

## 5. Week 6 Scope (Specific Deliverables)

### What to Implement in Week 6

**Core Focus**: Two-stage coordinator + MCP integration + production readiness

**Day-by-Day Breakdown**:

#### Day 1 (6 hours): TwoStageCoordinator Foundation
- **Morning** (3 hours):
  - Create `two_stage_coordinator.py`
  - Implement `__init__` and `retrieve` (main entry point)
  - Implement `_stage1_vector_retrieval` (VectorSearchTool)
- **Afternoon** (3 hours):
  - Implement `_stage2_graph_retrieval` (HippoRagService)
  - Implement `_fuse_scores` (weighted combination)
  - Unit tests (6 tests): Stage 1/2 execution, score fusion
- **Deliverables**: 150 LOC + 6 tests

#### Day 2 (6 hours): Confidence Scoring + Synonymy
- **Morning** (3 hours):
  - Implement `_calculate_confidence` (vector-graph agreement)
  - Create `synonymy_detector.py`
  - Implement `detect_synonyms` (embedding similarity)
- **Afternoon** (3 hours):
  - Implement `build_synonymy_edges` (batch processing)
  - Implement `expand_query_with_synonyms` (query expansion)
  - Unit tests (10 tests): Confidence calculation, synonymy detection
- **Deliverables**: 200 LOC + 10 tests

#### Day 3 (6 hours): MCP Tool Integration
- **Morning** (3 hours):
  - Create `hipporag_search.py` (MCP tool)
  - Implement `HippoRagSearchTool` class
  - Implement `execute(query, top_k, use_graph)`
- **Afternoon** (3 hours):
  - Update `mcp/server.py` to register tool
  - Add tool metadata and validation
  - Unit tests (6 tests): MCP execution, parameter validation
- **Deliverables**: 100 LOC + 6 tests

#### Day 4 (6 hours): End-to-End Testing
- **Morning** (3 hours):
  - Create `test_two_stage_retrieval.py`
  - Test complete workflow (Obsidian → indexing → retrieval)
  - Test multi-hop reasoning accuracy
- **Afternoon** (3 hours):
  - Test confidence scoring accuracy
  - Test real-world queries (sample vault data)
  - Bug fixes and refinements
- **Deliverables**: 15 integration tests passing

#### Day 5 (6 hours): Documentation + Polish
- **Morning** (3 hours):
  - Create `HIPPORAG-IMPLEMENTATION.md` (architecture)
  - Create `TWO-STAGE-RETRIEVAL-GUIDE.md` (user guide)
  - Update `MCP-SERVER-QUICKSTART.md`
- **Afternoon** (3 hours):
  - Code cleanup and refactoring
  - Final performance validation
  - WEEK-6-COMPLETE-SUMMARY.md
- **Deliverables**: 3 documentation guides + summary

---

### Success Criteria (Week 6)

**Functional Requirements**:
- [ ] TwoStageCoordinator combines vector + graph retrieval
- [ ] Confidence scores reflect vector-graph agreement (0.0-1.0)
- [ ] Synonymy detection creates similar_to edges (threshold ≥0.9)
- [ ] MCP tool integration works (callable via MCP server)
- [ ] End-to-end workflow tested (Obsidian → retrieval)

**Performance Requirements**:
- [ ] Two-stage retrieval <300ms (100ms vector + 100ms graph + 100ms fusion)
- [ ] Synonymy detection <50ms per entity pair
- [ ] Confidence calculation <10ms
- [ ] Memory usage <600MB for 100k nodes + 10k chunks

**Quality Requirements**:
- [ ] 38 unit tests passing (12+8+6+12 across 4 modules)
- [ ] 15 integration tests passing
- [ ] NASA Rule 10 compliance ≥95%
- [ ] Code coverage ≥85%
- [ ] Zero critical bugs
- [ ] All MCP tools functional

**Documentation**:
- [ ] 3 comprehensive guides complete
- [ ] User-facing examples and tutorials
- [ ] Performance tuning recommendations

---

## 6. Technical Requirements

### 6.1 Python Libraries Needed

**Core Dependencies** (add to `requirements.txt`):
```txt
# Existing (Weeks 1-4)
networkx>=3.1          # Graph operations (already installed)
spacy>=3.7             # NER (already installed)
chromadb>=0.4.18       # Vector DB (already installed)
sentence-transformers  # Embeddings (already installed)

# NEW for Week 5-6
numpy>=1.24.0          # Numerical operations (already a transitive dep)
scipy>=1.10.0          # Sparse matrix operations (optional - for large graphs)
```

**Optional Enhancements** (Phase 2):
```txt
faiss-cpu>=1.7.4       # Faster similarity search (if ChromaDB becomes bottleneck)
igraph>=0.10.0         # Alternative graph library (faster PageRank for >1M nodes)
```

**No new dependencies required** - all libraries already in project

---

### 6.2 NetworkX Graph Queries for Multi-Hop Reasoning

**1. Personalized PageRank** (core algorithm):
```python
import networkx as nx

def run_personalized_pagerank(
    graph: nx.DiGraph,
    query_nodes: List[str],
    alpha: float = 0.85,
    max_iter: int = 100
) -> Dict[str, float]:
    """
    Run Personalized PageRank from query nodes.

    Args:
        graph: NetworkX directed graph
        query_nodes: List of node IDs to personalize from
        alpha: Damping parameter (0.85 = 85% follow edges, 15% random jump)
        max_iter: Maximum iterations for convergence

    Returns:
        Dictionary of {node_id: ppr_score}
    """
    # Create uniform personalization vector over query nodes
    personalization = {node: 1.0 / len(query_nodes) for node in query_nodes}

    # Run NetworkX PageRank with personalization
    ppr_scores = nx.pagerank(
        graph,
        alpha=alpha,
        personalization=personalization,
        max_iter=max_iter,
        tol=1e-6
    )

    return ppr_scores
```

**2. Multi-Hop Path Finding** (BFS-based):
```python
def find_multihop_paths(
    graph: nx.DiGraph,
    source_nodes: List[str],
    max_hops: int = 3
) -> List[List[str]]:
    """
    Find all nodes reachable within max_hops from source nodes.

    Args:
        graph: NetworkX directed graph
        source_nodes: Starting nodes
        max_hops: Maximum path length

    Returns:
        List of paths (each path is a list of node IDs)
    """
    all_paths = []

    for source in source_nodes:
        # BFS from source node
        visited = {source}
        queue = [(source, [source], 0)]  # (node, path, depth)

        while queue:
            current, path, depth = queue.pop(0)

            if depth < max_hops:
                for neighbor in graph.successors(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        new_path = path + [neighbor]
                        all_paths.append(new_path)
                        queue.append((neighbor, new_path, depth + 1))

    return all_paths
```

**3. Connecting Paths Between Entities**:
```python
def find_connecting_paths(
    graph: nx.DiGraph,
    entity_a: str,
    entity_b: str,
    cutoff: int = 3
) -> List[List[str]]:
    """
    Find all simple paths between two entities (up to cutoff length).

    Args:
        graph: NetworkX directed graph
        entity_a: Source entity
        entity_b: Target entity
        cutoff: Maximum path length

    Returns:
        List of paths (each path is a list of node IDs)
    """
    try:
        # NetworkX built-in: all simple paths
        paths = list(nx.all_simple_paths(
            graph,
            source=entity_a,
            target=entity_b,
            cutoff=cutoff
        ))
        return paths
    except nx.NetworkXNoPath:
        return []
```

**4. Entity Neighborhood Extraction** (reuse existing GraphService):
```python
def get_entity_neighborhood(
    graph_service: GraphService,
    entity_id: str,
    depth: int = 2
) -> Dict[str, Any]:
    """
    Get local subgraph around entity (reuses GraphService.get_subgraph).

    Args:
        graph_service: GraphService instance
        entity_id: Entity node ID
        depth: Number of hops to include

    Returns:
        Dictionary with nodes and edges
    """
    return graph_service.get_subgraph(entity_id, depth=depth)
```

**5. Synonymy Edge Traversal**:
```python
def expand_via_synonymy(
    graph: nx.DiGraph,
    entity_id: str
) -> Set[str]:
    """
    Expand entity to include synonyms via similar_to edges.

    Args:
        graph: NetworkX directed graph
        entity_id: Entity node ID

    Returns:
        Set of entity IDs (original + synonyms)
    """
    synonyms = {entity_id}  # Include original

    # Find neighbors connected by "similar_to" edges
    for neighbor in graph.neighbors(entity_id):
        edge_data = graph.get_edge_data(entity_id, neighbor)
        if edge_data and edge_data.get('type') == 'similar_to':
            synonyms.add(neighbor)

    return synonyms
```

---

### 6.3 Entity Extraction Pipeline Integration

**Reuse EntityService (Week 4)** - no changes needed:
```python
from src.services.entity_service import EntityService

# Initialize
entity_service = EntityService(model_name="en_core_web_sm")

# Extract entities from query
query = "What company did Elon Musk start before Tesla?"
entities = entity_service.extract_entities(query)

# Output:
# [
#   {'text': 'Elon Musk', 'type': 'PERSON', 'start': 17, 'end': 26},
#   {'text': 'Tesla', 'type': 'ORG', 'start': 41, 'end': 46}
# ]

# Normalize entity IDs
entity_ids = [
    entity_service._normalize_entity_text(ent['text'])
    for ent in entities
]
# ['elon_musk', 'tesla']
```

**Entity-to-Node Matching** (embedding similarity):
```python
from src.indexing.vector_indexer import VectorIndexer
import numpy as np

def match_entities_to_nodes(
    entity_texts: List[str],
    vector_indexer: VectorIndexer,
    threshold: float = 0.85
) -> List[str]:
    """
    Match extracted entities to graph nodes via embedding similarity.

    Args:
        entity_texts: List of entity texts (e.g., ["Elon Musk", "Tesla"])
        vector_indexer: VectorIndexer instance (ChromaDB)
        threshold: Cosine similarity threshold for match (default: 0.85)

    Returns:
        List of matched node IDs
    """
    matched_nodes = []

    for entity_text in entity_texts:
        # Get embedding for entity
        entity_embedding = vector_indexer.embedder.encode_single(entity_text)

        # Search for similar nodes in ChromaDB
        results = vector_indexer.collection.query(
            query_embeddings=[entity_embedding.tolist()],
            n_results=1,  # Top match
            where={"type": "entity"}  # Filter to entity nodes only
        )

        # Check if match exceeds threshold
        if results['distances'][0] and (1.0 - results['distances'][0][0]) >= threshold:
            matched_nodes.append(results['ids'][0][0])

    return matched_nodes
```

---

### 6.4 Memory and Performance Considerations

#### Performance Characteristics

| Operation | Time Complexity | Space Complexity | Benchmark (100k nodes) |
|-----------|----------------|------------------|----------------------|
| **Personalized PageRank** | O(E × iter) | O(V) | ~80ms (20 iterations) |
| **Multi-hop BFS** | O(V + E) | O(V) | ~50ms (3 hops) |
| **Entity extraction** | O(text_length) | O(entities) | ~20ms (200 words) |
| **Score fusion** | O(K log K) | O(K) | ~5ms (K=20 results) |
| **Total retrieval** | - | - | **<200ms** (target) |

Where:
- V = number of nodes (entities + chunks)
- E = number of edges (relationships)
- iter = PageRank iterations (typically 20-30)
- K = number of results to return

#### Memory Optimization Strategies

**1. Graph Persistence** (existing - use GraphService.save_graph):
```python
# Save graph to disk (JSON format)
graph_service.save_graph("./data/graph.json")

# Load on startup (lazy loading)
graph_service.load_graph("./data/graph.json")
```

**2. Sparse Matrix Storage** (for large graphs >1M nodes):
```python
import scipy.sparse as sp

# Convert NetworkX graph to sparse adjacency matrix
adj_matrix = nx.adjacency_matrix(graph)  # scipy.sparse.csr_matrix

# Run PageRank on sparse matrix (faster for large graphs)
from scipy.sparse.linalg import eigs
```

**3. Chunk-level Caching** (cache PPR scores for frequent queries):
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_personalized_pagerank(
    graph_id: str,  # Hash of graph structure
    query_nodes_tuple: Tuple[str, ...],  # Hashable
    alpha: float
) -> Dict[str, float]:
    """Cache PPR results for repeated queries."""
    # ... run PPR ...
    return ppr_scores
```

**4. Batch Processing** (for indexing phase):
```python
# Extract entities from all chunks in batch (faster than one-by-one)
all_texts = [chunk['text'] for chunk in chunks]
all_entities = entity_service.batch_extract_entities(all_texts)

# Build graph in batch (accumulate updates, save once)
for chunk, entities in zip(chunks, all_entities):
    # Add nodes and edges (in-memory)
    pass

# Single save at end
graph_service.save_graph()
```

#### Performance Targets

| Graph Size | Nodes | Edges | PPR Time | Memory | Status |
|-----------|-------|-------|----------|--------|--------|
| Small | 1k | 5k | <10ms | <50MB | ✅ Easy |
| Medium | 10k | 50k | <50ms | <200MB | ✅ Achievable |
| Large | 100k | 500k | <100ms | <500MB | ⚠️ Target |
| Very Large | 1M+ | 5M+ | <500ms | <2GB | ❌ Phase 2 |

**Obsidian Vault Estimate** (typical user):
- Notes: 1,000-5,000 notes
- Chunks: 5,000-25,000 chunks (avg 5 chunks/note)
- Entities: 10,000-50,000 entities (avg 2 entities/chunk)
- Edges: 50,000-250,000 edges (avg 5 edges/entity)

**Result**: Falls into "Medium" category → <50ms PPR, <200MB memory ✅

---

## 7. Test Strategy

### 7.1 Unit Tests (45 tests in Week 5, 38 in Week 6)

#### Week 5 Unit Tests (45 total)

**HippoRagService (15 tests)** - `tests/unit/test_hipporag_service.py`:
1. `test_init_with_valid_dependencies` - Constructor initialization
2. `test_retrieve_with_empty_graph` - No entities in graph
3. `test_extract_query_entities_person_org` - Extract PERSON + ORG
4. `test_extract_query_entities_no_entities` - Query with no entities
5. `test_match_entities_exact_match` - Exact entity ID match
6. `test_match_entities_fuzzy_match` - Embedding similarity >0.85
7. `test_match_entities_no_match` - No similar nodes found
8. `test_run_personalized_pagerank_single_node` - PPR from 1 node
9. `test_run_personalized_pagerank_multiple_nodes` - PPR from 2+ nodes
10. `test_run_personalized_pagerank_convergence` - PPR converges <100 iter
11. `test_rank_chunks_by_ppr_scores` - Aggregate PPR scores for chunks
12. `test_rank_chunks_empty_ppr` - No PPR scores (empty result)
13. `test_retrieve_end_to_end` - Full workflow (query → ranking)
14. `test_retrieve_with_alpha_variation` - Different alpha values (0.7, 0.85, 0.95)
15. `test_retrieve_performance_100k_nodes` - Performance on large graph

**GraphQueryEngine (12 tests)** - `tests/unit/test_graph_query_engine.py`:
1. `test_init_with_graph_service` - Constructor initialization
2. `test_find_multihop_paths_2_hops` - 2-hop paths from source
3. `test_find_multihop_paths_3_hops` - 3-hop paths
4. `test_find_multihop_paths_no_neighbors` - Isolated node (no paths)
5. `test_get_entity_neighborhood_depth_1` - 1-hop neighborhood
6. `test_get_entity_neighborhood_depth_2` - 2-hop neighborhood
7. `test_find_connecting_paths_direct` - Direct edge between entities
8. `test_find_connecting_paths_2_hop` - 2-hop path
9. `test_find_connecting_paths_no_path` - No path exists
10. `test_expand_via_synonymy_single` - 1 synonym found
11. `test_expand_via_synonymy_multiple` - Multiple synonyms
12. `test_expand_via_synonymy_no_synonyms` - No similar_to edges

**PersonalizedPageRank (8 tests)** - `tests/unit/test_personalized_pagerank.py`:
1. `test_run_ppr_single_node_personalization` - PPR from 1 node
2. `test_run_ppr_multiple_nodes_personalization` - PPR from 2+ nodes
3. `test_run_ppr_convergence_under_100_iterations` - Fast convergence
4. `test_run_ppr_alpha_0_85` - Default alpha value
5. `test_run_ppr_alpha_variation` - Different alpha (0.5, 0.7, 0.95)
6. `test_create_personalization_vector_uniform` - Uniform distribution
7. `test_aggregate_node_scores` - Sum PPR scores for chunks
8. `test_aggregate_node_scores_no_entities` - Chunk with no entities

**Integration (10 tests)** - `tests/integration/test_hipporag_retrieval.py`:
1. `test_full_retrieval_workflow_single_hop` - Query → PPR → ranking (1 hop)
2. `test_full_retrieval_workflow_multi_hop` - 3-hop question
3. `test_multihop_question_answering` - "What company did X start before Y?"
4. `test_synonymy_edge_usage` - USA = United States
5. `test_query_with_no_entities` - "What is the meaning of life?" (no NER)
6. `test_query_with_entities_not_in_graph` - New entities (cold start)
7. `test_performance_100ms_target` - Latency <100ms for <100k nodes
8. `test_performance_1k_nodes` - Small graph benchmark
9. `test_performance_10k_nodes` - Medium graph benchmark
10. `test_performance_100k_nodes` - Large graph benchmark

---

#### Week 6 Unit Tests (38 total)

**TwoStageCoordinator (12 tests)** - `tests/unit/test_two_stage_coordinator.py`:
1. `test_init_with_dependencies` - Constructor initialization
2. `test_retrieve_two_stage` - Full two-stage retrieval
3. `test_stage1_vector_retrieval` - Stage 1 only
4. `test_stage2_graph_retrieval` - Stage 2 only
5. `test_fuse_scores_equal_weights` - 50-50 fusion
6. `test_fuse_scores_vector_heavy` - 70-30 fusion (vector bias)
7. `test_fuse_scores_graph_heavy` - 30-70 fusion (graph bias)
8. `test_calculate_confidence_high` - Vector + graph agree (both >0.8)
9. `test_calculate_confidence_medium` - One high, one low
10. `test_calculate_confidence_low` - Both low scores
11. `test_deduplication` - Remove duplicate chunks
12. `test_empty_results` - No results from either stage

**SynonymyDetector (8 tests)** - `tests/unit/test_synonymy_detector.py`:
1. `test_detect_synonyms_high_similarity` - Cosine >0.9 (synonym)
2. `test_detect_synonyms_low_similarity` - Cosine <0.9 (not synonym)
3. `test_detect_synonyms_identical_entities` - Same entity (1.0 similarity)
4. `test_build_synonymy_edges_batch` - Build edges for all entities
5. `test_build_synonymy_edges_threshold` - Only add if >threshold
6. `test_expand_query_with_synonyms` - USA → [USA, United States]
7. `test_expand_query_no_synonyms` - No similar_to edges
8. `test_expand_query_multiple_synonyms` - 3+ synonyms per entity

**HippoRagSearchTool (6 tests)** - `tests/unit/test_hipporag_search.py`:
1. `test_execute_with_graph_enabled` - use_graph=True
2. `test_execute_with_graph_disabled` - use_graph=False (vector only)
3. `test_execute_parameter_validation` - Invalid top_k, query
4. `test_execute_empty_query` - Query="" (should fail)
5. `test_execute_large_top_k` - top_k=100 (max limit)
6. `test_mcp_tool_metadata` - Tool name, description, params

**Performance (5 tests)** - `tests/performance/test_two_stage_performance.py`:
1. `test_two_stage_latency_300ms` - Total <300ms
2. `test_vector_stage_latency_100ms` - Stage 1 <100ms
3. `test_graph_stage_latency_100ms` - Stage 2 <100ms
4. `test_fusion_latency_10ms` - Score fusion <10ms
5. `test_memory_usage_600mb` - Memory <600MB

**Integration (15 tests)** - `tests/integration/test_two_stage_retrieval.py`:
1. `test_end_to_end_obsidian_workflow` - Vault → indexing → retrieval
2. `test_confidence_scoring_verified_chunks` - High confidence for verified
3. `test_confidence_scoring_unverified_chunks` - Lower confidence
4. `test_multihop_reasoning_3_hops` - 3-hop question answering
5. `test_multihop_reasoning_accuracy` - Correct answer in top-3
6. `test_real_world_query_who_founded_x` - "Who founded Tesla?"
7. `test_real_world_query_what_is_x` - "What is PageRank?"
8. `test_real_world_query_when_did_x` - "When did SpaceX launch?"
9. `test_vector_only_baseline` - Compare vs. vector-only
10. `test_graph_only_baseline` - Compare vs. graph-only
11. `test_two_stage_vs_vector_accuracy` - % improvement
12. `test_two_stage_vs_graph_accuracy` - % improvement
13. `test_synonymy_improves_recall` - USA = United States recall boost
14. `test_cold_start_new_entities` - Entities not in graph
15. `test_empty_graph_fallback_to_vector` - No graph → vector only

---

### 7.2 Integration Tests (25 total)

**Week 5**: 10 integration tests (see above - `test_hipporag_retrieval.py`)
**Week 6**: 15 integration tests (see above - `test_two_stage_retrieval.py`)

**Focus Areas**:
1. End-to-end workflows (Obsidian vault → retrieval)
2. Multi-hop reasoning accuracy
3. Confidence scoring correctness
4. Performance vs. baselines (vector-only, graph-only)
5. Real-world query evaluation

---

### 7.3 Performance Benchmarks (10 total)

**Week 5**: 5 benchmarks (HippoRAG-only)
**Week 6**: 5 benchmarks (Two-stage coordinator)

**Benchmark Suite** - `tests/performance/`:

#### Week 5 Benchmarks
1. **PPR Scalability** (`test_ppr_scalability`):
   - 1k nodes: <10ms ✅
   - 10k nodes: <50ms ✅
   - 100k nodes: <100ms ⚠️ (target)
   - 1M nodes: <500ms ❌ (Phase 2)

2. **Multi-Hop Query Latency** (`test_multihop_latency`):
   - 2-hop: <30ms ✅
   - 3-hop: <50ms ✅
   - 4-hop: <100ms ⚠️

3. **Memory Usage** (`test_memory_usage`):
   - 1k nodes: <50MB ✅
   - 10k nodes: <200MB ✅
   - 100k nodes: <500MB ⚠️
   - Measure with `tracemalloc` module

4. **Entity Extraction Speed** (`test_entity_extraction_speed`):
   - 50 words: <10ms ✅
   - 200 words: <20ms ✅
   - 1000 words: <100ms ⚠️

5. **HippoRAG vs. Vector-Only** (`test_hipporag_vs_vector`):
   - Accuracy improvement: +10-20% (multi-hop queries)
   - Latency: +50ms overhead (acceptable)

#### Week 6 Benchmarks
1. **Two-Stage Total Latency** (`test_two_stage_latency`):
   - Target: <300ms (100ms vector + 100ms graph + 100ms fusion)
   - Measure: 10 queries, average latency

2. **Synonymy Detection Speed** (`test_synonymy_detection_speed`):
   - Per entity pair: <5ms ✅
   - Batch 100 pairs: <200ms ✅

3. **Score Fusion Overhead** (`test_fusion_overhead`):
   - 20 results: <5ms ✅
   - 100 results: <20ms ✅

4. **Confidence Calculation Speed** (`test_confidence_calculation_speed`):
   - Per result: <1ms ✅
   - Batch 100 results: <50ms ✅

5. **Two-Stage vs. Baselines** (`test_two_stage_vs_baselines`):
   - Accuracy: +15-25% over vector-only
   - Latency: +100ms over vector-only (acceptable trade-off)
   - Memory: +200MB over vector-only (graph storage)

---

## 8. Performance Targets

### 8.1 Latency Targets

| Operation | Target | Measurement Method | Acceptable Range |
|-----------|--------|-------------------|------------------|
| **Query entity extraction** | <20ms | spaCy NER on 200-word query | 10-30ms |
| **Entity-to-node matching** | <30ms | ChromaDB similarity search (K=1) | 20-50ms |
| **Personalized PageRank** | <100ms | NetworkX pagerank() (100k nodes) | 50-150ms |
| **Multi-hop path finding** | <50ms | BFS traversal (3 hops, 100k nodes) | 30-100ms |
| **Score aggregation** | <10ms | Sum PPR scores for 20 chunks | 5-20ms |
| **Vector retrieval (Stage 1)** | <100ms | ChromaDB query (existing) | 50-150ms |
| **Graph retrieval (Stage 2)** | <100ms | HippoRAG full pipeline | 80-150ms |
| **Score fusion** | <10ms | Weighted combination (20 results) | 5-20ms |
| **Confidence calculation** | <10ms | Vector-graph agreement (20 results) | 5-20ms |
| **Total two-stage retrieval** | <300ms | End-to-end (query → results) | 200-400ms |

**Rationale**:
- <300ms total latency = near-instant for users (similar to web search)
- Individual components budgeted to sum to ~200ms, leaving 100ms buffer
- Targets based on NeurIPS'24 paper benchmarks (6-13x faster than iterative methods)

---

### 8.2 Throughput Targets

| Metric | Target | Measurement | Acceptable Range |
|--------|--------|-------------|------------------|
| **Queries per second (QPS)** | 10 QPS | Concurrent retrieval (10 threads) | 5-15 QPS |
| **Indexing throughput** | 100 chunks/sec | Batch entity extraction + graph updates | 50-200 chunks/sec |
| **Graph update rate** | 500 edges/sec | Batch add_relationship calls | 300-1000 edges/sec |
| **Synonymy edge creation** | 50 pairs/sec | Embedding similarity + add_edge | 30-100 pairs/sec |

**Notes**:
- QPS assumes single-threaded retrieval (NetworkX is not thread-safe by default)
- For production, use process-based parallelism (multiprocessing) or read-only graph copies

---

### 8.3 Memory Targets

| Graph Size | Nodes | Edges | Memory Budget | Breakdown |
|-----------|-------|-------|---------------|-----------|
| **Small** | 1k | 5k | <50MB | 30MB graph + 20MB embeddings |
| **Medium** | 10k | 50k | <200MB | 120MB graph + 80MB embeddings |
| **Large** | 100k | 500k | <500MB | 300MB graph + 200MB embeddings |
| **Very Large** | 1M+ | 5M+ | <2GB | 1.2GB graph + 800MB embeddings |

**Obsidian Vault Estimate** (typical user):
- 5,000 notes → 25,000 chunks → 50,000 entities → 250,000 edges
- **Expected**: Medium category (<200MB) ✅

**Memory Optimization**:
- Use `graph_service.save_graph()` to persist to disk (JSON)
- Load graph lazily on startup (only when retrieval is needed)
- For very large graphs (>1M nodes), use memory-mapped storage (Phase 2)

---

### 8.4 Accuracy Targets

| Metric | Target | Measurement | Baseline |
|--------|--------|-------------|----------|
| **Multi-hop QA accuracy** | +20% over vector-only | Top-3 recall on multi-hop questions | NeurIPS'24 paper |
| **Single-hop QA accuracy** | ≥95% (maintain parity) | Top-3 recall on single-hop questions | ChromaDB vector search |
| **Synonymy recall** | +10-15% | USA = United States recall boost | Without synonymy edges |
| **Confidence correlation** | >0.8 Pearson correlation | Confidence score vs. human relevance | Manual annotation |

**Evaluation Dataset** (Week 6):
- Create 50 test queries (25 single-hop, 25 multi-hop)
- Sample from Obsidian vault or use public QA datasets (HotpotQA, MultiHopQA)
- Manually annotate correct answers (gold standard)

---

## 9. Risk Analysis

### 9.1 Technical Risks

| Risk | Severity | Probability | Mitigation | Status |
|------|----------|-------------|------------|--------|
| **PPR doesn't converge in <100 iter** | P1 | Low (10%) | Increase max_iter to 200, adjust tolerance | MONITOR |
| **Graph queries exceed 100ms target** | P2 | Medium (30%) | Optimize with caching, use sparse matrices | MITIGATE |
| **Synonymy detection too slow** | P2 | Low (15%) | Batch processing, cache embeddings | ACCEPT |
| **Entity extraction misses key entities** | P2 | Medium (25%) | Use larger spaCy model (en_core_web_md) | TEST |
| **NetworkX not thread-safe** | P3 | High (80%) | Use process-based parallelism, read-only copies | ACCEPT |
| **Memory exceeds 500MB for large graphs** | P2 | Medium (30%) | Lazy loading, disk persistence, sparse storage | MITIGATE |

**High-Priority Mitigations**:
1. **Graph query optimization** (Day 5, Week 5):
   - Profile with `cProfile` to identify bottlenecks
   - Cache PPR results for frequent queries
   - Use NetworkX optimized algorithms (`pagerank_scipy` for large graphs)

2. **Entity extraction accuracy** (Day 2, Week 5):
   - Test with en_core_web_sm (43MB, fast) vs. en_core_web_md (96MB, accurate)
   - Validate on sample Obsidian vault (manual annotation)
   - Fall back to regex-based entity extraction if spaCy fails

---

### 9.2 Integration Risks

| Risk | Severity | Probability | Mitigation | Status |
|------|----------|-------------|------------|--------|
| **GraphService API insufficient** | P1 | Low (10%) | Add `get_graph()` method to expose NetworkX graph | PLANNED |
| **VectorIndexer missing entity embeddings** | P2 | Medium (20%) | Add `get_embedding_by_id()` method | PLANNED |
| **ChromaDB performance degrades** | P2 | Low (15%) | Monitor query latency, consider FAISS (Phase 2) | MONITOR |
| **EntityService extracts wrong entity types** | P2 | Medium (25%) | Filter to relevant types (PERSON, ORG, GPE) | TEST |

**Planned Enhancements**:
1. **GraphService.get_graph()** (Week 5, Day 1):
   ```python
   def get_graph(self) -> nx.DiGraph:
       """Return underlying NetworkX graph for advanced algorithms."""
       return self.graph
   ```

2. **VectorIndexer.get_embedding_by_id()** (Week 6, Day 2):
   ```python
   def get_embedding_by_id(self, entity_id: str) -> Optional[np.ndarray]:
       """Retrieve embedding for entity by ID."""
       result = self.collection.get(ids=[entity_id])
       if result['embeddings']:
           return np.array(result['embeddings'][0])
       return None
   ```

---

### 9.3 Schedule Risks

| Risk | Severity | Probability | Mitigation | Status |
|------|----------|-------------|------------|--------|
| **Week 5 takes >5 days** | P2 | Medium (30%) | Focus on core PPR, defer optimizations to Week 6 | ACCEPT |
| **Integration testing uncovers bugs** | P1 | High (60%) | Daily integration testing (not just Day 4) | MITIGATE |
| **Performance optimization needed** | P2 | Medium (40%) | Build instrumentation early (Day 1 profiling) | MITIGATE |
| **Documentation takes >1 day** | P3 | Low (20%) | Write docs incrementally (daily updates) | ACCEPT |

**Risk Mitigation Strategy**:
1. **Daily integration testing**: Don't wait until Day 4
   - Day 1: Test entity extraction + node matching
   - Day 2: Test PPR execution
   - Day 3: Test multi-hop queries
   - Day 4: Full workflow testing

2. **Incremental documentation**: Write as you code
   - Docstrings first (before implementation)
   - Update README daily with new features
   - Record performance benchmarks in real-time

---

## 10. Success Metrics (Weeks 5-6 Combined)

### 10.1 Functional Metrics

| Metric | Target | Measurement | Status |
|--------|--------|-------------|--------|
| **Modules implemented** | 10 modules | Line count, test coverage | TBD |
| **Unit tests passing** | 83 tests (45+38) | pytest execution | TBD |
| **Integration tests passing** | 25 tests | pytest execution | TBD |
| **Performance benchmarks** | 10 benchmarks | All within target ranges | TBD |
| **NASA Rule 10 compliance** | ≥95% | AST-based function length check | TBD |
| **Code coverage** | ≥85% | pytest-cov report | TBD |
| **Zero critical bugs** | 0 bugs | Manual testing + user validation | TBD |

---

### 10.2 Performance Metrics

| Metric | Target | Measurement | Status |
|--------|--------|-------------|--------|
| **Two-stage retrieval latency** | <300ms | Average over 100 queries | TBD |
| **PPR query latency** | <100ms | 100k node graph | TBD |
| **Multi-hop accuracy** | +20% over vector-only | Top-3 recall on 25 multi-hop queries | TBD |
| **Memory usage** | <500MB | 100k nodes + 500k edges | TBD |
| **Indexing throughput** | 100 chunks/sec | Batch processing benchmark | TBD |

---

### 10.3 Quality Metrics

| Metric | Target | Measurement | Status |
|--------|--------|-------------|--------|
| **Docstring coverage** | 100% | All public methods documented | TBD |
| **Type hint coverage** | 100% | mypy validation | TBD |
| **NASA compliance** | ≥95% | Functions ≤60 LOC | TBD |
| **Code duplication** | <5% | pylint similarity checker | TBD |
| **Security vulnerabilities** | 0 critical | Bandit security scanner | TBD |

---

## 11. Documentation Deliverables

### Week 5 Documentation
1. **WEEK-5-IMPLEMENTATION-SUMMARY.md**:
   - Implementation summary (modules, LOC, tests)
   - Performance benchmark results
   - Known issues and limitations
   - Week 6 handoff notes

### Week 6 Documentation
1. **HIPPORAG-IMPLEMENTATION.md**:
   - Architecture overview (this document, refined)
   - Algorithm details (PPR, multi-hop reasoning)
   - Integration guide (how to use HippoRagService)
   - Performance tuning recommendations

2. **TWO-STAGE-RETRIEVAL-GUIDE.md**:
   - User-facing guide (how to use two-stage retrieval)
   - Example queries (single-hop vs. multi-hop)
   - Confidence score interpretation
   - Troubleshooting common issues

3. **MCP-SERVER-QUICKSTART.md** (update):
   - Add HippoRAG tool documentation
   - Example MCP calls
   - Parameter reference (top_k, alpha, weights)

---

## 12. Next Steps (Post-Week 6)

### Phase 2 Enhancements (Weeks 7-8 or later)

**1. Advanced Synonymy Detection**:
- Use LLM-based paraphrasing (e.g., "USA" ≈ "America" ≈ "United States")
- Build entity coreference resolution (e.g., "he" → "Elon Musk")

**2. Dynamic Graph Updates**:
- Incremental graph updates (add new chunks without full rebuild)
- Graph pruning (remove old/irrelevant entities)
- Adaptive edge weights (boost edges for frequently co-occurring entities)

**3. Query Expansion**:
- Automatic query reformulation (e.g., "Tesla founder" → "Who founded Tesla?")
- Pseudo-relevance feedback (use top-K results to expand query)

**4. Multi-Modal Retrieval**:
- Image entity extraction (OCR + object detection)
- Audio transcription + entity linking

**5. Scalability Optimizations**:
- Distributed PageRank (for >1M node graphs)
- Graph partitioning (shard large graphs across machines)
- GPU-accelerated similarity search (FAISS)

---

## Appendix A: HippoRAG Algorithm Pseudocode

```python
# OFFLINE INDEXING PHASE (run once per Obsidian vault update)

def index_vault(vault_path):
    """
    Index Obsidian vault into ChromaDB + NetworkX graph.
    """
    # 1. Load all markdown files
    chunks = load_markdown_files(vault_path)

    # 2. Extract entities (batch processing)
    all_entities = entity_service.batch_extract_entities([c.text for c in chunks])

    # 3. Build graph
    for chunk, entities in zip(chunks, all_entities):
        # Add chunk node
        graph_service.add_chunk_node(chunk.id, metadata={'text': chunk.text})

        # Add entity nodes + mention edges
        for entity in entities:
            entity_id = normalize_entity_text(entity.text)
            graph_service.add_entity_node(entity_id, entity.type, metadata={})
            graph_service.add_relationship(
                chunk.id, entity_id, 'mentions', metadata={}
            )

    # 4. Build synonymy edges (embedding similarity)
    entity_ids = graph_service.get_all_entity_ids()
    for i, entity_a in enumerate(entity_ids):
        for entity_b in entity_ids[i+1:]:
            similarity = compute_similarity(entity_a, entity_b)
            if similarity > 0.9:  # Threshold
                graph_service.add_relationship(
                    entity_a, entity_b, 'similar_to', metadata={'score': similarity}
                )

    # 5. Save graph + vector index
    graph_service.save_graph()
    vector_indexer.save()


# ONLINE RETRIEVAL PHASE (run per user query)

def retrieve_two_stage(query, top_k=10):
    """
    Two-stage retrieval: Vector (Stage 1) + Graph (Stage 2).
    """
    # STAGE 1: Vector retrieval (existing ChromaDB)
    vector_results = vector_search_tool.execute(query, limit=20)

    # STAGE 2: Graph-based retrieval (HippoRAG)

    # Step 2.1: Extract query entities
    query_entities = entity_service.extract_entities(query)
    query_entity_ids = [normalize_entity_text(e.text) for e in query_entities]

    # Step 2.2: Match entities to graph nodes (embedding similarity)
    query_nodes = []
    for entity_id in query_entity_ids:
        # Exact match
        if graph_service.graph.has_node(entity_id):
            query_nodes.append(entity_id)
        else:
            # Fuzzy match via embedding similarity
            similar_node = find_most_similar_node(entity_id, graph_service)
            if similar_node:
                query_nodes.append(similar_node)

    # Step 2.3: Run Personalized PageRank
    if query_nodes:
        # Create personalization vector (uniform over query nodes)
        personalization = {node: 1.0 / len(query_nodes) for node in query_nodes}

        # Run NetworkX PageRank
        ppr_scores = nx.pagerank(
            graph_service.graph,
            alpha=0.85,
            personalization=personalization,
            max_iter=100
        )
    else:
        # No entities in query → fall back to vector-only
        ppr_scores = {}

    # Step 2.4: Rank chunks by PPR scores
    chunk_scores = {}
    for chunk_id in graph_service.get_all_chunk_ids():
        # Get entities mentioned in chunk
        mentioned_entities = graph_service.get_neighbors(chunk_id, 'mentions')

        # Sum PPR scores for mentioned entities
        chunk_ppr_score = sum(ppr_scores.get(entity, 0.0) for entity in mentioned_entities)
        chunk_scores[chunk_id] = chunk_ppr_score

    # Sort chunks by PPR score
    graph_results = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)[:20]

    # SCORE FUSION (weighted combination)
    fused_results = []
    for chunk_id, vector_score in [(r['chunk_id'], r['score']) for r in vector_results]:
        graph_score = chunk_scores.get(chunk_id, 0.0)

        # Weighted fusion (40% vector, 60% graph)
        final_score = 0.4 * vector_score + 0.6 * graph_score

        # Confidence (vector-graph agreement)
        confidence = calculate_confidence(vector_score, graph_score)

        fused_results.append({
            'chunk_id': chunk_id,
            'score': final_score,
            'confidence': confidence,
            'vector_score': vector_score,
            'graph_score': graph_score
        })

    # Sort by fused score
    fused_results = sorted(fused_results, key=lambda x: x['score'], reverse=True)

    # Return top-K
    return fused_results[:top_k]


def calculate_confidence(vector_score, graph_score):
    """
    Calculate confidence based on vector-graph agreement.

    High confidence: Both scores high (>0.7)
    Medium: One high, one low
    Low: Both low (<0.5)
    """
    # Simple heuristic (can be refined)
    agreement = 1.0 - abs(vector_score - graph_score)
    avg_score = (vector_score + graph_score) / 2.0

    # Weighted combination
    confidence = 0.6 * avg_score + 0.4 * agreement

    return confidence
```

---

## Appendix B: Example Use Cases

### Use Case 1: Single-Hop Question (Vector-Only Sufficient)

**Query**: "What is PageRank?"

**Expected Behavior**:
- Stage 1 (Vector): Finds chunks mentioning "PageRank" → High scores
- Stage 2 (Graph): Extracts entity "PageRank" → PPR finds related concepts (Google, Larry Page)
- Fusion: Vector score high, graph score medium → High confidence (both agree)
- Result: Top chunk is definition of PageRank (verified)

**Performance**: <200ms (vector + graph both fast)

---

### Use Case 2: Multi-Hop Question (HippoRAG Shines)

**Query**: "What company did the founder of Tesla start before Tesla?"

**Expected Behavior**:
- Stage 1 (Vector): Finds chunks mentioning "Tesla" and "founder" → Medium scores
  - May miss "PayPal" or "Zip2" if not lexically similar
- Stage 2 (Graph): Extracts entities "Tesla", "founder" (may map to "Elon Musk")
  - PPR from "Tesla" + "Elon Musk" → Finds connected entities (PayPal, Zip2)
  - Path: Tesla ← founded_by ← Elon Musk → founded → PayPal, Zip2
  - Chunks mentioning PayPal/Zip2 get HIGH graph scores
- Fusion: Vector low, graph high → Medium-high confidence (graph compensates)
- Result: Top chunks mention PayPal (1999) and Zip2 (1995)

**Performance**: <300ms (graph traversal + PPR)

**Accuracy Improvement**: +30-50% over vector-only (which might miss PayPal entirely)

---

### Use Case 3: Synonymy Resolution

**Query**: "What is the capital of the United States?"

**Expected Behavior**:
- Stage 1 (Vector): Finds chunks mentioning "United States", "capital"
- Stage 2 (Graph): Extracts entity "United States"
  - Synonymy edges: "United States" ← similar_to → "USA", "America"
  - PPR expands to include chunks mentioning "USA" or "America"
- Fusion: Vector + graph both high → High confidence
- Result: Chunks mentioning "Washington D.C." (USA capital)

**Recall Improvement**: +15-20% (includes chunks with "USA" instead of "United States")

---

### Use Case 4: Cold Start (New Entities)

**Query**: "Who is Claude AI?" (new entity not in graph)

**Expected Behavior**:
- Stage 1 (Vector): Finds chunks mentioning "Claude AI" → Scores available
- Stage 2 (Graph): Extracts entity "Claude AI" → NOT in graph
  - PPR skipped (no query nodes)
  - Graph score = 0.0 for all chunks
- Fusion: Vector high, graph zero → Low-medium confidence (vector-only)
- Result: Falls back to vector retrieval (acceptable degradation)

**Graceful Degradation**: Vector-only mode when graph unavailable

---

## Appendix C: References

1. **HippoRAG Paper** (NeurIPS'24):
   - Title: "HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models"
   - Authors: Bernal Jiménez Gutiérrez, Yiheng Shu, Yu Su (OSU-NLP-Group)
   - arXiv: https://arxiv.org/abs/2405.14831
   - GitHub: https://github.com/OSU-NLP-Group/HippoRAG

2. **Hippocampal Indexing Theory**:
   - Teyler, T. J., & DiScenna, P. (1986). "The hippocampal memory indexing theory."
   - Behavioral Neuroscience, 100(2), 147-154.

3. **Personalized PageRank**:
   - Haveliwala, T. H. (2002). "Topic-sensitive PageRank."
   - Proceedings of the 11th International Conference on WWW.
   - NetworkX Documentation: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html

4. **Multi-Hop Question Answering**:
   - Yang, Z., et al. (2018). "HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering."
   - EMNLP 2018.

5. **Graph RAG Architectures**:
   - Joyce Birkins. (2024). "6 Graph RAG Architectures: the Development Direction of Knowledge Graphs in RAG."
   - Medium: https://medium.com/@joycebirkins/6-graph-rag-architectures-the-development-direction-of-knowledge-graphs-in-rag-d3b0508b317e

---

**Version**: 1.0
**Date**: 2025-10-18
**Status**: Architecture Plan Complete - Ready for Week 5 Implementation
**Research Agent**: Claude Sonnet 4.5
**Next Action**: Begin Week 5 Day 1 (HippoRagService Foundation)
**Estimated Completion**: 10 days (Weeks 5-6)

---

**End of Week 5-6 Architecture Plan**
