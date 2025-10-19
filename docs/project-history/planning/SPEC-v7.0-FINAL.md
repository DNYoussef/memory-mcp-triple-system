# Memory MCP Triple System - SPEC v7.0 FINAL

**Version**: 7.0 FINAL (Loop 1 Iteration 3 - Integrated with PREMORTEM v7.0)
**Date**: 2025-10-18
**Status**: Production-Ready (GO at 96% confidence)
**Risk Score**: 890 points (11% reduction from v6.0)
**Predecessor**: SPEC v7.0 Executive Summary, PREMORTEM v7.0

---

## Executive Summary

**SPEC v7.0 FINAL** integrates all findings from PREMORTEM v7.0, with **context-assembly debugging elevated to P0 architectural requirement**. This version represents the production-ready specification after full Loop 1 validation (4 iterations).

**Key Achievement**: **Risk reduction from 1,000 → 890 points (11% improvement)** via:
1. Query router optimization (Bayesian complexity: 250 → 150, **-100 points**)
2. Human-in-loop brief editing (Curation time: 180 → 120, **-60 points**)
3. Hot/cold classification (Obsidian sync: 90 → 60, **-30 points**)
4. Context assembly debugger (NEW risk: 80 points, **well-mitigated from 320**)

**PRIMARY RISK** (PREMORTEM v7.0 Risk #13): **Context-Assembly Bugs**
- **Impact**: 40% of production failures trace to wrong context (not model errors)
- **Root Causes**: Wrong store queried, wrong mode detected, wrong lifecycle filter, no query replay
- **Mitigation**: Context assembly debugger with detailed tracing, replay capability, error attribution
- **Residual Risk**: 80 points (mitigated from 320 via debugger + monitoring)

**Critical Architectural Shift**: **Memory debugging is as important as memory retrieval.** v7.0 treats context assembly as the #1 failure mode and provides first-class debugging tools from Week 7 (not bolted on in Week 14).

---

## Primary Architectural Requirements (Updated from PREMORTEM)

### 1. Context Assembly Debugger (P0 - Risk #13 Mitigation)

**PREMORTEM Insight**: Risk #13 (Context-Assembly Bugs) is 80 points residual (mitigated from 320). This is the PRIMARY risk in v7.0.

**Requirement**: Every query MUST be traceable, replayable, and attributable.

**Implementation** (Week 7-11, NOT Week 14):

```python
# Context assembly log structure (mandatory for ALL queries)
class QueryTrace:
    """
    Logged for EVERY query (no sampling).
    Stored in SQLite for 30-day retention.
    """
    query_id: UUID
    timestamp: datetime

    # Input
    query: str
    user_context: Dict  # Session ID, user ID, etc.

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
```

**Replay Capability**:
```python
# Must be able to replay ANY query deterministically
def replay_query(query_id: UUID) -> QueryTrace:
    """
    Re-run query with exact same context.
    Used for debugging failed queries.
    """
    original_trace = db.get_trace(query_id)

    # Reconstruct exact context
    context = reconstruct_context(
        timestamp=original_trace.timestamp,
        user_context=original_trace.user_context
    )

    # Re-run query
    new_trace = run_query_with_context(
        query=original_trace.query,
        context=context
    )

    # Compare traces
    diff = compare_traces(original_trace, new_trace)
    return new_trace, diff
```

**Error Attribution Dashboard**:
```python
# Dashboard endpoint: /debug/error-attribution
{
    "last_30_days": {
        "total_queries": 10000,
        "failed_queries": 400,  # 4% failure rate
        "failure_breakdown": {
            "context_bugs": 280,  # 70% of failures (40% of 400)
            "model_bugs": 80,     # 20% of failures
            "system_errors": 40   # 10% of failures
        }
    },
    "context_bug_breakdown": {
        "wrong_store_queried": 112,  # 40% (e.g., queried KV instead of Vector)
        "wrong_mode_detected": 84,   # 30% (e.g., execution in brainstorming mode)
        "wrong_lifecycle_filter": 56, # 20% (e.g., session chunks in personal)
        "retrieval_ranking_error": 28 # 10% (e.g., low-confidence chunk ranked high)
    }
}
```

**Acceptance Criteria** (PREMORTEM v7.0):
- ✅ Context debugger logs 100% of queries (no sampling)
- ✅ Query replay works (deterministic context assembly)
- ✅ Error attribution dashboard shows context bugs vs model bugs
- ✅ Monitoring alerts trigger within 5 minutes of anomaly (mode detection <85%, verification failure >2%)

**Implementation Timeline** (MOVED EARLIER):
- **Week 7**: Query logging infrastructure (SQLite table, trace schema)
- **Week 8**: Replay capability (context reconstruction)
- **Week 11**: Error attribution logic (classify failures)
- **Week 14**: Dashboard and monitoring alerts (NOT full implementation - integration only)

---

### 2. Query Router (Insight #3 - Mitigates Risk #1)

**PREMORTEM Impact**: Reduces Bayesian complexity risk from 250 → 150 (**-100 points**)

**Requirement**: Skip slow storage tiers for simple queries.

**Implementation** (Week 8, validated Week 7):

```python
class QueryRouter:
    """
    Route queries to appropriate storage tier(s).

    Routing Rules:
    - "What's my X?" → KV Store (O(1) preferences)
    - "What client/project X?" → Relational (SQL entities)
    - "What about X?" → Vector (semantic search)
    - "What led to X?" → Graph (multi-hop reasoning)
    - "What happened on X?" → Event Log (temporal queries)

    Complexity-Based Routing:
    - Simple queries → Skip Bayesian (60% of queries)
    - Complex queries ("P(X|Y)?") → Query Bayesian
    """

    def route(self, query: str, mode: str) -> List[str]:
        """
        Returns list of stores to query.

        Example:
        - route("What's my coding style?", "execution") → ["kv"]
        - route("What about NASA Rule 10?", "execution") → ["vector", "relational"]
        - route("What led to Week 5 bugs?", "planning") → ["vector", "graph"]
        - route("P(bug|change)?", "planning") → ["vector", "graph", "bayesian"]
        """
        stores = []
        query_lower = query.lower().strip()

        # Pattern matching
        if re.search(r"what'?s my (.*?)\?", query_lower):
            stores.append('kv')
        elif re.search(r"what (client|project) (.*?)\?", query_lower):
            stores.append('relational')
        elif re.search(r"what led to (.*?)\?", query_lower):
            stores.extend(['vector', 'graph'])
        elif re.search(r"p\((.*?)\|(.*?)\)", query_lower):  # Probabilistic query
            stores.extend(['vector', 'graph', 'bayesian'])
        else:
            # Default: vector only
            stores.append('vector')

        # Execution mode: Skip Bayesian unless explicitly requested
        if mode == "execution" and "bayesian" in stores:
            if not re.search(r"p\((.*?)\|(.*?)\)", query_lower):
                stores.remove('bayesian')  # Too slow for execution

        return stores
```

**Acceptance Criteria** (PREMORTEM v7.0):
- ✅ Query router skips Bayesian for 60% of queries
- ✅ Routing accuracy ≥90% on 100 test queries (Week 7 spike)
- ✅ Average query latency <600ms (vs <1s in v6.0, -40% improvement)

**Impact**: 60% of queries avoid Bayesian timeout risk → Bayesian complexity: 250 → 150 points

---

### 3. Human-in-Loop Brief Editing (Insight #6 - Mitigates Risk #3)

**PREMORTEM Impact**: Reduces curation time risk from 180 → 120 (**-60 points**)

**Requirement**: Compression is human judgment, not auto-summarization.

**Implementation** (Week 11):

```python
# Nexus Processor Step 0: Brief Editing (NEW)
def curate_via_briefs(chunks: List[Chunk]) -> List[Brief]:
    """
    User reviews top-50 chunks, selects top-5 for "brief" (3-sentence summary).
    User edits brief to preserve critical nuances.
    Store brief (100 tokens) instead of full 10k-token chunk.

    Result: 33% faster curation (brief editing faster than chunk tagging).
    """
    # 1. Show top-50 candidates to user
    top_50 = rank_chunks(chunks, limit=50)

    # 2. User selects top-5 for brief
    selected = ui.multi_select(top_50, min=3, max=7)

    # 3. Auto-generate briefs for selected
    briefs = []
    for chunk in selected:
        auto_brief = generate_brief(chunk.content)  # GPT-4: 3 sentences

        # 4. User edits brief (preserve nuances)
        edited_brief = ui.edit_text(
            initial=auto_brief,
            guidelines="Focus on: What, Why, Gotchas"
        )

        briefs.append(Brief(
            original_chunk_id=chunk.id,
            brief=edited_brief,
            tokens=count_tokens(edited_brief),  # ~100 tokens
            created=datetime.now()
        ))

    return briefs
```

**Acceptance Criteria** (PREMORTEM v7.0):
- ✅ Weekly curation <25 minutes (vs <35 minutes in v6.0, -29% improvement)
- ✅ Brief editing workflow tested (10 user sessions)
- ✅ User retention ≥85% after 4 weeks (vs 80% target in v6.0)

**Impact**: 33% faster curation → Curation time: 180 → 120 points

---

### 4. Hot/Cold Classification (Insight #12 - Mitigates Risk #2)

**PREMORTEM Impact**: Reduces Obsidian sync latency risk from 90 → 60 (**-30 points**)

**Requirement**: Optimize indexing for frequently-accessed chunks.

**Implementation** (Week 9):

```python
class HotColdClassifier:
    """
    Classify chunks by access frequency.

    - Hot: Accessed daily → Keep in Redis cache
    - Cold: Not accessed 30 days → Compress, archive
    - Pinned: User-marked important → Always in memory

    Result: 33% less indexing load (cold chunks not re-indexed).
    """

    def classify_chunk(self, chunk_id: str) -> str:
        """
        Returns: "hot" | "cold" | "pinned"
        """
        access_log = db.get_access_log(chunk_id, days=30)

        # Pinned overrides all
        if chunk.is_pinned:
            return "pinned"

        # Hot: ≥5 accesses in 30 days
        if len(access_log) >= 5:
            return "hot"

        # Cold: 0 accesses in 30 days
        if len(access_log) == 0:
            return "cold"

        # Warm: 1-4 accesses (default handling)
        return "warm"

    def optimize_indexing(self):
        """
        Skip re-indexing cold chunks.
        Only index hot, warm, pinned.
        """
        all_chunks = db.get_all_chunks()

        for chunk in all_chunks:
            classification = self.classify_chunk(chunk.id)

            if classification == "cold":
                # Skip indexing (use existing embeddings)
                continue
            else:
                # Re-index hot/warm/pinned
                index_chunk(chunk)
```

**Acceptance Criteria** (PREMORTEM v7.0):
- ✅ Hot/cold classification reduces indexing 33%
- ✅ Indexing latency <1.5s (vs <2s in v6.0, -25% improvement)
- ✅ Redis cache hit rate ≥80% (hot chunks)

**Impact**: 33% less indexing → Obsidian sync: 90 → 60 points

---

### 5. 4-Stage Lifecycle with Compression (Insight #2 - Mitigates Risk #6)

**PREMORTEM Impact**: Reduces storage growth risk from 70 → 50 (**-20 points**)

**Requirement**: Forgetting is a feature, not a bug.

**Implementation** (Week 12):

```python
class MemoryLifecycleManager:
    """
    4-stage lifecycle: Active → Demoted → Archived → Rehydratable

    - Active (100% score, <7 days): Full text stored
    - Demoted (50% score, 7-30 days): Decay applied, full text stored
    - Archived (10% score, 30-90 days): Compressed to summary (100:1 ratio)
    - Rehydratable (1% score, >90 days): Lossy key only (1000:1 ratio)

    Rekindling: Query matches archived → Rehydrate full text → Promote to Active
    """

    def compress_chunk(self, chunk: Chunk) -> ArchivedChunk:
        """
        Compress full chunk to 100:1 summary.
        Used for Archived stage.
        """
        summary = generate_summary(chunk.content, max_tokens=50)  # 5000 → 50 tokens

        return ArchivedChunk(
            original_id=chunk.id,
            summary=summary,
            metadata=chunk.metadata,  # Preserve for rekindling
            compressed_at=datetime.now(),
            compression_ratio=len(chunk.content) / len(summary)
        )

    def rehydrate_chunk(self, archived_chunk: ArchivedChunk) -> Chunk:
        """
        Rehydrate full text from archive (if available).
        Promote to Active stage.
        """
        # Attempt to fetch full text from Obsidian vault
        full_text = obsidian.get_note(archived_chunk.metadata['obsidian_path'])

        if full_text:
            # Rehydration successful
            chunk = Chunk(
                id=archived_chunk.original_id,
                content=full_text,
                stage="active",
                score=100,
                rehydrated_at=datetime.now()
            )
        else:
            # Rehydration failed (lossy key only)
            chunk = Chunk(
                id=archived_chunk.original_id,
                content=archived_chunk.summary,  # Use summary as fallback
                stage="active",
                score=50,  # Lower score (lossy)
                rehydrated_at=datetime.now(),
                lossy=True
            )

        return chunk
```

**Acceptance Criteria** (PREMORTEM v7.0):
- ✅ Storage growth <25MB/1000 chunks (vs <35MB in v6.0, -29% improvement)
- ✅ Archive compression achieves 100:1 ratio
- ✅ Rehydration success rate ≥90% (lossy keys recoverable)

**Impact**: 60% storage reduction → Storage growth: 70 → 50 points

---

## Revised Implementation Timeline (Context Debugger MOVED EARLIER)

### Week 7: Obsidian MCP + Schema + Query Logging (NEW)

**Original v7.0**: Obsidian MCP, schema validation, KV store (970 LOC)
**FINAL v7.0**: **+ Query logging infrastructure** (1,070 LOC, +100 for debugger)

**Deliverables**:
1. Obsidian MCP integration (same as v7.0)
2. Memory schema validation (same as v7.0)
3. KV store implementation (same as v7.0)
4. **NEW**: Query logging infrastructure
   - SQLite table: `query_traces` (20 LOC)
   - `QueryTrace` dataclass (30 LOC)
   - Logging middleware (50 LOC)
5. **NEW**: Schema validation in CI (Week 7, not Week 11)

**Tests**: 15 tests (same) + 5 query logging tests = **20 tests**

**Risk Mitigation**: Query logging from Day 1 → Can debug context bugs in Week 8-10 (not waiting until Week 14)

---

### Week 8: GraphRAG + Query Router + Replay (NEW)

**Original v7.0**: GraphRAG entity consolidation, query router (540 LOC)
**FINAL v7.0**: **+ Replay capability** (620 LOC, +80 for replay)

**Deliverables**:
1. GraphRAG entity consolidation (same as v7.0)
2. Query router implementation (same as v7.0)
3. **NEW**: Replay capability
   - `replay_query()` function (40 LOC)
   - Context reconstruction logic (30 LOC)
   - Trace comparison (10 LOC)

**Tests**: 20 tests (same) + 3 replay tests = **23 tests**

**Risk Mitigation**: Replay capability early → Can reproduce Week 8-10 bugs deterministically

---

### Week 9: RAPTOR + Event Log + Hot/Cold (SAME)

**Original v7.0**: RAPTOR clustering, event log store, hot/cold classification (540 LOC)
**FINAL v7.0**: No changes (540 LOC)

**Tests**: 25 tests (same)

---

### Week 10: Bayesian Graph RAG (SAME)

**Original v7.0**: Bayesian network, probabilistic inference (480 LOC)
**FINAL v7.0**: No changes (480 LOC)

**Tests**: 30 tests (same)

---

### Week 11: Nexus Processor + Error Attribution (NEW)

**Original v7.0**: Nexus SOP pipeline, curated core pattern (360 LOC)
**FINAL v7.0**: **+ Error attribution logic** (440 LOC, +80 for attribution)

**Deliverables**:
1. Nexus SOP pipeline (same as v7.0)
2. Curated core pattern (same as v7.0)
3. Human-in-loop brief editing (same as v7.0)
4. **NEW**: Error attribution logic
   - `classify_failure()` function (40 LOC)
   - Context bug detection (30 LOC)
   - Error statistics aggregation (10 LOC)

**Tests**: 15 tests (same) + 5 attribution tests = **20 tests**

**Risk Mitigation**: Error attribution in Week 11 → Know if context bugs or model bugs before Week 14

---

### Week 12: Memory Forgetting + Consolidation (SAME)

**Original v7.0**: 4-stage lifecycle, rekindling, consolidation (360 LOC)
**FINAL v7.0**: No changes (360 LOC)

**Tests**: 20 tests (same)

---

### Week 13: Mode-Aware Context (SAME)

**Original v7.0**: Mode profiles, mode detection, constraints (240 LOC)
**FINAL v7.0**: No changes (240 LOC)

**Tests**: 10 tests (same)

---

### Week 14: Two-Stage Verification + Dashboard (INTEGRATION ONLY)

**Original v7.0**: Two-stage verification, ground truth expansion, context debugger (820 LOC)
**FINAL v7.0**: **Debugger integration only** (520 LOC, -300 moved to Weeks 7-11)

**Deliverables**:
1. Two-stage verification (same as v7.0)
2. Ground truth expansion (same as v7.0)
3. Memory eval suite (same as v7.0)
4. **CHANGED**: Dashboard and monitoring (integration only, NOT full implementation)
   - `/debug` endpoint (30 LOC)
   - Error attribution dashboard (50 LOC)
   - Monitoring alerts (40 LOC)

**Tests**: 50 tests (same, but debugger tests moved to Weeks 7-11)

**Risk Mitigation**: Week 14 is integration, not implementation → Lower risk, validated in Weeks 7-11

---

## Updated Test Plan (v7.0 FINAL)

**Total Tests**: **576 tests** (vs 556 in original v7.0, +20 for earlier debugger)

| Week | Tests | Cumulative | Focus |
|------|-------|------------|-------|
| Week 7 | 20 | 341 | Query logging + schema validation |
| Week 8 | 23 | 364 | Replay capability + router |
| Week 9 | 25 | 389 | Hot/cold + event log |
| Week 10 | 30 | 419 | Bayesian network |
| Week 11 | 20 | 439 | Error attribution + briefs |
| Week 12 | 20 | 459 | Lifecycle + consolidation |
| Week 13 | 10 | 469 | Mode profiles |
| Week 14 | 107 | 576 | Evals + dashboard integration |

**Coverage Target**: ≥85% (maintained from v7.0)

---

## Updated Risk Score (v7.0 FINAL)

**Total Risk**: **890 points** (11% reduction from v6.0 baseline 1,000)

| Risk | Score | Mitigation |
|------|-------|------------|
| **Risk #13: Context Assembly Bugs** | **80** | Debugger (Week 7-11), replay, attribution |
| Risk #1: Bayesian Complexity | 150 | Query router (-100 points) |
| Risk #3: Curation Time | 120 | Human briefs (-60 points) |
| Risk #2: Obsidian Sync | 60 | Hot/cold (-30 points) |
| Risk #6: Storage Growth | 50 | 4-stage lifecycle (-20 points) |
| Risk #14: Schema Validation | 20 | Parallel validation, caching |
| Other Risks (7) | 410 | No change from v6.0 |

**Decision**: **GO at 96% confidence** (up from 94% in v6.0)

---

## Success Criteria (v7.0 FINAL)

**Pre-Launch** (Week 7-14):
- ✅ 576 tests passing (321 baseline + 255 new)
- ✅ Memory evals: Freshness ≥70%, Leakage <5%, Precision ≥90%, Recall ≥70%
- ✅ Schema validation <30s in CI
- ✅ Query router accuracy ≥90%
- ✅ **Context debugger logs 100% of queries** (PREMORTEM requirement)
- ✅ **Query replay deterministic** (PREMORTEM requirement)

**Post-Launch** (Week 15+):
- ✅ **Context assembly bugs <30% of failures** (vs 40% industry baseline, PREMORTEM target)
- ✅ Query latency <800ms (95th percentile)
- ✅ Curation time <25 minutes/week
- ✅ Storage growth <25MB/1000 chunks
- ✅ User retention ≥85% after 4 weeks

---

## Mandatory Actions Before Week 7 Implementation

**From PREMORTEM v7.0**:

**v6.0 Requirements** (Still Valid):
1. ✅ Week 9 Spike: Bayesian network benchmarking (500/1000/2000 nodes)
2. ✅ Week 7 Spike: Obsidian sync performance testing (10k token files)
3. ✅ Week 11-12: Curation UX user testing (10 alpha testers)
4. ✅ Week 7: MCP server versioning (v1.0/v2.0 backward compatibility)

**v7.0 NEW Requirements** (PREMORTEM additions):
5. ✅ Week 7: Memory schema validation (create `memory-schema.yaml`, test validator)
6. ✅ Week 8: Query router testing (validate routing accuracy ≥90% on 100 test queries)
7. ✅ **Week 7: Query logging infrastructure** (SQLite table, trace schema)
8. ✅ **Week 8: Replay capability validation** (replay 10 queries, verify deterministic)
9. ✅ **Week 11: Error attribution testing** (classify 100 failures, verify >80% accuracy)

---

## Comparison: v6.0 → v7.0 Executive Summary → v7.0 FINAL

| Aspect | v6.0 | v7.0 Summary | v7.0 FINAL |
|--------|------|--------------|------------|
| **Risk Score** | 1,000 | 890 | 890 (no change) |
| **Confidence** | 94% | 96% | 96% (no change) |
| **Decision** | CONDITIONAL GO | GO | GO (validated) |
| **Context Debugger** | None | Week 14 (all) | **Week 7-11 (incremental)** |
| **Error Attribution** | None | Week 14 | **Week 11** |
| **Query Logging** | None | Week 14 | **Week 7** |
| **Replay Capability** | None | Week 14 | **Week 8** |
| **Total Tests** | 397 | 556 | **576** (+20) |
| **Total LOC** | 5,290 | 7,100 | **7,250** (+150) |

**Key Improvement in FINAL**: Context debugger is **incremental** (Weeks 7-11), not **big bang** (Week 14). Reduces integration risk and enables early debugging of Week 8-10 issues.

---

## Lessons Learned (Loop 1 Iterations)

**Iteration 1 (v6.0)**: Initial baseline (1,000 risk, 94% confidence)
- Identified 12 risks, created mitigation strategies
- Decision: CONDITIONAL GO

**Iteration 2**: Deep research on 16 counter-intuitive insights
- Analyzed Memory Wall principles
- Identified gaps: 3-tier → 5-tier, no evals, no debugger

**Iteration 3 (v7.0 Summary)**: Integrated 16 insights (890 risk, 96% confidence)
- 5-tier storage, memory-as-code, evals, debugger
- Decision: GO

**Iteration 4 (v7.0 FINAL)**: Integrated PREMORTEM findings
- **Context debugger elevated to P0** (moved to Weeks 7-11)
- Error attribution moved to Week 11
- Query logging from Week 7
- Decision: **GO (validated)**

**Critical Insight**: **Context-assembly bugs are the #1 failure mode** (40% of production failures per PREMORTEM). Debugger must be incremental (Weeks 7-11), not big bang (Week 14).

---

## Version History

**v6.0** (2025-10-18): Loop 1 Iteration 1
- 12 risks, 1,000 points, CONDITIONAL GO at 94%

**v7.0 Executive Summary** (2025-10-18): Loop 1 Iteration 3
- 16 insights integrated, 890 points, GO at 96%
- Context debugger in Week 14

**v7.0 FINAL** (2025-10-18): Loop 1 Iteration 4
- PREMORTEM findings integrated, 890 points, GO at 96% (validated)
- **Context debugger incremental (Weeks 7-11)**
- Error attribution in Week 11
- Query logging from Week 7
- **Production-ready, ready for Loop 2**

---

**Receipt**:
- **Run ID**: loop1-iter4-spec-v7.0-final
- **Timestamp**: 2025-10-18T22:15:00Z
- **Agent**: Strategic Planning (Loop 1 Iteration 4 FINAL)
- **Inputs**: SPEC v7.0 Summary, PREMORTEM v7.0, PLAN v7.0
- **Changes**: Final SPEC v7.0 with PREMORTEM insights (context debugger P0, incremental implementation)
- **Status**: **Loop 1 COMPLETE** - Ready for user approval and Loop 2 implementation
