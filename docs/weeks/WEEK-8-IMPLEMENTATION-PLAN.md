# Week 8 Implementation Plan - Memory MCP Triple System

**Date**: 2025-10-18
**Status**: IN PROGRESS
**Agent**: Claude Code (Queen) using Loop 2 Implementation methodology
**Duration**: 26 hours (estimated)

---

## Executive Summary

Week 8 delivers 3 critical components for the Memory MCP Triple System:

1. **GraphRAG Entity Consolidation** (300 LOC) - NetworkX-based entity merging with spaCy NER
2. **Query Router** (240 LOC) - Polyglot storage selector with pattern-based routing
3. **Query Replay Capability** (80 LOC) - Deterministic debugging for failed queries

**Total Deliverables**:
- Production Code: 620 LOC
- Test Code: 360 LOC
- Total Tests: 23 (15 entity + 5 router + 3 replay)
- Risk Mitigation: Context-assembly bugs (Risk #13): 160 → 80 points

---

## Context from Week 7

### What's Already Implemented ✅

From Week 7 (COMPLETE):
- ✅ 5-tier storage architecture schema ([config/memory-schema.yaml](../../config/memory-schema.yaml))
- ✅ Schema validation ([src/validation/schema_validator.py](../../src/validation/schema_validator.py))
- ✅ KV store (Tier 1) ([src/stores/kv_store.py](../../src/stores/kv_store.py))
- ✅ Query logging infrastructure ([src/debug/query_trace.py](../../src/debug/query_trace.py))
- ✅ Obsidian vault sync ([src/mcp/obsidian_client.py](../../src/mcp/obsidian_client.py))

From Week 6 (COMPLETE):
- ✅ ChromaDB VectorIndexer ([src/indexing/vector_indexer.py](../../src/indexing/vector_indexer.py))
- ✅ HippoRAG service ([src/services/hipporag_service.py](../../src/services/hipporag_service.py))
- ✅ Graph service (NetworkX) ([src/services/graph_service.py](../../src/services/graph_service.py))
- ✅ Entity extraction (spaCy) - assumed in existing HippoRAG

### What Week 8 Adds

**GraphRAG Entity Consolidation**:
- Merges duplicate entities (e.g., "NASA Rule 10", "NASA_Rule_10", "rule 10")
- Consolidates chunk references across variants
- Uses spaCy NER + string similarity (Levenshtein distance)
- Target: ≥90% consolidation accuracy (Risk #7 mitigation)

**Query Router**:
- Pattern-based routing to appropriate storage tier(s)
- Examples:
  - "What's my coding style?" → KV Store (O(1) preference)
  - "What client worked on X?" → Relational (SQL entities)
  - "What about machine learning?" → Vector (semantic search)
  - "What led to this bug?" → Graph (multi-hop reasoning)
  - "What happened on 2025-10-15?" → Event Log (temporal queries)
- Optimization: Skip Bayesian for execution mode (60% of queries)
- Target: ≥90% routing accuracy

**Query Replay**:
- Reconstruct exact context at original timestamp
- Re-run query with same context
- Compare original vs replay traces
- Identify context bugs (wrong store, wrong mode, etc.)
- Target: 100% deterministic replay

---

## Implementation Plan (4 Phases)

### Phase 1: GraphRAG Entity Consolidation (8 hours)

**Files to Create**:
1. `src/services/entity_service.py` (300 LOC)
   - `EntityConsolidator` class
   - Entity merging logic (spaCy NER + string similarity)
   - Chunk reference consolidation
   - Graph update integration

**Implementation Structure**:
```python
# src/services/entity_service.py

import spacy
from typing import List, Dict, Set, Tuple
from difflib import SequenceMatcher
import networkx as nx

class EntityConsolidator:
    """
    Consolidate duplicate entities in knowledge graph.

    PREMORTEM Risk #7 Mitigation:
    - Target: ≥90% consolidation accuracy
    - Method: spaCy NER + Levenshtein distance
    - Use case: Merge "NASA Rule 10", "NASA_Rule_10", "rule 10"

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, nlp_model: str = "en_core_web_sm"):
        """Initialize with spaCy model."""
        self.nlp = spacy.load(nlp_model)

    def find_duplicate_entities(
        self,
        graph: nx.DiGraph,
        similarity_threshold: float = 0.85
    ) -> List[Set[str]]:
        """
        Find groups of duplicate entities using string similarity.

        Args:
            graph: NetworkX knowledge graph
            similarity_threshold: Min similarity to consider duplicates (0.85)

        Returns:
            List of entity groups (sets) that are duplicates

        Example:
            >>> consolidator = EntityConsolidator()
            >>> duplicates = consolidator.find_duplicate_entities(graph)
            >>> print(duplicates)
            [
                {"NASA Rule 10", "NASA_Rule_10", "rule 10"},
                {"Python", "python", "Python language"}
            ]
        """
        # Implementation in Phase 1
        pass

    def merge_entities(
        self,
        graph: nx.DiGraph,
        entity_group: Set[str],
        canonical_name: str = None
    ) -> str:
        """
        Merge duplicate entities into single canonical entity.

        Args:
            graph: NetworkX knowledge graph
            entity_group: Set of duplicate entity names
            canonical_name: Name for merged entity (auto-select if None)

        Returns:
            Canonical entity name

        Logic:
        1. Select canonical name (most frequent or provided)
        2. Consolidate chunk references from all variants
        3. Merge node attributes (frequency, importance)
        4. Update edges to point to canonical entity
        5. Remove duplicate nodes
        """
        # Implementation in Phase 1
        pass

    def consolidate_all(
        self,
        graph: nx.DiGraph,
        similarity_threshold: float = 0.85
    ) -> Dict[str, any]:
        """
        Run full consolidation pipeline on graph.

        Returns:
            {
                "groups_found": 15,
                "entities_merged": 42,
                "canonical_entities": ["NASA Rule 10", "Python", ...],
                "consolidation_rate": 0.93  # 93% accuracy
            }
        """
        # Implementation in Phase 1
        pass
```

**Test Strategy**:
- 15 tests in `tests/unit/test_entity_service.py`
- Test cases:
  - Exact duplicates ("NASA Rule 10" == "NASA Rule 10")
  - Case variants ("Python" vs "python")
  - Underscore variants ("NASA_Rule_10" vs "NASA Rule 10")
  - Partial matches ("rule 10" vs "NASA Rule 10")
  - False positives (don't merge "Python" and "C++")
  - Chunk reference consolidation
  - Graph integrity after merge
  - Edge preservation
  - Node attribute merging
  - Consolidation accuracy ≥90%

---

### Phase 2: Query Router Implementation (8 hours)

**Files to Create**:
1. `src/routing/query_router.py` (240 LOC)
   - `QueryRouter` class
   - Pattern-based routing logic
   - Multi-tier query support
   - Mode-based optimization (skip Bayesian for execution)

**Implementation Structure**:
```python
# src/routing/query_router.py

from typing import List, Dict, Optional
from enum import Enum
import re

class StorageTier(Enum):
    """Storage tier identifiers."""
    KV = "kv"
    RELATIONAL = "relational"
    VECTOR = "vector"
    GRAPH = "graph"
    EVENT_LOG = "event_log"
    BAYESIAN = "bayesian"

class QueryMode(Enum):
    """Query modes from mode detection."""
    EXECUTION = "execution"
    PLANNING = "planning"
    BRAINSTORMING = "brainstorming"

class QueryRouter:
    """
    Route queries to appropriate storage tier(s) based on pattern.

    PREMORTEM Risk #1 Mitigation:
    - Skip Bayesian for execution mode (60% of queries)
    - Reduces query latency from 800ms → 200ms

    Routing Rules:
    - "What's my X?" → KV (preferences)
    - "What client/project X?" → Relational (entities)
    - "What about X?" → Vector (semantic)
    - "What led to X?" → Graph (multi-hop)
    - "What happened on X?" → Event Log (temporal)
    - "P(X|Y)?" → Bayesian (probabilistic)

    Target: ≥90% routing accuracy
    """

    def __init__(self):
        """Initialize router with pattern rules."""
        self.patterns = self._compile_patterns()

    def route(
        self,
        query: str,
        mode: QueryMode,
        user_context: Dict = None
    ) -> List[StorageTier]:
        """
        Route query to appropriate storage tier(s).

        Args:
            query: User query text
            mode: Detected query mode (execution/planning/brainstorming)
            user_context: Optional context for routing hints

        Returns:
            List of storage tiers to query (ordered by priority)

        Example:
            >>> router = QueryRouter()
            >>> tiers = router.route("What's my coding style?", QueryMode.EXECUTION)
            >>> print(tiers)
            [StorageTier.KV]

            >>> tiers = router.route("What about machine learning?", QueryMode.PLANNING)
            >>> print(tiers)
            [StorageTier.VECTOR, StorageTier.GRAPH]
        """
        # Implementation in Phase 2
        pass

    def should_skip_bayesian(
        self,
        mode: QueryMode,
        query_complexity: float = None
    ) -> bool:
        """
        Decide whether to skip Bayesian network query.

        PREMORTEM Risk #1 Optimization:
        - Skip for execution mode (60% of queries)
        - Always query for planning/brainstorming modes

        Args:
            mode: Query mode
            query_complexity: Optional complexity score (0-1)

        Returns:
            True if should skip Bayesian, False otherwise
        """
        # Implementation in Phase 2
        pass

    def _compile_patterns(self) -> Dict[str, List[StorageTier]]:
        """
        Compile regex patterns for routing rules.

        Returns pattern dictionary:
            {
                r"^what'?s? my (.+)": [StorageTier.KV],
                r"what (client|project) (.+)": [StorageTier.RELATIONAL],
                r"what about (.+)": [StorageTier.VECTOR, StorageTier.GRAPH],
                ...
            }
        """
        # Implementation in Phase 2
        pass

    def validate_routing_accuracy(
        self,
        test_queries: List[Dict]
    ) -> float:
        """
        Validate routing accuracy against labeled test queries.

        Args:
            test_queries: List of {query, expected_tiers, mode}

        Returns:
            Accuracy score (0-1), target ≥0.90
        """
        # Implementation in Phase 2
        pass
```

**Test Strategy**:
- 5 tests in `tests/unit/test_query_router.py`
- Test cases:
  - KV routing ("What's my X?" patterns)
  - Relational routing ("What client/project X?")
  - Vector routing ("What about X?")
  - Graph routing ("What led to X?")
  - Event log routing ("What happened on X?")
  - Bayesian skip logic (execution mode)
  - Multi-tier queries
  - Routing accuracy ≥90% (100-query benchmark)

---

### Phase 3: Query Replay Capability (4 hours)

**Files to Create**:
1. `src/debug/query_replay.py` (80 LOC)
   - `QueryReplay` class
   - Context reconstruction logic
   - Trace comparison
   - Difference reporting

**Implementation Structure** (from PLAN v7.0 FINAL):
```python
# src/debug/query_replay.py

from uuid import UUID
from datetime import datetime
from typing import Dict, Tuple, List
from src.debug.query_trace import QueryTrace
import sqlite3

class QueryReplay:
    """
    Replay queries deterministically for debugging.

    PREMORTEM Risk #13 Mitigation:
    - Reconstruct exact context (stores, mode, lifecycle)
    - Re-run query with same context
    - Compare traces (original vs replay)
    - Identify context bugs (wrong store, wrong mode, etc.)

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, db_path: str = "memory.db"):
        """Initialize with database path."""
        self.db_path = db_path

    def replay(self, query_id: UUID) -> Tuple[QueryTrace, Dict]:
        """
        Replay query with exact same context.

        Args:
            query_id: UUID of original query

        Returns:
            (new_trace, diff): New trace + difference from original

        Example:
            >>> replay = QueryReplay()
            >>> new_trace, diff = replay.replay("abc-123")
            >>> print(diff)
            {
                "mode_detected": {"original": "execution", "replay": "planning"},
                "stores_queried": {"original": ["vector"], "replay": ["vector", "relational"]},
                "output": {"original": "Wrong answer", "replay": "Correct answer"}
            }
        """
        # 1. Fetch original trace
        original = self._get_trace(query_id)

        # 2. Reconstruct exact context
        context = self._reconstruct_context(
            timestamp=original.timestamp,
            user_context=original.user_context
        )

        # 3. Re-run query
        # (NOTE: Requires NexusProcessor from Week 11, placeholder for now)
        new_trace = self._rerun_query(original.query, context)

        # 4. Compare traces
        diff = self._compare_traces(original, new_trace)

        return new_trace, diff

    def _get_trace(self, query_id: UUID) -> QueryTrace:
        """Fetch query trace from SQLite by ID."""
        # Implementation in Phase 3
        pass

    def _reconstruct_context(
        self,
        timestamp: datetime,
        user_context: Dict
    ) -> Dict:
        """
        Reconstruct exact context at timestamp.

        - Memory state (chunks available at timestamp)
        - User preferences (as of timestamp)
        - Session lifecycle (active sessions at timestamp)
        """
        # Implementation in Phase 3
        pass

    def _rerun_query(self, query: str, context: Dict) -> QueryTrace:
        """
        Re-run query with reconstructed context.

        NOTE: Full implementation requires NexusProcessor (Week 11).
        Week 8: Create mock implementation for testing.
        """
        # Implementation in Phase 3 (mock for Week 8)
        pass

    def _compare_traces(
        self,
        original: QueryTrace,
        replay: QueryTrace
    ) -> Dict:
        """
        Compare two traces, identify differences.

        Returns:
            Dictionary of differences:
            {
                "mode_detected": {"original": "X", "replay": "Y"},
                "stores_queried": {"original": [...], "replay": [...]},
                "output": {"original": "...", "replay": "..."}
            }
        """
        # Implementation in Phase 3
        pass
```

**Test Strategy**:
- 3 tests in `tests/unit/test_query_replay.py`
- Test cases:
  - Replay successful query (deterministic, diff should be empty)
  - Replay failed query (context bug, diff shows differences)
  - Context reconstruction (verify memory snapshot matches timestamp)

---

### Phase 4: Integration Testing & Audits (6 hours)

**Integration Tests** (`tests/integration/test_week8_integration.py`, 10 tests):

1. **Entity Consolidation + Graph Integration**:
   - Test entity merging updates graph correctly
   - Verify chunk references consolidated
   - Validate no broken edges after merge

2. **Query Router + Storage Tier Integration**:
   - Test KV routing actually queries KV store
   - Test vector routing queries VectorIndexer
   - Test graph routing queries GraphService
   - Validate multi-tier queries work correctly

3. **Query Replay + Query Logging Integration**:
   - Test replay fetches trace from SQLite
   - Test context reconstruction with KV store
   - Validate replay produces identical results (deterministic)

4. **Full Pipeline Integration**:
   - Ingest document → Entity consolidation → Query router → Results
   - End-to-end flow with all Week 8 components

**Audit Workflow**:
1. Theater Detection (Audit #1): Scan for TODOs, placeholders, mock code
2. Functionality (Audit #2): Run all 23 tests, validate 100% passing
3. Style Compliance (Audit #3): Check NASA Rule 10 (≥92% compliance)

---

## Success Criteria

### Pre-Launch (Week 8)

| Criterion | Target | Status |
|-----------|--------|--------|
| Production LOC | 620 | TBD |
| Test LOC | 360 | TBD |
| Total Tests | 23 | TBD |
| Tests Passing | 23/23 (100%) | TBD |
| Coverage | ≥80% | TBD |
| NASA Compliance | ≥92% | TBD |
| Theater Score | <60 | TBD |
| Entity Consolidation Accuracy | ≥90% | TBD |
| Query Routing Accuracy | ≥90% | TBD |
| Replay Determinism | 100% | TBD |

### Risk Mitigation Targets

| Risk | Baseline | Week 8 Target | Mitigation |
|------|----------|---------------|------------|
| #7: Entity Consolidation <90% | 75 | 0 | GraphRAG entity merging ≥90% accuracy |
| #1: Bayesian Complexity | 150 | 50 | Query router skips 60% of queries |
| #13: Context-Assembly Bugs | 160 | 80 | Replay capability enables deterministic debugging |

---

## File Structure

```
src/
├── services/
│   └── entity_service.py          (NEW, 300 LOC)
├── routing/
│   └── query_router.py             (NEW, 240 LOC)
└── debug/
    ├── query_trace.py              (Week 7, existing)
    └── query_replay.py             (NEW, 80 LOC)

tests/
├── unit/
│   ├── test_entity_service.py      (NEW, 15 tests, ~120 LOC)
│   ├── test_query_router.py        (NEW, 5 tests, ~100 LOC)
│   └── test_query_replay.py        (NEW, 3 tests, ~60 LOC)
└── integration/
    └── test_week8_integration.py   (NEW, 10 tests, ~150 LOC)

docs/weeks/
└── WEEK-8-IMPLEMENTATION-PLAN.md   (This file)
```

---

## Dependencies

### From Week 7 (Required)
- ✅ QueryTrace ([src/debug/query_trace.py](../../src/debug/query_trace.py))
- ✅ KV Store ([src/stores/kv_store.py](../../src/stores/kv_store.py))
- ✅ Memory Schema ([config/memory-schema.yaml](../../config/memory-schema.yaml))

### From Week 6 (Required)
- ✅ GraphService ([src/services/graph_service.py](../../src/services/graph_service.py))
- ✅ VectorIndexer ([src/indexing/vector_indexer.py](../../src/indexing/vector_indexer.py))
- ✅ spaCy NER (assumed in existing code)

### External Libraries
- `spacy` (3.7+) - Entity extraction
- `networkx` (3.2+) - Graph operations
- `sqlite3` (built-in) - Query logging storage

---

## Known Limitations

1. **Query Replay**: Full implementation requires NexusProcessor (Week 11)
   - Week 8: Mock implementation for testing
   - Week 11: Wire to real NexusProcessor

2. **Entity Consolidation**: Similarity threshold (0.85) may need tuning
   - Start with 0.85, adjust based on accuracy testing
   - Trade-off: Higher threshold = fewer false positives, but more false negatives

3. **Query Router**: Pattern-based routing may miss edge cases
   - 100-query benchmark will identify gaps
   - Iterative refinement based on real-world usage

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1** | 8 hours | GraphRAG Entity Consolidation (300 LOC, 15 tests) |
| **Phase 2** | 8 hours | Query Router (240 LOC, 5 tests) |
| **Phase 3** | 4 hours | Query Replay (80 LOC, 3 tests) |
| **Phase 4** | 6 hours | Integration tests (10 tests) + Audits |
| **TOTAL** | **26 hours** | **620 LOC + 360 test LOC + 23 tests** |

---

## Next Steps

1. ✅ Week 8 plan created
2. ⏳ Phase 1: Implement GraphRAG Entity Consolidation
3. ⏳ Phase 2: Implement Query Router
4. ⏳ Phase 3: Implement Query Replay
5. ⏳ Phase 4: Integration testing & audits

---

**Plan Status**: ✅ APPROVED
**Ready to Begin**: YES
**Agent**: Claude Code (Queen)
**Methodology**: Loop 2 Implementation
**Next Milestone**: Phase 1 (Entity Consolidation)

---

**Document Version**: 1.0
**Author**: Claude Code (Queen)
**Last Updated**: 2025-10-18T18:00:00Z
**Next Review**: Week 8 Phase 1 Complete
