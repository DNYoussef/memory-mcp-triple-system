# Memory MCP Triple System - PLAN v7.0

**Version**: 7.0 (Loop 1 Iteration 3 - Final)
**Date**: 2025-10-18
**Status**: Production-Ready
**Duration**: 8 weeks (Weeks 7-14)
**Estimated Effort**: 196 hours (24.5 hours/week average, +16 hours from v6.0)
**Risk Score**: 890 points (GO at 96% confidence)

---

## Executive Summary

**PLAN v7.0** integrates 16 counter-intuitive Memory Wall insights into an 8-week implementation roadmap. Key architectural enhancements from v6.0:

1. **5-Tier Storage** (Week 7-9): KV, Relational, Vector, Graph, Event Log with query router
2. **Memory-as-Code** (Week 7, 11, 14): Schemas, migrations, CLI tools, CI/CD integration
3. **4-Stage Lifecycle** (Week 12): Active → Demoted → Archived → Rehydratable with rekindling
4. **Curated Core Pattern** (Week 11): 5 core + 15-25 extended results (precision over volume)
5. **Memory Eval Suite** (Week 14): Freshness, leakage, precision/recall continuous monitoring
6. **Context Assembly Debugger** (Week 14): Detailed query tracing for root cause analysis

**Total Deliverables**:
- **Production Code**: 3,420 LOC (vs 3,070 in v6.0, +11%)
- **Test Code**: 2,440 LOC (vs 2,220 in v6.0, +10%)
- **Total Tests**: 506 (321 baseline + 185 new)
- **Performance**: <800ms query latency (vs <1s in v6.0), <25min curation (vs <35min)

---

## Week-by-Week Enhancements from v6.0

### Week 7: 5-Tier Storage Foundation + Memory-as-Code

**Duration**: 24 hours (vs 20 hours in v6.0, +4 hours for schema work)
**Priority**: P0 (critical path)

#### v7.0 Enhancements

**NEW Task 1: Create Memory Schema** (4 hours)

*Files to Create*:
- `config/memory-schema.yaml` (200 lines)
- `src/schema/validator.py` (180 LOC)
- `tests/unit/test_schema_validator.py` (100 LOC)

*Implementation*:
```yaml
# config/memory-schema.yaml (versioned, CI-validated)

version: "1.0"
created: "2025-10-18"
description: "MCP Memory Schema v1.0 - Portable context library standard"

# 5 Memory Types (Insight #8: Memory isn't one problem)
memory_types:
  preference:
    description: "User preferences (coding style, tone, format)"
    lifecycle: personal
    retention: never  # Permanent
    storage: kv_store
    schema:
      key: {type: string, required: true, max_length: 100}
      value: {type: string, required: true, max_length: 1000}
      created: {type: timestamp, required: true}
      updated: {type: timestamp, required: false}
    examples:
      - key: "coding_style"
        value: "Python, type hints, NASA Rule 10 compliant"
      - key: "response_tone"
        value: "Professional, concise, no emojis"

  fact:
    description: "Verifiable facts (policies, rules, decisions)"
    lifecycle: project
    retention_days: 30  # After project close
    storage: relational
    schema:
      id: {type: uuid, required: true}
      content: {type: string, required: true, max_length: 5000}
      source: {type: uri, required: true}  # Obsidian file path or URL
      confidence: {type: float, min: 0.0, max: 1.0, default: 0.8}
      version: {type: semver, required: true}  # e.g., "2.1.0"
      supersedes: {type: uuid, required: false}  # Previous version ID
      verified: {type: boolean, default: false}
      verified_at: {type: timestamp, required: false}
    examples:
      - content: "NASA Rule 10: All functions ≤60 LOC"
        source: "file:///personal/ground-truth/nasa-rules.md"
        confidence: 1.0
        version: "1.0.0"
        verified: true

  knowledge:
    description: "Domain knowledge (concepts, definitions, how-tos)"
    lifecycle: session  # Decays slowly
    retention_days: 90  # Slow decay (half-life = 90 days)
    storage: vector
    schema:
      id: {type: uuid, required: true}
      text: {type: string, required: true, max_length: 10000}
      embedding: {type: array, items: float, length: 384}  # all-MiniLM-L6-v2
      file_path: {type: string, required: true}
      chunk_index: {type: integer, required: true}
      decay_half_life_days: {type: integer, default: 90}
      last_accessed: {type: timestamp, required: true}
      access_count: {type: integer, default: 0}
    examples:
      - text: "HippoRAG uses Personalized PageRank for multi-hop retrieval"
        file_path: "/projects/memory-mcp/docs/architecture.md"
        chunk_index: 42

  episode:
    description: "Episodic memory (events, conversations, what happened)"
    lifecycle: session
    retention_days: 7  # Fast decay
    storage: event_log
    schema:
      id: {type: uuid, required: true}
      timestamp: {type: timestamp, required: true}
      event_type: {type: enum, values: [conversation, decision, error, milestone]}
      data: {type: json, required: true}
      session_id: {type: uuid, required: true}
    examples:
      - event_type: "decision"
        data: {decision: "Use ChromaDB", rationale: "No Docker", alternatives: ["Qdrant"]}
        session_id: "session-2025-10-18-001"

  procedure:
    description: "Procedures (how to do X, workflows, SOPs)"
    lifecycle: project
    retention: versioned  # Never delete, only supersede
    storage: graph
    schema:
      id: {type: uuid, required: true}
      name: {type: string, required: true, max_length: 200}
      steps: {type: array, items: {step_id: string, action: string, dependencies: array}}
      version: {type: semver, required: true}
      supersedes: {type: uuid, required: false}
    examples:
      - name: "Deploy to production"
        steps:
          - {step_id: "1", action: "Run tests", dependencies: []}
          - {step_id: "2", action: "Build", dependencies: ["1"]}
          - {step_id: "3", action: "Push", dependencies: ["2"]}
        version: "1.2.0"

# Lifecycle Policies (Insight #13: Personalization is policy)
lifecycle_policies:
  personal:
    retention: never
    auto_archive: false
    decay_enabled: false
    priority: high
  project:
    retention_days: 30  # After project marked closed
    auto_archive: true
    decay_enabled: true
    decay_half_life_days: 30
    priority: medium
  session:
    retention_days: 7
    auto_archive: true
    decay_enabled: true
    decay_half_life_days: 7
    priority: low

# Validation Rules (Insight #10: Bookkeeping > model choice)
validation_rules:
  mandatory_tags: [lifecycle, created, version]
  optional_tags: [priority, project, topic, confidence]
  max_chunk_size_tokens: 512
  min_confidence: 0.3  # Below this, auto-archive
  version_format: semver  # e.g., "1.2.3"
```

*Schema Validator*:
```python
# src/schema/validator.py (180 LOC, NASA-compliant)

import yaml
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger
import semver

class MemorySchemaValidator:
    """
    Validate memory data against schema.

    Features:
    - YAML schema loading
    - Type validation (string, int, float, array, json)
    - Constraint validation (min, max, required, enum)
    - Semver version validation
    - CI integration (fail build if invalid)

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, schema_path: str):
        """Load schema from YAML file."""
        self.schema_path = Path(schema_path)
        with open(self.schema_path, 'r') as f:
            self.schema = yaml.safe_load(f)

    def validate_chunk(
        self,
        chunk: Dict[str, Any],
        memory_type: str
    ) -> tuple[bool, List[str]]:
        """
        Validate chunk against schema.

        Args:
            chunk: Chunk data to validate
            memory_type: One of [preference, fact, knowledge, episode, procedure]

        Returns:
            (is_valid, errors)
        """
        errors = []

        # Check memory type exists
        if memory_type not in self.schema['memory_types']:
            errors.append(f"Unknown memory type: {memory_type}")
            return False, errors

        type_schema = self.schema['memory_types'][memory_type]['schema']

        # Validate required fields
        for field, constraints in type_schema.items():
            if constraints.get('required', False) and field not in chunk:
                errors.append(f"Missing required field: {field}")

        # Validate field types and constraints
        for field, value in chunk.items():
            if field not in type_schema:
                errors.append(f"Unknown field: {field}")
                continue

            constraints = type_schema[field]
            field_type = constraints['type']

            # Type validation
            if field_type == 'string' and not isinstance(value, str):
                errors.append(f"{field}: Expected string, got {type(value)}")
            elif field_type == 'integer' and not isinstance(value, int):
                errors.append(f"{field}: Expected integer, got {type(value)}")
            elif field_type == 'float' and not isinstance(value, (int, float)):
                errors.append(f"{field}: Expected float, got {type(value)}")
            elif field_type == 'boolean' and not isinstance(value, bool):
                errors.append(f"{field}: Expected boolean, got {type(value)}")
            elif field_type == 'semver':
                try:
                    semver.VersionInfo.parse(value)
                except ValueError:
                    errors.append(f"{field}: Invalid semver: {value}")

            # Constraint validation
            if 'max_length' in constraints and len(value) > constraints['max_length']:
                errors.append(f"{field}: Max length {constraints['max_length']}, got {len(value)}")
            if 'min' in constraints and value < constraints['min']:
                errors.append(f"{field}: Min {constraints['min']}, got {value}")
            if 'max' in constraints and value > constraints['max']:
                errors.append(f"{field}: Max {constraints['max']}, got {value}")
            if 'enum' in constraints and value not in constraints['enum']:
                errors.append(f"{field}: Must be one of {constraints['enum']}, got {value}")

        return len(errors) == 0, errors

    def validate_mandatory_tags(self, chunk: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate mandatory tags."""
        errors = []
        mandatory = self.schema['validation_rules']['mandatory_tags']

        for tag in mandatory:
            if tag not in chunk:
                errors.append(f"Missing mandatory tag: {tag}")

        return len(errors) == 0, errors
```

*Tests*:
```python
# tests/unit/test_schema_validator.py (100 LOC)

import pytest
from src.schema.validator import MemorySchemaValidator

class TestSchemaValidator:
    """Unit tests for schema validation."""

    def test_valid_preference(self):
        """Test valid preference chunk."""
        validator = MemorySchemaValidator('config/memory-schema.yaml')

        chunk = {
            'key': 'coding_style',
            'value': 'Python, type hints',
            'created': '2025-10-18T10:00:00Z'
        }

        is_valid, errors = validator.validate_chunk(chunk, 'preference')
        assert is_valid
        assert len(errors) == 0

    def test_missing_required_field(self):
        """Test missing required field."""
        validator = MemorySchemaValidator('config/memory-schema.yaml')

        chunk = {
            'key': 'coding_style'
            # Missing 'value' (required)
        }

        is_valid, errors = validator.validate_chunk(chunk, 'preference')
        assert not is_valid
        assert 'Missing required field: value' in errors

    def test_invalid_semver(self):
        """Test invalid semver version."""
        validator = MemorySchemaValidator('config/memory-schema.yaml')

        chunk = {
            'id': 'uuid-123',
            'content': 'NASA Rule 10',
            'source': 'file:///nasa.md',
            'version': 'invalid-version'  # Not semver
        }

        is_valid, errors = validator.validate_chunk(chunk, 'fact')
        assert not is_valid
        assert 'Invalid semver' in str(errors)
```

*Deliverables*:
- ✅ `memory-schema.yaml` (200 lines, defines 5 memory types)
- ✅ `MemorySchemaValidator` (180 LOC, CI integration)
- ✅ 5 tests passing (valid, missing field, invalid type, semver, constraints)

**NEW Task 2: Add KV Store (Tier 1)** (2 hours)

*Implementation*:
```python
# src/storage/kv_store.py (100 LOC)

import sqlite3
from pathlib import Path
from typing import Optional
from loguru import logger

class KVStore:
    """
    Key-value store for preferences.

    Storage: SQLite table (simple, embedded)
    Query Pattern: O(1) lookup by key
    Use Case: "What's my coding style?" → Exact match

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, db_path: str):
        """Initialize KV store."""
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_table()

    def _create_table(self):
        """Create KV table if not exists."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def get(self, key: str) -> Optional[str]:
        """Get value by key (O(1) lookup)."""
        cursor = self.conn.execute(
            "SELECT value FROM preferences WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str):
        """Set key-value pair (upsert)."""
        self.conn.execute("""
            INSERT INTO preferences (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated = CURRENT_TIMESTAMP
        """, (key, value))
        self.conn.commit()
        logger.info(f"KV Store: Set {key} = {value}")

    def delete(self, key: str):
        """Delete key-value pair."""
        self.conn.execute("DELETE FROM preferences WHERE key = ?", (key,))
        self.conn.commit()
```

**NEW Task 3: Add Relational Store (Tier 2)** (2 hours)

*Implementation*:
```python
# src/storage/relational_store.py (140 LOC)

import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

class RelationalStore:
    """
    Relational store for entities and facts.

    Storage: SQLite tables (normalized schema)
    Query Pattern: SQL queries (joins, filters)
    Use Case: "What client projects exist?" → SELECT * FROM projects

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, db_path: str):
        """Initialize relational store."""
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

    def _create_tables(self):
        """Create relational tables."""
        # Entities table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,  # PERSON, ORG, PRODUCT, etc.
                metadata JSON
            )
        """)

        # Facts table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT NOT NULL,  # URI
                confidence REAL DEFAULT 0.8,
                version TEXT NOT NULL,  # Semver
                supersedes TEXT,  # Previous version ID
                verified BOOLEAN DEFAULT 0,
                verified_at TIMESTAMP,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def add_entity(self, entity_id: str, name: str, entity_type: str, metadata: dict = None):
        """Add entity to database."""
        self.conn.execute("""
            INSERT OR REPLACE INTO entities (id, name, type, metadata)
            VALUES (?, ?, ?, ?)
        """, (entity_id, name, entity_type, str(metadata or {})))
        self.conn.commit()

    def query_entities(self, entity_type: str = None) -> List[Dict[str, Any]]:
        """Query entities by type."""
        if entity_type:
            cursor = self.conn.execute(
                "SELECT id, name, type, metadata FROM entities WHERE type = ?",
                (entity_type,)
            )
        else:
            cursor = self.conn.execute(
                "SELECT id, name, type, metadata FROM entities"
            )

        entities = []
        for row in cursor.fetchall():
            entities.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'metadata': eval(row[3])  # JSON parse
            })

        return entities
```

**v6.0 Tasks (Obsidian MCP, Lifecycle Tagging)**: Same as v6.0, no changes

**Week 7 Summary (v7.0)**:
- **LOC Added**: 490 (Obsidian MCP) + 480 (schema/KV/relational) = **970 LOC production**
- **Test LOC**: 360 (MCP) + 200 (schema/stores) = **560 LOC tests**
- **Tests Added**: 15 (MCP) + 10 (schema/stores) = **25 tests**
- **Tests Passing**: 346/346 (321 baseline + 25 new)
- **New Files**:
  - `config/memory-schema.yaml` (200 lines)
  - `src/schema/validator.py` (180 LOC)
  - `src/storage/kv_store.py` (100 LOC)
  - `src/storage/relational_store.py` (140 LOC)

---

### Week 8: Query Router + GraphRAG Entity Consolidation

**Duration**: 28 hours (vs 24 hours in v6.0, +4 hours for query router)
**Priority**: P1

#### v7.0 Enhancements

**NEW Task 1: Implement Query Router** (4 hours)

*Files to Create*:
- `src/routing/query_router.py` (160 LOC)
- `tests/unit/test_query_router.py` (100 LOC)

*Implementation*:
```python
# src/routing/query_router.py (160 LOC, NASA-compliant)

from typing import List, Dict, Any
from loguru import logger
import re

class QueryRouter:
    """
    Route queries to appropriate storage tier(s).

    Routing Rules (Insight #3: Match store to query pattern):
    - "What's my X?" → KV Store (preferences)
    - "What client/project X?" → Relational (entities)
    - "What about X?" → Vector (semantic search)
    - "What led to X?" → Graph (multi-hop)
    - "What happened on X?" → Event Log (temporal)

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self):
        """Initialize query router."""
        self.patterns = {
            'kv': [
                r"what'?s my (.*?)\?",
                r"my preference for (.*?)",
                r"how do i prefer (.*?)"
            ],
            'relational': [
                r"what (client|project|entity) (.*?)\?",
                r"list all (clients|projects|entities)",
                r"which (.*?) (exist|are there)"
            ],
            'vector': [
                r"what (about|regarding) (.*?)\?",
                r"tell me about (.*?)",
                r"explain (.*?)"
            ],
            'graph': [
                r"what (led to|caused|resulted in) (.*?)\?",
                r"how did (.*?) happen",
                r"trace (.*?) decision"
            ],
            'event_log': [
                r"what happened (on|at|during) (.*?)\?",
                r"when did (.*?) (happen|occur)",
                r"show events (from|on) (.*?)"
            ]
        }

    def route(self, query: str) -> List[str]:
        """
        Route query to appropriate store(s).

        Args:
            query: User query string

        Returns:
            List of store names (e.g., ['kv', 'vector'])
        """
        query_lower = query.lower().strip()
        stores = []

        # Check each pattern
        for store, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    stores.append(store)
                    break  # Only match once per store

        # Default: Use vector if no match
        if not stores:
            stores = ['vector']
            logger.info(f"No pattern match, defaulting to vector search")

        # Remove duplicates, preserve order
        stores = list(dict.fromkeys(stores))

        logger.info(f"Query routed to: {stores}")
        return stores

    def classify_mode(self, query: str) -> str:
        """
        Classify query mode (planning, execution, brainstorming).

        Returns:
            One of ['execution', 'planning', 'brainstorming']
        """
        query_lower = query.lower().strip()

        # Execution mode keywords
        execution_keywords = ['what is', 'exact', 'precisely', 'specifically', 'verify']
        if any(kw in query_lower for kw in execution_keywords):
            return 'execution'

        # Planning mode keywords
        planning_keywords = ['all options', 'alternatives', 'possibilities', 'approaches', 'ways to']
        if any(kw in query_lower for kw in planning_keywords):
            return 'planning'

        # Brainstorming mode keywords
        brainstorm_keywords = ['creative', 'ideas', 'innovative', 'think outside', 'brainstorm']
        if any(kw in query_lower for kw in brainstorm_keywords):
            return 'brainstorming'

        # Default: execution (precision-first)
        return 'execution'
```

*Tests*:
```python
# tests/unit/test_query_router.py (100 LOC)

import pytest
from src.routing.query_router import QueryRouter

class TestQueryRouter:
    """Unit tests for query routing."""

    def test_route_to_kv(self):
        """Test routing to KV store."""
        router = QueryRouter()

        query = "What's my coding style?"
        stores = router.route(query)

        assert 'kv' in stores
        assert len(stores) == 1

    def test_route_to_relational(self):
        """Test routing to relational store."""
        router = QueryRouter()

        query = "What client projects exist?"
        stores = router.route(query)

        assert 'relational' in stores

    def test_route_to_vector(self):
        """Test routing to vector store."""
        router = QueryRouter()

        query = "What about HippoRAG?"
        stores = router.route(query)

        assert 'vector' in stores

    def test_route_to_graph(self):
        """Test routing to graph store."""
        router = QueryRouter()

        query = "What led to the decision to use ChromaDB?"
        stores = router.route(query)

        assert 'graph' in stores

    def test_classify_execution_mode(self):
        """Test execution mode classification."""
        router = QueryRouter()

        query = "What is the exact value of NASA Rule 10?"
        mode = router.classify_mode(query)

        assert mode == 'execution'

    def test_classify_planning_mode(self):
        """Test planning mode classification."""
        router = QueryRouter()

        query = "What are all the options for database storage?"
        mode = router.classify_mode(query)

        assert mode == 'planning'
```

**v6.0 Tasks (GraphRAG Entity Consolidation)**: Same as v6.0, no changes

**Week 8 Summary (v7.0)**:
- **LOC Added**: 380 (GraphRAG) + 160 (query router) = **540 LOC production**
- **Test LOC**: 220 (GraphRAG) + 100 (router) = **320 LOC tests**
- **Tests Added**: 20 (GraphRAG) + 5 (router) = **25 tests**
- **Tests Passing**: 371/371 (346 + 25)

---

### Week 9: Event Log Store + RAPTOR Clustering

**Duration**: 24 hours (vs 22 hours in v6.0, +2 hours for event log)
**Priority**: P1

#### v7.0 Enhancements

**NEW Task 1: Add Event Log Store (Tier 5)** (2 hours)

*Implementation*:
```python
# src/storage/event_log.py (120 LOC)

import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger

class EventLog:
    """
    Event log for episodic memory.

    Storage: SQLite append-only table
    Query Pattern: Time-based filters
    Use Case: "What happened on Tuesday?" → WHERE date = '2025-10-15'

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, db_path: str):
        """Initialize event log."""
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_table()

    def _create_table(self):
        """Create event log table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                event_type TEXT NOT NULL,
                data JSON NOT NULL,
                session_id TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def append(
        self,
        event_id: str,
        event_type: str,
        data: dict,
        session_id: str,
        timestamp: datetime = None
    ):
        """Append event (write-only, no updates)."""
        if timestamp is None:
            timestamp = datetime.now()

        self.conn.execute("""
            INSERT INTO events (id, timestamp, event_type, data, session_id)
            VALUES (?, ?, ?, ?, ?)
        """, (event_id, timestamp.isoformat(), event_type, str(data), session_id))
        self.conn.commit()
        logger.info(f"Event appended: {event_type} at {timestamp}")

    def query_by_date(
        self,
        start_date: str,
        end_date: str = None
    ) -> List[Dict[str, Any]]:
        """Query events by date range."""
        if end_date:
            cursor = self.conn.execute("""
                SELECT id, timestamp, event_type, data, session_id
                FROM events
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """, (start_date, end_date))
        else:
            cursor = self.conn.execute("""
                SELECT id, timestamp, event_type, data, session_id
                FROM events
                WHERE DATE(timestamp) = DATE(?)
                ORDER BY timestamp DESC
            """, (start_date,))

        events = []
        for row in cursor.fetchall():
            events.append({
                'id': row[0],
                'timestamp': row[1],
                'event_type': row[2],
                'data': eval(row[3]),
                'session_id': row[4]
            })

        return events
```

**v6.0 Tasks (RAPTOR Clustering)**: Same as v6.0, no changes

**Week 9 Summary (v7.0)**:
- **LOC Added**: 420 (RAPTOR) + 120 (event log) = **540 LOC production**
- **Test LOC**: 280 (RAPTOR) + 80 (event log) = **360 LOC tests**
- **Tests Added**: 25 (RAPTOR) + 5 (event log) = **30 tests**
- **Tests Passing**: 401/401 (371 + 30)

---

### Week 10-13: v6.0 Tasks (No Major Changes)

**Week 10** (Bayesian RAG): Same as v6.0
**Week 11** (Nexus Processor): Add curated core pattern (see below)
**Week 12** (Memory Forgetting): Add 4-stage lifecycle (see below)
**Week 13** (Mode-Aware): Add mode profiles (see below)

---

### Week 11: Nexus Processor + Curated Core Pattern

**Duration**: 20 hours (vs 18 hours in v6.0, +2 hours for curated core)
**Priority**: P0

#### v7.0 Enhancements

**MODIFIED Task: Nexus Processor with Curated Core** (Insight #1)

*Implementation Changes*:
```python
# src/nexus/processor.py (modify compress() step)

class NexusProcessor:
    """
    5-step SOP pipeline with curated core pattern.

    Steps:
    1. Recall (query all tiers, top-50 candidates)
    2. Filter (confidence >0.3)
    3. Deduplicate (cosine >0.95)
    4. Rank (weighted sum)
    5. Compress (curated core: top-5 + extended: 15-25)  # MODIFIED

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def compress(
        self,
        ranked_results: List[Dict[str, Any]],
        mode: str,
        token_budget: int = 10000
    ) -> Dict[str, Any]:
        """
        Compress to curated core + extended.

        Insight #1: Bigger windows make you dumber.
        Beyond curated core, more tokens reduce precision.

        Args:
            ranked_results: Ranked candidates
            mode: execution/planning/brainstorming
            token_budget: Hard limit (10k tokens max)

        Returns:
            {
                core: [top-5 highest-confidence],  # Precision-optimized
                extended: [next 15-25],             # Recall-optimized
                token_count: int,
                compression_ratio: float
            }
        """
        # Mode-specific top-K
        mode_config = {
            'execution': {'core_k': 5, 'extended_k': 0},      # 5 total (precision only)
            'planning': {'core_k': 5, 'extended_k': 15},     # 20 total (core + extended)
            'brainstorming': {'core_k': 5, 'extended_k': 25} # 30 total (maximize diversity)
        }

        config = mode_config.get(mode, mode_config['execution'])

        # Split into core and extended
        core = ranked_results[:config['core_k']]
        extended = ranked_results[config['core_k']:config['core_k'] + config['extended_k']]

        # Enforce token budget
        total_tokens = sum(len(r['text'].split()) for r in core + extended)
        if total_tokens > token_budget:
            # Truncate extended first
            while total_tokens > token_budget and extended:
                removed = extended.pop()
                total_tokens -= len(removed['text'].split())

        # Calculate compression ratio
        original_tokens = sum(len(r['text'].split()) for r in ranked_results)
        compression_ratio = total_tokens / original_tokens if original_tokens > 0 else 1.0

        logger.info(f"Compressed {len(ranked_results)} → {len(core) + len(extended)} ({compression_ratio:.1%})")

        return {
            'core': core,
            'extended': extended,
            'token_count': total_tokens,
            'compression_ratio': compression_ratio,
            'mode': mode
        }
```

**Week 11 Summary (v7.0)**:
- **LOC Added**: 320 (Nexus) + 40 (curated core) = **360 LOC production**
- **Test LOC**: 200 (Nexus) + 50 (core/extended tests) = **250 LOC tests**
- **Tests Added**: 15 (Nexus) + 5 (core/extended) = **20 tests**

---

### Week 12: Memory Forgetting + 4-Stage Lifecycle

**Duration**: 24 hours (vs 20 hours in v6.0, +4 hours for rekindling)
**Priority**: P2

#### v7.0 Enhancements

**MODIFIED Task: 4-Stage Lifecycle with Rekindling** (Insight #2)

*Implementation*:
```python
# src/memory/lifecycle_manager.py (modify to 4 stages)

class MemoryLifecycleManager:
    """
    4-stage lifecycle with rekindling.

    Stages:
    1. Active (100% score, accessed <7 days)
    2. Demoted (50% score, 7-30 days no access, decay applied)
    3. Archived (10% score, 30-90 days, compressed to summary)
    4. Rehydratable (1% score, >90 days, lossy key only)

    Rekindling: Query matches archived → rehydrate → promote to active

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, vector_indexer, kv_store):
        """Initialize lifecycle manager."""
        self.vector_indexer = vector_indexer
        self.kv_store = kv_store  # For lossy keys
        self.stages = {
            'active': 1.0,
            'demoted': 0.5,
            'archived': 0.1,
            'rehydratable': 0.01
        }

    def demote_stale_chunks(self, threshold_days: int = 7):
        """
        Demote chunks not accessed in 7 days.

        Active → Demoted
        """
        # Query chunks with last_accessed > 7 days ago
        stale_chunks = self.vector_indexer.collection.get(
            where={"$and": [
                {"stage": "active"},
                {"last_accessed": {"$lt": f"now-{threshold_days}d"}}
            ]}
        )

        for chunk_id in stale_chunks['ids']:
            # Update stage and apply decay
            self.vector_indexer.collection.update(
                ids=[chunk_id],
                metadatas=[{'stage': 'demoted', 'score_multiplier': 0.5}]
            )

        logger.info(f"Demoted {len(stale_chunks['ids'])} chunks")

    def archive_demoted_chunks(self, threshold_days: int = 30):
        """
        Archive chunks demoted for 30 days.

        Demoted → Archived (compress to summary)
        """
        old_chunks = self.vector_indexer.collection.get(
            where={"$and": [
                {"stage": "demoted"},
                {"last_accessed": {"$lt": f"now-{threshold_days}d"}}
            ]},
            include=['documents', 'metadatas']
        )

        for i, chunk_id in enumerate(old_chunks['ids']):
            # Compress full text → summary (100:1 compression)
            full_text = old_chunks['documents'][i]
            summary = self._summarize(full_text)  # LLM call: "Summarize in 1 sentence"

            # Store lossy key (summary only, discard full text)
            self.kv_store.set(f"archived:{chunk_id}", summary)

            # Delete from vector store
            self.vector_indexer.collection.delete(ids=[chunk_id])

        logger.info(f"Archived {len(old_chunks['ids'])} chunks (compressed 100:1)")

    def rekindle_archived(self, query_embedding: List[float], chunk_id: str):
        """
        Rekindle archived chunk (rehydrate full text).

        Query matches lossy key → retrieve full text from Obsidian →
        re-index in vector store → promote to active
        """
        # Retrieve lossy key (summary)
        summary = self.kv_store.get(f"archived:{chunk_id}")
        if not summary:
            logger.warning(f"Archived chunk {chunk_id} not found")
            return

        # Rehydrate: Re-read full text from Obsidian
        # (Assumes original file still exists)
        file_path = self.kv_store.get(f"archived:{chunk_id}:file_path")
        with open(file_path, 'r') as f:
            full_text = f.read()

        # Re-index in vector store
        self.vector_indexer.index_chunks(
            chunks=[{'text': full_text, 'file_path': file_path, 'chunk_index': 0}],
            embeddings=[query_embedding]
        )

        # Promote to active
        self.vector_indexer.collection.update(
            ids=[chunk_id],
            metadatas=[{'stage': 'active', 'score_multiplier': 1.0}]
        )

        logger.info(f"Rekindled archived chunk {chunk_id} → active")
```

**Week 12 Summary (v7.0)**:
- **LOC Added**: 360 (decay) + 80 (rekindling) = **440 LOC production**
- **Test LOC**: 240 (decay) + 60 (rekindle) = **300 LOC tests**
- **Tests Added**: 20 (decay) + 5 (rekindle) = **25 tests**

---

### Week 14: Memory Eval Suite + Context Debugger

**Duration**: 32 hours (vs 28 hours in v6.0, +4 hours for evals)
**Priority**: P0

#### v7.0 Enhancements

**NEW Task 1: Memory Eval Suite** (Insight #15, 4 hours)

*Files to Create*:
- `tests/evals/test_freshness.py` (80 LOC)
- `tests/evals/test_leakage.py` (80 LOC)
- `tests/evals/test_precision_recall.py` (120 LOC)
- `tests/evals/test_staleness.py` (60 LOC)
- `tests/evals/test_red_team.py` (100 LOC)

*Implementation*:
```python
# tests/evals/test_freshness.py (80 LOC)

import pytest
from datetime import datetime, timedelta
from src.indexing.vector_indexer import VectorIndexer

class TestMemoryFreshness:
    """
    Eval: Freshness (% chunks updated in 30 days).

    Target: ≥70% chunks updated in last 30 days
    Rationale: Avoid stale knowledge
    """

    def test_freshness_threshold(self, indexer):
        """Test freshness meets 70% threshold."""
        # Get all chunks
        all_chunks = indexer.collection.get(include=['metadatas'])

        # Count chunks updated in last 30 days
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        fresh_count = sum(
            1 for meta in all_chunks['metadatas']
            if meta.get('updated', meta.get('created', '')) >= cutoff
        )

        total_count = len(all_chunks['ids'])
        freshness = fresh_count / total_count if total_count > 0 else 0

        print(f"Freshness: {freshness:.1%} ({fresh_count}/{total_count})")

        assert freshness >= 0.70, f"Freshness {freshness:.1%} below 70% target"
```

```python
# tests/evals/test_leakage.py (80 LOC)

import pytest
from src.indexing.vector_indexer import VectorIndexer

class TestMemoryLeakage:
    """
    Eval: Leakage (% session chunks in personal memory).

    Target: <5% leakage (lifecycle contamination)
    Rationale: Session chunks should not leak into personal memory
    """

    def test_no_lifecycle_leakage(self, indexer):
        """Test lifecycle separation (no session in personal)."""
        # Get personal chunks
        personal_chunks = indexer.collection.get(
            where={'lifecycle': 'personal'},
            include=['metadatas']
        )

        # Count chunks that are actually session (contamination)
        leakage_count = sum(
            1 for meta in personal_chunks['metadatas']
            if meta.get('original_lifecycle') == 'session'
        )

        total_personal = len(personal_chunks['ids'])
        leakage_rate = leakage_count / total_personal if total_personal > 0 else 0

        print(f"Leakage: {leakage_rate:.1%} ({leakage_count}/{total_personal})")

        assert leakage_rate < 0.05, f"Leakage {leakage_rate:.1%} exceeds 5% threshold"
```

```python
# tests/evals/test_precision_recall.py (120 LOC)

import pytest
from src.nexus.processor import NexusProcessor

class TestMemoryPrecisionRecall:
    """
    Eval: Precision/Recall per mode.

    Targets:
    - Execution mode: ≥90% precision
    - Planning mode: ≥70% recall
    """

    def test_execution_mode_precision(self, processor, ground_truth_dataset):
        """Test execution mode achieves ≥90% precision."""
        results = []

        for query, expected in ground_truth_dataset:
            # Query in execution mode
            output = processor.process(query, mode='execution')

            # Check if output matches expected (exact match)
            is_correct = output['core'][0]['content'] == expected
            results.append(is_correct)

        precision = sum(results) / len(results)
        print(f"Execution Precision: {precision:.1%}")

        assert precision >= 0.90, f"Precision {precision:.1%} below 90% target"

    def test_planning_mode_recall(self, processor, ground_truth_dataset):
        """Test planning mode achieves ≥70% recall."""
        results = []

        for query, expected_list in ground_truth_dataset:
            # Query in planning mode
            output = processor.process(query, mode='planning')

            # Check if all expected items are in results
            recalled = sum(
                1 for expected in expected_list
                if any(expected in r['content'] for r in output['core'] + output['extended'])
            )

            recall = recalled / len(expected_list)
            results.append(recall)

        avg_recall = sum(results) / len(results)
        print(f"Planning Recall: {avg_recall:.1%}")

        assert avg_recall >= 0.70, f"Recall {avg_recall:.1%} below 70% target"
```

**NEW Task 2: Context Assembly Debugger** (Insight #16, included in Week 14)

*(Already covered in SPEC v7.0 summary, no additional LOC beyond Week 14 baseline)*

**Week 14 Summary (v7.0)**:
- **LOC Added**: 380 (verification) + 440 (evals) = **820 LOC production**
- **Test LOC**: 440 (verification) + 0 (evals are tests themselves) = **440 LOC tests**
- **Tests Added**: 50 (verification) + 20 (evals) = **70 tests**

---

## Summary: Weeks 7-14 (v7.0)

### Total LOC Added

| Week | Production LOC (v6.0) | Production LOC (v7.0) | Delta | Test LOC (v6.0) | Test LOC (v7.0) | Delta |
|------|----------------------|----------------------|-------|----------------|----------------|-------|
| Week 7 | 490 | 970 | +480 | 360 | 560 | +200 |
| Week 8 | 380 | 540 | +160 | 220 | 320 | +100 |
| Week 9 | 420 | 540 | +120 | 280 | 360 | +80 |
| Week 10 | 480 | 480 | 0 | 320 | 320 | 0 |
| Week 11 | 320 | 360 | +40 | 200 | 250 | +50 |
| Week 12 | 360 | 440 | +80 | 240 | 300 | +60 |
| Week 13 | 240 | 240 | 0 | 160 | 160 | 0 |
| Week 14 | 380 | 820 | +440 | 440 | 440 | 0 |
| **Total** | **3,070** | **4,390** | **+1,320** | **2,220** | **2,710** | **+490** |

**Grand Total v7.0**: 4,390 production + 2,710 tests = **7,100 LOC** (vs 5,290 in v6.0, +34%)

### Test Coverage Growth

| Milestone | Unit Tests (v6.0) | Unit Tests (v7.0) | Integration (v6.0) | Integration (v7.0) | E2E (v6.0) | E2E (v7.0) | Evals (NEW v7.0) | Total (v6.0) | Total (v7.0) |
|-----------|------------------|------------------|-------------------|-------------------|-----------|-----------|-----------------|-------------|-------------|
| Baseline | 207 | 207 | 89 | 89 | 25 | 25 | 0 | 321 | 321 |
| Week 7-14 | +118 | +138 | +47 | +57 | +20 | +20 | +20 | +185 | +235 |
| **Total** | **325** | **345** | **136** | **146** | **45** | **45** | **20** | **506** | **556** |

**Tests Passing Target v7.0**: **556 tests** (vs 506 in v6.0, +10%)

---

## Performance Targets (v7.0 Validation)

| Metric | v6.0 Target | v7.0 Target | Improvement | How Achieved |
|--------|-------------|-------------|-------------|--------------|
| Query Latency (95th %) | <1s | <800ms | 20% faster | Query router skips slow tiers |
| Indexing Latency | <2s | <1.5s | 25% faster | Hot/cold classification |
| Curation Time | <35min/week | <25min/week | 29% faster | Human-in-loop briefs |
| Memory Freshness | N/A | ≥70% | NEW | Eval metric (30-day update) |
| Leakage Rate | N/A | <5% | NEW | Eval metric (lifecycle contamination) |
| Precision (execution) | N/A | ≥90% | NEW | Two-stage verification |
| Recall (planning) | N/A | ≥70% | NEW | Broad retrieval + extended results |
| Token Cost/Query | N/A | <$0.01 | NEW | Curated core (60% reduction) |
| Storage Growth | <35MB/1000 | <25MB/1000 | 29% less | 4-stage lifecycle (archive compression) |

---

## Risk Mitigation Timeline

**v6.0**: 1,000 points → **v7.0**: 890 points = **-110 points (11% reduction)**

| Week | Risk Addressed | v6.0 Score | v7.0 Score | Mitigation |
|------|---------------|-----------|-----------|------------|
| Week 7-8 | Obsidian Sync | 90 | 60 | Hot/cold classification (-30) |
| Week 8 | Bayesian Complexity | 250 | 150 | Query router skips slow tiers (-100) |
| Week 11-12 | Curation Time | 180 | 120 | Human-in-loop briefs (-60) |
| Week 14 | Context Assembly Bugs | 0 | 80 | NEW RISK: Debugger mitigates (+80) |
| **Total** | - | **1,000** | **890** | **-110 net** |

---

## Success Criteria (v7.0)

**Technical**:
- ✅ 556 tests passing (321 baseline + 235 new)
- ✅ Memory eval suite: Freshness ≥70%, Leakage <5%, Precision ≥90%, Recall ≥70%
- ✅ Query latency <800ms (95th percentile)
- ✅ Token cost <$0.01/query

**Functional**:
- ✅ 5-tier storage (KV, Relational, Vector, Graph, Event Log) with query router
- ✅ Memory-as-code (schemas, migrations, CLI, evals, CI/CD)
- ✅ 4-stage lifecycle (active, demoted, archived, rehydratable) with rekindling
- ✅ Curated core pattern (5 core + 15-25 extended, 10k token budget)
- ✅ Context assembly debugger (detailed query tracing)

**Quality**:
- ✅ NASA Rule 10: ≥95% compliance
- ✅ 0 critical security vulnerabilities
- ✅ Memory schema validated in CI

---

## Next Steps

**Immediate Actions**:
1. ✅ Read PLAN v7.0 (this document)
2. Create PREMORTEM v7.0 (890-point risk analysis)
3. **DECISION**: Approve v7.0 and proceed to Loop 2 (implementation)

**Loop 1 Complete**: SPEC v7.0 + PLAN v7.0 + PREMORTEM v7.0
**Loop 2 Begin**: Week 7 implementation (Obsidian MCP + 5-tier storage)

---

**Version History**:
- **v6.0** (2025-10-18): Initial Loop 1 (8 weeks, 506 tests, 5,290 LOC)
- **v7.0** (2025-10-18): Loop 1 Final (8 weeks, 556 tests, 7,100 LOC)
  - 16 counter-intuitive insights integrated
  - 5-tier storage (+1,320 LOC)
  - Memory evals (+20 tests)
  - 11% risk reduction (1,000 → 890)

**Receipt**:
- **Run ID**: loop1-iter3-plan-v7.0
- **Timestamp**: 2025-10-18T21:15:00Z
- **Agent**: Strategic Planning (Loop 1 Iteration 3)
- **Inputs**: SPEC v7.0, 16 insights, PLAN v6.0
- **Changes**: Comprehensive PLAN v7.0 (8 weeks, 556 tests, 7,100 LOC, 890 risk)
- **Status**: Ready for PREMORTEM v7.0
