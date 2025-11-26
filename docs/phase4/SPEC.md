# Phase 4: Feature Completion - Specification

## Overview

Complete missing MCP tools and implement remaining features to achieve full system functionality.

## Requirements

### Functional Requirements

1. **C1.2-C1.6 - Missing MCP Tools**
   - C1.2: graph_query - HippoRAG multi-hop query tool
   - C1.3: bayesian_inference - Probabilistic query tool
   - C1.4: entity_extraction - NER from text tool
   - C1.5: hipporag_retrieve - Full HippoRAG pipeline tool
   - C1.6: Mode detection, routing, event log tools

2. **B2.3-B2.5 - Query Replay** (Deferred - requires Week 11 infrastructure)
   - Context reconstruction from memory/KV/session stores
   - Query re-run with trace generation

3. **B1.7 - RAPTOR LLM Summaries** (Deferred - requires LLM integration)
   - Replace first 200 chars with actual LLM summary

### Priority Order

1. **C1.2-C1.5** - Core MCP tools (enables full 3-tier retrieval)
2. C1.6 - Auxiliary tools (mode detection, event log)
3. B1.7/B2.3-5 - Deferred to Phase 5 (require external dependencies)

## Constraints

- Must follow stdio MCP protocol
- Must integrate with existing NexusProcessor
- Must follow NASA Rule 10 (functions <=60 LOC)

## Success Criteria

1. All 4 core tools exposed via MCP
2. Tools work with NexusSearchTool
3. Integration tests pass
