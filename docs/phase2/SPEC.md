# Phase 2: Runtime Wiring - Specification

## Overview

Wire the NexusProcessor 5-step SOP pipeline into the MCP servers and create the hooks infrastructure for metadata tagging protocol (WHO/WHEN/PROJECT/WHY).

## Requirements

### Functional Requirements

1. **C3.1 - NexusProcessor Integration**
   - Wire NexusProcessor into stdio_server.py
   - Enable all 3 retrieval tiers (Vector + HippoRAG + Bayesian)
   - Route MCP tool calls through Nexus 5-step SOP
   - Support mode-aware retrieval (execution/planning/brainstorming)

2. **C2.1 - Hooks Directory Structure**
   - Create ~/.claude/hooks/12fa/ directory
   - Follow Claude Code hooks convention

3. **C2.2 - Memory Tagging Protocol Hook**
   - Create memory-mcp-tagging-protocol.js
   - Implement taggedMemoryStore() function
   - Auto-inject WHO/WHEN/PROJECT/WHY metadata

4. **C2.3 - Agent Access Control Hook**
   - Create agent-mcp-access-control.js
   - Define agent permissions for MCP tools
   - Implement access validation

5. **C2.4 - WHO/WHEN/PROJECT/WHY Tagging**
   - WHO: Agent name, category, capabilities
   - WHEN: ISO timestamp, Unix timestamp, readable format
   - PROJECT: Project identifier from env or default
   - WHY: Intent classification (implementation, bugfix, etc.)

6. **C2.5 - Hooks Integration Validation**
   - Test hooks with real MCP calls
   - Verify metadata appears in stored memories

### Non-Functional Requirements

- Performance: <50ms overhead for tagging
- Compatibility: Windows + Unix paths
- Reliability: Graceful fallback if hooks unavailable

## Constraints

- Technical: Must integrate with existing src/nexus/processor.py
- Technical: Hooks must be JavaScript (Claude Code convention)
- Technical: No breaking changes to existing vector_search tool
- Architecture: Follow Unified Architecture (ADR-001)

## Success Criteria

1. MCP server uses NexusProcessor for all queries
2. All 3 tiers (V/G/B) are queried on each search
3. Hooks directory exists with functional hooks
4. Memory stores include WHO/WHEN/PROJECT/WHY metadata
5. No regression in existing functionality

## Out of Scope

- Phase 3 mock code replacement
- Phase 4 new MCP tools (graph_query, etc.)
- Bayesian tier fixes (mock CPD acceptable for Phase 2)

## Dependencies

- Phase 0: Architecture Decision (COMPLETE)
- Phase 1: Foundation Fixes (COMPLETE)
- Existing: NexusProcessor in src/nexus/processor.py
- Existing: VectorIndexer in src/indexing/vector_indexer.py
