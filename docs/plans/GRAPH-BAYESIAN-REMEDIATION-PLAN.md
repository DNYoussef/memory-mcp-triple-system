# Graph & Bayesian Layer Remediation Plan

## System Architecture (Clarified)

### The Five-Layer Mental Model

```
+------------------------------------------------------------------+
|                        OBSIDIAN (UI Layer)                        |
|    Frontmatter visualization, note editing, relationship view     |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
|                     BEADS (Action Layer)                          |
|    Ideas/plans -> Clear actionable tasks, DAG dependencies        |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
|              BAYESIAN GRAPH (World Model Layer)                   |
|    Probabilistic beliefs, relationship confidence, inference      |
|    "How things connect and why" - MUTABLE, learns over time       |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
|                VECTOR STORE (Truth Layer)                         |
|    ChromaDB - Accurate, stable facts that DON'T change            |
|    Documentation, definitions, proven patterns - IMMUTABLE        |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
|             TRIPLE-LAYER MEMORY (Temporal Layer)                  |
|    Daily (24h) -> Weekly (7d) -> Monthly (30d) -> ARCHIVE         |
|    Decay-based short-term memory, ephemeral context               |
+------------------------------------------------------------------+
```

### Layer Purposes

| Layer | Purpose | Mutability | Decay |
|-------|---------|------------|-------|
| **Obsidian** | UI/visualization, frontmatter editing | User-driven | None |
| **Beads** | Task management, DAG of actions | Task lifecycle | Completed tasks archive |
| **Bayesian Graph** | World model, relationship inference | Learns continuously | Confidence decays without reinforcement |
| **Vector Store** | Ground truth, stable facts | Rarely changes | None (permanent) |
| **Triple-Layer Memory** | Session context, recent work | Automatic | 24h -> 7d -> 30d -> Archive |

### Data Flow

```
New Information
      |
      v
[Triple-Layer Memory] ---(if valuable)---> [Vector Store]
      |                                          ^
      |                                          |
      v                                          |
[Bayesian Graph] <---(learns from)---------------+
      |
      v
[Beads] ---(actionable items)
      |
      v
[Obsidian] ---(visualize/edit)
```

### 30-Day Seed Memory Handling

When memories reach 30-day expiration, they face a decision gate:

```
30-Day Memory Expiring
         |
         v
   [Promotion Check]
         |
    +----+----+
    |         |
    v         v
 PROMOTE   ARCHIVE
    |         |
    v         v
 Vector    Cold Storage
 Store     (seed_archive/)
```

**Promotion Criteria** (to Vector Store):
- Accessed >= 3 times in 30 days
- Referenced by >= 2 other chunks
- Contains factual/definitional content
- User explicitly marked as important

**Archive Criteria** (to seed_archive/):
- Low access frequency
- Contextual/ephemeral content
- Session-specific information
- BUT still retrievable if needed

---

## Executive Summary

**Status Assessment (2026-01-19)**:
| Component | Expected | Actual | Severity |
|-----------|----------|--------|----------|
| Graph Size | "Bloated" | 15 nodes, 12 edges | NOT BLOATED |
| ChromaDB | Populated | 0 documents | CRITICAL |
| Edge Metadata | weight, confidence, evidence | Only type, metadata | CRITICAL |
| Node Metadata | states, frequency, importance | Only type, metadata | HIGH |
| Bayesian CPDs | Real data | Synthetic defaults | HIGH |

**Root Cause**: Edges and nodes lack the Bayesian-required attributes (confidence, weight, evidence, states). The Bayesian layer defaults missing values to synthetic data, making probabilistic inference meaningless.

---

## Phase 1: Data Audit & Cleanup (Priority: HIGH)

### 1.1 Current Graph Inventory

```
Graph Statistics (from diagnostic):
- Total Nodes: 15
  - Entity nodes: 11
  - Chunk nodes: 4
- Total Edges: 12
- Edge Attributes: {type, relationship_type, metadata}
- MISSING: weight, confidence, evidence
```

### 1.2 Audit Tasks

| Task | Description | Command |
|------|-------------|---------|
| AUD-001 | Export all nodes with attributes | `python -c "from src.services.graph_service import GraphService; g = GraphService('~/.claude/memory-mcp-data'); g.load_graph(); print(list(g.graph.nodes(data=True)))"` |
| AUD-002 | Export all edges with attributes | `python -c "from src.services.graph_service import GraphService; g = GraphService('~/.claude/memory-mcp-data'); g.load_graph(); print(list(g.graph.edges(data=True)))"` |
| AUD-003 | Identify orphan nodes (no edges) | Check for nodes with degree 0 |
| AUD-004 | Identify cycles | NetworkX `simple_cycles()` |
| AUD-005 | Validate node types | All nodes must have valid type attribute |

### 1.3 Cleanup Rules

**Delete if**:
- Node has no edges (orphan) AND no meaningful metadata
- Node references non-existent entity
- Edge connects to non-existent node
- Duplicate edges between same nodes

**Keep if**:
- Node is a valid chunk with text content
- Node is a valid entity with defined type
- Edge represents meaningful relationship

---

## Phase 2: Edge Metadata Enhancement (Priority: CRITICAL)

### 2.1 Current Edge Schema

```python
# File: src/services/graph_edge_manager.py:56-60
self.graph.add_edge(
    source, target,
    type=relationship_type,
    metadata=metadata or {}
)
```

### 2.2 Required Edge Schema (Per SPEC-v7.0)

```python
# REQUIRED for Bayesian layer
self.graph.add_edge(
    source, target,
    type=relationship_type,
    weight=0.5,          # 0.0-1.0, strength of relationship
    confidence=0.5,      # 0.0-1.0, certainty of edge existence
    evidence=0.5,        # 0.0-1.0, Bayesian evidence rating
    frequency=1,         # How often this relationship observed
    evidence_chunks=[],  # Source chunks supporting this edge
    metadata=metadata or {}
)
```

### 2.3 Implementation Tasks

| Task | File | Changes |
|------|------|---------|
| EDG-001 | `graph_edge_manager.py` | Add default values for weight, confidence, evidence, frequency |
| EDG-002 | `graph_edge_manager.py` | Add `update_edge_confidence()` method |
| EDG-003 | `graph_edge_manager.py` | Add `increment_frequency()` method |
| EDG-004 | `graph_service.py` | Expose new edge methods through facade |
| EDG-005 | Migration script | Backfill existing edges with default values |

### 2.4 Edge Confidence Sources

| Source | Initial Confidence | Notes |
|--------|-------------------|-------|
| Explicit user link | 0.9 | User explicitly created relationship |
| Frontmatter parents/children | 0.85 | Obsidian explicit hierarchy |
| Entity co-occurrence (same chunk) | 0.7 | Entities mentioned together |
| Semantic similarity > 0.85 | 0.6 | Embedding-based |
| Semantic similarity 0.7-0.85 | 0.5 | Weaker embedding match |
| Inferred (2-hop) | 0.4 | Transitive inference |

---

## Phase 3: Node Metadata Enhancement (Priority: HIGH)

### 3.1 Current Node Schema

```python
# File: src/services/graph_node_manager.py
self.graph.add_node(
    node_id,
    type='chunk' or 'entity',
    metadata=metadata or {}
)
```

### 3.2 Required Node Schema (Per SPEC-v1)

```python
# REQUIRED for Bayesian layer
self.graph.add_node(
    node_id,
    type=node_type,              # chunk, entity, concept
    states=["true", "false"],    # Bayesian states for this node
    frequency=1,                 # How often this node accessed/referenced
    importance=0.5,              # Prior probability (0.0-1.0)
    decay_score=1.0,             # Memory layer indicator
    created_at=timestamp,
    last_accessed=timestamp,
    metadata=metadata or {}
)
```

### 3.3 Implementation Tasks

| Task | File | Changes |
|------|------|---------|
| NOD-001 | `graph_node_manager.py` | Add default values for states, frequency, importance |
| NOD-002 | `graph_node_manager.py` | Add `update_importance()` method |
| NOD-003 | `graph_node_manager.py` | Add `increment_frequency()` method |
| NOD-004 | `graph_node_manager.py` | Add `update_decay_score()` method |
| NOD-005 | Migration script | Backfill existing nodes with default values |

### 3.4 Node Importance Calculation

```python
# Importance formula
importance = min(1.0, (
    0.3 * normalized_degree +      # Connectivity
    0.3 * normalized_frequency +    # Access patterns
    0.2 * recency_score +          # How recently accessed
    0.2 * explicit_weight          # User-assigned importance
))
```

---

## Phase 4: Bayesian Feedback Loop (Priority: HIGH)

### 4.1 Current Problem

```python
# File: network_builder.py:393
confidence = data.get("confidence", 1.0)  # ALWAYS 1.0 if missing!
```

The Bayesian layer:
1. Reads edge confidence (defaults to 1.0)
2. Estimates CPDs from synthetic data
3. Returns query results
4. **NEVER updates the graph with learned probabilities**

### 4.2 Required Feedback Loop

```
Query -> Bayesian Inference -> Update Graph
         ^                          |
         |                          v
         +--- Load from Graph <-----+
```

### 4.3 Implementation Tasks

| Task | File | Description |
|------|------|-------------|
| BAY-001 | `network_builder.py` | Remove default confidence=1.0, require explicit value |
| BAY-002 | `probabilistic_query.py` | After inference, update edge confidence in graph |
| BAY-003 | `graph_service.py` | Add `update_edge_from_bayesian()` method |
| BAY-004 | New file | Create `bayesian_graph_sync.py` for bidirectional sync |
| BAY-005 | `nexus_processor.py` | Integrate feedback loop into query pipeline |

### 4.4 Confidence Update Formula

```python
# After Bayesian inference
new_confidence = (
    0.7 * prior_confidence +           # Historical confidence
    0.3 * bayesian_posterior           # New evidence
)
# Clamp to [0.1, 0.95] to prevent certainty
```

---

## Phase 5: ChromaDB as Truth Layer (Priority: CRITICAL)

### 5.1 Current State

```
ChromaDB Collections:
- memory_chunks: 0 documents (EMPTY!)
```

### 5.2 Role Clarification

ChromaDB is the **Truth Layer** - it stores:
- **Stable facts** that don't change (documentation, definitions)
- **Proven patterns** validated through use
- **Promoted memories** that passed the 30-day gate
- **Reference material** (specs, APIs, procedures)

It does NOT store:
- Ephemeral session context (that's Triple-Layer Memory)
- Uncertain beliefs (that's Bayesian Graph)
- Action items (that's Beads)

### 5.3 Population Strategy (Truth-Focused)

| Source | Priority | Content Type | Expected |
|--------|----------|--------------|----------|
| Promoted 30-day memories | HIGH | Validated knowledge | ~50-100 |
| Documentation/specs | HIGH | Reference facts | ~100-200 |
| Stable Obsidian notes (non-daily) | MEDIUM | Definitions, procedures | ~200-300 |
| Proven code patterns | MEDIUM | Reusable solutions | ~50-100 |
| Entity definitions from graph | LOW | Concept definitions | ~50 |

### 5.4 Implementation Tasks

| Task | Description |
|------|-------------|
| VEC-001 | Create import script for stable Obsidian notes (exclude daily/journal) |
| VEC-002 | Extract entity definitions from graph, embed as facts |
| VEC-003 | Create promotion pipeline from Triple-Layer -> Vector |
| VEC-004 | Verify embedding dimensions match (384 or 1536) |
| VEC-005 | Add metadata: `is_fact=True`, `source`, `promoted_at` |

---

## Phase 6: Seed Memory Archive System (Priority: HIGH)

### 6.1 The Problem

When memories age past 30 days, they currently just... disappear. We need:
1. **Promotion path** to Vector Store (for valuable facts)
2. **Archive path** to cold storage (for retrievable but low-priority)

### 6.2 Archive Location

```
~/.claude/memory-mcp-data/
  |-- seed_archive/
  |   |-- 2026-01/
  |   |   |-- week-01.jsonl
  |   |   |-- week-02.jsonl
  |   |-- index.json  # Quick lookup index
  |-- promoted/
  |   |-- log.jsonl   # Promotion audit trail
```

### 6.3 Promotion Decision Algorithm

```python
def should_promote(memory: Memory) -> bool:
    """Decide if expiring memory should be promoted to Vector Store."""
    score = 0.0

    # Access frequency (max 0.3)
    score += min(0.3, memory.access_count * 0.1)

    # Reference count (max 0.3)
    score += min(0.3, memory.reference_count * 0.15)

    # Content type bonus (max 0.2)
    if memory.is_definitional():
        score += 0.2
    elif memory.is_procedural():
        score += 0.15

    # User importance flag (max 0.2)
    if memory.metadata.get("important"):
        score += 0.2

    return score >= 0.5  # Promote if score >= 0.5
```

### 6.4 Implementation Tasks

| Task | Description |
|------|-------------|
| SEED-001 | Create `seed_archive/` directory structure |
| SEED-002 | Implement `MemoryPromoter` class |
| SEED-003 | Add promotion hook to decay scheduler |
| SEED-004 | Create archive retrieval API (for rare lookups) |
| SEED-005 | Add promotion audit logging |

### 6.5 Archive Schema

```python
# seed_archive/2026-01/week-03.jsonl (one line per memory)
{
    "id": "mem-abc123",
    "text": "Original memory content...",
    "created_at": "2025-12-19T10:00:00Z",
    "archived_at": "2026-01-19T10:00:00Z",
    "final_decay_score": 0.12,
    "access_count": 1,
    "reference_count": 0,
    "promotion_score": 0.25,  # Below 0.5, so archived
    "tags": ["session", "context"],
    "retrievable": true
}
```

---

## Phase 7: Data Migration Script

### 7.1 Migration Script Outline

```python
# File: scripts/migrate_graph_bayesian.py

def migrate_graph():
    """Backfill missing Bayesian attributes."""

    # 1. Load graph
    graph_service = GraphService(data_dir)
    graph_service.load_graph()

    # 2. Update edges with missing attributes
    for u, v, data in graph.edges(data=True):
        if 'confidence' not in data:
            data['confidence'] = compute_initial_confidence(u, v, data)
        if 'weight' not in data:
            data['weight'] = 0.5
        if 'evidence' not in data:
            data['evidence'] = 0.5
        if 'frequency' not in data:
            data['frequency'] = 1

    # 3. Update nodes with missing attributes
    for node, data in graph.nodes(data=True):
        if 'states' not in data:
            data['states'] = ['true', 'false']
        if 'frequency' not in data:
            data['frequency'] = 1
        if 'importance' not in data:
            data['importance'] = compute_initial_importance(node, data)

    # 4. Remove orphan nodes
    orphans = [n for n in graph.nodes() if graph.degree(n) == 0]
    graph.remove_nodes_from(orphans)

    # 5. Save migrated graph
    graph_service.save_graph()
```

---

## Implementation Order

### Week 1: Foundation & Audit
1. **AUD-001 to AUD-005**: Complete audit of current graph
2. **EDG-001 to EDG-003**: Edge schema enhancement (confidence, weight, evidence)
3. **NOD-001 to NOD-003**: Node schema enhancement (states, frequency, importance)

### Week 2: Migration & Bayesian Fix
4. **EDG-005, NOD-005**: Run migration script to backfill attributes
5. **BAY-001**: Fix default confidence=1.0 issue
6. **SEED-001, SEED-002**: Set up seed archive structure

### Week 3: Vector Store & Promotion
7. **VEC-001 to VEC-003**: Populate ChromaDB with truth/facts
8. **SEED-003 to SEED-005**: Implement promotion pipeline
9. **VEC-004, VEC-005**: Add metadata and verify embeddings

### Week 4: Feedback Loop & Integration
10. **BAY-002 to BAY-005**: Implement Bayesian feedback loop
11. Integration testing across all layers
12. Obsidian sync verification (NEX-003)

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Edge confidence coverage | 100% | All edges have explicit confidence |
| Node importance coverage | 100% | All nodes have importance score |
| ChromaDB documents (facts) | > 100 | Populated with truth/facts |
| Seed archive functional | Yes | 30-day memories handled |
| Promotion pipeline active | Yes | Valuable memories promoted |
| Bayesian accuracy | > 0.7 | Test queries return meaningful results |
| Orphan nodes | 0 | No disconnected nodes |
| Cycles | 0 | DAG property maintained |
| Layer separation | Clean | Each layer serves its purpose |

---

## Files to Modify

| File | Priority | Changes |
|------|----------|---------|
| `src/services/graph_edge_manager.py` | P0 | Add Bayesian edge attributes |
| `src/services/graph_node_manager.py` | P0 | Add Bayesian node attributes |
| `src/services/graph_service.py` | P0 | Expose new methods |
| `src/bayesian/network_builder.py` | P1 | Fix confidence defaults |
| `src/bayesian/probabilistic_query.py` | P1 | Add feedback loop |
| `scripts/migrate_graph_bayesian.py` | P1 | New migration script |
| `src/sync/bayesian_graph_sync.py` | P2 | New bidirectional sync |
| `src/memory/seed_archive.py` | P1 | **NEW**: Seed memory archive system |
| `src/memory/memory_promoter.py` | P1 | **NEW**: Promotion decision engine |
| `src/stores/vector_store.py` | P1 | Add `is_fact` metadata support |
| `src/decay/decay_scheduler.py` | P2 | Hook promotion check at 30-day |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Backup graph.json before migration |
| Breaking existing queries | Version bump, deprecation warnings |
| Performance degradation | Lazy loading of Bayesian attributes |
| Obsidian sync issues | Wait for bidirectional sync (NEX-003) |

---

## Next Steps

1. **Approve this plan**
2. **Run audit commands** to get exact node/edge inventory
3. **Backup current graph.json**
4. **Begin Phase 2 implementation** (edge metadata)

---

## Phase 8: AI Exoskeleton Organism Integration (Priority: CRITICAL)

### 8.1 Memory MCP's Role in the Organism

Memory MCP is NOT just a database - it's the **Central Nervous System** of the AI Exoskeleton:

```
+------------------------------------------------------------------+
|                    AI EXOSKELETON ORGANISM                        |
+------------------------------------------------------------------+
                              |
        +---------------------+---------------------+
        |                     |                     |
   +---------+         +-------------+        +----------+
   | CAPTURE |         | BRAIN       |        | IMMUNE   |
   | life-os |         | context-    |        | connascence
   | content |         | cascade     |        | slop-detect
   | trader  |         | council     |        +----------+
   +---------+         +-------------+              |
        |                     |                     |
        v                     v                     v
+------------------------------------------------------------------+
|              CENTRAL NERVOUS SYSTEM (Memory MCP)                  |
|   - Semantic Memory (WHO/WHEN/PROJECT/WHY)                        |
|   - Mode Detection (Execution/Planning/Brainstorm)                |
|   - Hybrid Retrieval (Vector 40% + Graph 40% + Bayesian 20%)     |
|   - Triple-Layer Decay (24h -> 7d -> 30d -> ARCHIVE/PROMOTE)     |
|   - Loop 1.5 Learnings Storage                                   |
|   - Telemetry Packet Reception                                   |
+------------------------------------------------------------------+
        |                     |                     |
        v                     v                     v
   +---------+         +-------------+        +----------+
   | BEADS   |         | DASHBOARD   |        | LIBRARY  |
   | Task DAG|<------->| Pipeline    |        | Bone     |
   | "What   |  mode   | Executor    |        | Marrow   |
   | next?"  |  aware  | 14 nodes    |        | 84 comp  |
   +---------+         +-------------+        +----------+
```

### 8.2 The Dual Filing Cabinet Contract

| Mode | Primary Source | Secondary | Blend |
|------|----------------|-----------|-------|
| **Execution** | Beads FIRST | Memory MCP | 80/20 |
| **Planning** | Both + Council | Council | 50/50 |
| **Brainstorm** | Memory MCP | Beads deps | 20/80 |

**Key Insight**: "Keep general info in Memory MCP, put specific coding memories in Beads to remove burden from Memory MCP"

### 8.3 Four-Loop Self-Improvement Data Flows

```
+------------------------------------------------------------------+
|   LOOP 1: EXECUTION (Per-Request)                                 |
|   5-phase: Intent -> Prompt -> Plan -> Route -> Execute           |
|   Output: Task completion, errors, decisions                      |
|   WRITES TO Memory MCP: WHO/WHEN/PROJECT/WHY tagged results       |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|   LOOP 1.5: SESSION REFLECTION (/reflect)                         |
|   Signals: Corrections (0.90), Rules (0.90), Approvals (0.75)    |
|   Output: LEARNED PATTERNS in skill files                         |
|   WRITES TO Memory MCP: expertise:{domain}:{topic}                |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|   LOOP 2: QUALITY VALIDATION                                      |
|   Theater detection, functionality audits, security checks        |
|   Connascence 7-analyzer suite (sigma >= 4.0, DPMO <= 6210)      |
|   WRITES TO Memory MCP: findings:{agent}:{severity}:{id}          |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|   LOOP 3: META-OPTIMIZATION (Every 3 Days)                        |
|   1. Query Memory MCP for Loop 1.5 learnings                     |
|   2. Run GlobalMOO 5D exploration                                 |
|   3. Run PyMOO NSGA-II 14D refinement                            |
|   4. Distill named modes (audit, speed, research, robust)        |
|   5. Cascade: templates -> commands -> agents -> skills          |
|   READS FROM Memory MCP: All loop learnings                       |
|   WRITES TO Memory MCP: optimization:{cycle}:{timestamp}          |
+------------------------------------------------------------------+
```

### 8.4 Telemetry Data That MUST Flow Into Memory MCP

| Source | Namespace | Data |
|--------|-----------|------|
| Loop 1 (Execution) | `agents:{category}:{type}:{project}:{timestamp}` | Task results, decisions |
| Loop 1.5 (Reflect) | `expertise:{domain}:{topic}` | Learned patterns |
| Loop 2 (Quality) | `findings:{agent}:{severity}:{id}` | Quality issues |
| Loop 2 (Fixes) | `fixes:{agent}:{finding-id}` | Resolution patterns |
| Loop 3 (Meta) | `optimization:{cycle}:{timestamp}` | Mode configurations |
| Connascence | `quality:{project}:{timestamp}` | 7-analyzer metrics |
| Beads | `tasks:{project}:{bead-id}` | Task completions |
| Dashboard | `pipelines:{pipeline-id}:{run-id}` | Execution telemetry |

### 8.5 Missing Physiology Organs (Depend on Memory MCP)

| Organ | Purpose | Memory MCP Role |
|-------|---------|-----------------|
| **Metabolic Ledger** | Cost/budget tracking | Store `cost:{pipeline}:{run}` metrics |
| **Waste System** | GC, drift cleanup | Compaction policy, dedup detection |
| **Apoptosis** | Failure containment | Quarantine registry `quarantine:{component}` |
| **Sleep System** | Offline consolidation | Scheduled telemetry packet generation |

### 8.6 Implementation Tasks for Organism Integration

| Task | Description | Priority |
|------|-------------|----------|
| ORG-001 | Add namespace support for all telemetry types | P0 |
| ORG-002 | Implement mode-aware routing (Beads vs Memory blend) | P0 |
| ORG-003 | Create Loop 1.5 storage interface | P1 |
| ORG-004 | Create Loop 3 query interface (aggregate learnings) | P1 |
| ORG-005 | Add Beads <-> Memory MCP bridge | P1 |
| ORG-006 | Implement telemetry packet schema | P1 |
| ORG-007 | Add quarantine registry support | P2 |
| ORG-008 | Implement sleep system hooks | P2 |

### 8.7 Beads Integration Points

```python
# Beads queries Memory MCP for context
async def get_bead_context(bead_id: str) -> dict:
    """Retrieve semantic context for a Beads task."""
    # 1. Get bead metadata from Beads
    bead = await beads_client.get_bead(bead_id)

    # 2. Query Memory MCP for related context
    context = await memory_mcp.query(
        query=bead.title,
        mode="execution",  # Beads-first mode
        filters={"project": bead.project}
    )

    # 3. Include any learned patterns for this project
    patterns = await memory_mcp.get(
        namespace=f"expertise:{bead.project}:*"
    )

    return {"bead": bead, "context": context, "patterns": patterns}

# Memory MCP receives task completion
async def store_task_completion(bead_id: str, result: dict):
    """Store task completion in Memory MCP."""
    await memory_mcp.store(
        namespace=f"tasks:{result['project']}:{bead_id}",
        data=result,
        metadata={
            "WHO": "beads:completion",
            "WHEN": datetime.now().isoformat(),
            "PROJECT": result["project"],
            "WHY": "task-completion"
        }
    )
```

### 8.8 Updated Architecture with Organism Context

```
+------------------------------------------------------------------+
|                        OBSIDIAN (UI)                              |
|    Visualization, frontmatter, relationship editing               |
+------------------------------------------------------------------+
                                |
                                v
+------------------------------------------------------------------+
|                     BEADS (Procedural Memory)                     |
|    Task DAG, dependencies, "what's unblocked?" (bd ready)         |
|    Git-backed, distributed                                        |
+------------------------------------------------------------------+
                                |
                         [Mode-Aware Router]
                    Execution: 80/20 Beads/Memory
                    Planning: 50/50 + Council
                    Brainstorm: 20/80 Memory/Beads
                                |
                                v
+------------------------------------------------------------------+
|              MEMORY MCP (Central Nervous System)                  |
|  +----------------------------------------------------------+   |
|  | BAYESIAN GRAPH (World Model)                              |   |
|  | Probabilistic beliefs, confidence, inference              |   |
|  | Learns from Loop 1.5/2/3, updates edge weights           |   |
|  +----------------------------------------------------------+   |
|  | VECTOR STORE (Truth Layer)                                |   |
|  | Stable facts, promoted memories, documentation            |   |
|  | Receives: 30-day promotions, proven patterns             |   |
|  +----------------------------------------------------------+   |
|  | TRIPLE-LAYER MEMORY (Temporal)                            |   |
|  | 24h -> 7d -> 30d -> [PROMOTE or ARCHIVE]                 |   |
|  | Session context, recent decisions, ephemeral             |   |
|  +----------------------------------------------------------+   |
|  | TELEMETRY STORE                                           |   |
|  | Loop 1.5 learnings, Loop 3 modes, quality metrics        |   |
|  | Namespaces: expertise, findings, fixes, optimization     |   |
|  +----------------------------------------------------------+   |
+------------------------------------------------------------------+
                                |
               +----------------+----------------+
               |                |                |
               v                v                v
        +-----------+    +-----------+    +-----------+
        | DASHBOARD |    | CONNASCENCE|   | LOOP 3    |
        | Pipeline  |    | 7-Analyzer|    | Meta-     |
        | Executor  |    | Quality   |    | Optimizer |
        +-----------+    +-----------+    +-----------+
```

---

## Updated Implementation Order (With Organism Context)

### Week 1: Foundation & Audit
1. **AUD-001 to AUD-005**: Audit current graph (15 nodes, 12 edges)
2. **EDG-001 to EDG-003**: Edge schema (confidence, weight, evidence)
3. **NOD-001 to NOD-003**: Node schema (states, frequency, importance)

### Week 2: Migration & Telemetry Foundation
4. **EDG-005, NOD-005**: Migration script
5. **BAY-001**: Fix confidence defaults
6. **ORG-001**: Add namespace support for telemetry types
7. **ORG-006**: Implement telemetry packet schema

### Week 3: Seed Archive & Vector Truth Layer
8. **SEED-001 to SEED-005**: Seed memory archive + promotion
9. **VEC-001 to VEC-005**: Vector store as truth layer

### Week 4: Organism Integration
10. **ORG-002**: Mode-aware routing (Beads/Memory blend)
11. **ORG-003, ORG-004**: Loop 1.5/Loop 3 interfaces
12. **ORG-005**: Beads <-> Memory MCP bridge

### Week 5: Feedback Loops & Validation
13. **BAY-002 to BAY-005**: Bayesian feedback loop
14. Integration testing across all layers
15. Obsidian bidirectional sync (NEX-003)

---

## Updated Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Edge confidence coverage | 100% | All edges have explicit confidence |
| Node importance coverage | 100% | All nodes have importance score |
| ChromaDB documents (facts) | > 100 | Populated with truth/facts |
| Seed archive functional | Yes | 30-day memories handled |
| Promotion pipeline active | Yes | Valuable memories promoted |
| Bayesian accuracy | > 0.7 | Meaningful probabilistic queries |
| Mode-aware routing | Yes | Execution/Planning/Brainstorm blends |
| Telemetry namespaces | 8+ | All loop data has home |
| Loop 1.5 storage | Yes | Learnings persisted |
| Loop 3 query | Yes | Can aggregate learnings |
| Beads bridge | Yes | Task context flows |
| Layer separation | Clean | Each layer serves its purpose |

---

## Updated Files to Create/Modify

| File | Priority | Changes |
|------|----------|---------|
| `src/services/graph_edge_manager.py` | P0 | Bayesian edge attributes |
| `src/services/graph_node_manager.py` | P0 | Bayesian node attributes |
| `src/bayesian/network_builder.py` | P1 | Fix confidence defaults |
| `src/memory/seed_archive.py` | P1 | **NEW**: Seed memory archive |
| `src/memory/memory_promoter.py` | P1 | **NEW**: Promotion decision |
| `src/telemetry/namespace_router.py` | P1 | **NEW**: Telemetry namespaces |
| `src/telemetry/packet_schema.py` | P1 | **NEW**: Telemetry packet format |
| `src/integrations/beads_bridge.py` | P1 | **NEW**: Beads <-> Memory |
| `src/integrations/loop_interfaces.py` | P1 | **NEW**: Loop 1.5/3 storage |
| `src/routing/mode_aware_router.py` | P1 | **NEW**: Execution/Planning blend |
| `src/sync/bayesian_graph_sync.py` | P2 | Bidirectional sync |
| `src/decay/decay_scheduler.py` | P2 | Promotion hook at 30-day |

---

*Plan created: 2026-01-19*
*Updated: 2026-01-19 (Added organism context)*
*Author: Claude (Memory MCP Triple System)*
*Reference: AI Exoskeleton Organ Map, Metabolic Map, Beads Audit*
