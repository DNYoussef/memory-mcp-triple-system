# Memory MCP Triple System: Implementation Plan

## Executive Summary

**Project Objective**: Build a production-ready, self-hosted personal memory system combining Vector RAG, GraphRAG, and Bayesian probabilistic reasoning with MCP protocol integration for seamless LLM access and Obsidian knowledge management.

**Timeline**: 12 weeks (3 phases of 4 weeks each)

**Key Milestones**:
1. **Week 4**: Vector RAG MVP (functional search system)
2. **Week 8**: GraphRAG enhancement (multi-hop reasoning)
3. **Week 12**: Bayesian integration (probabilistic queries)

**Success Criteria**:
- All 3 reasoning layers functional and integrated
- MCP-compatible (works with Claude Desktop, other LLM clients)
- Obsidian auto-sync operational
- Retrieval recall@10 ≥85%, multi-hop accuracy ≥85%
- Query latency: vector <200ms, graph <500ms, multi-hop <2s
- Self-hosted, privacy-preserving, no external dependencies
- 200+ tests passing, ≥90% coverage
- Complete documentation and deployment guide

---

## Phase 1: MVP - Vector RAG (Weeks 1-4)

### Week 1: Foundation Setup

**Objective**: Local development environment + Obsidian integration

**Tasks**:
1. **Environment Setup** (4 hours)
   - Install Docker Desktop + Docker Compose
   - Install Python 3.11 (virtual environment)
   - Install Node.js 18+ (for potential TypeScript MCP server)
   - Configure git repository structure

2. **Qdrant Vector Database** (3 hours)
   - Create `docker/docker-compose.yml` with Qdrant service
   - Configure Qdrant on port 6333
   - Set up persistent storage volume
   - Test connection via Python client

3. **Obsidian Vault Structure** (2 hours)
   - Create vault at `~/Documents/Memory-Vault`
   - Design folder structure (People/, Projects/, Notes/, Journal/)
   - Configure frontmatter templates (tags, dates, projects)
   - Create sample documents (10-20 notes)

4. **Sentence-Transformers Setup** (3 hours)
   - Install `sentence-transformers` package
   - Download `all-MiniLM-L6-v2` model (local, free)
   - Test embedding generation (384-dimensional vectors)
   - Benchmark embedding speed (target: 50+ docs/sec)

5. **File Watcher Implementation** (4 hours)
   - Create `src/utils/file_watcher.py` (watchdog library)
   - Monitor Obsidian vault for changes (create/update/delete)
   - Trigger reindexing on file events
   - Implement debouncing (wait 2s for batch changes)
   - Add logging (structured logs with loguru)

6. **Initial Testing** (4 hours)
   - Unit tests for file watcher
   - Integration test: modify note → verify reindex
   - Docker health checks
   - Document setup process

**Agents Needed**:
- `devops` (Docker, deployment)
- `backend-dev` (database setup)
- `coder` (file watcher, utilities)

**Deliverables**:
- `docker/docker-compose.yml` (Qdrant service)
- `~/Documents/Memory-Vault/` (Obsidian vault with 20+ notes)
- `src/utils/file_watcher.py` (watchdog-based monitor)
- `src/utils/config.py` (configuration management)
- `src/indexing/embedding_pipeline.py` (Sentence-Transformers)
- `tests/unit/test_file_watcher.py`
- `docs/SETUP.md` (installation guide)

**Success Criteria**:
- ✅ Qdrant running on localhost:6333 (verified via HTTP API)
- ✅ File changes in Obsidian trigger reindexing (<5s latency)
- ✅ Embeddings generated for 20+ test documents
- ✅ All unit tests passing (≥3 tests)
- ✅ Setup documentation complete

**Rollback**: If Docker fails, use Qdrant cloud (free tier) temporarily

---

### Week 2: Vector Search & MCP Server

**Objective**: Basic vector search + MCP protocol integration

**Tasks**:
1. **Semantic Chunking Pipeline** (6 hours)
   - Implement Max-Min Semantic Chunker (AMI-based)
   - Parse markdown (extract frontmatter, headers, paragraphs)
   - Create 200-500 token chunks with semantic boundaries
   - Preserve metadata (source file, section, tags)
   - Test on long documents (2000+ words)

2. **Vector Indexing** (5 hours)
   - Create `src/indexing/vector_indexer.py`
   - Index chunks into Qdrant collections
   - Store metadata (file path, tags, dates, project IDs)
   - Implement batch indexing (50 chunks/batch)
   - Add incremental updates (delta indexing)

3. **MCP Server Implementation** (6 hours)
   - Choose Python MCP SDK (easier integration)
   - Create `src/mcp/server.py` (FastMCP or custom)
   - Implement `vector_search` tool:
     - Input: query string, top_k (default: 10), filters (optional)
     - Output: ranked chunks with metadata and scores
   - Add `list_collections` tool (diagnostic)
   - Handle errors gracefully (return structured errors)

4. **Claude Desktop Integration** (3 hours)
   - Create MCP config file (`~/.claude/mcp_config.json`)
   - Test connection via Claude Desktop
   - Verify tool availability in Claude UI
   - Test sample queries ("What projects did I work on last month?")

5. **Testing & Debugging** (4 hours)
   - Unit tests for chunking (verify AMI score >0.85)
   - Unit tests for indexing (verify metadata preservation)
   - Integration test: index 50 docs → search → verify results
   - MCP tool tests (mock client)

**Agents Needed**:
- `coder` (chunking, indexing)
- `backend-dev` (MCP server)
- `tester` (test suite)

**Deliverables**:
- `src/chunking/semantic_chunker.py` (Max-Min algorithm)
- `src/indexing/vector_indexer.py` (Qdrant client)
- `src/mcp/server.py` (MCP protocol server)
- `src/mcp/tools/vector_search.py` (tool implementation)
- `config/mcp_config.json` (Claude Desktop config)
- `tests/unit/test_semantic_chunker.py` (≥5 tests)
- `tests/unit/test_vector_indexer.py` (≥5 tests)
- `tests/integration/test_mcp_server.py` (≥3 tests)
- `docs/MCP_INTEGRATION.md` (usage guide)

**Success Criteria**:
- ✅ Semantic chunking produces 200-500 token chunks (AMI >0.85)
- ✅ Vector search returns top-10 relevant chunks (manual validation)
- ✅ MCP tools visible in Claude Desktop UI
- ✅ Search latency <200ms (p95)
- ✅ All tests passing (≥13 tests total)

**Rollback**: If MCP integration fails, provide REST API fallback

---

### Week 3: Query Interface & Retrieval

**Objective**: Production-quality retrieval with reranking and hybrid search

**Tasks**:
1. **Hybrid Search Implementation** (5 hours)
   - Combine vector similarity + keyword (BM25)
   - Use Qdrant's built-in keyword indexing (if available) or tantivy
   - Implement Reciprocal Rank Fusion (RRF) for combining scores
   - Test on 50 queries (measure recall improvement)

2. **Reranking Layer** (5 hours)
   - Choose reranker: Cross-Encoder (free, local) or Cohere (API)
   - Start with `cross-encoder/ms-marco-MiniLM-L-6-v2`
   - Rerank top-20 candidates to top-10
   - Measure latency impact (target: +50ms max)
   - Implement caching for repeated queries

3. **Query Expansion** (4 hours)
   - Extract synonyms from WordNet (nltk)
   - Expand key terms (max 3 synonyms per term)
   - Test on ambiguous queries ("Python" → "Python programming language")
   - Measure precision/recall impact

4. **Metadata Filtering** (3 hours)
   - Implement date range filters (last week, last month)
   - Implement tag filters (AND/OR logic)
   - Implement project filters (exact match)
   - Test complex filters ("Python notes from last month tagged 'ML'")

5. **Web UI for Testing** (5 hours)
   - Create simple FastAPI backend (`src/api/query_endpoint.py`)
   - Create React frontend (search box, results display)
   - Show metadata (file, tags, dates, relevance score)
   - Add filtering controls (date picker, tag selector)
   - Deploy locally (localhost:3000)

6. **Performance Optimization** (2 hours)
   - Profile slow queries (py-spy or cProfile)
   - Optimize Qdrant index parameters (HNSW tuning)
   - Add connection pooling
   - Implement batch query API

**Agents Needed**:
- `coder` (hybrid search, query expansion)
- `backend-dev` (API endpoint)
- `frontend-dev` (React UI)
- `performance-engineer` (optimization)

**Deliverables**:
- `src/retrieval/hybrid_search.py` (vector + keyword + RRF)
- `src/retrieval/reranker.py` (Cross-Encoder integration)
- `src/retrieval/query_expander.py` (synonym expansion)
- `src/retrieval/metadata_filter.py` (filtering logic)
- `src/api/query_endpoint.py` (FastAPI REST API)
- `src/web/app.tsx` (React UI)
- `tests/unit/test_hybrid_search.py` (≥5 tests)
- `tests/integration/test_query_flow.py` (≥5 tests)
- `docs/API_REFERENCE.md` (REST API docs)

**Success Criteria**:
- ✅ Hybrid search improves recall by 10-15% vs vector-only
- ✅ Reranking improves top-3 precision by 20%+
- ✅ Query latency <200ms (p95, including reranking)
- ✅ Metadata filters work correctly (100% accuracy on test cases)
- ✅ Web UI functional and responsive
- ✅ All tests passing (≥10 new tests)

**Rollback**: If reranking is too slow, skip it (use hybrid search only)

---

### Week 4: Testing & Documentation

**Objective**: Production-ready MVP with comprehensive tests

**Tasks**:
1. **Unit Test Expansion** (6 hours)
   - Achieve ≥90% coverage for all modules
   - Test edge cases (empty queries, malformed input)
   - Test error handling (Qdrant down, invalid API calls)
   - Use pytest fixtures for common test data
   - Generate coverage report (pytest-cov)

2. **Integration Testing** (6 hours)
   - E2E test: Add note → index → search → verify retrieval
   - E2E test: Update note → reindex → verify changes reflected
   - E2E test: Delete note → remove from index → verify absence
   - Test MCP server integration (mock Claude client)
   - Test concurrent queries (10 parallel requests)

3. **Performance Benchmarking** (4 hours)
   - Measure indexing throughput (docs/min)
   - Measure query latency (p50, p95, p99)
   - Measure QPS (queries per second)
   - Stress test with 1000+ documents
   - Document bottlenecks and optimization opportunities

4. **User Documentation** (4 hours)
   - `docs/USER_GUIDE.md` (setup, daily workflow)
   - `docs/API_REFERENCE.md` (REST + MCP APIs)
   - `docs/ARCHITECTURE.md` (system overview)
   - `docs/TROUBLESHOOTING.md` (common issues)
   - Include screenshots and examples

5. **Local Deployment** (3 hours)
   - Update `docker-compose.yml` with all services
   - Create setup script (`scripts/setup.sh`)
   - Test fresh install on clean machine
   - Document environment variables
   - Create `.env.example` file

6. **User Acceptance Testing** (3 hours)
   - Daily use for 3 days (dogfooding)
   - Track query success rate
   - Identify usability issues
   - Gather qualitative feedback
   - Iterate on UX improvements

**Agents Needed**:
- `tester` (test suite, benchmarks)
- `docs-writer` (documentation)
- `devops` (deployment)
- `reviewer` (code review, quality checks)

**Deliverables**:
- `tests/unit/` (50+ unit tests, ≥90% coverage)
- `tests/integration/` (10+ integration tests)
- `tests/e2e/test_complete_flow.py` (≥3 E2E tests)
- `docs/USER_GUIDE.md` (2000+ words)
- `docs/API_REFERENCE.md` (complete API docs)
- `docs/ARCHITECTURE.md` (system diagram + explanations)
- `docs/TROUBLESHOOTING.md` (FAQ + common errors)
- `scripts/setup.sh` (one-command setup)
- `benchmarks/performance_report.md` (QPS, latency, throughput)

**Success Criteria**:
- ✅ ≥90% test coverage (measured via pytest-cov)
- ✅ All 60+ tests passing
- ✅ Indexing throughput ≥100 docs/min
- ✅ Query latency <200ms (p95)
- ✅ QPS ≥10 (single process)
- ✅ Documentation complete and clear
- ✅ Fresh install works on clean machine
- ✅ MVP functional for daily use (3 days dogfooding successful)

**Phase 1 Deliverable**: Functional Vector RAG system with MCP integration, ready for daily use

**Rollback Strategy**: If Phase 1 fails, fallback to Obsidian native search only

---

## Phase 2: GraphRAG Enhancement (Weeks 5-8)

### Week 5: Knowledge Graph Construction

**Objective**: Neo4j setup + entity/relationship extraction

**Tasks**:
1. **Neo4j Installation** (3 hours)
   - Add Neo4j to `docker-compose.yml`
   - Configure ports (7474 HTTP, 7687 Bolt)
   - Set up persistent storage volume
   - Configure authentication (strong password)
   - Test connection via Python driver (neo4j-python-driver)

2. **Graph Schema Design** (4 hours)
   - Define node types: `Person`, `Project`, `Note`, `Tag`, `Concept`
   - Define relationships: `MENTIONS`, `WORKS_ON`, `RELATED_TO`, `TAGGED_WITH`
   - Add properties (name, date, metadata)
   - Create uniqueness constraints (Cypher)
   - Design indexing strategy (full-text search on names)

3. **Entity Extraction** (6 hours)
   - Install spaCy + en_core_web_trf (transformer-based NER)
   - Install Relik for advanced entity linking
   - Extract entities from markdown: People, Organizations, Locations
   - Deduplicate entities (fuzzy matching via fuzzywuzzy)
   - Store entity metadata (first mention, frequency)

4. **Relationship Extraction** (5 hours)
   - Parse markdown for explicit links (`[[Person]]` syntax)
   - Extract co-occurrence relationships (entities in same chunk)
   - Extract temporal relationships (event mentions)
   - Use dependency parsing (spaCy) for implicit relationships
   - Store relationship metadata (source note, confidence score)

5. **Graph Population** (4 hours)
   - Create `scripts/populate_graph.py`
   - Batch insert nodes (50+ nodes/batch)
   - Batch insert relationships (100+ edges/batch)
   - Populate from existing Obsidian vault (100+ notes)
   - Validate graph structure (check dangling nodes)

6. **Testing** (4 hours)
   - Unit tests for entity extraction (precision/recall)
   - Unit tests for relationship extraction
   - Integration test: note → graph → verify nodes/edges
   - Test graph queries (Cypher)

**Agents Needed**:
- `backend-dev` (Neo4j setup, graph APIs)
- `ml-developer` (entity/relationship extraction)
- `coder` (graph population scripts)

**Deliverables**:
- `docker/docker-compose.yml` (updated with Neo4j)
- `src/graph/entity_extractor.py` (spaCy + Relik)
- `src/graph/relationship_mapper.py` (link + co-occurrence extraction)
- `src/graph/schema.cypher` (graph schema definition)
- `src/graph/graph_indexer.py` (Neo4j client)
- `scripts/populate_graph.py` (batch population)
- `tests/unit/test_entity_extractor.py` (≥5 tests)
- `tests/unit/test_relationship_mapper.py` (≥5 tests)
- `tests/integration/test_graph_population.py` (≥3 tests)
- `docs/GRAPH_SCHEMA.md` (schema documentation)

**Success Criteria**:
- ✅ Neo4j running on localhost:7474 (verified via browser)
- ✅ Graph populated with 100+ nodes, 200+ relationships
- ✅ Entity extraction precision ≥80% (manual validation on 50 entities)
- ✅ Relationship extraction recall ≥70% (manual validation)
- ✅ All tests passing (≥13 new tests)

**Rollback**: If graph extraction quality is poor, use manual tagging only (defer ML extraction to Phase 3)

---

### Week 6: HippoRAG Integration

**Objective**: Multi-hop reasoning with HippoRAG

**Tasks**:
1. **HippoRAG Installation** (2 hours)
   - Install `hipporag` package (pip install hipporag)
   - Review HippoRAG API documentation
   - Configure for Neo4j backend
   - Test basic queries

2. **Multi-Hop Query Decomposition** (6 hours)
   - Implement query parser (extract entities + relationships)
   - Decompose complex queries into subqueries
   - Example: "What projects involve people I met last month?" →
     - Subquery 1: Find people met last month
     - Subquery 2: Find projects mentioning those people
   - Use LLM (local Llama or Claude API) for query understanding
   - Validate decomposition accuracy

3. **Personalized PageRank (PPR) Retrieval** (5 hours)
   - Implement PPR algorithm in Neo4j (Cypher query)
   - Seed PPR from query entities
   - Rank nodes by PPR score
   - Retrieve top-k nodes + connected subgraph
   - Optimize for speed (index critical properties)

4. **HippoRAG Engine Integration** (5 hours)
   - Create `src/graph/hipporag_engine.py`
   - Integrate with existing vector retrieval
   - Implement hybrid ranking (vector score + PPR score)
   - Add graph context to retrieved chunks
   - Return structured results (chunks + graph paths)

5. **Complex Query Testing** (4 hours)
   - Create test suite for multi-hop queries (3+ hops)
   - Examples:
     - "Projects related to Python and data science"
     - "People working on ML who I met in Q1 2024"
     - "Notes about research papers cited by Project X"
   - Measure accuracy vs vector-only baseline
   - Measure latency (target: <2s for 3-hop queries)

6. **Performance Optimization** (4 hours)
   - Profile slow queries (Neo4j query profiler)
   - Add graph indexes (node properties, relationship types)
   - Optimize PPR computation (limit depth, breadth)
   - Implement query result caching (Redis)

**Agents Needed**:
- `ml-developer` (HippoRAG, query decomposition)
- `coder` (integration, PPR implementation)
- `performance-engineer` (optimization)

**Deliverables**:
- `src/graph/hipporag_engine.py` (HippoRAG integration)
- `src/retrieval/multihop_query.py` (query decomposition)
- `src/graph/ppr_ranker.py` (Personalized PageRank)
- `src/retrieval/hybrid_ranker.py` (vector + PPR fusion)
- `tests/unit/test_query_decomposition.py` (≥5 tests)
- `tests/unit/test_ppr_ranker.py` (≥5 tests)
- `tests/integration/test_multihop_queries.py` (≥5 tests)
- `benchmarks/multihop_accuracy.md` (accuracy report)

**Success Criteria**:
- ✅ Multi-hop queries work correctly (manual validation on 20 queries)
- ✅ 20% accuracy improvement over vector-only (measured on test set)
- ✅ 10x faster than iterative RAG (baseline: 20s → target: 2s)
- ✅ Query latency <2s (p95 for 3-hop queries)
- ✅ All tests passing (≥15 new tests)

**Rollback**: If HippoRAG is too complex, use basic graph traversal (Cypher-only, no PPR)

---

### Week 7: Graph Visualization & MCP Tools

**Objective**: Visual graph exploration + MCP integration

**Tasks**:
1. **Graph Visualization Setup** (6 hours)
   - Choose visualization: D3.js force-directed graph or Neo4j Bloom
   - If D3.js: Create React component for graph rendering
   - If Neo4j Bloom: Configure Bloom perspective (node styling)
   - Implement zoom, pan, node selection
   - Color-code node types (Person=blue, Project=green, Note=yellow)

2. **Interactive Graph Explorer** (5 hours)
   - Click node → show details panel (properties, connected nodes)
   - Click edge → show relationship metadata
   - Search nodes by name/type
   - Filter graph by date range, tags
   - Export subgraph as image (PNG/SVG)

3. **MCP Graph Tools** (6 hours)
   - Implement `graph_query` tool:
     - Input: Cypher query or natural language
     - Output: Graph structure (nodes + edges) as JSON
   - Implement `entity_search` tool:
     - Input: entity name
     - Output: entity details + connected entities
   - Implement `graph_path` tool:
     - Input: source entity, target entity
     - Output: shortest path(s) in graph
   - Add error handling (invalid queries, missing entities)

4. **Graph-Based Context Expansion** (4 hours)
   - For retrieved chunks, expand to include:
     - Connected entities (1-hop neighbors)
     - Related notes (via shared entities)
     - Temporal context (notes from same time period)
   - Return expanded context to LLM
   - Measure impact on answer quality

5. **Claude Desktop Testing** (3 hours)
   - Update MCP config with new graph tools
   - Test queries: "Show me the graph of Project X"
   - Test queries: "Find path from Person A to Project B"
   - Verify graph results render correctly
   - Test context expansion impact on Claude responses

6. **Documentation** (2 hours)
   - Update `docs/MCP_INTEGRATION.md` with graph tools
   - Create `docs/GRAPH_VISUALIZATION.md` (usage guide)
   - Add example queries and screenshots

**Agents Needed**:
- `frontend-dev` (graph visualization UI)
- `backend-dev` (MCP tools, API)
- `coder` (context expansion logic)

**Deliverables**:
- `src/web/components/GraphVisualization.tsx` (D3.js graph)
- `src/mcp/tools/graph_query.py` (Cypher execution)
- `src/mcp/tools/entity_search.py` (entity lookup)
- `src/mcp/tools/graph_path.py` (pathfinding)
- `src/retrieval/context_expander.py` (graph-based expansion)
- `tests/unit/test_graph_tools.py` (≥5 tests)
- `tests/integration/test_mcp_graph.py` (≥3 tests)
- `docs/GRAPH_VISUALIZATION.md` (visualization guide)

**Success Criteria**:
- ✅ Graph visualizes relationships clearly (manual UX validation)
- ✅ MCP graph tools accessible in Claude Desktop
- ✅ Context expansion improves answer quality (qualitative evaluation)
- ✅ Graph queries execute in <500ms (p95)
- ✅ All tests passing (≥8 new tests)

**Rollback**: If visualization is too complex, use Neo4j Browser (built-in Neo4j UI)

---

### Week 8: Testing & Refinement

**Objective**: Production-ready GraphRAG system

**Tasks**:
1. **E2E Test Suite** (6 hours)
   - E2E test: Add note with entities → graph populated → query via graph
   - E2E test: Multi-hop query → verify correct results
   - E2E test: Update note → graph updated → verify changes
   - E2E test: MCP graph tools → verify JSON output
   - Test error scenarios (Neo4j down, malformed queries)

2. **Performance Optimization** (6 hours)
   - Profile graph queries (Neo4j query profiler)
   - Add compound indexes (multi-property indexes)
   - Optimize PPR computation (reduce graph depth)
   - Implement query result caching (Redis with TTL)
   - Measure performance improvements

3. **Graph Quality Validation** (4 hours)
   - Manual audit of 100 extracted entities (precision/recall)
   - Manual audit of 50 relationships (correctness)
   - Fix common extraction errors (false positives, false negatives)
   - Retrain/tune entity extraction if needed

4. **Documentation Updates** (3 hours)
   - Update `docs/ARCHITECTURE.md` with graph layer
   - Update `docs/API_REFERENCE.md` with graph endpoints
   - Update `docs/USER_GUIDE.md` with graph queries
   - Create `docs/GRAPH_MAINTENANCE.md` (how to fix bad extractions)

5. **User Acceptance Testing** (4 hours)
   - Dogfood for 3 days (daily use with graph queries)
   - Test multi-hop queries on real data
   - Identify edge cases and bugs
   - Gather qualitative feedback
   - Iterate on UX improvements

6. **Deployment** (3 hours)
   - Update `docker-compose.yml` with optimized settings
   - Update setup script for Phase 2
   - Test fresh install with graph layer
   - Document backup/restore procedures (Neo4j dumps)

**Agents Needed**:
- `tester` (E2E tests, quality validation)
- `performance-engineer` (optimization)
- `docs-writer` (documentation updates)
- `devops` (deployment)

**Deliverables**:
- `tests/e2e/test_graph_flow.py` (≥5 E2E tests)
- `benchmarks/graph_performance.md` (before/after optimization)
- `docs/ARCHITECTURE.md` (updated with graph layer)
- `docs/API_REFERENCE.md` (updated with graph APIs)
- `docs/GRAPH_MAINTENANCE.md` (graph curation guide)
- `scripts/backup_graph.sh` (Neo4j dump script)
- `scripts/restore_graph.sh` (Neo4j restore script)

**Success Criteria**:
- ✅ Graph query latency <500ms (p95, optimized)
- ✅ Multi-hop accuracy ≥85% (measured on 50-query test set)
- ✅ Entity extraction precision ≥85% (manual validation)
- ✅ All tests passing (≥5 new E2E tests)
- ✅ Documentation complete and updated
- ✅ Phase 2 deployable and stable

**Phase 2 Deliverable**: GraphRAG system with multi-hop reasoning and visual exploration

**Rollback Strategy**: If Phase 2 fails, continue using Phase 1 (vector-only RAG)

---

## Phase 3: Bayesian Networks (Weeks 9-12)

### Week 9: Probabilistic Reasoning Setup

**Objective**: Bayesian network for uncertainty quantification

**Tasks**:
1. **Bayesian Framework Selection** (3 hours)
   - Evaluate: PyMC (full Bayesian), pgmpy (belief networks), custom (minimal)
   - Choose pgmpy for interpretability and speed
   - Install pgmpy and dependencies
   - Review pgmpy API and examples

2. **Belief Network Design** (6 hours)
   - Design DAG: Query → Retrieval → Relevance
   - Add nodes: QueryClarity, EntityMatch, ChunkRelevance, GraphPath
   - Define conditional probability tables (CPTs)
   - Example CPT: P(ChunkRelevance | QueryClarity, EntityMatch)
   - Use expert knowledge + data-driven priors

3. **Uncertainty Scoring** (5 hours)
   - Implement `src/bayesian/uncertainty_scorer.py`
   - For each retrieved chunk:
     - Compute P(Relevant | evidence)
     - Compute confidence interval (Bayesian credible interval)
   - Aggregate across multiple chunks (weighted average)
   - Return probability distribution over relevance

4. **Probabilistic Graph Traversal** (5 hours)
   - Modify graph queries to return probability scores
   - Compute P(PathRelevant | entities, relationships)
   - Use graph structure for priors (shorter paths = higher prior)
   - Combine with vector/graph scores

5. **Ambiguous Query Testing** (4 hours)
   - Create test set of ambiguous queries (20 queries)
   - Examples: "Python" (language or snake?), "Apple" (fruit or company?)
   - Measure: does system return probability distribution?
   - Measure: are confidence intervals calibrated? (manual validation)

6. **Integration with Existing Retrieval** (3 hours)
   - Add uncertainty scores to vector search results
   - Add uncertainty scores to graph search results
   - Update MCP tools to return confidence intervals
   - Test integration with Claude Desktop

**Agents Needed**:
- `ml-developer` (Bayesian network design, CPT estimation)
- `researcher` (literature review for priors)
- `coder` (integration with retrieval)

**Deliverables**:
- `src/bayesian/belief_network.py` (pgmpy network definition)
- `src/bayesian/uncertainty_scorer.py` (Bayesian inference)
- `src/bayesian/cpt_estimator.py` (CPT data-driven tuning)
- `src/retrieval/probabilistic_retriever.py` (integration)
- `tests/unit/test_belief_network.py` (≥5 tests)
- `tests/unit/test_uncertainty_scorer.py` (≥5 tests)
- `tests/integration/test_probabilistic_queries.py` (≥3 tests)
- `docs/BAYESIAN_NETWORK.md` (network design documentation)

**Success Criteria**:
- ✅ Uncertainty scores computed for all retrieved chunks
- ✅ Ambiguous queries return probability distributions (100% on test set)
- ✅ Confidence intervals calibrated (within 10% on manual validation)
- ✅ Probabilistic queries execute in <300ms (p95, overhead <100ms)
- ✅ All tests passing (≥13 new tests)

**Rollback**: If Bayesian network is too slow, use simple heuristic scoring (fallback to rule-based uncertainty)

---

### Week 10: Neurosymbolic Integration

**Objective**: GNN-RBN neurosymbolic reasoning

**Tasks**:
1. **GNN-RBN Research** (4 hours)
   - Review GNN-RBN papers (neurosymbolic reasoning)
   - Identify key algorithms (belief propagation on GNNs)
   - Determine feasibility for implementation
   - Create implementation plan

2. **GNN Implementation** (6 hours)
   - Choose GNN library: PyTorch Geometric (PyG)
   - Implement GNN over Neo4j graph
   - Train GNN embeddings (node features from text embeddings)
   - Use pre-trained model or train on small dataset (100-200 nodes)
   - Validate GNN embeddings (clustering, similarity)

3. **RBN Integration** (5 hours)
   - Combine GNN node embeddings with Bayesian network
   - Use GNN outputs as evidence for Bayesian inference
   - Implement belief propagation over graph
   - Test on multi-hop queries with uncertainty

4. **Neurosymbolic Query Engine** (5 hours)
   - Create `src/bayesian/gnn_rbn.py`
   - Implement query pipeline:
     - Step 1: GNN forward pass (get node embeddings)
     - Step 2: Bayesian inference (compute probabilities)
     - Step 3: Rank results by probability
   - Return results with confidence scores

5. **MCP Tool for Probabilistic Queries** (3 hours)
   - Implement `probabilistic_query` MCP tool:
     - Input: query string
     - Output: ranked results + probability distribution
   - Add `explain_uncertainty` tool (show CPT reasoning)
   - Test with Claude Desktop

6. **Complex Reasoning Testing** (3 hours)
   - Test on complex queries (3+ entities, temporal constraints)
   - Examples:
     - "Who is most likely to know about X given they worked on Y?"
     - "What's the probability that Project A relates to Concept B?"
   - Measure accuracy vs baseline (vector-only, graph-only)
   - Measure calibration (are 70% confidence predictions correct 70% of the time?)

**Agents Needed**:
- `ml-developer` (GNN-RBN implementation)
- `researcher` (neurosymbolic reasoning research)
- `coder` (integration, MCP tools)

**Deliverables**:
- `src/bayesian/gnn_rbn.py` (GNN + Bayesian integration)
- `src/bayesian/gnn_embeddings.py` (PyG GNN implementation)
- `src/mcp/tools/probabilistic_query.py` (MCP tool)
- `src/mcp/tools/explain_uncertainty.py` (explainability tool)
- `tests/unit/test_gnn_rbn.py` (≥5 tests)
- `tests/integration/test_neurosymbolic.py` (≥3 tests)
- `docs/NEUROSYMBOLIC.md` (GNN-RBN documentation)

**Success Criteria**:
- ✅ Neurosymbolic reasoning improves accuracy (≥10% on complex queries)
- ✅ Probabilistic queries return calibrated confidence scores
- ✅ MCP tools functional in Claude Desktop
- ✅ Query latency <1s (p95, including GNN inference)
- ✅ All tests passing (≥8 new tests)

**Rollback**: If GNN-RBN is too complex, skip and use Bayesian-only (Week 9 deliverables)

---

### Week 11: Context Fusion & Agentic Routing

**Objective**: Intelligent routing between 3 layers (vector, graph, Bayesian)

**Tasks**:
1. **Context Fusion Implementation** (5 hours)
   - Implement Reciprocal Rank Fusion (RRF) for 3 layers
   - Implement weighted averaging (weights per layer)
   - Tune weights on validation set (20% of data)
   - Test on 50 queries (measure improvement)

2. **Agentic Router Design** (6 hours)
   - Use LLM to classify query complexity:
     - Simple (vector-only): factual, single-entity queries
     - Medium (graph): multi-entity, relationship queries
     - Complex (Bayesian): ambiguous, uncertain queries
   - Use local Llama 3.1 8B or Claude API (caching)
   - Implement routing logic in `src/routing/agentic_router.py`
   - Fallback: if LLM fails, use rule-based heuristics

3. **Query Complexity Analyzer** (4 hours)
   - Implement rule-based heuristics (fallback for LLM):
     - Count entities (≥2 → graph)
     - Detect ambiguity (multiple word senses → Bayesian)
     - Detect temporal constraints (dates → graph)
   - Combine with LLM routing (LLM takes precedence)
   - Log routing decisions for debugging

4. **Caching Layer** (5 hours)
   - Install Redis (add to `docker-compose.yml`)
   - Implement query result caching:
     - Key: query hash
     - Value: results JSON
     - TTL: 1 hour (configurable)
   - Implement embedding caching (reduce recomputation)
   - Implement graph path caching

5. **Performance Optimization** (4 hours)
   - Profile full query pipeline (vector → graph → Bayesian → fusion)
   - Parallelize independent operations (vector + graph in parallel)
   - Optimize cache hit rate (measure before/after)
   - Target: 50% latency reduction via caching

6. **Testing & Validation** (4 hours)
   - Test routing accuracy (does router choose correct layer?)
   - Test context fusion (does RRF improve results?)
   - Test caching (verify cache hits, correctness)
   - Benchmark performance (latency, QPS, cache hit rate)

**Agents Needed**:
- `ml-developer` (agentic router, query complexity)
- `performance-engineer` (optimization, caching)
- `coder` (context fusion, integration)

**Deliverables**:
- `src/fusion/context_aggregator.py` (RRF + weighted averaging)
- `src/routing/agentic_router.py` (LLM + rule-based routing)
- `src/routing/query_complexity.py` (complexity analyzer)
- `src/caching/redis_cache.py` (Redis integration)
- `docker/docker-compose.yml` (updated with Redis)
- `tests/unit/test_context_fusion.py` (≥5 tests)
- `tests/unit/test_agentic_router.py` (≥5 tests)
- `tests/integration/test_full_pipeline.py` (≥3 tests)
- `benchmarks/caching_performance.md` (cache impact report)

**Success Criteria**:
- ✅ Router selects optimal layer (≥80% accuracy on test set)
- ✅ Context fusion improves answer quality (≥10% on qualitative eval)
- ✅ Caching reduces latency by ≥50% (on repeated queries)
- ✅ Cache hit rate ≥30% (on realistic query distribution)
- ✅ All tests passing (≥13 new tests)

**Rollback**: If agentic routing fails, use rule-based routing only (simpler heuristics)

---

### Week 12: Final Testing & Production Launch

**Objective**: Production-ready complete system with all 3 layers

**Tasks**:
1. **Complete E2E Test Suite** (6 hours)
   - E2E test: simple query → vector layer → verify results
   - E2E test: multi-hop query → graph layer → verify results
   - E2E test: ambiguous query → Bayesian layer → verify probabilities
   - E2E test: complex query → router → fusion → verify final results
   - E2E test: MCP tools → all layers → verify JSON outputs
   - Test error scenarios (all services down, partial failures)

2. **Performance Benchmarking** (5 hours)
   - Measure QPS (queries per second) for each layer
   - Measure latency (p50, p95, p99) for each layer
   - Measure accuracy (precision, recall, F1) on test set (200 queries)
   - Measure indexing throughput (docs/min)
   - Measure memory usage (Docker containers)
   - Measure storage growth (disk usage per 1000 docs)
   - Compare against targets (see Performance Targets section)

3. **Security Audit** (4 hours)
   - Review authentication (Neo4j, Qdrant passwords)
   - Review secrets management (.env files, not committed)
   - Review input validation (prevent SQL/Cypher injection)
   - Review API rate limiting (prevent abuse)
   - Scan for vulnerabilities (Bandit, Safety)
   - Document security best practices

4. **Final Documentation** (6 hours)
   - `docs/ARCHITECTURE.md` (complete system architecture)
   - `docs/API_REFERENCE.md` (all REST + MCP APIs)
   - `docs/USER_GUIDE.md` (setup, daily workflow, troubleshooting)
   - `docs/DEPLOYMENT.md` (production deployment guide)
   - `docs/MAINTENANCE.md` (backup, monitoring, updates)
   - `README.md` (project overview, quick start)

5. **Production Deployment Preparation** (4 hours)
   - Create production `docker-compose.prod.yml`
   - Configure environment variables (secrets, URLs)
   - Set up health checks (all services)
   - Configure logging (structured logs, log rotation)
   - Configure monitoring (Prometheus + Grafana, optional)
   - Test production deployment on staging server

6. **User Acceptance & Launch** (3 hours)
   - Final dogfooding (7 days of daily use)
   - Gather qualitative feedback (ease of use, accuracy)
   - Fix critical bugs (P0 issues only)
   - Announce launch (personal use or share with team)
   - Monitor for issues (first 48 hours)

**Agents Needed**:
- `tester` (E2E tests, benchmarking)
- `security-manager` (security audit)
- `performance-engineer` (performance validation)
- `docs-writer` (final documentation)
- `devops` (production deployment)
- `reviewer` (final code review)

**Deliverables**:
- `tests/e2e/test_complete_system.py` (≥10 E2E tests)
- `benchmarks/final_performance_report.md` (comprehensive benchmarks)
- `security/audit_report.md` (security findings + mitigations)
- `docs/ARCHITECTURE.md` (complete, 3000+ words)
- `docs/API_REFERENCE.md` (all APIs documented)
- `docs/USER_GUIDE.md` (comprehensive, 4000+ words)
- `docs/DEPLOYMENT.md` (production deployment)
- `docs/MAINTENANCE.md` (operations guide)
- `README.md` (project overview)
- `docker/docker-compose.prod.yml` (production config)

**Success Criteria**:
- ✅ All 3 layers functional and integrated (manual validation)
- ✅ System performance meets targets (see Performance Targets section)
- ✅ Security audit passed (no critical vulnerabilities)
- ✅ All 200+ tests passing (unit + integration + E2E)
- ✅ Documentation complete (15,000+ words total)
- ✅ Production deployment successful (staging → production)
- ✅ User satisfaction high (daily use for 7 days without critical issues)
- ✅ Ready for daily use and/or sharing

**Phase 3 Deliverable**: Complete Memory MCP Triple System, production-ready

**Rollback Strategy**: If Phase 3 fails, continue using Phase 2 (vector + graph RAG)

---

## Performance Targets

| Metric | Target | Rationale | Measurement |
|--------|--------|-----------|-------------|
| **Vector search latency** | <200ms | Interactive UX requirement | p95, single query |
| **Graph query latency** | <500ms | Multi-hop acceptable delay | p95, 3-hop query |
| **Multi-hop query latency** | <2s | Complex reasoning tradeoff | p95, 3+ hop query |
| **Bayesian inference overhead** | <100ms | Additive to retrieval | p95, per query |
| **Retrieval recall@10** | ≥85% | High-quality results | Test set (200 queries) |
| **Multi-hop accuracy** | ≥85% | Graph reasoning quality | Complex query test set (50) |
| **Indexing throughput** | ≥100 docs/min | Real-time Obsidian sync | Batch indexing test |
| **QPS (vector layer)** | ≥10 | Single-process baseline | Apache Bench test |
| **QPS (graph layer)** | ≥5 | Graph query complexity | Apache Bench test |
| **Memory usage** | <2GB RAM | Docker containers total | docker stats |
| **Storage growth** | <10MB/1000 docs | Vector + graph combined | Measure on 1000-doc corpus |
| **Cache hit rate** | ≥30% | Realistic query distribution | Redis stats (1 week) |
| **Entity extraction precision** | ≥85% | Manual validation | 100-entity sample |
| **Relationship extraction recall** | ≥70% | Manual validation | 50-relationship sample |

**Measurement Plan**:
- Unit tests: pytest with coverage report
- Integration tests: full pipeline tests
- Performance: Apache Bench, custom Python scripts
- Accuracy: Manual validation on test sets
- Production: Prometheus + Grafana (optional)

---

## Complete File Tree

```
memory-mcp-triple-system/
├── README.md                          # Project overview, quick start
├── LICENSE                            # MIT or similar
├── .gitignore                         # Exclude .env, __pycache__, etc.
│
├── src/
│   ├── __init__.py
│   │
│   ├── chunking/
│   │   ├── __init__.py
│   │   └── semantic_chunker.py        # Max-Min Semantic Chunker (AMI-based)
│   │
│   ├── indexing/
│   │   ├── __init__.py
│   │   ├── vector_indexer.py          # Qdrant vector indexing
│   │   ├── graph_indexer.py           # Neo4j graph indexing
│   │   └── embedding_pipeline.py      # Sentence-Transformers embeddings
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── hybrid_search.py           # Vector + keyword (BM25) + RRF
│   │   ├── reranker.py                # Cross-Encoder reranking
│   │   ├── query_expander.py          # Synonym expansion (WordNet)
│   │   ├── metadata_filter.py         # Date, tag, project filters
│   │   ├── multihop_query.py          # HippoRAG multi-hop decomposition
│   │   ├── context_expander.py        # Graph-based context expansion
│   │   └── probabilistic_retriever.py # Bayesian uncertainty scoring
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── entity_extractor.py        # spaCy + Relik NER
│   │   ├── relationship_mapper.py     # Link + co-occurrence extraction
│   │   ├── graph_indexer.py           # Neo4j client + batch insert
│   │   ├── hipporag_engine.py         # HippoRAG integration
│   │   ├── ppr_ranker.py              # Personalized PageRank
│   │   └── schema.cypher              # Neo4j schema definition
│   │
│   ├── bayesian/
│   │   ├── __init__.py
│   │   ├── belief_network.py          # pgmpy Bayesian network
│   │   ├── uncertainty_scorer.py      # Bayesian inference for relevance
│   │   ├── cpt_estimator.py           # Conditional Probability Tables
│   │   ├── gnn_embeddings.py          # PyTorch Geometric GNN
│   │   └── gnn_rbn.py                 # GNN-RBN neurosymbolic integration
│   │
│   ├── fusion/
│   │   ├── __init__.py
│   │   └── context_aggregator.py      # RRF + weighted averaging (3 layers)
│   │
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── agentic_router.py          # LLM-based layer selection
│   │   └── query_complexity.py        # Complexity analyzer (heuristics)
│   │
│   ├── caching/
│   │   ├── __init__.py
│   │   └── redis_cache.py             # Redis query + embedding cache
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py                  # MCP protocol server (FastMCP)
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── vector_search.py       # Vector search MCP tool
│   │       ├── graph_query.py         # Cypher query MCP tool
│   │       ├── entity_search.py       # Entity lookup MCP tool
│   │       ├── graph_path.py          # Pathfinding MCP tool
│   │       ├── probabilistic_query.py # Bayesian query MCP tool
│   │       └── explain_uncertainty.py # Explainability MCP tool
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── query_endpoint.py          # FastAPI REST API
│   │
│   ├── web/
│   │   ├── app.tsx                    # React app entry point
│   │   └── components/
│   │       ├── SearchBox.tsx          # Query input component
│   │       ├── ResultsList.tsx        # Search results display
│   │       ├── GraphVisualization.tsx # D3.js force-directed graph
│   │       └── MetadataFilters.tsx    # Date/tag/project filters
│   │
│   └── utils/
│       ├── __init__.py
│       ├── file_watcher.py            # Watchdog file monitor
│       ├── config.py                  # Configuration management
│       └── logger.py                  # Structured logging (loguru)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Pytest fixtures
│   │
│   ├── unit/
│   │   ├── test_semantic_chunker.py
│   │   ├── test_vector_indexer.py
│   │   ├── test_hybrid_search.py
│   │   ├── test_reranker.py
│   │   ├── test_query_expander.py
│   │   ├── test_metadata_filter.py
│   │   ├── test_entity_extractor.py
│   │   ├── test_relationship_mapper.py
│   │   ├── test_graph_indexer.py
│   │   ├── test_hipporag_engine.py
│   │   ├── test_ppr_ranker.py
│   │   ├── test_belief_network.py
│   │   ├── test_uncertainty_scorer.py
│   │   ├── test_gnn_rbn.py
│   │   ├── test_context_fusion.py
│   │   ├── test_agentic_router.py
│   │   └── test_query_complexity.py
│   │
│   ├── integration/
│   │   ├── test_mcp_server.py
│   │   ├── test_query_flow.py
│   │   ├── test_graph_population.py
│   │   ├── test_multihop_queries.py
│   │   ├── test_mcp_graph.py
│   │   ├── test_probabilistic_queries.py
│   │   ├── test_neurosymbolic.py
│   │   └── test_full_pipeline.py
│   │
│   └── e2e/
│       ├── test_complete_flow.py      # Phase 1 E2E
│       ├── test_graph_flow.py         # Phase 2 E2E
│       └── test_complete_system.py    # Phase 3 E2E
│
├── docs/
│   ├── ARCHITECTURE.md                # Complete system architecture
│   ├── USER_GUIDE.md                  # Setup + daily workflow
│   ├── API_REFERENCE.md               # REST + MCP APIs
│   ├── SETUP.md                       # Installation guide
│   ├── MCP_INTEGRATION.md             # MCP tools usage
│   ├── GRAPH_SCHEMA.md                # Neo4j schema docs
│   ├── GRAPH_VISUALIZATION.md         # Graph UI guide
│   ├── BAYESIAN_NETWORK.md            # Bayesian network design
│   ├── NEUROSYMBOLIC.md               # GNN-RBN documentation
│   ├── DEPLOYMENT.md                  # Production deployment
│   ├── MAINTENANCE.md                 # Backup, monitoring, updates
│   ├── TROUBLESHOOTING.md             # Common issues + fixes
│   └── GRAPH_MAINTENANCE.md           # Graph curation guide
│
├── docker/
│   ├── docker-compose.yml             # Development setup
│   ├── docker-compose.prod.yml        # Production setup
│   ├── Dockerfile.api                 # FastAPI + MCP server
│   ├── Dockerfile.web                 # React frontend (optional)
│   └── .env.example                   # Example environment variables
│
├── config/
│   ├── qdrant_config.yaml             # Qdrant settings
│   ├── neo4j_config.yaml              # Neo4j settings
│   ├── mcp_config.json                # MCP server config (for Claude Desktop)
│   └── logging_config.yaml            # Loguru logging settings
│
├── scripts/
│   ├── setup.sh                       # One-command setup
│   ├── populate_graph.py              # Batch graph population
│   ├── backup_graph.sh                # Neo4j dump script
│   ├── restore_graph.sh               # Neo4j restore script
│   ├── benchmark.py                   # Performance benchmarking
│   └── validate_accuracy.py           # Accuracy measurement
│
├── benchmarks/
│   ├── performance_report.md          # Phase 1 performance
│   ├── multihop_accuracy.md           # Phase 2 accuracy
│   ├── graph_performance.md           # Phase 2 optimization
│   ├── caching_performance.md         # Phase 3 caching impact
│   └── final_performance_report.md    # Complete system benchmarks
│
├── security/
│   └── audit_report.md                # Security audit findings
│
└── plans/
    └── implementation-plan.md         # This document
```

**Estimated Total Files**: ~100 files (60 source, 20 tests, 10 docs, 10 configs/scripts)

**Estimated Total LOC**: ~15,000 LOC (10,000 source, 3,000 tests, 2,000 docs)

---

## Agent Assignments

### Phase 1: MVP - Vector RAG (Weeks 1-4)

| Week | Agent(s) | Responsibilities |
|------|----------|------------------|
| **Week 1** | `devops` | Docker setup, Qdrant deployment |
| | `backend-dev` | Database configuration, testing |
| | `coder` | File watcher, embedding pipeline |
| **Week 2** | `coder` | Semantic chunking, indexing |
| | `backend-dev` | MCP server implementation |
| | `tester` | Unit + integration tests |
| **Week 3** | `coder` | Hybrid search, query expansion |
| | `backend-dev` | FastAPI REST API |
| | `frontend-dev` | React web UI |
| | `performance-engineer` | Optimization |
| **Week 4** | `tester` | E2E tests, benchmarking |
| | `docs-writer` | Documentation |
| | `devops` | Deployment scripts |
| | `reviewer` | Code review, quality gates |

### Phase 2: GraphRAG Enhancement (Weeks 5-8)

| Week | Agent(s) | Responsibilities |
|------|----------|------------------|
| **Week 5** | `backend-dev` | Neo4j setup, graph APIs |
| | `ml-developer` | Entity/relationship extraction (spaCy, Relik) |
| | `coder` | Graph population scripts |
| **Week 6** | `ml-developer` | HippoRAG integration, PPR implementation |
| | `coder` | Query decomposition, hybrid ranking |
| | `performance-engineer` | Graph query optimization |
| **Week 7** | `frontend-dev` | D3.js graph visualization |
| | `backend-dev` | MCP graph tools |
| | `coder` | Context expansion logic |
| **Week 8** | `tester` | E2E tests, quality validation |
| | `performance-engineer` | Performance tuning |
| | `docs-writer` | Documentation updates |
| | `devops` | Deployment with graph layer |

### Phase 3: Bayesian Networks (Weeks 9-12)

| Week | Agent(s) | Responsibilities |
|------|----------|------------------|
| **Week 9** | `ml-developer` | Bayesian network design (pgmpy) |
| | `researcher` | Literature review, CPT priors |
| | `coder` | Uncertainty scoring integration |
| **Week 10** | `ml-developer` | GNN-RBN implementation (PyG) |
| | `researcher` | Neurosymbolic reasoning research |
| | `coder` | MCP probabilistic tools |
| **Week 11** | `ml-developer` | Agentic router (LLM-based) |
| | `performance-engineer` | Caching (Redis), optimization |
| | `coder` | Context fusion (RRF) |
| **Week 12** | `tester` | Complete E2E suite, benchmarking |
| | `security-manager` | Security audit |
| | `performance-engineer` | Performance validation |
| | `docs-writer` | Final documentation |
| | `devops` | Production deployment |
| | `reviewer` | Final code review |

**Total Agent-Weeks**: 38 agent-weeks across 12 calendar weeks (average 3.2 agents in parallel)

---

## Technology Stack

### Infrastructure
- **Docker**: Container orchestration (Qdrant, Neo4j, Redis, API services)
- **Docker Compose**: Multi-container management
- **Python 3.11**: Primary language (type hints, asyncio)
- **Node.js 18+**: Optional (TypeScript MCP server)

### Vector Layer
- **Qdrant**: Vector database (1,238 QPS, 99% recall)
- **Sentence-Transformers**: Embeddings (all-MiniLM-L6-v2, 384-dim, free)
- **tantivy** or **Qdrant keyword**: BM25 keyword search

### Graph Layer
- **Neo4j**: Graph database (multi-hop queries, Cypher)
- **spaCy**: Named Entity Recognition (en_core_web_trf)
- **Relik**: Advanced entity linking
- **HippoRAG**: Multi-hop reasoning (Personalized PageRank)

### Bayesian Layer
- **pgmpy**: Probabilistic graphical models (belief networks)
- **PyTorch Geometric**: Graph Neural Networks (GNN-RBN)
- **PyMC** (optional): Full Bayesian inference (if needed)

### Integration
- **FastMCP** or **Custom**: MCP protocol server (Python)
- **FastAPI**: REST API framework
- **watchdog**: File system monitoring (Obsidian auto-sync)

### Frontend
- **React**: Web UI (TypeScript)
- **D3.js**: Graph visualization (force-directed layout)
- **TailwindCSS**: Styling

### Caching & Storage
- **Redis**: Query result caching, embedding caching
- **Obsidian**: Markdown notes (~/Documents/Memory-Vault)

### Testing & Quality
- **pytest**: Testing framework (unit, integration, E2E)
- **pytest-cov**: Coverage reporting
- **Apache Bench**: Performance benchmarking
- **Bandit + Safety**: Security scanning

### Optional
- **Prometheus + Grafana**: Production monitoring
- **Cohere API**: Reranking (if better than Cross-Encoder)
- **Llama 3.1 8B**: Local LLM for query routing

---

## Dependencies

### Python Libraries (requirements.txt)

```txt
# Core
python==3.11

# Vector Layer
qdrant-client>=1.7.0
sentence-transformers>=2.2.0

# Graph Layer
neo4j>=5.14.0
spacy>=3.7.0
relik>=1.0.0
hipporag>=0.1.0

# Bayesian Layer
pgmpy>=0.1.23
torch>=2.1.0
torch-geometric>=2.4.0

# Retrieval
rank-bm25>=0.2.2
nltk>=3.8.1

# API & Integration
fastapi>=0.104.0
uvicorn>=0.24.0
watchdog>=3.0.0
redis>=5.0.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0

# Security
bandit>=1.7.5
safety>=2.3.5

# Logging
loguru>=0.7.2

# Utilities
pydantic>=2.4.0
python-dotenv>=1.0.0
```

### External Services

- **Qdrant**: Self-hosted via Docker (port 6333)
- **Neo4j**: Self-hosted via Docker (ports 7474 HTTP, 7687 Bolt)
- **Redis**: Self-hosted via Docker (port 6379, optional)
- **Obsidian**: Desktop app (~/Documents/Memory-Vault)

### Optional APIs

- **Cohere**: Reranking API (free tier: 100 calls/min)
- **Claude API**: Query routing LLM (use prompt caching)

---

## Risk Mitigation

### Risk: Docker/Deployment Complexity
- **Mitigation**: Provide `docker-compose.yml` with one-command setup
- **Fallback**: Use cloud services (Qdrant Cloud, Neo4j Aura) temporarily
- **Validation**: Test on clean machine in Week 4, 8, 12

### Risk: Graph Extraction Quality Poor
- **Mitigation**: Start with manual tagging (frontmatter in Obsidian)
- **Iteration**: Improve extraction incrementally with training data
- **Fallback**: Use manual graph curation if ML extraction fails

### Risk: Performance Doesn't Meet Targets
- **Mitigation**: Optimize incrementally (profiling, indexing, caching)
- **Fallback**: Use simpler models (remove reranking, reduce GNN complexity)
- **Validation**: Benchmark after each phase (Weeks 4, 8, 12)

### Risk: MCP Protocol Changes
- **Mitigation**: Abstract MCP layer (adapter pattern)
- **Fallback**: Provide REST API as stable interface
- **Validation**: Monitor MCP spec updates, plan for updates

### Risk: User Doesn't Adopt Obsidian Workflow
- **Mitigation**: Support multiple input formats (markdown, text, PDFs)
- **Fallback**: Generic file watcher for any directory
- **Validation**: User testing in Weeks 4, 8, 12

### Risk: Bayesian Network Too Slow
- **Mitigation**: Profile and optimize (reduce graph depth, cache CPTs)
- **Fallback**: Use simple heuristic scoring (rule-based uncertainty)
- **Validation**: Performance benchmarks in Week 9

### Risk: GNN-RBN Too Complex
- **Mitigation**: Start with simple GNN (2 layers, small model)
- **Fallback**: Skip GNN, use Bayesian network only
- **Validation**: Accuracy vs latency tradeoff in Week 10

### Risk: Agentic Routing Fails
- **Mitigation**: Implement rule-based fallback (heuristics)
- **Fallback**: Use all 3 layers in parallel (slower but safe)
- **Validation**: Routing accuracy tests in Week 11

### Risk: Budget Overrun (API Costs)
- **Mitigation**: Use free/local models (Sentence-Transformers, spaCy, Llama)
- **Fallback**: Remove optional APIs (Cohere, Claude routing)
- **Validation**: Track costs weekly, stay within $0 incremental budget

### Risk: Timeline Slippage
- **Mitigation**: Each phase is independently deployable (no dependencies)
- **Fallback**: Ship Phase 1 or Phase 2 if Phase 3 delayed
- **Validation**: Weekly progress reviews, adjust scope if needed

---

## Success Criteria (Overall)

The Memory MCP Triple System is considered successful when:

### Functional Requirements ✅
- ✅ **All 3 layers functional**: Vector RAG, GraphRAG, Bayesian networks working
- ✅ **MCP-compatible**: Works with Claude Desktop and other MCP clients
- ✅ **Obsidian integration seamless**: Auto-sync on file changes (<5s latency)
- ✅ **Multi-hop queries accurate**: ≥85% accuracy on complex queries (3+ hops)
- ✅ **Probabilistic reasoning**: Ambiguous queries return probability distributions

### Performance Requirements ✅
- ✅ **Query latency**: Vector <200ms, graph <500ms, multi-hop <2s (p95)
- ✅ **Retrieval quality**: Recall@10 ≥85% (vector), accuracy ≥85% (multi-hop)
- ✅ **Indexing throughput**: ≥100 docs/min (real-time sync)
- ✅ **Resource efficiency**: Memory <2GB RAM, storage <10MB/1000 docs
- ✅ **Caching effectiveness**: Cache hit rate ≥30%, latency reduction ≥50%

### Quality Requirements ✅
- ✅ **Privacy-preserving**: Self-hosted, no external APIs (except optional)
- ✅ **Transferable**: MCP standard enables switching between LLMs
- ✅ **Production-ready**: ≥200 tests passing, ≥90% coverage
- ✅ **Documentation complete**: 15,000+ words (architecture, API, user guide)
- ✅ **Security validated**: Security audit passed (no critical vulnerabilities)

### User Experience ✅
- ✅ **Daily use successful**: 7 days of dogfooding without critical issues
- ✅ **User satisfaction high**: Qualitative feedback positive (ease of use, accuracy)
- ✅ **Setup simple**: One-command setup (`./scripts/setup.sh`) works on clean machine
- ✅ **Errors clear**: Structured error messages, troubleshooting guide available

### Deployment Requirements ✅
- ✅ **Production deployment**: Successfully deployed to staging → production
- ✅ **Monitoring operational**: Health checks, logging, optional metrics
- ✅ **Backup/restore tested**: Neo4j + Qdrant backup scripts functional
- ✅ **Rollback ready**: Fallback strategies documented and tested

---

## Rollback Strategy

Each phase is independently deployable. If a later phase fails, the system can continue running with earlier phases only.

### Phase 1 Rollback
**Trigger**: Vector RAG MVP fails to meet success criteria (Week 4)

**Fallback**: Use Obsidian native search only (no external systems)

**Mitigation**:
1. Simplify to basic vector search (no reranking, no hybrid search)
2. Use Qdrant cloud free tier (if Docker fails)
3. Provide REST API only (if MCP integration fails)

**Decision Point**: End of Week 4 (GO/NO-GO for Phase 2)

---

### Phase 2 Rollback
**Trigger**: GraphRAG enhancement fails to meet success criteria (Week 8)

**Fallback**: Continue using Phase 1 (vector-only RAG)

**Mitigation**:
1. Use simpler graph (no HippoRAG, basic Neo4j Cypher only)
2. Use manual graph curation (skip ML entity extraction)
3. Provide basic graph visualization (Neo4j Browser instead of custom UI)

**Decision Point**: End of Week 8 (GO/NO-GO for Phase 3)

---

### Phase 3 Rollback
**Trigger**: Bayesian networks fail to meet success criteria (Week 12)

**Fallback**: Continue using Phase 2 (vector + graph RAG)

**Mitigation**:
1. Skip GNN-RBN (use Bayesian network only)
2. Skip Bayesian layer entirely (use rule-based uncertainty)
3. Use simpler routing (rule-based heuristics instead of LLM)

**Decision Point**: End of Week 12 (Launch with Phase 2 if Phase 3 incomplete)

---

### Emergency Rollback (Any Phase)
**Trigger**: Critical production issue (data loss, security breach, system down)

**Procedure**:
1. Stop all services (`docker-compose down`)
2. Restore last known good backup (Neo4j dump, Qdrant snapshot)
3. Roll back to previous phase version (git tag)
4. Investigate root cause, fix, re-deploy

**Recovery Time Objective (RTO)**: <30 minutes

**Recovery Point Objective (RPO)**: <24 hours (daily backups)

---

## Timeline Summary

### Phase 1: MVP - Vector RAG (Weeks 1-4)
- **Week 1**: Foundation (Docker, Qdrant, Obsidian, file watcher)
- **Week 2**: Vector search + MCP (chunking, indexing, MCP server)
- **Week 3**: Advanced retrieval (hybrid search, reranking, web UI)
- **Week 4**: Testing & docs (50+ tests, documentation, deployment)

**Deliverable**: Functional vector RAG system with MCP integration

---

### Phase 2: GraphRAG Enhancement (Weeks 5-8)
- **Week 5**: Graph construction (Neo4j, entity/relationship extraction)
- **Week 6**: HippoRAG (multi-hop reasoning, PPR)
- **Week 7**: Graph UI + MCP (visualization, graph tools)
- **Week 8**: Testing & refinement (E2E tests, optimization, docs)

**Deliverable**: GraphRAG system with multi-hop reasoning

---

### Phase 3: Bayesian Networks (Weeks 9-12)
- **Week 9**: Probabilistic reasoning (Bayesian network, uncertainty scoring)
- **Week 10**: Neurosymbolic (GNN-RBN integration)
- **Week 11**: Fusion & routing (context aggregation, agentic router, caching)
- **Week 12**: Final testing & launch (E2E suite, security, docs, production)

**Deliverable**: Complete Memory MCP Triple System, production-ready

---

**Total Timeline**: 12 weeks (3 months)

**Launch Date**: Week 12 (with rollback to Phase 1 or Phase 2 if needed)

Each phase delivers a functional system — no "big bang" deployment. Users can start using Phase 1 (Week 4) and benefit from incremental improvements in Phases 2 and 3.

---

## Budget

**Infrastructure Costs**: $0 (self-hosted via Docker)

**API Costs**: $0 baseline (free tier for all services)

**Optional Costs**:
- Cohere reranking API: $0 (free tier: 100 calls/min)
- Claude API for routing: $0 (use free tier + prompt caching)
- Llama 3.1 8B: $0 (self-hosted, 8GB VRAM required)

**Hardware Requirements**:
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 50GB minimum (100GB recommended for large vaults)
- **GPU**: Optional (for GNN training, not required for inference)

**Time Investment**: 12 weeks × 20 hours/week = 240 hours total

**ROI**: Permanent personal memory system, no recurring costs, privacy-preserving

---

## Appendix: NASA Rule 10 Compliance

All code in this project follows **NASA Rule 10** for safety-critical systems:

1. **≤60 lines per function**: Enforced via AST-based linting (automated check)
2. **≥2 assertions**: Required for critical paths (data validation, API inputs)
3. **No recursion**: Use iterative alternatives (explicit loops, stacks)
4. **Fixed loop bounds**: No `while(true)` loops (use timeouts, max iterations)

**Enforcement**:
- Pre-commit hook runs NASA compliance check (fail if violations)
- CI/CD pipeline includes NASA compliance gate (GitHub Actions)
- Manual review for complex functions (edge cases)

**Target**: ≥92% compliance (pragmatic, not 100%)

**Measurement**: AST-based checker counts violations, reports in CI logs

---

## Appendix: Test Strategy

### Test Pyramid

```
       /\
      /  \  E2E Tests (20 tests, 10%)
     /____\
    /      \  Integration Tests (50 tests, 25%)
   /________\
  /          \ Unit Tests (130 tests, 65%)
 /____________\
```

**Total Tests**: ~200 tests (unit + integration + E2E)

**Coverage Target**: ≥90% (measured via pytest-cov)

---

### Unit Tests (130 tests)
- Test individual functions/classes in isolation
- Mock external dependencies (Qdrant, Neo4j, Redis)
- Fast execution (<1s per test)
- Examples: `test_semantic_chunker.py`, `test_uncertainty_scorer.py`

---

### Integration Tests (50 tests)
- Test interactions between modules
- Use real dependencies (Docker containers)
- Moderate execution time (1-5s per test)
- Examples: `test_query_flow.py`, `test_graph_population.py`

---

### E2E Tests (20 tests)
- Test complete user workflows
- Use production-like environment
- Slow execution (5-30s per test)
- Examples: `test_complete_flow.py`, `test_complete_system.py`

---

### Performance Tests
- Benchmark QPS, latency, throughput
- Stress tests (1000+ docs, 100 concurrent queries)
- Regression tests (ensure optimizations don't break functionality)
- Examples: `scripts/benchmark.py`, `benchmarks/performance_report.md`

---

### Accuracy Tests
- Validate retrieval quality (recall, precision, F1)
- Manual validation on test sets (50-200 queries)
- Compare against baselines (vector-only, graph-only)
- Examples: `scripts/validate_accuracy.py`, `benchmarks/multihop_accuracy.md`

---

## Version Control

**Version**: 1.0
**Timestamp**: 2025-10-17T12:00:00Z
**Agent/Model**: Planner Drone (SPEK Platform v2)
**Status**: PRODUCTION-READY PLAN

**Change Summary**:
- Complete 12-week implementation plan created
- 3 phases (Vector RAG, GraphRAG, Bayesian)
- 200+ tests, ≥90% coverage target
- Performance targets defined
- Rollback strategies for each phase
- Agent assignments across 12 weeks
- File tree with ~100 files, ~15,000 LOC

**Receipt**:
- **run_id**: memory-mcp-triple-system-plan-001
- **inputs**: Research findings (architecture, benchmarks, chunking, embeddings)
- **tools_used**: Write (implementation-plan.md)
- **changes**: Created `C:\Users\17175\Desktop\memory-mcp-triple-system\plans\implementation-plan.md`

---

**END OF IMPLEMENTATION PLAN**
