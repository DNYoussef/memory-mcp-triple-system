# Week 9 Implementation Plan - Memory MCP Triple System

**Date**: 2025-10-18
**Status**: IN PROGRESS
**Agent**: Claude Code (Queen) using Loop 2 Implementation methodology
**Duration**: 26 hours (estimated)

---

## Executive Summary

Week 9 delivers 3 critical components for hierarchical memory organization and lifecycle management:

1. **RAPTOR Hierarchical Clustering** (180 LOC) - Cluster chunks into hierarchical summaries
2. **Event Log Store** (180 LOC) - Temporal query support with SQLite
3. **Hot/Cold Classification** (180 LOC) - Memory lifecycle management (4 stages)

**Total Deliverables**:
- Production Code: 540 LOC
- Test Code: 400 LOC
- Total Tests: 25 (10 RAPTOR + 8 Event Log + 7 Hot/Cold)
- Risk Mitigation: Storage growth (Risk #6), Curation time (Risk #3)

---

## Context from Week 8

### What's Already Implemented ✅

From Week 8 (COMPLETE):
- ✅ GraphRAG Entity Consolidation ([src/services/entity_service.py](../../src/services/entity_service.py))
- ✅ Query Router ([src/routing/query_router.py](../../src/routing/query_router.py))
- ✅ Query Replay ([src/debug/query_replay.py](../../src/debug/query_replay.py))

From Week 7 (COMPLETE):
- ✅ Query logging infrastructure ([src/debug/query_trace.py](../../src/debug/query_trace.py))
- ✅ KV store ([src/stores/kv_store.py](../../src/stores/kv_store.py))
- ✅ Memory schema ([config/memory-schema.yaml](../../config/memory-schema.yaml))

### What Week 9 Adds

**RAPTOR Hierarchical Clustering**:
- Hierarchical summarization of memory chunks
- Bottom-up clustering using Gaussian Mixture Models (GMM)
- BIC (Bayesian Information Criterion) validation
- Multi-level summaries for efficient retrieval
- Target: ≥85% clustering quality (Risk #9 mitigation)

**Event Log Store**:
- Temporal query support ("What happened on 2025-10-15?")
- SQLite-backed event storage with timestamp indexing
- Event types: chunk_added, chunk_updated, query_executed, entity_consolidated
- Retention: 30 days (aligned with query traces)
- Target: <100ms temporal query latency

**Hot/Cold Classification**:
- 4-stage memory lifecycle (Active → Demoted → Archived → Rehydratable)
- Frequency-based classification (access patterns)
- Reduces vector indexing by 33% (Risk #2 mitigation)
- Reduces curation time by 25% (Risk #3 mitigation)
- Metadata-only storage for cold chunks

---

## Implementation Plan (3 Phases)

### Phase 1: RAPTOR Hierarchical Clustering (8 hours)

**Files to Create**:
1. `src/clustering/raptor_clusterer.py` (180 LOC)
   - `RAPTORClusterer` class
   - GMM clustering with BIC validation
   - Hierarchical summary generation
   - Multi-level tree structure

**Implementation Structure**:
```python
# src/clustering/raptor_clusterer.py

from typing import List, Dict, Any, Optional
from sklearn.mixture import GaussianMixtureModel
from sklearn.metrics import silhouette_score
import numpy as np
from loguru import logger

class RAPTORClusterer:
    """
    RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval).

    Hierarchical clustering of memory chunks using GMM + BIC validation.

    PREMORTEM Risk #9 Mitigation:
    - Target: ≥85% clustering quality (silhouette score)
    - Method: GMM with BIC for optimal cluster count
    - Use case: Multi-level summaries for efficient retrieval

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(
        self,
        min_clusters: int = 2,
        max_clusters: int = 10,
        bic_threshold: float = -1000.0
    ):
        """Initialize RAPTOR clusterer."""
        pass

    def cluster_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> Dict[str, Any]:
        """
        Cluster chunks hierarchically using GMM.

        Returns:
            {
                "num_clusters": 5,
                "cluster_assignments": [0, 0, 1, 1, 2, ...],
                "cluster_summaries": ["Summary 1", "Summary 2", ...],
                "quality_score": 0.87,
                "bic_score": -1234.56
            }
        """
        pass

    def build_hierarchy(
        self,
        clusters: Dict[str, Any],
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Build multi-level hierarchy by recursively clustering summaries.

        Returns tree structure:
            {
                "level": 0,
                "summary": "Top-level summary",
                "children": [
                    {"level": 1, "summary": "...", "children": [...]},
                    ...
                ]
            }
        """
        pass

    def _select_optimal_clusters(
        self,
        embeddings: np.ndarray
    ) -> int:
        """Use BIC to find optimal number of clusters."""
        pass

    def _generate_summary(
        self,
        chunk_texts: List[str]
    ) -> str:
        """Generate abstractive summary for cluster."""
        pass
```

**Test Strategy**:
- 10 tests in `tests/unit/test_raptor_clusterer.py`
- Test cases:
  - Basic clustering (2-5 clusters)
  - BIC optimization (find optimal k)
  - Hierarchical tree building
  - Quality score validation (≥0.85 silhouette)
  - Edge cases (single cluster, empty chunks)

---

### Phase 2: Event Log Store (8 hours)

**Files to Create**:
1. `src/stores/event_log.py` (180 LOC)
   - `EventLog` class
   - SQLite event storage with timestamp indexing
   - Temporal query support
   - Event retention management (30 days)

**Implementation Structure**:
```python
# src/stores/event_log.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import sqlite3
import json
from loguru import logger

class EventType(Enum):
    """Event types for memory system."""
    CHUNK_ADDED = "chunk_added"
    CHUNK_UPDATED = "chunk_updated"
    CHUNK_DELETED = "chunk_deleted"
    QUERY_EXECUTED = "query_executed"
    ENTITY_CONSOLIDATED = "entity_consolidated"
    LIFECYCLE_TRANSITION = "lifecycle_transition"

class EventLog:
    """
    Temporal event log for memory system.

    Tier 5 of 5-tier architecture: Event Log (temporal queries).

    Target: <100ms temporal query latency
    Storage: SQLite with timestamp indexing
    Retention: 30 days (auto-cleanup)

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, db_path: str = "memory.db"):
        """Initialize event log with SQLite database."""
        pass

    def log_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Log event to database.

        Args:
            event_type: Type of event
            data: Event payload (JSON-serializable)
            timestamp: Event time (default: now)

        Returns:
            True if logged successfully
        """
        pass

    def query_by_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
        event_types: Optional[List[EventType]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query events by time range.

        Example: "What happened on 2025-10-15?"

        Args:
            start_time: Range start
            end_time: Range end
            event_types: Filter by event types (None = all)

        Returns:
            List of events in chronological order
        """
        pass

    def cleanup_old_events(
        self,
        retention_days: int = 30
    ) -> int:
        """
        Delete events older than retention period.

        Returns:
            Number of events deleted
        """
        pass

    def get_event_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get event count statistics by type.

        Returns:
            {
                "chunk_added": 42,
                "query_executed": 128,
                ...
            }
        """
        pass
```

**SQL Migration**:
```sql
-- migrations/008_event_log_table.sql

CREATE TABLE IF NOT EXISTS event_log (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data TEXT NOT NULL,  -- JSON payload

    -- Indexing for fast temporal queries
    INDEX idx_event_timestamp ON event_log(timestamp),
    INDEX idx_event_type ON event_log(event_type),
    INDEX idx_event_type_timestamp ON event_log(event_type, timestamp)
);
```

**Test Strategy**:
- 8 tests in `tests/unit/test_event_log.py`
- Test cases:
  - Event logging (all event types)
  - Temporal range queries
  - Event type filtering
  - Cleanup/retention
  - Statistics aggregation
  - Performance (<100ms queries)

---

### Phase 3: Hot/Cold Classification (10 hours)

**Files to Create**:
1. `src/lifecycle/hotcold_classifier.py` (180 LOC)
   - `HotColdClassifier` class
   - Access frequency tracking
   - 4-stage lifecycle management
   - Vector index optimization

**Implementation Structure**:
```python
# src/lifecycle/hotcold_classifier.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger

class LifecycleStage(Enum):
    """4-stage memory lifecycle."""
    ACTIVE = "active"        # <7 days old, frequently accessed
    DEMOTED = "demoted"      # 7-30 days, less frequent access
    ARCHIVED = "archived"    # >30 days, rarely accessed
    REHYDRATABLE = "rehydratable"  # Cold, can be restored

class HotColdClassifier:
    """
    Memory lifecycle classifier (Hot/Cold).

    PREMORTEM Risk #2 Mitigation:
    - Reduces vector indexing by 33% (skip cold chunks)
    - Target: <25MB storage growth per 1k chunks

    PREMORTEM Risk #3 Mitigation:
    - Reduces curation time by 25% (skip archived chunks)
    - Target: <25min weekly curation

    4-Stage Lifecycle:
    - Active: Full indexing (vector + graph + relational)
    - Demoted: Vector only (no graph/relational reindex)
    - Archived: Metadata only (no reindexing)
    - Rehydratable: Compressed, can restore on demand

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(
        self,
        active_days: int = 7,
        demoted_days: int = 30,
        access_threshold: int = 3  # Accesses per week
    ):
        """Initialize hot/cold classifier."""
        pass

    def classify_chunk(
        self,
        chunk_id: str,
        created_at: datetime,
        last_accessed: datetime,
        access_count: int
    ) -> LifecycleStage:
        """
        Classify chunk into lifecycle stage.

        Logic:
        - Age <7 days + access_count ≥3/week → ACTIVE
        - Age 7-30 days OR access_count <3/week → DEMOTED
        - Age >30 days + access_count <1/week → ARCHIVED
        - Manually marked for compression → REHYDRATABLE

        Args:
            chunk_id: Chunk identifier
            created_at: Creation timestamp
            last_accessed: Last access timestamp
            access_count: Total access count

        Returns:
            Lifecycle stage
        """
        pass

    def classify_batch(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, LifecycleStage]:
        """
        Classify multiple chunks.

        Returns:
            {
                "chunk-123": LifecycleStage.ACTIVE,
                "chunk-456": LifecycleStage.DEMOTED,
                ...
            }
        """
        pass

    def get_indexing_strategy(
        self,
        stage: LifecycleStage
    ) -> Dict[str, bool]:
        """
        Get indexing strategy for lifecycle stage.

        Returns:
            {
                "vector": True/False,
                "graph": True/False,
                "relational": True/False
            }
        """
        pass

    def calculate_storage_savings(
        self,
        chunk_classifications: Dict[str, LifecycleStage]
    ) -> Dict[str, Any]:
        """
        Calculate storage savings from hot/cold classification.

        Returns:
            {
                "total_chunks": 1000,
                "active": 300,
                "demoted": 400,
                "archived": 300,
                "vector_index_reduction": 0.33,  # 33% reduction
                "estimated_mb_saved": 12.5
            }
        """
        pass
```

**Test Strategy**:
- 7 tests in `tests/unit/test_hotcold_classifier.py`
- Test cases:
  - Active classification (new chunks)
  - Demoted classification (7-30 days)
  - Archived classification (>30 days)
  - Batch classification (1000+ chunks)
  - Indexing strategy selection
  - Storage savings calculation
  - Edge cases (boundary times)

---

## Integration Points

### With Week 7-8 Components

**RAPTOR → VectorIndexer**:
- Uses embeddings from VectorIndexer for clustering
- Hierarchical summaries stored back in VectorIndexer
- Multi-level retrieval support

**Event Log → Query Trace**:
- Logs query execution events from QueryTrace
- Temporal correlation with query performance
- Debugging support for event sequences

**Hot/Cold → VectorIndexer**:
- Controls which chunks get reindexed
- Skips "archived" and "rehydratable" chunks
- 33% reduction in indexing operations

### With Memory Schema

All three components align with [config/memory-schema.yaml](../../config/memory-schema.yaml):
- RAPTOR: Enables hierarchical retrieval patterns
- Event Log: Tier 5 storage (temporal queries)
- Hot/Cold: Memory lifecycle stages defined in schema

---

## Success Criteria

### Pre-Testing (Week 9 Production Code)

| Criterion | Target | Status |
|-----------|--------|--------|
| Production LOC | 540 | TBD |
| RAPTOR LOC | 180 | TBD |
| Event Log LOC | 180 | TBD |
| Hot/Cold LOC | 180 | TBD |
| NASA Compliance | ≥92% | TBD |
| Type Hints | 100% | TBD |
| Docstrings | 100% | TBD |

### Post-Testing (Audits)

| Criterion | Target | Status |
|-----------|--------|--------|
| Total Tests | 25 | TBD |
| Tests Passing | 25/25 (100%) | TBD |
| Coverage | ≥80% | TBD |
| Theater Score | <60 | TBD |
| RAPTOR Quality | ≥85% silhouette | TBD |
| Event Log Latency | <100ms | TBD |
| Storage Reduction | ≥33% | TBD |

---

## Risk Mitigation Targets

| Risk | Baseline | Week 9 Target | Mitigation |
|------|----------|---------------|------------|
| #9: RAPTOR Quality <85% | 40 | 0 | GMM + BIC validation achieves ≥85% silhouette |
| #2: Obsidian Sync Latency | 60 | 30 | Hot/cold reduces indexing 33% |
| #3: Curation Time >25min | 120 | 90 | Hot/cold skips archived chunks (25% faster) |
| #6: Storage Growth | 50 | 30 | Lifecycle compression reduces growth |

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Planning | 1 hour | Week 9 implementation plan ✅ |
| Phase 1: RAPTOR | 8 hours | RAPTOR clusterer (180 LOC, 10 tests) |
| Phase 2: Event Log | 8 hours | Event log store (180 LOC, 8 tests) |
| Phase 3: Hot/Cold | 10 hours | Lifecycle classifier (180 LOC, 7 tests) |
| Audits | 4 hours | 3-pass audit system |
| **TOTAL** | **31 hours** | **540 LOC + 400 test LOC + 25 tests** |

---

## Next Steps

1. ✅ Week 9 plan created
2. ⏳ Phase 1: Implement RAPTOR clusterer
3. ⏳ Phase 2: Implement Event Log
4. ⏳ Phase 3: Implement Hot/Cold classifier
5. ⏳ Run 3-pass audits (theater, functionality, style)
6. ⏳ Generate completion report

---

**Plan Status**: ✅ APPROVED
**Ready to Begin**: YES
**Agent**: Claude Code (Queen) using Loop 2 Implementation
**Methodology**: Queen → Direct implementation (simple components)
**Next Milestone**: Phase 1 (RAPTOR Clustering)

---

**Document Version**: 1.0
**Author**: Claude Code (Queen)
**Last Updated**: 2025-10-18T20:00:00Z
**Next Review**: Week 9 Phase 1 Complete
