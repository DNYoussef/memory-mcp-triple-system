# Week 10 Implementation Plan - Bayesian Graph RAG

**Date**: 2025-10-18
**Status**: Ready for Implementation
**Agent**: Claude Code (Queen) using Loop 2 methodology
**Duration**: 24 hours (planned)

---

## Executive Summary

Week 10 implements **Bayesian Graph RAG** using pgmpy for probabilistic inference over the knowledge graph. This enables uncertainty quantification and probabilistic reasoning ("P(X|Y) = 0.73") for complex queries.

**Key Insight**: Bayesian complexity is mitigated by query router (Week 8) which skips Bayesian tier for 60% of queries (simple queries use KV store only).

**Deliverables**:
- Production Code: 480 LOC (Bayesian network + probabilistic query engine)
- Test Code: 480 LOC (30 tests)
- Components: 2 (NetworkBuilder, ProbabilisticQueryEngine)

---

## Requirements (from PLAN v6.0/v7.0)

### Core Functionality

1. **Bayesian Network Construction**:
   - Build belief network from knowledge graph (NetworkX → pgmpy)
   - Node limit: max 1000 nodes (prune low-frequency entities)
   - Edge pruning: confidence <0.3 (sparse graphs only)
   - Network caching: 1-hour TTL

2. **Probabilistic Inference**:
   - Variable elimination algorithm
   - Belief propagation for Bayesian queries
   - Conditional probability: P(X|Y, Z)
   - Marginal probability: P(X)

3. **Uncertainty Quantification**:
   - Return probabilities with results: "P(answer) = 0.73"
   - Confidence intervals: [low, high]
   - Entropy: measure uncertainty

4. **Complexity Mitigation**:
   - Timeout: 1s (fallback to Vector + HippoRAG)
   - Max nodes: 1000 (prevent combinatorial explosion)
   - Sparse graphs: skip low-confidence edges

---

## Architecture

### Component 1: Network Builder ([src/bayesian/network_builder.py](../../src/bayesian/network_builder.py))

**Purpose**: Convert knowledge graph → Bayesian belief network

**Target LOC**: 240 LOC

**Key Methods** (≤60 LOC each, NASA Rule 10):
1. `build_network(graph: nx.DiGraph) -> BayesianNetwork` (50 LOC)
   - Convert NetworkX graph to pgmpy Bayesian network
   - Prune to max 1000 nodes
   - Filter edges by confidence ≥0.3

2. `estimate_cpds(network: BayesianNetwork) -> BayesianNetwork` (45 LOC)
   - Estimate Conditional Probability Distributions
   - Use maximum likelihood estimation
   - Handle missing data

3. `validate_network(network: BayesianNetwork) -> bool` (30 LOC)
   - Check for cycles (DAG validation)
   - Verify CPD completeness
   - Validate node/edge counts

4. `prune_nodes(graph: nx.DiGraph, max_nodes: int) -> nx.DiGraph` (40 LOC)
   - Rank nodes by frequency/importance
   - Keep top-K nodes
   - Preserve graph connectivity

5. `cache_network(network: BayesianNetwork, cache_key: str)` (25 LOC)
   - Store network in memory cache (1-hour TTL)
   - Invalidate on graph updates

**Dependencies**:
- `pgmpy` - Bayesian network library
- `networkx` - Graph operations
- `src/services/graph_service.py` - Knowledge graph access

---

### Component 2: Probabilistic Query Engine ([src/bayesian/probabilistic_query_engine.py](../../src/bayesian/probabilistic_query_engine.py))

**Purpose**: Execute probabilistic queries over Bayesian network

**Target LOC**: 240 LOC

**Key Methods** (≤60 LOC each, NASA Rule 10):
1. `query_conditional(network, evidence: Dict, query_vars: List) -> Dict` (55 LOC)
   - Calculate P(X|Y=y, Z=z)
   - Use variable elimination
   - Return probabilities for all states

2. `query_marginal(network, query_vars: List) -> Dict` (40 LOC)
   - Calculate P(X)
   - Marginalize over all other variables
   - Return probability distribution

3. `calculate_entropy(prob_dist: Dict) -> float` (25 LOC)
   - Measure uncertainty: H(X) = -Σ p(x) log p(x)
   - Higher entropy = more uncertainty

4. `get_most_probable_explanation(network, evidence: Dict) -> Dict` (50 LOC)
   - Find MAP (Maximum A Posteriori) assignment
   - Given evidence, find most likely values for other vars
   - Return {var: value, probability: P}

5. `execute_with_timeout(query_func, timeout: float) -> Optional[Dict]` (30 LOC)
   - Execute query with 1s timeout
   - Return None if timeout (fallback to Vector + HippoRAG)

**Dependencies**:
- `pgmpy.inference` - VariableElimination, BeliefPropagation
- `src/bayesian/network_builder.py` - Network construction

---

## Implementation Phases

### Phase 1: Network Builder (8 hours)

**Files to Create**:
1. `src/bayesian/__init__.py` (NEW)
2. `src/bayesian/network_builder.py` (NEW, 240 LOC)

**Implementation Order**:
1. Create `build_network()` - Convert graph to Bayesian network (50 LOC)
2. Create `prune_nodes()` - Node pruning for complexity control (40 LOC)
3. Create `estimate_cpds()` - CPD estimation (45 LOC)
4. Create `validate_network()` - Network validation (30 LOC)
5. Create `cache_network()` - Caching with TTL (25 LOC)
6. Add helper methods (50 LOC total)

**Success Criteria**:
- All methods ≤60 LOC (NASA Rule 10)
- Network builds from graph with ≤1000 nodes
- Sparse edge filtering working (confidence ≥0.3)
- Caching with 1-hour TTL functional

---

### Phase 2: Probabilistic Query Engine (8 hours)

**Files to Create**:
1. `src/bayesian/probabilistic_query_engine.py` (NEW, 240 LOC)

**Implementation Order**:
1. Create `query_conditional()` - Conditional probability P(X|Y) (55 LOC)
2. Create `query_marginal()` - Marginal probability P(X) (40 LOC)
3. Create `get_most_probable_explanation()` - MAP queries (50 LOC)
4. Create `calculate_entropy()` - Uncertainty measurement (25 LOC)
5. Create `execute_with_timeout()` - Timeout handling (30 LOC)
6. Add helper methods (40 LOC total)

**Success Criteria**:
- All methods ≤60 LOC (NASA Rule 10)
- Conditional/marginal queries working correctly
- 1s timeout enforced (fallback mechanism)
- Uncertainty quantification accurate

---

### Phase 3: Unit Tests (6 hours)

**Files to Create**:
1. `tests/unit/test_bayesian_network.py` (NEW, 240 LOC, 20 tests)
2. `tests/unit/test_probabilistic_query_engine.py` (NEW, 240 LOC, 10 tests)

**Test Categories**:

**Network Builder Tests** (20 tests):
1. `test_build_network_from_graph` - Build network from sample graph
2. `test_prune_nodes_max_limit` - Verify 1000 node limit
3. `test_filter_low_confidence_edges` - Edge pruning at 0.3 threshold
4. `test_estimate_cpds` - CPD estimation correct
5. `test_validate_network_dag` - DAG validation (no cycles)
6. `test_validate_network_cpds` - CPD completeness check
7. `test_cache_network` - Caching with TTL
8. `test_cache_invalidation` - Cache clears after 1 hour
9. `test_empty_graph` - Handle empty graph gracefully
10. `test_single_node_graph` - Edge case: 1 node
11. `test_large_graph_pruning` - Prune >1000 nodes correctly
12. `test_disconnected_components` - Handle disconnected graphs
13. `test_cpd_missing_data` - Handle missing CPD data
14. `test_network_serialization` - Save/load network
15. `test_prune_preserves_connectivity` - Pruning doesn't disconnect graph
16. `test_edge_confidence_filtering` - Only edges ≥0.3 kept
17. `test_node_ranking_by_frequency` - Frequent nodes prioritized
18. `test_build_network_performance` - <100ms for 1000 nodes
19. `test_validate_rejects_cyclic` - Cyclic graphs rejected
20. `test_nasa_rule_10_compliance` - All methods ≤60 LOC

**Probabilistic Query Engine Tests** (10 tests):
1. `test_query_conditional_simple` - P(X|Y=y) calculation
2. `test_query_marginal` - P(X) calculation
3. `test_calculate_entropy` - Entropy correct
4. `test_most_probable_explanation` - MAP query correct
5. `test_timeout_fallback` - 1s timeout triggers fallback
6. `test_multiple_evidence_vars` - P(X|Y=y, Z=z)
7. `test_query_all_states` - Return all probability states
8. `test_uncertainty_high_entropy` - High entropy detected
9. `test_query_performance` - <1s for typical queries
10. `test_nasa_rule_10_compliance` - All methods ≤60 LOC

---

### Phase 4: Integration Tests (2 hours)

**Files to Create**:
1. `tests/integration/test_bayesian_integration.py` (NEW, ~100 LOC, TBD tests)

**Integration Scenarios**:
1. Full pipeline: Graph → Network → Query → Results
2. Integration with GraphService (Week 8)
3. Timeout fallback to Vector + HippoRAG
4. Network caching across multiple queries

---

## Dependencies

### External Libraries

**NEW Dependency**:
- `pgmpy` (0.1.23+) - Bayesian network inference

**Installation**:
```bash
pip install pgmpy
```

**Existing Dependencies** (from Weeks 1-9):
- `networkx` (2.8+) - Graph operations (Week 8)
- `numpy` (1.24+) - Numerical operations
- `loguru` - Logging

---

## Quality Requirements

### NASA Rule 10 Compliance
- **Target**: ≥95% (all methods ≤60 LOC)
- **Expected**: 100% (following Week 9 pattern)

### Test Coverage
- **Target**: ≥80%
- **Expected**: ≥90% (following Week 9 pattern)

### Theater Detection
- **Target**: <60/100
- **Expected**: 0/100 (no mocks, no TODOs)

### Type Hints
- **Target**: 100%
- **Expected**: 100%

### Docstrings
- **Target**: 100%
- **Expected**: 100%

---

## Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Network build | <100ms | 1000 nodes max, sparse graph |
| Query latency | <1s | Timeout enforced, fallback available |
| Cache hit rate | ≥80% | 1-hour TTL, stable graph |
| Node limit | ≤1000 | Prevent combinatorial explosion |
| Edge filtering | ≥0.3 confidence | Sparse graphs only |

---

## Risk Mitigation

### Risk #1: Bayesian Complexity Explosion (150 points in PREMORTEM)

**Mitigation Strategies**:
1. **Query Router Skip** (Week 8): 60% of queries skip Bayesian tier entirely
2. **Node Limit**: Max 1000 nodes prevents combinatorial explosion
3. **Sparse Graphs**: Confidence ≥0.3 edge filtering
4. **Timeout Fallback**: 1s timeout → fallback to Vector + HippoRAG
5. **Network Caching**: 1-hour TTL reduces rebuild overhead

**Expected Residual Risk**: 150 → 90 (40% reduction via mitigation)

---

## Success Criteria

### Pre-Testing Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| Production LOC | 480 | TBD |
| NetworkBuilder LOC | 240 | TBD |
| ProbabilisticQueryEngine LOC | 240 | TBD |
| NASA Compliance | ≥95% | TBD |
| Type Hints | 100% | TBD |
| Docstrings | 100% | TBD |
| Theater Score | <60 | TBD |

### Post-Testing Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| Unit Tests | 30 | TBD |
| Test Coverage | ≥80% | TBD |
| Tests Passing | 100% | TBD |
| Network Build | <100ms | TBD |
| Query Latency | <1s | TBD |
| Timeout Fallback | Working | TBD |

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Network Builder | 8 hours | Pending |
| Phase 2: Query Engine | 8 hours | Pending |
| Phase 3: Unit Tests | 6 hours | Pending |
| Phase 4: Integration Tests | 2 hours | Pending |
| **TOTAL** | **24 hours** | **Pending** |

---

## Next Steps

1. ✅ Create implementation plan (this document)
2. ⏳ Phase 1: Implement Network Builder (240 LOC)
3. ⏳ Phase 2: Implement Query Engine (240 LOC)
4. ⏳ Phase 3: Create unit tests (30 tests, 480 LOC)
5. ⏳ Phase 4: Run 3-part audit (Functionality, Style, Theater)
6. ⏳ Create Week 10 completion summary

---

**Plan Created**: 2025-10-18
**Agent**: Claude Code (Queen)
**Methodology**: Loop 2 (Implementation)
**Status**: READY FOR IMPLEMENTATION
**Next Milestone**: Phase 1 (Network Builder implementation)
