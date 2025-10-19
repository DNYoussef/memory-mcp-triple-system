# Memory MCP Triple System - PLAN v7.0 FINAL

**Version**: 7.0 FINAL (Loop 1 Iteration 4 - Integrated with PREMORTEM v7.0)
**Date**: 2025-10-18
**Status**: Production-Ready (GO at 96% confidence)
**Duration**: 8 weeks (Weeks 7-14)
**Estimated Effort**: 200 hours (25 hours/week average, +4 hours from v7.0 for earlier debugger)
**Risk Score**: 890 points (11% reduction from v6.0 baseline)

---

## Executive Summary

**PLAN v7.0 FINAL** integrates PREMORTEM v7.0 findings, with **context-assembly debugger implementation moved to Weeks 7-11** (incremental) instead of Week 14 (big bang). This reduces integration risk and enables early debugging of Week 8-10 issues.

**Key Change from v7.0**: Context debugger is **P0 architectural requirement**, not a Week 14 add-on.

**8-Week Roadmap Enhancements**:
1. **Week 7**: + Query logging infrastructure (100 LOC, 5 tests)
2. **Week 8**: + Replay capability (80 LOC, 3 tests)
3. **Week 11**: + Error attribution logic (80 LOC, 5 tests)
4. **Week 14**: Dashboard integration only (NOT full debugger implementation)

**Total Deliverables**:
- **Production Code**: 3,570 LOC (vs 3,420 in v7.0, +4%)
- **Test Code**: 2,520 LOC (vs 2,440 in v7.0, +3%)
- **Total Tests**: 576 (321 baseline + 255 new, vs 506 in v7.0)
- **Performance**: <800ms query latency, <25min curation
- **Risk Mitigation**: Context-assembly bugs: 80 points (mitigated from 320)

---

## Critical Path Changes (PREMORTEM Integration)

| Week | v7.0 Original | v7.0 FINAL | Reason |
|------|---------------|------------|--------|
| Week 7 | Schema + KV + Obsidian | **+ Query logging** | Risk #13: Log from Day 1 |
| Week 8 | Router + GraphRAG | **+ Replay capability** | Risk #13: Deterministic debugging |
| Week 11 | Nexus + Briefs | **+ Error attribution** | Risk #13: Know context bugs vs model bugs |
| Week 14 | Debugger (full) | **Dashboard integration** | Week 7-11 implemented incrementally |

**Rationale** (PREMORTEM Risk #13):
> "When output is wrong, replay query with same context to debug. Trace: Wrong mode → wrong retrieval → wrong output."

Incremental implementation (Weeks 7-11) allows debugging of Week 8-10 issues as they occur, not waiting until Week 14.

---

## Week 7: 5-Tier Storage + Memory-as-Code + Query Logging (NEW)

**Duration**: 26 hours (vs 24 hours in v7.0, +2 hours for query logging)
**Priority**: P0 (critical path + Risk #13 mitigation)

### v7.0 FINAL Enhancements

**NEW Task: Query Logging Infrastructure** (2 hours)

*Context* (PREMORTEM Risk #13):
> "No detailed logging to debug (can't replay failed queries)."

*Files to Create*:
- `src/debug/query_trace.py` (100 LOC)
- `tests/unit/test_query_trace.py` (80 LOC)
- SQL migration: `migrations/007_query_traces_table.sql` (30 lines)

*Implementation*:
```python
# src/debug/query_trace.py

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from uuid import UUID, uuid4

@dataclass
class QueryTrace:
    """
    Query trace record (logged for EVERY query).

    Stored in SQLite `query_traces` table for 30-day retention.
    Used for:
    - Debugging failed queries (replay with same context)
    - Error attribution (context bugs vs model bugs)
    - Performance monitoring (latency breakdown)

    PREMORTEM Risk #13 Mitigation:
    - 100% logging (no sampling)
    - Deterministic replay (same context → same output)
    - Error attribution (70% context bugs, 30% model bugs)
    """

    # Identifiers
    query_id: UUID
    timestamp: datetime

    # Input
    query: str
    user_context: Dict  # {"session_id": ..., "user_id": ...}

    # Mode Detection
    mode_detected: str  # "execution" | "planning" | "brainstorming"
    mode_confidence: float  # 0.0-1.0
    mode_detection_ms: int

    # Routing
    stores_queried: List[str]  # ["vector", "relational"], etc.
    routing_logic: str  # "KV skip (simple query)", "Bayesian skip (execution mode)"

    # Retrieval
    retrieved_chunks: List[Dict]  # [{"id": ..., "score": ..., "source": ...}]
    retrieval_ms: int

    # Verification (if execution mode)
    verification_result: Optional[Dict]  # {"verified": True/False, "ground_truth_match": ...}
    verification_ms: int

    # Output
    output: str
    total_latency_ms: int

    # Error Attribution
    error: Optional[str]  # NULL if success, error message if failure
    error_type: Optional[str]  # "context_bug" | "model_bug" | "system_error"

    @classmethod
    def create(cls, query: str, user_context: Dict) -> "QueryTrace":
        """Create new query trace."""
        return cls(
            query_id=uuid4(),
            timestamp=datetime.now(),
            query=query,
            user_context=user_context,
            mode_detected="",
            mode_confidence=0.0,
            mode_detection_ms=0,
            stores_queried=[],
            routing_logic="",
            retrieved_chunks=[],
            retrieval_ms=0,
            verification_result=None,
            verification_ms=0,
            output="",
            total_latency_ms=0,
            error=None,
            error_type=None
        )

    def log(self):
        """
        Save trace to SQLite `query_traces` table.

        Schema:
        CREATE TABLE query_traces (
            query_id TEXT PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            query TEXT NOT NULL,
            user_context TEXT NOT NULL,  -- JSON
            mode_detected TEXT,
            mode_confidence REAL,
            mode_detection_ms INTEGER,
            stores_queried TEXT,  -- JSON array
            routing_logic TEXT,
            retrieved_chunks TEXT,  -- JSON array
            retrieval_ms INTEGER,
            verification_result TEXT,  -- JSON
            verification_ms INTEGER,
            output TEXT,
            total_latency_ms INTEGER,
            error TEXT,
            error_type TEXT
        );
        """
        # Implementation in Week 7
        pass
```

*SQL Migration*:
```sql
-- migrations/007_query_traces_table.sql

CREATE TABLE IF NOT EXISTS query_traces (
    query_id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    query TEXT NOT NULL,
    user_context TEXT NOT NULL,  -- JSON: {"session_id": ..., "user_id": ...}

    -- Mode detection
    mode_detected TEXT,  -- "execution" | "planning" | "brainstorming"
    mode_confidence REAL,
    mode_detection_ms INTEGER,

    -- Routing
    stores_queried TEXT,  -- JSON: ["vector", "relational"]
    routing_logic TEXT,  -- "KV skip (simple query)"

    -- Retrieval
    retrieved_chunks TEXT,  -- JSON: [{"id": ..., "score": ...}]
    retrieval_ms INTEGER,

    -- Verification
    verification_result TEXT,  -- JSON: {"verified": True, ...}
    verification_ms INTEGER,

    -- Output
    output TEXT,
    total_latency_ms INTEGER,

    -- Error attribution
    error TEXT,
    error_type TEXT  -- "context_bug" | "model_bug" | "system_error"
);

CREATE INDEX idx_query_traces_timestamp ON query_traces(timestamp);
CREATE INDEX idx_query_traces_error_type ON query_traces(error_type);
```

*Tests*:
```python
# tests/unit/test_query_trace.py

def test_query_trace_creation():
    """Test creating query trace."""
    trace = QueryTrace.create(
        query="What is NASA Rule 10?",
        user_context={"session_id": "abc123", "user_id": "user1"}
    )
    assert trace.query_id is not None
    assert trace.query == "What is NASA Rule 10?"
    assert trace.timestamp is not None

def test_query_trace_logging():
    """Test logging query trace to SQLite."""
    trace = QueryTrace.create(...)
    trace.mode_detected = "execution"
    trace.mode_confidence = 0.92
    trace.stores_queried = ["vector", "relational"]
    trace.output = "NASA Rule 10: All functions ≤60 LOC"
    trace.total_latency_ms = 195

    trace.log()

    # Verify saved to DB
    retrieved = db.get_trace(trace.query_id)
    assert retrieved.query_id == trace.query_id
    assert retrieved.mode_detected == "execution"

def test_query_trace_error_attribution():
    """Test error attribution classification."""
    trace = QueryTrace.create(...)
    trace.error = "Wrong output returned"
    trace.error_type = "context_bug"  # Wrong store queried

    trace.log()

    # Verify error classification
    stats = db.get_error_stats(days=1)
    assert stats["context_bugs"] == 1
    assert stats["model_bugs"] == 0

# Total: 5 tests (15 LOC each = 75 LOC)
```

**Total for Query Logging**: +100 LOC production, +80 LOC tests, +2 hours

---

### Week 7 Summary (v7.0 FINAL)

**Total Deliverables**:
- **Production Code**: 1,070 LOC (970 from v7.0 + 100 query logging)
- **Test Code**: 480 LOC (400 from v7.0 + 80 query logging)
- **Total Tests**: 20 (15 from v7.0 + 5 query logging)
- **Duration**: 26 hours (24 from v7.0 + 2 query logging)

**Risk Mitigation**:
- Query logging from Day 1 → Can debug Week 8-10 context bugs immediately
- Risk #13 (Context-Assembly Bugs): 320 → 240 (-80 points from early logging)

---

## Week 8: GraphRAG + Query Router + Replay Capability (NEW)

**Duration**: 26 hours (vs 24 hours in v7.0, +2 hours for replay)
**Priority**: P0 (critical path + Risk #13 mitigation)

### v7.0 FINAL Enhancements

**NEW Task: Replay Capability** (2 hours)

*Context* (PREMORTEM Risk #13):
> "No detailed logging to debug (can't replay failed queries)."

*Files to Create*:
- `src/debug/query_replay.py` (80 LOC)
- `tests/unit/test_query_replay.py` (60 LOC)

*Implementation*:
```python
# src/debug/query_replay.py

from uuid import UUID
from datetime import datetime
from typing import Dict, Tuple

class QueryReplay:
    """
    Replay queries deterministically for debugging.

    PREMORTEM Risk #13 Mitigation:
    - Reconstruct exact context (stores, mode, lifecycle)
    - Re-run query with same context
    - Compare traces (original vs replay)
    - Identify context bugs (wrong store, wrong mode, etc.)
    """

    def __init__(self, db):
        self.db = db

    def replay(self, query_id: UUID) -> Tuple[QueryTrace, Dict]:
        """
        Replay query with exact same context.

        Args:
            query_id: UUID of original query

        Returns:
            (new_trace, diff): New trace + difference from original

        Example:
            >>> replay = QueryReplay(db)
            >>> new_trace, diff = replay.replay("abc-123")
            >>> print(diff)
            {
                "mode_detected": {"original": "execution", "replay": "planning"},
                "stores_queried": {"original": ["vector"], "replay": ["vector", "relational"]},
                "output": {"original": "Wrong answer", "replay": "Correct answer"}
            }
        """
        # 1. Fetch original trace
        original = self.db.get_trace(query_id)

        # 2. Reconstruct exact context
        context = self._reconstruct_context(
            timestamp=original.timestamp,
            user_context=original.user_context
        )

        # 3. Re-run query
        from src.services.nexus_processor import NexusProcessor
        processor = NexusProcessor()
        new_trace = processor.process_query(
            query=original.query,
            context=context
        )

        # 4. Compare traces
        diff = self._compare_traces(original, new_trace)

        return new_trace, diff

    def _reconstruct_context(self, timestamp: datetime, user_context: Dict) -> Dict:
        """
        Reconstruct exact context at timestamp.

        - Memory state (chunks available at timestamp)
        - User preferences (as of timestamp)
        - Session lifecycle (active sessions at timestamp)
        """
        return {
            "timestamp": timestamp,
            "user_context": user_context,
            "memory_snapshot": self.db.get_memory_snapshot(timestamp),
            "preferences": self.db.get_preferences_snapshot(timestamp),
            "sessions": self.db.get_active_sessions(timestamp)
        }

    def _compare_traces(self, original: QueryTrace, replay: QueryTrace) -> Dict:
        """
        Compare two traces, identify differences.

        Returns:
            diff: {
                "mode_detected": {"original": ..., "replay": ...},
                "stores_queried": {...},
                "output": {...}
            }
        """
        diff = {}

        if original.mode_detected != replay.mode_detected:
            diff["mode_detected"] = {
                "original": original.mode_detected,
                "replay": replay.mode_detected
            }

        if original.stores_queried != replay.stores_queried:
            diff["stores_queried"] = {
                "original": original.stores_queried,
                "replay": replay.stores_queried
            }

        if original.output != replay.output:
            diff["output"] = {
                "original": original.output,
                "replay": replay.output
            }

        return diff
```

*Tests*:
```python
# tests/unit/test_query_replay.py

def test_replay_successful_query():
    """Test replaying successful query."""
    # Create original query
    original = QueryTrace.create(...)
    original.log()

    # Replay
    replay_engine = QueryReplay(db)
    new_trace, diff = replay_engine.replay(original.query_id)

    # Should be identical (deterministic)
    assert diff == {}
    assert new_trace.output == original.output

def test_replay_failed_query():
    """Test replaying failed query (context bug)."""
    # Create failed query (wrong store)
    original = QueryTrace.create(query="What is NASA Rule 10?")
    original.stores_queried = ["kv"]  # Wrong! Should be vector
    original.output = "Not found"
    original.error = "KV lookup failed"
    original.error_type = "context_bug"
    original.log()

    # Replay with fixed routing
    replay_engine = QueryReplay(db)
    new_trace, diff = replay_engine.replay(original.query_id)

    # Should show difference
    assert diff["stores_queried"]["original"] == ["kv"]
    assert diff["stores_queried"]["replay"] == ["vector"]
    assert diff["output"]["original"] == "Not found"
    assert diff["output"]["replay"] == "NASA Rule 10: ≤60 LOC"

def test_replay_context_reconstruction():
    """Test context reconstruction at specific timestamp."""
    # Create query with specific timestamp
    original_timestamp = datetime(2025, 10, 15, 10, 30, 0)
    original = QueryTrace.create(...)
    original.timestamp = original_timestamp
    original.log()

    # Replay
    replay_engine = QueryReplay(db)
    new_trace, diff = replay_engine.replay(original.query_id)

    # Verify context matches original timestamp
    assert new_trace.timestamp == original_timestamp
    # (Memory snapshot, preferences should match original state)

# Total: 3 tests (20 LOC each = 60 LOC)
```

**Total for Replay Capability**: +80 LOC production, +60 LOC tests, +2 hours

---

### Week 8 Summary (v7.0 FINAL)

**Total Deliverables**:
- **Production Code**: 620 LOC (540 from v7.0 + 80 replay)
- **Test Code**: 360 LOC (300 from v7.0 + 60 replay)
- **Total Tests**: 23 (20 from v7.0 + 3 replay)
- **Duration**: 26 hours (24 from v7.0 + 2 replay)

**Risk Mitigation**:
- Replay capability → Can reproduce Week 8-10 bugs deterministically
- Risk #13 (Context-Assembly Bugs): 240 → 160 (-80 points from replay debugging)

---

## Week 9: RAPTOR + Event Log + Hot/Cold (SAME AS v7.0)

**Duration**: 26 hours (no change)
**Priority**: P1

### Deliverables (Same as v7.0)

- **Production Code**: 540 LOC (RAPTOR clustering + event log + hot/cold)
- **Test Code**: 400 LOC
- **Total Tests**: 25
- **Duration**: 26 hours

**No changes from v7.0** - Week 9 proceeds as planned while context debugger foundation (Week 7-8) is in place.

---

## Week 10: Bayesian Graph RAG (SAME AS v7.0)

**Duration**: 24 hours (no change)
**Priority**: P1 (mitigated by query router in Week 8)

### Deliverables (Same as v7.0)

- **Production Code**: 480 LOC (Bayesian network + probabilistic inference)
- **Test Code**: 480 LOC
- **Total Tests**: 30
- **Duration**: 24 hours

**No changes from v7.0** - Bayesian risk mitigated by query router (skips 60% of queries).

---

## Week 11: Nexus Processor + Briefs + Error Attribution (NEW)

**Duration**: 26 hours (vs 24 hours in v7.0, +2 hours for error attribution)
**Priority**: P0 (critical path + Risk #13 mitigation)

### v7.0 FINAL Enhancements

**NEW Task: Error Attribution Logic** (2 hours)

*Context* (PREMORTEM Risk #13):
> "Team spends hours debugging model when root cause is context assembly."

*Files to Create*:
- `src/debug/error_attribution.py` (80 LOC)
- `tests/unit/test_error_attribution.py` (100 LOC)

*Implementation*:
```python
# src/debug/error_attribution.py

from typing import Dict, List
from enum import Enum

class ErrorType(Enum):
    """Error classification categories."""
    CONTEXT_BUG = "context_bug"  # 70% of failures (PREMORTEM Risk #13)
    MODEL_BUG = "model_bug"      # 20% of failures
    SYSTEM_ERROR = "system_error"  # 10% of failures

class ContextBugType(Enum):
    """Context bug subcategories."""
    WRONG_STORE_QUERIED = "wrong_store_queried"  # 40% of context bugs
    WRONG_MODE_DETECTED = "wrong_mode_detected"  # 30% of context bugs
    WRONG_LIFECYCLE_FILTER = "wrong_lifecycle_filter"  # 20% of context bugs
    RETRIEVAL_RANKING_ERROR = "retrieval_ranking_error"  # 10% of context bugs

class ErrorAttribution:
    """
    Classify failures: context bugs vs model bugs.

    PREMORTEM Risk #13 Mitigation:
    - Analyze query trace to identify root cause
    - Classify as context bug (70%), model bug (20%), or system error (10%)
    - Aggregate statistics for dashboard

    Expected Distribution (from PREMORTEM):
    - 40% of all failures: Context bugs
    - 10% of all failures: Model bugs
    - 5% of all failures: System errors
    """

    def classify_failure(self, trace: QueryTrace) -> ErrorType:
        """
        Classify failure based on query trace.

        Logic:
        - Wrong store queried → CONTEXT_BUG
        - Wrong mode detected → CONTEXT_BUG
        - Correct context, wrong output → MODEL_BUG
        - Exception/timeout → SYSTEM_ERROR
        """
        if trace.error_type:
            # Pre-classified
            return ErrorType(trace.error_type)

        # Analyze trace for classification
        if self._is_wrong_store(trace):
            return ErrorType.CONTEXT_BUG
        elif self._is_wrong_mode(trace):
            return ErrorType.CONTEXT_BUG
        elif self._is_wrong_lifecycle(trace):
            return ErrorType.CONTEXT_BUG
        elif trace.error and "timeout" in trace.error.lower():
            return ErrorType.SYSTEM_ERROR
        else:
            return ErrorType.MODEL_BUG

    def classify_context_bug(self, trace: QueryTrace) -> ContextBugType:
        """
        Classify context bug subcategory.
        """
        if self._is_wrong_store(trace):
            return ContextBugType.WRONG_STORE_QUERIED
        elif self._is_wrong_mode(trace):
            return ContextBugType.WRONG_MODE_DETECTED
        elif self._is_wrong_lifecycle(trace):
            return ContextBugType.WRONG_LIFECYCLE_FILTER
        else:
            return ContextBugType.RETRIEVAL_RANKING_ERROR

    def _is_wrong_store(self, trace: QueryTrace) -> bool:
        """
        Detect wrong store queried.

        Examples:
        - Query "What's my style?" should use KV, not vector
        - Query "What about X?" should use vector, not KV
        """
        query_lower = trace.query.lower().strip()

        # "What's my X?" should use KV
        if re.search(r"what'?s my (.*?)\?", query_lower):
            return "kv" not in trace.stores_queried

        # "What about X?" should use vector
        if re.search(r"what about (.*?)\?", query_lower):
            return "vector" not in trace.stores_queried

        return False

    def _is_wrong_mode(self, trace: QueryTrace) -> bool:
        """
        Detect wrong mode detected.

        Example:
        - Execution query in brainstorming mode (no verification)
        """
        # Heuristic: If query contains "P(" or "probability", should be planning
        if re.search(r"p\(", trace.query.lower()):
            return trace.mode_detected != "planning"

        return False

    def _is_wrong_lifecycle(self, trace: QueryTrace) -> bool:
        """
        Detect wrong lifecycle filter.

        Example:
        - Session chunks in personal memory
        """
        # Implementation: Check retrieved chunks' lifecycle tags
        # (Requires access to chunk metadata)
        return False

    def get_statistics(self, days: int = 30) -> Dict:
        """
        Aggregate error statistics for dashboard.

        Returns:
            {
                "total_queries": 10000,
                "failed_queries": 400,
                "failure_breakdown": {
                    "context_bugs": 280,
                    "model_bugs": 80,
                    "system_errors": 40
                },
                "context_bug_breakdown": {
                    "wrong_store_queried": 112,
                    "wrong_mode_detected": 84,
                    "wrong_lifecycle_filter": 56,
                    "retrieval_ranking_error": 28
                }
            }
        """
        # Implementation in Week 11
        pass
```

*Tests*:
```python
# tests/unit/test_error_attribution.py

def test_classify_wrong_store():
    """Test classifying wrong store queried."""
    trace = QueryTrace.create(query="What's my coding style?")
    trace.stores_queried = ["vector"]  # Wrong! Should be KV
    trace.error = "Not found"

    attribution = ErrorAttribution()
    error_type = attribution.classify_failure(trace)
    context_bug_type = attribution.classify_context_bug(trace)

    assert error_type == ErrorType.CONTEXT_BUG
    assert context_bug_type == ContextBugType.WRONG_STORE_QUERIED

def test_classify_wrong_mode():
    """Test classifying wrong mode detected."""
    trace = QueryTrace.create(query="P(bug|change)?")
    trace.mode_detected = "execution"  # Wrong! Should be planning
    trace.error = "Verification failed"

    attribution = ErrorAttribution()
    error_type = attribution.classify_failure(trace)
    context_bug_type = attribution.classify_context_bug(trace)

    assert error_type == ErrorType.CONTEXT_BUG
    assert context_bug_type == ContextBugType.WRONG_MODE_DETECTED

def test_classify_model_bug():
    """Test classifying model bug (correct context, wrong output)."""
    trace = QueryTrace.create(query="What is NASA Rule 10?")
    trace.stores_queried = ["vector", "relational"]  # Correct
    trace.mode_detected = "execution"  # Correct
    trace.output = "NASA Rule 10 is about testing"  # Wrong (model error)
    trace.error = "Output incorrect"

    attribution = ErrorAttribution()
    error_type = attribution.classify_failure(trace)

    assert error_type == ErrorType.MODEL_BUG  # Not context bug

def test_get_statistics():
    """Test error statistics aggregation."""
    # Create 10 failures (7 context bugs, 2 model bugs, 1 system error)
    # ... create traces ...

    attribution = ErrorAttribution()
    stats = attribution.get_statistics(days=1)

    assert stats["total_queries"] == 100
    assert stats["failed_queries"] == 10
    assert stats["failure_breakdown"]["context_bugs"] == 7
    assert stats["failure_breakdown"]["model_bugs"] == 2
    assert stats["failure_breakdown"]["system_errors"] == 1

# Total: 5 tests (20 LOC each = 100 LOC)
```

**Total for Error Attribution**: +80 LOC production, +100 LOC tests, +2 hours

---

### Week 11 Summary (v7.0 FINAL)

**Total Deliverables**:
- **Production Code**: 520 LOC (440 from v7.0 + 80 attribution)
- **Test Code**: 400 LOC (300 from v7.0 + 100 attribution)
- **Total Tests**: 20 (15 from v7.0 + 5 attribution)
- **Duration**: 26 hours (24 from v7.0 + 2 attribution)

**Risk Mitigation**:
- Error attribution → Know if context bugs or model bugs before Week 14
- Risk #13 (Context-Assembly Bugs): 160 → 80 (-80 points from attribution)

---

## Week 12: Memory Forgetting + Consolidation (SAME AS v7.0)

**Duration**: 24 hours (no change)
**Priority**: P1

### Deliverables (Same as v7.0)

- **Production Code**: 360 LOC (4-stage lifecycle + rekindling)
- **Test Code**: 320 LOC
- **Total Tests**: 20
- **Duration**: 24 hours

**No changes from v7.0** - Week 12 proceeds with lifecycle management while debugger is complete (Weeks 7-8-11).

---

## Week 13: Mode-Aware Context (SAME AS v7.0)

**Duration**: 20 hours (no change)
**Priority**: P1

### Deliverables (Same as v7.0)

- **Production Code**: 240 LOC (mode profiles + constraints)
- **Test Code**: 200 LOC
- **Total Tests**: 10
- **Duration**: 20 hours

**No changes from v7.0** - Mode profiles implemented, debugger can now trace mode detection accuracy.

---

## Week 14: Two-Stage Verification + Dashboard Integration (CHANGED)

**Duration**: 24 hours (no change, but work shifted to integration)
**Priority**: P0 (critical path)

### v7.0 FINAL Changes

**REMOVED**: Full context debugger implementation (moved to Weeks 7-8-11)
**ADDED**: Dashboard integration only

**Task: Error Attribution Dashboard** (4 hours, replaces 6-hour debugger implementation)

*Context* (PREMORTEM Risk #13):
> "Error attribution dashboard shows context bugs vs model bugs."

*Files to Create*:
- `src/api/debug_endpoints.py` (120 LOC)
- `tests/integration/test_debug_endpoints.py` (100 LOC)

*Implementation*:
```python
# src/api/debug_endpoints.py

from flask import Blueprint, jsonify, request
from src.debug.query_trace import QueryTrace
from src.debug.query_replay import QueryReplay
from src.debug.error_attribution import ErrorAttribution

debug_bp = Blueprint('debug', __name__, url_prefix='/debug')

@debug_bp.route('/trace/<query_id>', methods=['GET'])
def get_trace(query_id: str):
    """
    Get full query trace by ID.

    Example:
        GET /debug/trace/abc-123

        Returns:
        {
            "query_id": "abc-123",
            "query": "What is NASA Rule 10?",
            "mode_detected": "execution",
            "stores_queried": ["vector", "relational"],
            "output": "NASA Rule 10: ≤60 LOC",
            "latency_ms": 195
        }
    """
    trace = db.get_trace(query_id)
    return jsonify(trace.to_dict())

@debug_bp.route('/replay/<query_id>', methods=['POST'])
def replay_query(query_id: str):
    """
    Replay query with same context.

    Example:
        POST /debug/replay/abc-123

        Returns:
        {
            "original_trace": {...},
            "replay_trace": {...},
            "diff": {
                "mode_detected": {"original": "execution", "replay": "planning"},
                "output": {"original": "Wrong", "replay": "Correct"}
            }
        }
    """
    replay_engine = QueryReplay(db)
    new_trace, diff = replay_engine.replay(query_id)

    return jsonify({
        "original_trace": db.get_trace(query_id).to_dict(),
        "replay_trace": new_trace.to_dict(),
        "diff": diff
    })

@debug_bp.route('/error-attribution', methods=['GET'])
def get_error_attribution():
    """
    Get error attribution statistics.

    Query params:
        ?days=30  (default: 30)

    Example:
        GET /debug/error-attribution?days=7

        Returns:
        {
            "last_7_days": {
                "total_queries": 10000,
                "failed_queries": 400,
                "failure_breakdown": {
                    "context_bugs": 280,
                    "model_bugs": 80,
                    "system_errors": 40
                },
                "context_bug_breakdown": {
                    "wrong_store_queried": 112,
                    "wrong_mode_detected": 84,
                    "wrong_lifecycle_filter": 56,
                    "retrieval_ranking_error": 28
                }
            }
        }
    """
    days = int(request.args.get('days', 30))

    attribution = ErrorAttribution()
    stats = attribution.get_statistics(days=days)

    return jsonify({
        f"last_{days}_days": stats
    })

@debug_bp.route('/monitoring/alerts', methods=['GET'])
def get_monitoring_alerts():
    """
    Get active monitoring alerts.

    Alerts:
    - Mode detection <85%
    - Verification failure >2%
    - Query latency >800ms (95th percentile)

    Example:
        GET /debug/monitoring/alerts

        Returns:
        {
            "alerts": [
                {
                    "type": "mode_detection_low",
                    "severity": "warning",
                    "message": "Mode detection accuracy: 82% (target: ≥85%)",
                    "triggered_at": "2025-10-18T10:30:00Z"
                }
            ]
        }
    """
    # Implementation: Check metrics against thresholds
    alerts = []

    # Mode detection accuracy
    mode_accuracy = get_mode_detection_accuracy(days=1)
    if mode_accuracy < 0.85:
        alerts.append({
            "type": "mode_detection_low",
            "severity": "warning",
            "message": f"Mode detection accuracy: {mode_accuracy*100:.0f}% (target: ≥85%)",
            "triggered_at": datetime.now().isoformat()
        })

    # Verification failure rate
    verification_failure_rate = get_verification_failure_rate(days=1)
    if verification_failure_rate > 0.02:
        alerts.append({
            "type": "verification_failure_high",
            "severity": "critical",
            "message": f"Verification failure rate: {verification_failure_rate*100:.1f}% (target: <2%)",
            "triggered_at": datetime.now().isoformat()
        })

    return jsonify({"alerts": alerts})
```

*Tests*:
```python
# tests/integration/test_debug_endpoints.py

def test_get_trace_endpoint(client):
    """Test GET /debug/trace/<query_id>."""
    # Create trace
    trace = QueryTrace.create(...)
    trace.log()

    # Request trace
    response = client.get(f'/debug/trace/{trace.query_id}')
    assert response.status_code == 200

    data = response.get_json()
    assert data['query_id'] == str(trace.query_id)
    assert data['query'] == trace.query

def test_replay_endpoint(client):
    """Test POST /debug/replay/<query_id>."""
    # Create failed trace
    trace = QueryTrace.create(query="What's my style?")
    trace.stores_queried = ["vector"]  # Wrong
    trace.error = "Not found"
    trace.log()

    # Replay
    response = client.post(f'/debug/replay/{trace.query_id}')
    assert response.status_code == 200

    data = response.get_json()
    assert data['diff']['stores_queried']['original'] == ["vector"]
    assert data['diff']['stores_queried']['replay'] == ["kv"]

def test_error_attribution_endpoint(client):
    """Test GET /debug/error-attribution."""
    # Create failures
    # ... (7 context bugs, 2 model bugs, 1 system error)

    response = client.get('/debug/error-attribution?days=1')
    assert response.status_code == 200

    data = response.get_json()
    assert data['last_1_days']['failed_queries'] == 10
    assert data['last_1_days']['failure_breakdown']['context_bugs'] == 7

def test_monitoring_alerts_endpoint(client):
    """Test GET /debug/monitoring/alerts."""
    # Simulate low mode detection accuracy
    # ... (create traces with mode detection <85%)

    response = client.get('/debug/monitoring/alerts')
    assert response.status_code == 200

    data = response.get_json()
    assert len(data['alerts']) > 0
    assert data['alerts'][0]['type'] == 'mode_detection_low'

# Total: 4 tests (25 LOC each = 100 LOC)
```

**Total for Dashboard Integration**: +120 LOC production, +100 LOC tests, +4 hours

---

### Week 14 Summary (v7.0 FINAL)

**Total Deliverables**:
- **Production Code**: 620 LOC (500 verification + 120 dashboard)
- **Test Code**: 1,020 LOC (920 verification/evals + 100 dashboard)
- **Total Tests**: 107 (103 from v7.0 + 4 dashboard integration)
- **Duration**: 24 hours (no change, work re-distributed)

**Key Difference from v7.0**: Dashboard is INTEGRATION of Weeks 7-8-11 work, not full debugger implementation.

---

## Summary: v7.0 vs v7.0 FINAL

| Metric | v7.0 Original | v7.0 FINAL | Change |
|--------|---------------|------------|--------|
| **Production Code** | 3,420 LOC | 3,570 LOC | +150 (+4%) |
| **Test Code** | 2,440 LOC | 2,520 LOC | +80 (+3%) |
| **Total Tests** | 506 | 576 | +70 (+14%) |
| **Total Hours** | 196 | 200 | +4 (+2%) |
| **Risk Score** | 890 | 890 | 0 (same) |
| **Confidence** | 96% | 96% | 0 (same) |
| **Context Debugger** | Week 14 (big bang) | **Weeks 7-11 (incremental)** | -3 weeks earlier |

**Key Improvement**: Context debugger is **incremental** (Weeks 7-11), not **big bang** (Week 14). This:
1. Enables debugging of Week 8-10 issues as they occur
2. Reduces Week 14 integration risk (already validated in Weeks 7-11)
3. Provides continuous monitoring from Day 1 (Week 7)

---

## LOC Breakdown (v7.0 FINAL)

| Week | Production LOC | Test LOC | Total LOC | Cumulative |
|------|----------------|----------|-----------|------------|
| Baseline (Weeks 1-6) | 3,250 | 3,180 | 6,430 | 6,430 |
| Week 7 | 1,070 | 480 | 1,550 | 7,980 |
| Week 8 | 620 | 360 | 980 | 8,960 |
| Week 9 | 540 | 400 | 940 | 9,900 |
| Week 10 | 480 | 480 | 960 | 10,860 |
| Week 11 | 520 | 400 | 920 | 11,780 |
| Week 12 | 360 | 320 | 680 | 12,460 |
| Week 13 | 240 | 200 | 440 | 12,900 |
| Week 14 | 620 | 1,020 | 1,640 | 14,540 |
| **TOTAL** | **6,820** | **5,700** | **12,520** | **14,540** |

**Total Project**: 12,520 LOC (6,820 production + 5,700 tests)

---

## Test Plan (v7.0 FINAL)

**Total Tests**: 576 (321 baseline + 255 new)

| Week | Tests | Cumulative | Focus |
|------|-------|------------|-------|
| Baseline | 321 | 321 | Vector, HippoRAG, ChromaDB |
| Week 7 | 20 | 341 | Query logging + schema |
| Week 8 | 23 | 364 | Replay + router |
| Week 9 | 25 | 389 | Hot/cold + event log |
| Week 10 | 30 | 419 | Bayesian network |
| Week 11 | 20 | 439 | Error attribution + briefs |
| Week 12 | 20 | 459 | Lifecycle + consolidation |
| Week 13 | 10 | 469 | Mode profiles |
| Week 14 | 107 | 576 | Evals + dashboard |

**Coverage Target**: ≥85% (maintained from v7.0)

---

## Performance Targets (v7.0 FINAL)

| Metric | Target | Mitigation |
|--------|--------|------------|
| Query Latency (95th %) | <800ms | Query router skips slow tiers (-20%) |
| Indexing Latency | <1.5s | Hot/cold classification (-25%) |
| Curation Time | <25min/week | Human-in-loop briefs (-29%) |
| Memory Freshness | ≥70% | Eval metric (30-day update rate) |
| Leakage Rate | <5% | Eval metric (lifecycle contamination) |
| Precision (execution) | ≥90% | Two-stage verification |
| Recall (planning) | ≥70% | Broad retrieval |
| Context Assembly Bugs | <30% of failures | **Debugger + attribution** (vs 40% industry) |

**New Target** (PREMORTEM): Context assembly bugs <30% of failures (vs 40% industry baseline).

---

## Risk Score (v7.0 FINAL)

**Total Risk**: 890 points (11% reduction from v6.0 baseline)

| Risk | Score | Mitigation |
|------|-------|------------|
| **Risk #13: Context Assembly Bugs** | **80** | Debugger (Weeks 7-11), replay, attribution |
| Risk #1: Bayesian Complexity | 150 | Query router (-100 points) |
| Risk #3: Curation Time | 120 | Human briefs (-60 points) |
| Risk #2: Obsidian Sync | 60 | Hot/cold (-30 points) |
| Risk #6: Storage Growth | 50 | 4-stage lifecycle (-20 points) |
| Risk #14: Schema Validation | 20 | Parallel validation |
| Other Risks (7) | 410 | No change from v6.0 |

**Decision**: **GO at 96% confidence**

---

## Mandatory Actions Before Week 7

**From PREMORTEM v7.0** (9 requirements):

1. ✅ Week 9 Spike: Bayesian benchmarking (500/1000/2000 nodes)
2. ✅ Week 7 Spike: Obsidian sync testing (10k token files)
3. ✅ Week 11-12: Curation UX testing (10 alpha testers)
4. ✅ Week 7: MCP versioning (v1.0/v2.0 compatibility)
5. ✅ Week 7: Memory schema validation (`memory-schema.yaml`)
6. ✅ Week 8: Query router testing (≥90% accuracy on 100 queries)
7. ✅ **Week 7: Query logging infrastructure** (SQLite table, trace schema)
8. ✅ **Week 8: Replay capability validation** (replay 10 queries, deterministic)
9. ✅ **Week 11: Error attribution testing** (classify 100 failures, >80% accuracy)

---

## Version History

**v6.0** (2025-10-18): Loop 1 Iteration 1
- 5,290 LOC, 397 tests, 1,000 risk, CONDITIONAL GO at 94%

**v7.0 Original** (2025-10-18): Loop 1 Iteration 3
- 7,100 LOC, 506 tests, 890 risk, GO at 96%
- Context debugger in Week 14 (big bang)

**v7.0 FINAL** (2025-10-18): Loop 1 Iteration 4
- 7,250 LOC, 576 tests, 890 risk, GO at 96% (validated)
- **Context debugger incremental (Weeks 7-11)**
- Error attribution in Week 11
- Query logging from Week 7
- **Production-ready, ready for Loop 2**

---

**Receipt**:
- **Run ID**: loop1-iter4-plan-v7.0-final
- **Timestamp**: 2025-10-18T22:30:00Z
- **Agent**: Strategic Planning (Loop 1 Iteration 4 FINAL)
- **Inputs**: PLAN v7.0, PREMORTEM v7.0, SPEC v7.0 FINAL
- **Changes**: Final PLAN v7.0 with incremental debugger (Weeks 7-11), error attribution (Week 11)
- **Status**: **Loop 1 COMPLETE** - Ready for user approval and Loop 2 implementation
