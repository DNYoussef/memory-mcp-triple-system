# Memory MCP Triple System - Verification Plan

**Generated**: 2025-11-25
**Updated**: 2025-11-25 (Post Phase 0)
**Purpose**: Double-check all discovered errors are real using playbooks/skills

---

## POST-PHASE 0 VERIFICATION STATUS

```
+-------------------------------------------------------------------+
|                   VERIFICATION STATUS UPDATE                       |
+-------------------------------------------------------------------+
| Phase 5 (Architecture):  COMPLETE - A1.* verified and RESOLVED     |
| Remaining Phases:        1-4 (Dependencies, Mocks, Algorithms, Int)|
| Total Verifications:     40 -> 34 (6 completed in Phase 0)         |
+-------------------------------------------------------------------+
```

---

## VERIFICATION METHODOLOGY

Each discovered issue will be verified using a specific playbook/skill combination:

```
Issue Category          -> Verification Playbook        -> Verification Skill
================================================================================
Mock Code (B1.*)       -> code-quality-audit           -> functionality-audit
TODO Items (B2.*)      -> code-quality-audit           -> clarity-linter
Algorithm Bugs (B3.*)  -> testing-quality              -> smart-bug-fix
Config Issues (D3.*)   -> codebase-onboarding          -> Explore agent
Integration (C*.*)     -> comprehensive-review         -> code-review-assistant
Architecture (A*.*)    -> research-quick-investigation -> interactive-planner
Dependencies (D1.*)    -> testing-quality              -> tester agent
```

---

## PHASE 1: DEPENDENCY VERIFICATION (Immediate - 30 minutes)

### V1.1: Verify Missing tenacity Dependency (D1.1)
**Playbook**: testing-quality
**Skill**: functionality-audit
**Agent**: tester

```bash
# Verification Steps:
1. Check pyproject.toml for tenacity
   Grep("tenacity", path="pyproject.toml")

2. Check if import fails
   python -c "from src.indexing.vector_indexer import VectorIndexer"

3. Confirm crash behavior
   python -m src.mcp.stdio_server
```

**Expected Result**: Import error for tenacity confirms D1.1 is REAL

### V1.2: Verify Collection Mismatch (D3.2)
**Playbook**: codebase-onboarding
**Skill**: Explore agent

```bash
# Verification Steps:
1. Find collection names in config
   Grep("collection", path="config/memory-mcp.yaml")

2. Find collection names in code
   Grep("collection", path="src/", glob="*.py")

3. Compare values
   # config: memory_embeddings
   # code: memory_chunks
```

**Expected Result**: Mismatch confirms D3.2 is REAL

---

## PHASE 2: MOCK CODE VERIFICATION (2-4 hours)

### V2.1: Verify Obsidian Client Mock (B1.1)
**Playbook**: code-quality-audit
**Skill**: functionality-audit
**Agent**: code-analyzer

```python
# Verification Steps:
1. Read src/mcp/obsidian_client.py lines 150-174
2. Check for actual API calls vs fake returns
3. Trace _sync_file() method execution path

# Verification Code:
def verify_obsidian_mock():
    # Check if VectorIndexer.index() is ever called
    indexer_calls = Grep("indexer.index", path="src/mcp/obsidian_client.py")
    # Check if only len(content)//500 is returned
    mock_pattern = Grep("max.*len.*content.*500", path="src/mcp/obsidian_client.py")
    return len(indexer_calls) == 0 and len(mock_pattern) > 0
```

**Expected Result**: No real indexing calls confirms B1.1 is REAL

### V2.2: Verify Query Replay Mock (B1.3-B1.5)
**Playbook**: code-quality-audit
**Skill**: clarity-linter
**Agent**: reviewer

```python
# Verification Steps:
1. Read src/debug/query_replay.py lines 160-219
2. Check if NexusProcessor is actually invoked
3. Verify context dicts are empty

# Key Patterns to Find:
- "return {}" in context methods
- "Week 8" or "Week 11" comments
- "TODO" markers
```

**Expected Result**: Empty returns and TODO markers confirm B1.3-B1.5 are REAL

### V2.3: Verify Bayesian Random CPD (B1.6)
**Playbook**: code-quality-audit
**Skill**: functionality-audit
**Agent**: code-analyzer

```python
# Verification Steps:
1. Read src/bayesian/network_builder.py lines 145-156
2. Find random.choice usage
3. Verify no historical data source

# Pattern:
import random
row[node] = random.choice(states)  # <-- MOCK
```

**Expected Result**: random.choice for CPD confirms B1.6 is REAL

---

## PHASE 3: ALGORITHM BUG VERIFICATION (2-4 hours)

### V3.1: Verify Distance-to-Similarity Bug (B3.1)
**Playbook**: smart-bug-fix
**Skill**: tester
**Agent**: tester

```python
# Verification Steps:
1. Read src/mcp/tools/vector_search.py line 140
2. Check if 1.0 - distance handles L2 > 1.0
3. Test with actual ChromaDB distances

# Test Code:
def test_similarity_overflow():
    # L2 distance can be > 1.0 for non-normalized vectors
    distance = 1.5  # Valid L2 distance
    similarity = 1.0 - distance  # Returns -0.5 (INVALID)
    assert similarity < 0, "Bug confirmed: negative similarity possible"
```

**Expected Result**: Negative similarity for L2>1 confirms B3.1 is REAL

### V3.2: Verify Jaccard vs Cosine (B3.2)
**Playbook**: code-quality-audit
**Skill**: code-review-assistant
**Agent**: reviewer

```python
# Verification Steps:
1. Read src/nexus/processor.py lines 587-590
2. Find "Jaccard" comment
3. Verify embedding similarity not used

# Pattern:
# Jaccard similarity as fast approximation
# (For production, use embeddings for better accuracy)
```

**Expected Result**: Jaccard comment confirms B3.2 is REAL (but may be intentional)

### V3.3: Verify Entity Extraction Bug (B3.3)
**Playbook**: smart-bug-fix
**Skill**: functionality-audit
**Agent**: tester

```python
# Verification Steps:
1. Read src/nexus/processor.py line 529
2. Verify first-word-only logic

# Pattern:
query_entity = query.split()[0] if query.split() else "unknown"
# Query: "What is the capital of France?"
# Entity: "What" (WRONG - should be "France" or "capital")
```

**Expected Result**: First-word extraction confirms B3.3 is REAL

---

## PHASE 4: INTEGRATION VERIFICATION (4-8 hours)

### V4.1: Verify MCP Tools Limited (C1.1-C1.6)
**Playbook**: comprehensive-review
**Skill**: Explore agent
**Agent**: code-analyzer

```python
# Verification Steps:
1. List all tools in stdio_server.py
2. Compare against expected tools

# Expected Tools (per docs):
EXPECTED = ["vector_search", "memory_store", "graph_query",
            "bayesian_inference", "entity_extraction", "hipporag_retrieve"]

# Actual Tools (in code):
Grep("@tool", path="src/mcp/stdio_server.py")
```

**Expected Result**: Only 2 tools found confirms C1.1-C1.6 are REAL

### V4.2: Verify Hooks Missing (C2.1-C2.5)
**Playbook**: codebase-onboarding
**Skill**: Explore agent
**Agent**: researcher

```bash
# Verification Steps:
1. Check if directory exists
   ls -la ~/.claude/hooks/12fa/

2. Check for specific files
   cat ~/.claude/hooks/12fa/memory-mcp-tagging-protocol.js
```

**Expected Result**: Directory/files not found confirms C2.* are REAL

### V4.3: Verify Runtime Wiring (C3.1-C3.7)
**Playbook**: comprehensive-review
**Skill**: code-review-assistant
**Agent**: code-analyzer

```python
# Verification Steps:
1. Search for NexusProcessor instantiation in server code
   Grep("NexusProcessor", path="src/mcp/")

2. Search for ObsidianClient import in non-test code
   Grep("from.*obsidian_client import", path="src/", exclude="tests/")

3. Trace what actually runs on vector_search MCP call
```

**Expected Result**: No instantiation/imports confirm C3.* are REAL

---

## PHASE 5: ARCHITECTURE VERIFICATION [COMPLETE]

### V5.1: Verify Architecture Conflict (A1.1-A1.5) [COMPLETE]
**Status**: VERIFIED AND RESOLVED
**Completed**: 2025-11-25
**Resolution**: Unified Architecture adopted (ADR-001)

```
VERIFICATION RESULTS:
[x] A1.1 - THREE competing architectures -> VERIFIED, RESOLVED
[x] A1.2 - V/G/B in code -> VERIFIED, KEPT as core
[x] A1.3 - Time-Based in docs -> VERIFIED, MERGED as metadata
[x] A1.4 - P/E/S in Obsidian doc -> VERIFIED, MERGED as metadata
[x] A1.5 - Backend/frontend mismatch -> VERIFIED, RESOLVED

DOCUMENTS CREATED:
- docs/ARCHITECTURE-DECISION.md (ADR-001)
- docs/ARCHITECTURE.md (canonical reference)

DOCUMENTS ARCHIVED:
- docs/archive/MEMORY-MCP-TRUE-ARCHITECTURE-ARCHIVED.md
- docs/archive/MEMORY-MCP-OBSIDIAN-INTEGRATION-ARCHIVED.md
```

### V5.2: Verify Documentation Drift (A2.1-A2.3) [PARTIALLY COMPLETE]
**Status**: A2.1 VERIFIED AND FIXED
**Remaining**: A2.2, A2.3

```
VERIFICATION RESULTS:
[x] A2.1 - Banner drift -> VERIFIED, FIXED in src/__init__.py (v1.1.0)
[ ] A2.2 - Test references to Qdrant -> OPEN (Phase 5 target)
[ ] A2.3 - Week N references -> OPEN (Phase 5 target)

CODE CHANGES:
- src/__init__.py banner: Qdrant/Neo4j -> Chroma/NetworkX
- Version bumped to 1.1.0
```

---

## VERIFICATION EXECUTION PLAN

### Parallel Verification Tracks

```
TRACK A: Dependencies & Config (1 developer, 2 hours)
=====================================================
V1.1 -> V1.2 -> V4.2 -> D2.* (hardcoded paths)

TRACK B: Mock Code (1 developer, 4 hours)
=========================================
V2.1 -> V2.2 -> V2.3 -> B1.7-B1.9

TRACK C: Algorithms & Bugs (1 developer, 4 hours)
=================================================
V3.1 -> V3.2 -> V3.3 -> B3.4

TRACK D: Integration & Architecture (1 developer, 6 hours)
==========================================================
V4.1 -> V4.3 -> V5.1 -> V5.2
```

### Verification Output Format

Each verification produces a report:

```json
{
  "issue_id": "B1.1",
  "issue_description": "Obsidian client mock sync",
  "verification_method": "functionality-audit",
  "status": "CONFIRMED" | "FALSE_POSITIVE" | "PARTIAL",
  "evidence": [
    "Line 167: chunks = max(1, len(content) // 500)",
    "No VectorIndexer.index() calls found"
  ],
  "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "remediation_required": true,
  "blocked_by": [],
  "blocks": ["C3.2"]
}
```

---

## AUTOMATED VERIFICATION SCRIPT

```python
# scripts/verify_issues.py
"""
Automated verification of all discovered issues.
Run: python scripts/verify_issues.py --output docs/VERIFICATION-RESULTS.json
"""

VERIFICATIONS = [
    # Phase 1: Dependencies
    {"id": "D1.1", "check": "tenacity_missing", "method": "grep_pyproject"},
    {"id": "D3.2", "check": "collection_mismatch", "method": "compare_config_code"},

    # Phase 2: Mock Code
    {"id": "B1.1", "check": "obsidian_mock", "method": "trace_sync_file"},
    {"id": "B1.3", "check": "query_replay_mock", "method": "find_empty_returns"},
    {"id": "B1.6", "check": "bayesian_random", "method": "find_random_choice"},

    # Phase 3: Algorithms
    {"id": "B3.1", "check": "similarity_overflow", "method": "test_l2_distance"},
    {"id": "B3.3", "check": "entity_first_word", "method": "test_entity_extraction"},

    # Phase 4: Integration
    {"id": "C1.1", "check": "mcp_tools_count", "method": "count_tool_decorators"},
    {"id": "C2.1", "check": "hooks_missing", "method": "check_directory_exists"},
    {"id": "C3.1", "check": "nexus_not_used", "method": "grep_instantiation"},

    # Phase 5: Architecture
    {"id": "A1.1", "check": "arch_conflict", "method": "compare_docs_code"},
    {"id": "A2.1", "check": "doc_drift", "method": "compare_banner_imports"},
]

def run_all_verifications():
    results = []
    for v in VERIFICATIONS:
        result = verify(v)
        results.append(result)
    return results
```

---

## EXPECTED VERIFICATION TIMELINE

| Phase | Duration | Issues Verified | Developers |
|-------|----------|-----------------|------------|
| Phase 1 | 30 min | D1.1, D3.2 | 1 |
| Phase 2 | 4 hours | B1.1-B1.9 | 1 |
| Phase 3 | 4 hours | B3.1-B3.4 | 1 |
| Phase 4 | 6 hours | C1.*, C2.*, C3.* | 1 |
| Phase 5 | 4 hours | A1.*, A2.* | 1 |
| **Total** | **18.5 hours** | **40 issues** | **1-4 parallel** |

With 4 developers in parallel: **~6 hours to verify all issues**

---

## NEXT: See REMEDIATION-PLAN.md for fix implementation
