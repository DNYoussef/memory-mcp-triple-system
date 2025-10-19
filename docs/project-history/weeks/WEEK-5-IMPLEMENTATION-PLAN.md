# Week 5 Implementation Plan: HippoRAG Core Development

**Project**: Memory MCP Triple System v5.0
**Date**: 2025-10-18
**Week**: 5 of 8 (HippoRAG Implementation)
**Methodology**: SPARC - Implementation Phase
**Planning Agent**: Claude Sonnet 4.5

---

## Executive Summary

### Week 5 Goals

Implement **core HippoRAG retrieval engine** - a neurobiologically-inspired graph-based retrieval system using Personalized PageRank for multi-hop reasoning. This week focuses on **graph-only retrieval** (no vector fusion), building the foundation for Week 6's two-stage coordinator.

### Success Criteria

**Functional**:
- HippoRagService retrieves top-K chunks using Personalized PageRank
- Query entity extraction works (spaCy NER integration)
- Multi-hop path finding (2-3 hop queries)
- Synonymy edge traversal functional

**Performance**:
- Graph queries <100ms (100k nodes)
- PPR convergence <100 iterations
- Memory usage <500MB (100k nodes)

**Quality**:
- 45 unit tests passing (100% pass rate)
- 17 integration tests passing
- ≥85% code coverage
- ≥95% NASA Rule 10 compliance (all functions ≤60 LOC)

### Dependencies

**Week 4 Complete** ✅:
- GraphService (NetworkX-based knowledge graph)
- EntityService (spaCy NER)
- VectorIndexer (ChromaDB embeddings)

**Required Enhancements**:
- GraphService.get_graph() method (expose NetworkX graph)
- VectorIndexer.get_embedding_by_id() method (synonymy detection)

### Performance Targets

| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| PPR execution | <100ms | 50-150ms |
| Multi-hop query | <150ms | 100-200ms |
| Entity extraction | <20ms | 10-30ms |
| Total query latency | <200ms | 150-300ms |
| Memory usage | <500MB | 300-600MB |

---

## Day-by-Day Implementation Plan

### Day 1: HippoRagService Foundation (6 hours)

**Morning Session (3 hours)**

**Task 1.1: Create HippoRagService Skeleton** (90 minutes)
- File: `C:\Users\17175\Desktop\memory-mcp-triple-system\src\services\hipporag_service.py`
- Implement:
  - `__init__(graph_service, entity_service, vector_indexer)` - Dependency injection
  - Type definitions (RetrievalResult, QueryEntity)
  - Basic structure with docstrings
- LOC: ~50 LOC
- Tests: Create `tests/unit/test_hipporag_service.py` (3 tests: initialization)

**Task 1.2: Implement Query Parsing** (90 minutes)
- Method: `_extract_query_entities(query: str) -> List[str]`
- Integration:
  ```python
  entities = self.entity_service.extract_entities(query)
  entity_ids = [self._normalize_entity_text(e['text']) for e in entities]
  ```
- Handle edge cases: empty query, no entities found
- LOC: ~40 LOC
- Tests: TestQueryParsing (5 tests)

**Afternoon Session (3 hours)**

**Task 1.3: Implement Entity-to-Node Matching** (120 minutes)
- Method: `_match_entities_to_nodes(entities: List[str]) -> List[str]`
- Algorithm:
  1. Check exact match in graph (O(1) lookup)
  2. If no exact match, use embedding similarity (ChromaDB query)
  3. Threshold: cosine similarity ≥0.85
- Integration with VectorIndexer
- LOC: ~50 LOC
- Tests: TestNodeMatching (5 tests: exact match, fuzzy match, no match)

**Task 1.4: Add GraphService Enhancement** (60 minutes)
- File: `C:\Users\17175\Desktop\memory-mcp-triple-system\src\services\graph_service.py`
- Add method:
  ```python
  def get_graph(self) -> nx.DiGraph:
      """Return underlying NetworkX graph for advanced algorithms."""
      return self.graph
  ```
- LOC: ~10 LOC
- Tests: 2 tests (get_graph returns valid graph, graph is mutable)

**End of Day 1 Deliverables**:
- ✅ HippoRagService class with initialization + entity extraction
- ✅ GraphService.get_graph() method
- ✅ 15 tests passing (3 init + 5 parsing + 5 matching + 2 graph)
- ✅ ~150 LOC implementation + ~180 LOC tests = 330 total

**Day 1 Checklist**:
```markdown
### Morning Session
- [ ] Create hipporag_service.py skeleton
- [ ] Implement __init__ with dependency injection
- [ ] Implement _extract_query_entities method
- [ ] Create test_hipporag_service.py
- [ ] Tests: 8 tests passing (3 init + 5 parsing)
- [ ] LOC: ~90 implementation + ~100 tests

### Afternoon Session
- [ ] Implement _match_entities_to_nodes method
- [ ] Add GraphService.get_graph() method
- [ ] Tests: 7 tests passing (5 matching + 2 graph)
- [ ] LOC: ~60 implementation + ~80 tests

### End of Day
- [ ] Total tests: 15 passing
- [ ] Total LOC: ~150 implementation + ~180 tests = 330
- [ ] NASA compliance: 100% (all functions ≤60 LOC)
- [ ] Coverage: ≥80%
- [ ] Blockers: None (or document)
```

---

### Day 2: Personalized PageRank Engine (6 hours)

**Morning Session (3 hours)**

**Task 2.1: Create GraphQueryEngine Class** (90 minutes)
- File: `C:\Users\17175\Desktop\memory-mcp-triple-system\src\services\graph_query_engine.py`
- Implement:
  - `__init__(graph_service: GraphService)`
  - `personalized_pagerank(query_nodes: List[str], alpha: float = 0.85) -> Dict[str, float]`
- Algorithm:
  ```python
  personalization = {node: 1.0 / len(query_nodes) for node in query_nodes}
  ppr_scores = nx.pagerank(
      self.graph_service.get_graph(),
      alpha=alpha,
      personalization=personalization,
      max_iter=100,
      tol=1e-6
  )
  ```
- LOC: ~50 LOC
- Tests: TestPPR (5 tests: single node, multiple nodes, convergence)

**Task 2.2: Implement PPR Score Aggregation** (90 minutes)
- Method: `aggregate_chunk_scores(ppr_scores: Dict[str, float]) -> Dict[str, float]`
- Algorithm:
  1. For each chunk node in graph
  2. Get entities mentioned in chunk (GraphService.get_neighbors)
  3. Sum PPR scores for mentioned entities
  4. Return dict of {chunk_id: aggregated_score}
- LOC: ~40 LOC
- Tests: TestAggregation (5 tests: empty PPR, single entity, multiple entities)

**Afternoon Session (3 hours)**

**Task 2.3: Integrate PPR into HippoRagService** (120 minutes)
- Method: `_run_personalized_pagerank(query_nodes: List[str], alpha: float) -> Dict[str, float]`
- Integration:
  ```python
  self.graph_query_engine = GraphQueryEngine(self.graph_service)
  ppr_scores = self.graph_query_engine.personalized_pagerank(query_nodes, alpha)
  ```
- Handle edge cases: no query nodes, empty graph
- LOC: ~30 LOC
- Tests: TestPPRIntegration (6 tests)

**Task 2.4: Implement Chunk Ranking** (60 minutes)
- Method: `_rank_chunks_by_ppr(ppr_scores: Dict[str, float]) -> List[Tuple[str, float]]`
- Algorithm:
  1. Call aggregate_chunk_scores
  2. Sort chunks by score (descending)
  3. Return list of (chunk_id, score) tuples
- LOC: ~30 LOC
- Tests: TestRanking (4 tests: sorting, top-K, empty results)

**End of Day 2 Deliverables**:
- ✅ GraphQueryEngine with PPR implementation
- ✅ Score aggregation working
- ✅ HippoRagService integrated with PPR
- ✅ 20 tests passing (10 new + 15 from Day 1)
- ✅ ~150 LOC implementation + ~200 LOC tests = 350 total

**Day 2 Checklist**:
```markdown
### Morning Session
- [ ] Create graph_query_engine.py
- [ ] Implement personalized_pagerank method
- [ ] Implement aggregate_chunk_scores method
- [ ] Tests: 10 tests passing (5 PPR + 5 aggregation)
- [ ] LOC: ~90 implementation + ~120 tests

### Afternoon Session
- [ ] Integrate PPR into HippoRagService
- [ ] Implement _rank_chunks_by_ppr method
- [ ] Tests: 10 tests passing (6 integration + 4 ranking)
- [ ] LOC: ~60 implementation + ~80 tests

### End of Day
- [ ] Total tests: 35 passing (20 new + 15 from Day 1)
- [ ] Total LOC: ~300 implementation + ~380 tests = 680
- [ ] NASA compliance: ≥95% (check with AST)
- [ ] Coverage: ≥85%
- [ ] Blockers: None (or document)
```

---

### Day 3: Multi-Hop Path Finding (6 hours)

**Morning Session (3 hours)**

**Task 3.1: Implement Multi-Hop Search** (120 minutes)
- Method: `multi_hop_search(source_nodes: List[str], max_hops: int = 3) -> List[List[str]]`
- Algorithm (BFS-based):
  ```python
  all_paths = []
  for source in source_nodes:
      visited = {source}
      queue = [(source, [source], 0)]
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
- LOC: ~50 LOC (split into helper functions if >60 LOC)
- Tests: TestMultiHop (8 tests: 1-hop, 2-hop, 3-hop, no neighbors, cycles)

**Task 3.2: Implement Entity Neighborhood Extraction** (60 minutes)
- Method: `get_entity_neighborhood(entity_id: str, depth: int = 2) -> Dict[str, Any]`
- Reuse existing GraphService.get_subgraph:
  ```python
  return self.graph_service.get_subgraph(entity_id, depth=depth)
  ```
- LOC: ~20 LOC
- Tests: TestNeighborhood (4 tests: depth 1, depth 2, isolated node)

**Afternoon Session (3 hours)**

**Task 3.3: Implement Synonymy Expansion** (90 minutes)
- Method: `expand_via_synonymy(entity_id: str) -> Set[str]`
- Algorithm:
  ```python
  synonyms = {entity_id}
  for neighbor in graph.neighbors(entity_id):
      edge_data = graph.get_edge_data(entity_id, neighbor)
      if edge_data and edge_data.get('type') == 'similar_to':
          synonyms.add(neighbor)
  return synonyms
  ```
- LOC: ~30 LOC
- Tests: TestSynonymy (6 tests: single synonym, multiple, no synonyms)

**Task 3.4: Add VectorIndexer Enhancement** (90 minutes)
- File: `C:\Users\17175\Desktop\memory-mcp-triple-system\src\indexing\vector_indexer.py`
- Add method:
  ```python
  def get_embedding_by_id(self, entity_id: str) -> Optional[np.ndarray]:
      """Retrieve embedding for entity by ID."""
      result = self.collection.get(ids=[entity_id])
      if result['embeddings']:
          return np.array(result['embeddings'][0])
      return None
  ```
- LOC: ~15 LOC
- Tests: 4 tests (valid ID, invalid ID, empty collection)

**End of Day 3 Deliverables**:
- ✅ Multi-hop path finding working
- ✅ Synonymy expansion functional
- ✅ VectorIndexer.get_embedding_by_id() method
- ✅ 22 tests passing (18 new + 4 VectorIndexer)
- ✅ ~115 LOC implementation + ~220 LOC tests = 335 total

**Day 3 Checklist**:
```markdown
### Morning Session
- [ ] Implement multi_hop_search method
- [ ] Implement get_entity_neighborhood method
- [ ] Tests: 12 tests passing (8 multi-hop + 4 neighborhood)
- [ ] LOC: ~70 implementation + ~150 tests

### Afternoon Session
- [ ] Implement expand_via_synonymy method
- [ ] Add VectorIndexer.get_embedding_by_id method
- [ ] Tests: 10 tests passing (6 synonymy + 4 VectorIndexer)
- [ ] LOC: ~45 implementation + ~70 tests

### End of Day
- [ ] Total tests: 57 passing (22 new + 35 from Days 1-2)
- [ ] Total LOC: ~415 implementation + ~600 tests = 1015
- [ ] NASA compliance: ≥95%
- [ ] Coverage: ≥85%
- [ ] Blockers: None (or document)
```

---

### Day 4: Integration Testing and Refinement (6 hours)

**Morning Session (3 hours)**

**Task 4.1: Create Integration Test Suite** (90 minutes)
- File: `C:\Users\17175\Desktop\memory-mcp-triple-system\tests\integration\test_hipporag_integration.py`
- Test fixtures:
  ```python
  @pytest.fixture
  def sample_graph():
      """Build small test graph with entities and chunks."""
      # 10 entities, 5 chunks, 20 edges

  @pytest.fixture
  def hipporag_service(sample_graph):
      """Initialize HippoRagService with test dependencies."""
  ```
- Tests:
  1. `test_full_retrieval_workflow_single_hop` - Query → entities → PPR → ranking
  2. `test_full_retrieval_workflow_multi_hop` - 3-hop question
  3. `test_query_with_no_entities` - "What is the meaning of life?" (no NER)
  4. `test_query_with_entities_not_in_graph` - New entities (cold start)
- LOC: ~120 LOC tests

**Task 4.2: Implement retrieve() Method** (90 minutes)
- Method: `retrieve(query: str, top_k: int = 10, alpha: float = 0.85) -> List[RetrievalResult]`
- End-to-end workflow:
  ```python
  # 1. Extract entities
  query_entities = self._extract_query_entities(query)
  # 2. Match to nodes
  query_nodes = self._match_entities_to_nodes(query_entities)
  # 3. Run PPR
  ppr_scores = self._run_personalized_pagerank(query_nodes, alpha)
  # 4. Rank chunks
  ranked_chunks = self._rank_chunks_by_ppr(ppr_scores)
  # 5. Return top-K
  return ranked_chunks[:top_k]
  ```
- LOC: ~40 LOC
- Tests: TestEndToEnd (5 tests)

**Afternoon Session (3 hours)**

**Task 4.3: Multi-Hop Reasoning Tests** (90 minutes)
- Test scenarios:
  1. `test_multihop_question_answering` - "What company did X start before Y?"
  2. `test_synonymy_edge_usage` - USA = United States
  3. `test_multihop_path_extraction` - Extract connecting paths
- Build test graph with known multi-hop structure:
  ```
  elon_musk --founded--> zip2 --timeline--> paypal --timeline--> tesla
  ```
- LOC: ~100 LOC tests

**Task 4.4: Bug Fixes and Refinements** (90 minutes)
- Run all 62 tests (45 unit + 17 integration)
- Fix any failures
- Refactor functions >60 LOC (NASA Rule 10)
- Add error handling for edge cases
- LOC: ~50 LOC refinements

**End of Day 4 Deliverables**:
- ✅ Full HippoRagService.retrieve() method working
- ✅ 17 integration tests passing
- ✅ All 62 tests passing (45 unit + 17 integration)
- ✅ Bug fixes applied
- ✅ ~90 LOC implementation + ~220 LOC tests = 310 total

**Day 4 Checklist**:
```markdown
### Morning Session
- [ ] Create test_hipporag_integration.py
- [ ] Implement full workflow integration tests
- [ ] Implement retrieve() method in HippoRagService
- [ ] Tests: 9 tests passing (4 integration + 5 end-to-end)
- [ ] LOC: ~40 implementation + ~120 tests

### Afternoon Session
- [ ] Implement multi-hop reasoning tests
- [ ] Fix any test failures
- [ ] Refactor functions >60 LOC
- [ ] Tests: 8 tests passing (3 multi-hop + bugfixes)
- [ ] LOC: ~50 refinements + ~100 tests

### End of Day
- [ ] Total tests: 62 passing (45 unit + 17 integration)
- [ ] Total LOC: ~505 implementation + ~820 tests = 1325
- [ ] NASA compliance: ≥95% (all functions ≤60 LOC)
- [ ] Coverage: ≥85%
- [ ] Blockers: None (or document)
```

---

### Day 5: Performance Benchmarking and Audit (6 hours)

**Morning Session (3 hours)**

**Task 5.1: Create Performance Benchmark Suite** (120 minutes)
- File: `C:\Users\17175\Desktop\memory-mcp-triple-system\tests\performance\test_hipporag_performance.py`
- Benchmarks:
  1. `test_ppr_scalability_1k_nodes` - PPR on 1k node graph (<10ms)
  2. `test_ppr_scalability_10k_nodes` - PPR on 10k node graph (<50ms)
  3. `test_ppr_scalability_100k_nodes` - PPR on 100k node graph (<100ms)
  4. `test_multihop_query_latency_2hop` - 2-hop query (<30ms)
  5. `test_multihop_query_latency_3hop` - 3-hop query (<50ms)
- Use pytest-benchmark plugin:
  ```python
  def test_ppr_scalability_1k_nodes(benchmark, sample_graph_1k):
      result = benchmark(run_pagerank, sample_graph_1k)
      assert benchmark.stats['mean'] < 0.010  # 10ms
  ```
- LOC: ~150 LOC tests

**Task 5.2: Memory Usage Profiling** (60 minutes)
- Tests:
  1. `test_memory_usage_1k_nodes` - <50MB
  2. `test_memory_usage_10k_nodes` - <200MB
  3. `test_memory_usage_100k_nodes` - <500MB
- Use tracemalloc:
  ```python
  import tracemalloc
  tracemalloc.start()
  # ... run operations ...
  current, peak = tracemalloc.get_traced_memory()
  assert peak < 500 * 1024 * 1024  # 500MB
  ```
- LOC: ~60 LOC tests

**Afternoon Session (3 hours)**

**Task 5.3: Run Comprehensive Audit** (90 minutes)
- Theater detection audit:
  ```bash
  python -m analyzer.engines.pattern_detector --file src/services/hipporag_service.py
  python -m analyzer.engines.pattern_detector --file src/services/graph_query_engine.py
  ```
  - Target: 0 theater patterns found
- NASA compliance audit:
  ```bash
  python -c "
  import ast
  with open('src/services/hipporag_service.py', 'r', encoding='utf-8') as f:
      tree = ast.parse(f.read())
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef):
          length = node.end_lineno - node.lineno + 1
          if length > 60:
              print(f'{node.name}: {length} LOC (violation)')
  "
  ```
  - Target: ≥95% compliance
- Coverage audit:
  ```bash
  pytest tests/unit/test_hipporag_service.py --cov=src/services/hipporag_service --cov-report=term-missing
  ```
  - Target: ≥85% coverage

**Task 5.4: Write Week 5 Summary Documentation** (90 minutes)
- File: `C:\Users\17175\Desktop\memory-mcp-triple-system\docs\WEEK-5-DAY-5-IMPLEMENTATION-SUMMARY.md`
- Sections:
  1. **Implementation Summary** (modules, LOC, tests)
  2. **Performance Benchmark Results** (tables with actual numbers)
  3. **Quality Metrics** (coverage, NASA compliance, bugs found/fixed)
  4. **Known Issues and Limitations**
  5. **Week 6 Handoff Notes** (what's ready, what's needed)
- LOC: ~0 implementation + ~200 LOC documentation

**End of Day 5 Deliverables**:
- ✅ 10 performance benchmarks complete
- ✅ All benchmarks within target ranges
- ✅ Comprehensive audit complete (theater, NASA, coverage)
- ✅ Week 5 summary documentation written
- ✅ All 62 tests passing, ready for Week 6

**Day 5 Checklist**:
```markdown
### Morning Session
- [ ] Create test_hipporag_performance.py
- [ ] Implement PPR scalability benchmarks (5 tests)
- [ ] Implement memory profiling tests (3 tests)
- [ ] LOC: ~0 implementation + ~210 tests

### Afternoon Session
- [ ] Run theater detection audit (target: 0 patterns)
- [ ] Run NASA compliance audit (target: ≥95%)
- [ ] Run coverage audit (target: ≥85%)
- [ ] Write WEEK-5-DAY-5-IMPLEMENTATION-SUMMARY.md
- [ ] LOC: ~0 implementation + ~200 documentation

### End of Day
- [ ] Total tests: 72 passing (62 + 10 performance)
- [ ] Total LOC: ~505 implementation + ~1030 tests = 1535
- [ ] NASA compliance: ≥95%
- [ ] Coverage: ≥85%
- [ ] Documentation: Week 5 summary complete
- [ ] Ready for Week 6: YES
```

---

## Module Breakdown with Technical Details

### Module 1: HippoRagService

**File**: `src/services/hipporag_service.py`

**LOC**: ~250 LOC

**Dependencies**:
- GraphService (graph operations)
- EntityService (entity extraction)
- VectorIndexer (embedding similarity)
- GraphQueryEngine (PPR execution)

**Key Methods** (8 total):

1. `__init__(graph_service, entity_service, vector_indexer)` (~20 LOC)
   - Dependency injection
   - Initialize GraphQueryEngine
   - Validate dependencies

2. `retrieve(query, top_k=10, alpha=0.85)` (~40 LOC)
   - Main entry point for retrieval
   - Orchestrates full workflow
   - Returns List[RetrievalResult]

3. `_extract_query_entities(query)` (~40 LOC)
   - Use EntityService to extract entities
   - Normalize entity texts
   - Return List[str] of entity IDs

4. `_match_entities_to_nodes(entities)` (~50 LOC)
   - Exact match check (graph.has_node)
   - Fuzzy match via embedding similarity
   - Threshold: cosine ≥0.85
   - Return List[str] of matched node IDs

5. `_run_personalized_pagerank(query_nodes, alpha)` (~30 LOC)
   - Call GraphQueryEngine.personalized_pagerank
   - Handle edge cases (no nodes, empty graph)
   - Return Dict[str, float] of PPR scores

6. `_rank_chunks_by_ppr(ppr_scores)` (~30 LOC)
   - Call GraphQueryEngine.aggregate_chunk_scores
   - Sort by score descending
   - Return List[Tuple[str, float]]

7. `_normalize_entity_text(text)` (~15 LOC)
   - Lowercase, remove spaces, strip punctuation
   - Return normalized ID

8. `_create_retrieval_result(chunk_id, score)` (~25 LOC)
   - Fetch chunk metadata
   - Create RetrievalResult dataclass
   - Return RetrievalResult

**Type Definitions**:
```python
@dataclass
class RetrievalResult:
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    source_entities: List[str]
```

**Tests**: 15 unit tests
- TestInitialization (3): valid deps, missing deps, invalid deps
- TestQueryParsing (5): with entities, no entities, empty query, multiple entity types
- TestNodeMatching (5): exact match, fuzzy match, no match, multiple entities
- TestRanking (2): sort order, top-K limit

**Coverage Target**: ≥85%

---

### Module 2: GraphQueryEngine

**File**: `src/services/graph_query_engine.py`

**LOC**: ~250 LOC

**Dependencies**:
- GraphService (graph access)
- NetworkX (graph algorithms)
- NumPy (numerical operations)

**Key Methods** (6 total):

1. `__init__(graph_service)` (~15 LOC)
   - Store graph_service reference
   - Cache graph object

2. `personalized_pagerank(query_nodes, alpha=0.85)` (~50 LOC)
   - Create personalization vector (uniform distribution)
   - Call nx.pagerank with personalization
   - Handle convergence failures
   - Return Dict[str, float] of PPR scores

3. `aggregate_chunk_scores(ppr_scores)` (~45 LOC)
   - Iterate over chunk nodes
   - Get mentioned entities (graph.get_neighbors)
   - Sum PPR scores for entities
   - Return Dict[str, float] of chunk scores

4. `multi_hop_search(source_nodes, max_hops=3)` (~60 LOC)
   - BFS traversal from source nodes
   - Track visited nodes (avoid cycles)
   - Collect paths up to max_hops
   - Return List[List[str]] of paths
   - **NOTE**: Split into helper if >60 LOC

5. `get_entity_neighborhood(entity_id, depth=2)` (~30 LOC)
   - Reuse GraphService.get_subgraph
   - Add convenience wrapper
   - Return Dict[str, Any] subgraph

6. `expand_via_synonymy(entity_id)` (~40 LOC)
   - Traverse "similar_to" edges
   - Collect synonym entity IDs
   - Return Set[str] of entities (original + synonyms)

**Tests**: 20 unit tests
- TestPPR (7): single node, multiple nodes, convergence, alpha variation
- TestAggregation (5): empty PPR, single entity, multiple entities, no entities
- TestMultiHop (8): 1-hop, 2-hop, 3-hop, no neighbors, isolated nodes, cycles

**Coverage Target**: ≥90% (core algorithm)

---

### Module 3: Integration Tests

**File**: `tests/integration/test_hipporag_integration.py`

**LOC**: ~250 LOC (pure test code)

**Test Classes** (3 total):

1. **TestEndToEnd** (7 tests):
   - `test_full_retrieval_workflow_single_hop` - Basic query
   - `test_full_retrieval_workflow_multi_hop` - 3-hop question
   - `test_retrieve_with_alpha_variation` - Different alpha values
   - `test_retrieve_empty_graph` - No nodes in graph
   - `test_retrieve_no_matching_nodes` - Entities not in graph
   - `test_retrieve_top_k_limit` - Verify top-K results
   - `test_retrieve_performance_100ms` - Latency check

2. **TestMultiHopReasoning** (5 tests):
   - `test_multihop_question_answering` - "What company did X start before Y?"
   - `test_multihop_path_extraction` - Extract paths between entities
   - `test_multihop_accuracy` - Correct answer in top-3
   - `test_synonymy_edge_usage` - USA = United States
   - `test_multihop_complex_graph` - 100+ nodes, 500+ edges

3. **TestEdgeCases** (5 tests):
   - `test_query_with_no_entities` - "What is the meaning of life?"
   - `test_query_with_entities_not_in_graph` - New entities (cold start)
   - `test_empty_query` - Query = ""
   - `test_malformed_graph` - Missing edges, orphan nodes
   - `test_concurrent_queries` - Thread safety (if applicable)

**Fixtures**:
```python
@pytest.fixture
def small_graph():
    """10 entities, 5 chunks, 20 edges."""

@pytest.fixture
def medium_graph():
    """100 entities, 50 chunks, 500 edges."""

@pytest.fixture
def multihop_graph():
    """Known multi-hop structure (elon_musk → companies)."""
```

**Coverage Target**: 100% integration coverage

---

### Module 4: Performance Benchmarks

**File**: `tests/performance/test_hipporag_performance.py`

**LOC**: ~250 LOC (pure test code)

**Benchmark Categories** (10 total):

1. **PPR Scalability** (3 benchmarks):
   - `test_ppr_scalability_1k_nodes` - Target: <10ms
   - `test_ppr_scalability_10k_nodes` - Target: <50ms
   - `test_ppr_scalability_100k_nodes` - Target: <100ms

2. **Multi-Hop Query Latency** (2 benchmarks):
   - `test_multihop_latency_2hop` - Target: <30ms
   - `test_multihop_latency_3hop` - Target: <50ms

3. **Memory Usage** (3 benchmarks):
   - `test_memory_usage_1k_nodes` - Target: <50MB
   - `test_memory_usage_10k_nodes` - Target: <200MB
   - `test_memory_usage_100k_nodes` - Target: <500MB

4. **Entity Extraction Speed** (2 benchmarks):
   - `test_entity_extraction_50_words` - Target: <10ms
   - `test_entity_extraction_200_words` - Target: <20ms

**Benchmark Framework**:
```python
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

def test_ppr_scalability_100k_nodes(benchmark: BenchmarkFixture, large_graph):
    """Benchmark PPR on 100k node graph."""
    result = benchmark(
        hipporag_service.retrieve,
        query="What is PageRank?",
        top_k=10
    )
    assert benchmark.stats['mean'] < 0.100  # 100ms
    assert benchmark.stats['stddev'] < 0.020  # Low variance
```

**Output Format**:
- Tables with mean, median, stddev, min, max
- Pass/fail based on target thresholds
- Save results to JSON for historical tracking

---

## Complete Test Plan

### Test Pyramid Structure

```
       /\
      /10\  Performance Benchmarks (10 tests)
     /----\
    / 17   \ Integration Tests (17 tests)
   /--------\
  /    45    \ Unit Tests (45 tests)
 /------------\
```

**Total Tests**: 72 (45 unit + 17 integration + 10 performance)

---

### Unit Tests Breakdown (45 total)

**HippoRagService** (15 tests) - `test_hipporag_service.py`:
1. `test_init_with_valid_dependencies` - Constructor works
2. `test_init_missing_graph_service` - Raises error
3. `test_init_missing_entity_service` - Raises error
4. `test_extract_query_entities_person_org` - Extract PERSON + ORG
5. `test_extract_query_entities_no_entities` - Query with no entities
6. `test_extract_query_entities_empty_query` - Empty string
7. `test_extract_query_entities_multiple_types` - PERSON, ORG, GPE
8. `test_match_entities_exact_match` - Entity ID in graph
9. `test_match_entities_fuzzy_match` - Embedding similarity >0.85
10. `test_match_entities_no_match` - No similar nodes found
11. `test_match_entities_threshold_boundary` - Cosine = 0.85 exactly
12. `test_rank_chunks_by_ppr_scores` - Aggregate PPR scores
13. `test_rank_chunks_empty_ppr` - No PPR scores (empty result)
14. `test_rank_chunks_top_k_limit` - Return only top-K
15. `test_normalize_entity_text` - Lowercasing, strip punctuation

**GraphQueryEngine** (20 tests) - `test_graph_query_engine.py`:
1. `test_init_with_graph_service` - Constructor works
2. `test_personalized_pagerank_single_node` - PPR from 1 node
3. `test_personalized_pagerank_multiple_nodes` - PPR from 2+ nodes
4. `test_personalized_pagerank_convergence` - Converges <100 iterations
5. `test_personalized_pagerank_alpha_0_85` - Default alpha
6. `test_personalized_pagerank_alpha_variation` - Different alpha (0.5, 0.95)
7. `test_personalized_pagerank_empty_graph` - No nodes
8. `test_aggregate_chunk_scores_single_entity` - 1 entity per chunk
9. `test_aggregate_chunk_scores_multiple_entities` - Multiple entities per chunk
10. `test_aggregate_chunk_scores_no_entities` - Chunk mentions no entities
11. `test_aggregate_chunk_scores_empty_ppr` - No PPR scores
12. `test_aggregate_chunk_scores_normalization` - Scores sum to 1.0
13. `test_multi_hop_search_2_hops` - 2-hop paths from source
14. `test_multi_hop_search_3_hops` - 3-hop paths
15. `test_multi_hop_search_no_neighbors` - Isolated node
16. `test_multi_hop_search_cycles` - Graph with cycles (avoid infinite loop)
17. `test_get_entity_neighborhood_depth_1` - 1-hop neighborhood
18. `test_get_entity_neighborhood_depth_2` - 2-hop neighborhood
19. `test_expand_via_synonymy_single` - 1 synonym found
20. `test_expand_via_synonymy_no_synonyms` - No similar_to edges

**Integration** (10 tests) - `test_hipporag_integration.py` (subset):
1. `test_full_workflow_integration` - Query → entities → PPR → ranking
2. `test_retrieve_performance_target` - <200ms for medium graph
3. `test_retrieve_accuracy` - Correct chunks in top-3
4. `test_empty_graph_handling` - No nodes, returns empty
5. `test_cold_start_entities` - Entities not in graph
6. `test_concurrent_retrieval` - Thread safety (if applicable)
7. `test_large_graph_100k_nodes` - Performance on large graph
8. `test_synonymy_improves_recall` - USA = United States
9. `test_multihop_3_hop_question` - Complex multi-hop
10. `test_normalize_scores` - Scores in [0, 1] range

---

### Integration Tests Breakdown (17 total)

**TestEndToEnd** (7 tests):
1. `test_full_retrieval_workflow_single_hop` - Basic query
2. `test_full_retrieval_workflow_multi_hop` - 3-hop question
3. `test_retrieve_with_alpha_variation` - Alpha 0.7, 0.85, 0.95
4. `test_retrieve_empty_graph` - No nodes
5. `test_retrieve_no_matching_nodes` - Entities not in graph
6. `test_retrieve_top_k_limit` - Verify top-K
7. `test_retrieve_performance_100ms` - Latency <100ms

**TestMultiHopReasoning** (5 tests):
1. `test_multihop_question_answering` - "What company did X start before Y?"
2. `test_multihop_path_extraction` - Extract paths
3. `test_multihop_accuracy` - Correct answer in top-3
4. `test_synonymy_edge_usage` - USA = United States
5. `test_multihop_complex_graph` - 100+ nodes

**TestEdgeCases** (5 tests):
1. `test_query_with_no_entities` - "What is the meaning of life?"
2. `test_query_with_entities_not_in_graph` - New entities
3. `test_empty_query` - Query = ""
4. `test_malformed_graph` - Missing edges, orphan nodes
5. `test_concurrent_queries` - Thread safety

---

### Performance Benchmarks Breakdown (10 total)

**PPR Scalability** (3 benchmarks):
1. `test_ppr_scalability_1k_nodes` - <10ms
2. `test_ppr_scalability_10k_nodes` - <50ms
3. `test_ppr_scalability_100k_nodes` - <100ms

**Multi-Hop Latency** (2 benchmarks):
1. `test_multihop_latency_2hop` - <30ms
2. `test_multihop_latency_3hop` - <50ms

**Memory Usage** (3 benchmarks):
1. `test_memory_usage_1k_nodes` - <50MB
2. `test_memory_usage_10k_nodes` - <200MB
3. `test_memory_usage_100k_nodes` - <500MB

**Entity Extraction** (2 benchmarks):
1. `test_entity_extraction_50_words` - <10ms
2. `test_entity_extraction_200_words` - <20ms

---

## Risk Mitigation Plan

### Risk 1: PPR Convergence Performance

**Description**: NetworkX PPR may be slow for large graphs (100k nodes)

**Probability**: 30%

**Impact**: High (blocks <100ms target)

**Mitigation Strategy**:
1. **Day 2**: Benchmark PPR on small graph (1k nodes) to establish baseline
2. **Day 3**: Test on medium graph (10k nodes), measure convergence iterations
3. **Day 5**: Test on large graph (100k nodes), profile with cProfile
4. **If slow**:
   - Use sparse matrix operations (scipy.sparse)
   - Cache PPR results for common queries (LRU cache)
   - Implement early stopping (epsilon=1e-4 instead of 1e-6)
   - Fall back to approximate PPR (Monte Carlo sampling)
   - Use `nx.pagerank_scipy` (faster for large graphs)

**Owner**: Coder agent (Day 2-5)

**Success Metric**: PPR <100ms for 100k nodes

---

### Risk 2: NASA Rule 10 Violations

**Description**: Complex algorithms may exceed 60 LOC per function

**Probability**: 40%

**Impact**: Medium (requires refactoring)

**Mitigation Strategy**:
1. **Prevention**:
   - Write functions incrementally (Day 1-4)
   - Check LOC daily with AST script
   - Use helper functions early (don't wait for violations)
2. **Day 5 Audit**:
   - Run NASA compliance check
   - Identify functions >60 LOC
   - Refactor into smaller functions:
     - Split PPR into: `_create_personalization_vector`, `_run_pagerank_iteration`, `_check_convergence`
     - Split multi_hop_search into: `_bfs_traversal`, `_collect_paths`, `_filter_cycles`
3. **Acceptable Violations**:
   - Allow up to 5% violations (≤3 functions) if refactoring hurts readability
   - Document reason for each violation

**Owner**: Coder agent (ongoing, Day 5 audit)

**Success Metric**: ≥95% NASA compliance

---

### Risk 3: Integration Complexity

**Description**: Three services (Hippo + Graph + Entity) may have coordination issues

**Probability**: 20%

**Impact**: Medium (delays testing)

**Mitigation Strategy**:
1. **Day 1**: Define clear interfaces early
   - RetrievalResult dataclass
   - QueryEntity type definition
   - Mock dependencies in unit tests
2. **Day 2-3**: Use builder pattern for test fixtures
   ```python
   class GraphBuilder:
       def add_entity(name, type): ...
       def add_chunk(id, text): ...
       def add_edge(source, target, type): ...
       def build(): ...
   ```
3. **Day 4**: Integration tests use real dependencies (not mocks)
4. **Daily integration testing**: Don't wait until Day 4

**Owner**: Coder agent (Day 1-4)

**Success Metric**: All 17 integration tests passing by Day 4

---

### Risk 4: Performance Targets Missed

**Description**: <100ms may not be achievable for complex queries

**Probability**: 25%

**Impact**: Medium (adjust targets or optimize)

**Mitigation Strategy**:
1. **Day 2**: Profile early (cProfile on simple query)
2. **Day 3**: Identify bottlenecks (likely NetworkX calls)
3. **Day 5**: Optimize hot paths:
   - Cache graph.successors() calls
   - Use sparse matrix for PPR (scipy.sparse)
   - Vectorize score aggregation (NumPy operations)
   - Pre-compute node degrees (avoid redundant calculations)
4. **If targets still missed**:
   - Document actual performance vs. targets
   - Adjust targets to realistic values (e.g., <150ms instead of <100ms)
   - Defer optimization to Week 6

**Owner**: Coder agent (Day 2-5)

**Success Metric**: Document performance benchmarks, even if targets missed

---

## Definition of Done (Week 5)

### Code Quality Checklist

- [ ] All modules implemented (HippoRagService, GraphQueryEngine)
- [ ] All functions ≤60 LOC (NASA Rule 10, ≥95% compliance)
- [ ] Type hints complete (mypy passing, no errors)
- [ ] Docstrings complete (Google style, all public methods)
- [ ] Error handling comprehensive (all edge cases covered)
- [ ] No hardcoded values (use constants or config)
- [ ] No print() debugging statements (use logging)
- [ ] Code formatted (black, isort, flake8)

### Testing Checklist

- [ ] 45 unit tests passing (100% pass rate)
- [ ] 17 integration tests passing (100% pass rate)
- [ ] 10 performance benchmarks run (all results documented)
- [ ] ≥85% code coverage (overall)
- [ ] ≥90% coverage (core algorithms: PPR, multi-hop)
- [ ] All test fixtures working (graph builders, sample data)
- [ ] No skipped tests (all tests run in CI/CD)

### Performance Checklist

- [ ] Graph queries <100ms (100k nodes) OR documented if slower
- [ ] PPR convergence <50ms (median case)
- [ ] Multi-hop queries <150ms (3 hops)
- [ ] Memory usage <500MB (100k nodes)
- [ ] Entity extraction <20ms (200 words)
- [ ] No memory leaks (tracemalloc shows stable usage)

### Integration Checklist

- [ ] GraphService integration working (get_graph() method added)
- [ ] EntityService integration working (entity extraction functional)
- [ ] VectorIndexer integration working (get_embedding_by_id() method added)
- [ ] ChromaDB vector search compatible (no breaking changes)
- [ ] MCP tool endpoints ready for Week 6 (interfaces defined)

### Documentation Checklist

- [ ] Code review passed (self-review or peer review)
- [ ] docs/WEEK-5-DAY-5-IMPLEMENTATION-SUMMARY.md written
- [ ] Algorithm documentation complete (PPR, multi-hop explained)
- [ ] API documentation generated (docstrings → HTML)
- [ ] Performance benchmark results documented (tables, charts)
- [ ] Known issues documented (limitations, future work)

### Audit Checklist

- [ ] Theater detection: 0 patterns found (no TODO, FIXME, mock data)
- [ ] Functionality audit: All 72 tests passing
- [ ] Style audit: ≥95% NASA compliance
- [ ] Security audit: No vulnerabilities (Bandit scan)
- [ ] Import validation: All imports resolve correctly
- [ ] Circular dependency check: No circular imports

---

## Week 5 Success Metrics

### Quantitative Metrics

| Metric | Target | Measurement | Status |
|--------|--------|-------------|--------|
| **Unit tests** | 45 | pytest execution | TBD |
| **Integration tests** | 17 | pytest execution | TBD |
| **Performance benchmarks** | 10 | pytest-benchmark | TBD |
| **Code coverage** | ≥85% | pytest-cov | TBD |
| **NASA compliance** | ≥95% | AST analysis | TBD |
| **Graph queries** | <100ms | Benchmark mean | TBD |
| **Memory usage** | <500MB | tracemalloc peak | TBD |
| **LOC implementation** | ~700 | Line count | TBD |
| **LOC tests** | ~1030 | Line count | TBD |

### Qualitative Metrics

- [ ] Multi-hop reasoning working (3-hop questions answered correctly)
- [ ] Personalized PageRank accurate (converges, correct scores)
- [ ] Synonymy expansion functional (USA = United States works)
- [ ] Integration with existing services seamless (no breaking changes)
- [ ] Code clean and maintainable (readable, well-structured)
- [ ] Documentation comprehensive (API docs, examples, benchmarks)

---

## Handoff to Week 6

### Week 6 Prerequisites (from Week 5)

**Week 5 Definition of Done**: Must be 100% complete before Week 6 starts

- [ ] All 72 tests passing (45 unit + 17 integration + 10 performance)
- [ ] Performance targets met (or documented if missed)
- [ ] No critical bugs (P0/P1 bugs must be fixed)
- [ ] Documentation up to date (WEEK-5-DAY-5-IMPLEMENTATION-SUMMARY.md complete)
- [ ] GraphService.get_graph() method added
- [ ] VectorIndexer.get_embedding_by_id() method added

### Week 6 Scope (Preview)

**Core Focus**: Two-stage coordinator + MCP integration + production readiness

**Day-by-Day**:
- **Day 1**: TwoStageCoordinator foundation (vector + graph fusion)
- **Day 2**: Confidence scoring + synonymy detection
- **Day 3**: MCP tool integration (HippoRagSearchTool)
- **Day 4**: End-to-end testing (Obsidian vault workflow)
- **Day 5**: Documentation + polish (user guides, API docs)

**Deliverables**:
- TwoStageCoordinator class (combines vector + graph retrieval)
- Confidence scoring (vector-graph agreement)
- Synonymy detection (build similar_to edges)
- MCP tool integration (callable via MCP server)
- 3 documentation guides (HIPPORAG-IMPLEMENTATION.md, TWO-STAGE-RETRIEVAL-GUIDE.md, MCP-SERVER-QUICKSTART.md)

**Total LOC Budget (Week 6)**:
- Implementation: ~470 LOC (220 coordinator + 150 synonymy + 100 MCP tool)
- Tests: ~340 LOC (160 unit + 180 integration)
- Documentation: ~600 LOC (3 guides)
- Total: ~1,410 LOC

---

## Summary

### Week 5 Scope

**Core Focus**: HippoRAG graph-only retrieval (no vector fusion)

**Days 1-3**: Build HippoRAG + PPR + Multi-hop
**Day 4**: Integration testing and refinement
**Day 5**: Performance benchmarking and audit

### Total LOC Budget

| Category | LOC |
|----------|-----|
| **Implementation** | ~700 LOC |
| - HippoRagService | 250 LOC |
| - GraphQueryEngine | 250 LOC |
| - GraphService enhancement | 10 LOC |
| - VectorIndexer enhancement | 15 LOC |
| - Integration code | 175 LOC |
| **Tests** | ~1,030 LOC |
| - Unit tests | 580 LOC |
| - Integration tests | 250 LOC |
| - Performance benchmarks | 200 LOC |
| **Documentation** | ~200 LOC |
| - WEEK-5-DAY-5-IMPLEMENTATION-SUMMARY.md | 200 LOC |
| **Total** | **~1,930 LOC** |

### Timeline

**5 days × 6 hours/day = 30 hours total**

- Day 1: 6 hours (Foundation)
- Day 2: 6 hours (PPR)
- Day 3: 6 hours (Multi-hop)
- Day 4: 6 hours (Integration)
- Day 5: 6 hours (Benchmarking)

### Readiness

**This plan is**:
- ✅ Actionable (clear tasks for each day)
- ✅ Specific (LOC estimates, test counts)
- ✅ Achievable (realistic timeline, proven dependencies)
- ✅ Measurable (quantitative success metrics)
- ✅ Time-bound (5-day schedule)

**The coder agent can start Day 1 immediately.**

---

**Version**: 1.0
**Date**: 2025-10-18
**Status**: Implementation Plan Complete - Ready for Week 5 Day 1
**Planning Agent**: Claude Sonnet 4.5
**Next Action**: Begin Week 5 Day 1 (HippoRagService Foundation)
**Estimated Completion**: 5 days (30 hours)

---

**End of Week 5 Implementation Plan**
