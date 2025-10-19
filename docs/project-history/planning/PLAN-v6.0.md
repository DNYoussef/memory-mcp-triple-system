# Memory MCP Triple System - PLAN v6.0

**Version**: 6.0 (Loop 1 Iteration 1)
**Date**: 2025-10-18
**Status**: Draft - Awaiting Review
**Methodology**: SPARC Loop 1 Planning Phase
**Duration**: 8 weeks (Weeks 7-14)
**Estimated Effort**: 180 hours (22.5 hours/week average)

---

## Executive Summary

This plan details the 8-week implementation roadmap (Weeks 7-14) to complete the Memory MCP Triple System specification (SPEC v6.0). Building on Weeks 1-6 foundation (321 tests, 85% coverage), we will implement:

1. **Obsidian MCP portability layer** (Week 7)
2. **GraphRAG entity consolidation** (Week 8)
3. **RAPTOR hierarchical clustering** (Week 9)
4. **Bayesian Graph RAG** (Week 10)
5. **Nexus Processor SOP pipeline** (Week 11)
6. **Memory forgetting & consolidation** (Week 12)
7. **Mode-aware context** (Week 13)
8. **Two-stage retrieval verification** (Week 14)

**Target Deliverables**:
- **+76 tests** (397 total from 321 baseline)
- **+2,800 LOC** (production code)
- **+1,900 LOC** (test code)
- **8 Memory Wall principles** fully implemented
- **<1s query latency** (95th percentile)
- **<35min weekly curation** (measured via analytics)

---

## Week-by-Week Roadmap

### Week 7: Obsidian MCP Integration + Lifecycle Separation

**Duration**: 20 hours (4 days × 5 hours/day)
**Priority**: P0 (critical path for portability)

#### Objectives
1. Implement Obsidian file watcher (auto-indexing <2s)
2. Create MCP server bidirectional sync (read vault + write sessions)
3. Add lifecycle tagging (personal, project, session) to ChromaDB metadata
4. Validate portability with ChatGPT, Claude, Gemini

#### Day-by-Day Breakdown

**Day 1: File Watcher + Auto-Indexing** (5 hours)

*Files to Create*:
- `src/obsidian/file_watcher.py` (120 LOC)
- `tests/unit/test_file_watcher.py` (80 LOC)

*Implementation*:
```python
# src/obsidian/file_watcher.py (120 LOC, NASA-compliant)

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from loguru import logger
import time

class ObsidianFileWatcher(FileSystemEventHandler):
    """
    Watch Obsidian vault for file changes and trigger auto-indexing.

    Features:
    - Debouncing (500ms wait after last change)
    - Incremental indexing (single file, not full reindex)
    - Background processing (async queue)

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(
        self,
        vault_path: str,
        indexer,  # VectorIndexer instance
        debounce_ms: int = 500
    ):
        """Initialize file watcher."""
        self.vault_path = Path(vault_path)
        self.indexer = indexer
        self.debounce_ms = debounce_ms
        self.pending_files = {}  # {path: last_modified_time}

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        if not event.src_path.endswith('.md'):
            return

        # Add to pending queue with current timestamp
        self.pending_files[event.src_path] = time.time()
        logger.debug(f"File modified: {event.src_path}")

    def on_created(self, event):
        """Handle file creation events."""
        self.on_modified(event)  # Same logic as modification

    def process_pending(self):
        """Process pending files after debounce period."""
        current_time = time.time()
        to_process = []

        for path, timestamp in list(self.pending_files.items()):
            # Check if debounce period has passed
            if (current_time - timestamp) * 1000 >= self.debounce_ms:
                to_process.append(path)
                del self.pending_files[path]

        for path in to_process:
            self._index_file(path)

    def _index_file(self, path: str):
        """Index a single markdown file."""
        start_time = time.perf_counter()

        # Read file content
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract YAML frontmatter (lifecycle, tags, etc.)
        metadata = self._extract_frontmatter(content)

        # Chunk content (semantic chunking from Week 3)
        chunks = self._semantic_chunk(content, path, metadata)

        # Generate embeddings (batch size 100)
        embeddings = self._generate_embeddings(chunks)

        # Index in ChromaDB
        self.indexer.index_chunks(chunks, embeddings)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Indexed {path} in {elapsed_ms:.1f}ms")

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from markdown."""
        if not content.startswith('---'):
            return {}

        # Simple YAML parsing (use pyyaml for production)
        lines = content.split('\n')
        frontmatter = {}
        for line in lines[1:]:
            if line == '---':
                break
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()

        return frontmatter

    def _semantic_chunk(
        self,
        content: str,
        file_path: str,
        metadata: dict
    ) -> list:
        """Semantic chunking (512 tokens max)."""
        # Use existing semantic chunker from Week 3
        from src.chunking.semantic_chunker import SemanticChunker
        chunker = SemanticChunker(max_tokens=512)
        return chunker.chunk(content, file_path, metadata)

    def _generate_embeddings(self, chunks: list) -> list:
        """Generate embeddings for chunks."""
        # Use existing embedding service from Week 1-2
        from src.services.embedding_service import EmbeddingService
        embedder = EmbeddingService()
        return embedder.embed_batch([c['text'] for c in chunks])
```

*Tests*:
```python
# tests/unit/test_file_watcher.py (80 LOC)

import pytest
from src.obsidian.file_watcher import ObsidianFileWatcher
from unittest.mock import Mock, patch
import time

class TestObsidianFileWatcher:
    """Unit tests for file watcher."""

    def test_on_modified_adds_to_pending(self):
        """Test file modification adds to pending queue."""
        indexer = Mock()
        watcher = ObsidianFileWatcher('/vault', indexer)

        event = Mock(is_directory=False, src_path='/vault/note.md')
        watcher.on_modified(event)

        assert '/vault/note.md' in watcher.pending_files

    def test_on_modified_ignores_non_markdown(self):
        """Test non-markdown files are ignored."""
        indexer = Mock()
        watcher = ObsidianFileWatcher('/vault', indexer)

        event = Mock(is_directory=False, src_path='/vault/image.png')
        watcher.on_modified(event)

        assert '/vault/image.png' not in watcher.pending_files

    def test_process_pending_debouncing(self):
        """Test debouncing waits for quiet period."""
        indexer = Mock()
        watcher = ObsidianFileWatcher('/vault', indexer, debounce_ms=500)

        # Add file to pending
        watcher.pending_files['/vault/note.md'] = time.time()

        # Process immediately (should NOT index)
        watcher.process_pending()
        assert '/vault/note.md' in watcher.pending_files

        # Wait 600ms and process (should index)
        time.sleep(0.6)
        with patch.object(watcher, '_index_file') as mock_index:
            watcher.process_pending()
            mock_index.assert_called_once_with('/vault/note.md')

        assert '/vault/note.md' not in watcher.pending_files

    def test_extract_frontmatter(self):
        """Test YAML frontmatter extraction."""
        indexer = Mock()
        watcher = ObsidianFileWatcher('/vault', indexer)

        content = """---
title: My Note
tags: [python, tutorial]
lifecycle: project
---

# Content here
"""
        metadata = watcher._extract_frontmatter(content)
        assert metadata['title'] == 'My Note'
        assert metadata['lifecycle'] == 'project'
```

*Deliverables*:
- ✅ File watcher detects changes within 1s
- ✅ Debouncing prevents rapid re-indexing (500ms quiet period)
- ✅ Incremental indexing (single file, not full reindex)
- ✅ 5 tests passing (file modification, debouncing, frontmatter)

**Day 2: MCP Server Bidirectional Sync** (5 hours)

*Files to Create/Modify*:
- `src/mcp/obsidian_sync.py` (150 LOC) *NEW*
- `src/mcp/mcp_server.py` (modify: +80 LOC)
- `tests/unit/test_obsidian_sync.py` (100 LOC)

*Implementation*:
```python
# src/mcp/obsidian_sync.py (150 LOC)

from pathlib import Path
from datetime import datetime
from loguru import logger

class ObsidianSync:
    """
    Bidirectional sync between MCP server and Obsidian vault.

    Features:
    - Read vault: Auto-index all markdown files
    - Write sessions: Save AI conversations to /sessions/
    - YAML frontmatter: Lifecycle, tags, version

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, vault_path: str):
        """Initialize Obsidian sync."""
        self.vault_path = Path(vault_path)
        self.sessions_dir = self.vault_path / 'sessions'
        self.sessions_dir.mkdir(exist_ok=True)

    def read_vault(self) -> list:
        """Read all markdown files from vault."""
        markdown_files = []
        for file_path in self.vault_path.rglob('*.md'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            markdown_files.append({
                'path': str(file_path),
                'content': content,
                'metadata': self._extract_frontmatter(content)
            })

        logger.info(f"Read {len(markdown_files)} markdown files from vault")
        return markdown_files

    def write_session(
        self,
        conversation: list,
        metadata: dict = None
    ) -> str:
        """
        Write AI conversation to /sessions/ folder.

        Args:
            conversation: List of {"role": "user"|"assistant", "content": str}
            metadata: Optional metadata (tags, lifecycle, etc.)

        Returns:
            str: File path of created session
        """
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        session_file = self.sessions_dir / f"{timestamp}-session.md"

        # Build YAML frontmatter
        frontmatter = self._build_frontmatter(metadata or {})

        # Build markdown content
        content_lines = [frontmatter, '']
        for msg in conversation:
            role = msg['role'].capitalize()
            content_lines.append(f"## {role}")
            content_lines.append(msg['content'])
            content_lines.append('')

        # Write to file
        with open(session_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_lines))

        logger.info(f"Saved session to {session_file}")
        return str(session_file)

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter."""
        # (Same as file_watcher.py, consider refactoring to shared util)
        pass

    def _build_frontmatter(self, metadata: dict) -> str:
        """Build YAML frontmatter from metadata dict."""
        lines = ['---']

        # Default metadata
        metadata.setdefault('lifecycle', 'session')
        metadata.setdefault('created', datetime.now().isoformat())

        for key, value in metadata.items():
            if isinstance(value, list):
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: {value}")

        lines.append('---')
        return '\n'.join(lines)
```

*MCP Server Integration*:
```python
# src/mcp/mcp_server.py (modify: add /save-session endpoint)

@app.route('/save-session', methods=['POST'])
def save_session():
    """Save AI conversation to Obsidian /sessions/ folder."""
    data = request.json
    conversation = data.get('conversation', [])
    metadata = data.get('metadata', {})

    # Write to Obsidian vault
    obsidian_sync = ObsidianSync(vault_path=config.obsidian_vault_path)
    session_file = obsidian_sync.write_session(conversation, metadata)

    return jsonify({
        'status': 'success',
        'file_path': session_file
    })
```

*Tests*:
```python
# tests/unit/test_obsidian_sync.py (100 LOC)

import pytest
from src.mcp.obsidian_sync import ObsidianSync
from pathlib import Path

class TestObsidianSync:
    """Unit tests for Obsidian sync."""

    def test_read_vault(self, tmp_path):
        """Test reading all markdown files from vault."""
        # Create test vault
        (tmp_path / 'note1.md').write_text('# Note 1')
        (tmp_path / 'note2.md').write_text('# Note 2')

        sync = ObsidianSync(str(tmp_path))
        files = sync.read_vault()

        assert len(files) == 2
        assert files[0]['content'] == '# Note 1'

    def test_write_session(self, tmp_path):
        """Test writing AI conversation to /sessions/."""
        sync = ObsidianSync(str(tmp_path))

        conversation = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there!'}
        ]

        session_file = sync.write_session(conversation)

        assert Path(session_file).exists()
        content = Path(session_file).read_text()
        assert '## User' in content
        assert '## Assistant' in content
        assert 'lifecycle: session' in content
```

*Deliverables*:
- ✅ Read vault: Index all markdown files on startup
- ✅ Write sessions: Auto-save AI conversations to `/sessions/`
- ✅ YAML frontmatter: Lifecycle, tags, created timestamp
- ✅ 5 tests passing (read vault, write session, frontmatter)

**Day 3: Lifecycle Tagging + Query Filtering** (5 hours)

*Files to Modify*:
- `src/indexing/vector_indexer.py` (modify: +40 LOC)
- `config/memory-mcp.yaml` (modify: add lifecycle config)
- `tests/unit/test_lifecycle_filtering.py` (80 LOC) *NEW*

*Implementation*:
```python
# src/indexing/vector_indexer.py (add lifecycle filtering)

def search_with_lifecycle(
    self,
    query_embedding: List[float],
    lifecycle: str = None,  # 'personal', 'project', 'session'
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Search with optional lifecycle filtering.

    Args:
        query_embedding: Query vector
        lifecycle: Filter by lifecycle (None = all)
        top_k: Number of results

    Returns:
        List of results with lifecycle metadata
    """
    where_filter = {}
    if lifecycle:
        where_filter['lifecycle'] = lifecycle

    results = self.collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter if where_filter else None
    )

    # Format results
    formatted = []
    for i in range(len(results['ids'][0])):
        formatted.append({
            'id': results['ids'][0][i],
            'document': results['documents'][0][i],
            'metadata': results['metadatas'][0][i],
            'distance': results['distances'][0][i],
            'lifecycle': results['metadatas'][0][i].get('lifecycle', 'unknown')
        })

    return formatted
```

*Configuration*:
```yaml
# config/memory-mcp.yaml (add lifecycle config)

lifecycle:
  personal:
    retention: never  # Never expires
    priority: high
  project:
    retention_days: 30  # 30 days after project close
    priority: medium
  session:
    retention_days: 7  # 7 days auto-expire
    priority: low

  # Auto-expiration schedule
  cleanup_schedule:
    enabled: true
    cron: "0 2 * * 0"  # Every Sunday at 2am
```

*Tests*:
```python
# tests/unit/test_lifecycle_filtering.py (80 LOC)

import pytest
from src.indexing.vector_indexer import VectorIndexer

class TestLifecycleFiltering:
    """Unit tests for lifecycle filtering."""

    def test_filter_by_personal(self, indexer):
        """Test filtering by personal lifecycle."""
        # Index chunks with different lifecycles
        chunks = [
            {'text': 'Personal pref', 'file_path': '/personal/', 'chunk_index': 0, 'metadata': {'lifecycle': 'personal'}},
            {'text': 'Project fact', 'file_path': '/projects/', 'chunk_index': 0, 'metadata': {'lifecycle': 'project'}},
            {'text': 'Session data', 'file_path': '/sessions/', 'chunk_index': 0, 'metadata': {'lifecycle': 'session'}}
        ]
        embeddings = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
        indexer.index_chunks(chunks, embeddings)

        # Query with lifecycle filter
        query_emb = [0.15] * 384
        results = indexer.search_with_lifecycle(query_emb, lifecycle='personal', top_k=5)

        assert len(results) == 1
        assert results[0]['lifecycle'] == 'personal'

    def test_filter_no_lifecycle(self, indexer):
        """Test no filter returns all lifecycles."""
        # (Same setup as above)
        results = indexer.search_with_lifecycle(query_emb, lifecycle=None, top_k=5)
        assert len(results) == 3
```

*Deliverables*:
- ✅ Lifecycle tagging in ChromaDB metadata
- ✅ Query filtering by lifecycle (`lifecycle=personal`)
- ✅ Auto-expiration config (session: 7 days, project: 30 days)
- ✅ 5 tests passing (filter personal, project, session, no filter, auto-expiration)

**Day 4: MCP Portability Testing** (5 hours)

*Tasks*:
1. Test MCP server with ChatGPT (OpenAI API) - 2 hours
2. Test MCP server with Claude (Anthropic API) - 2 hours
3. Test MCP server with Gemini (Google API) - 1 hour

*Integration Tests*:
```python
# tests/integration/test_mcp_portability.py (120 LOC)

import pytest
import requests

class TestMCPPortability:
    """Integration tests for MCP server portability."""

    @pytest.mark.integration
    def test_chatgpt_client(self):
        """Test MCP server responds to ChatGPT client."""
        response = requests.post(
            'http://localhost:5000/query',
            headers={'X-Client': 'chatgpt'},
            json={'query': 'What is NASA Rule 10?', 'mode': 'execution'}
        )

        assert response.status_code == 200
        data = response.json()
        assert 'results' in data
        assert len(data['results']) <= 5  # Execution mode

    @pytest.mark.integration
    def test_claude_client(self):
        """Test MCP server responds to Claude client."""
        response = requests.post(
            'http://localhost:5000/query',
            headers={'X-Client': 'claude'},
            json={'query': 'What are all database options?', 'mode': 'planning'}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data['results']) >= 10  # Planning mode

    @pytest.mark.integration
    def test_gemini_client(self):
        """Test MCP server responds to Gemini client."""
        response = requests.post(
            'http://localhost:5000/query',
            headers={'X-Client': 'gemini'},
            json={'query': 'Creative ideas for caching?', 'mode': 'brainstorming'}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data['results']) >= 20  # Brainstorming mode
```

*Deliverables*:
- ✅ MCP server responds to ChatGPT client
- ✅ MCP server responds to Claude client
- ✅ MCP server responds to Gemini client
- ✅ 5 integration tests passing (3 clients + 2 edge cases)

**Week 7 Summary**:
- **LOC Added**: 490 production + 360 tests = 850 LOC
- **Tests Added**: 15 tests (10 unit + 5 integration)
- **Tests Passing**: 336/336 (321 baseline + 15 new)
- **Key Files**:
  - `src/obsidian/file_watcher.py` (120 LOC)
  - `src/mcp/obsidian_sync.py` (150 LOC)
  - `src/indexing/vector_indexer.py` (+40 LOC lifecycle filtering)
  - `tests/integration/test_mcp_portability.py` (120 LOC)

---

### Week 8: GraphRAG Entity Consolidation (Leiden Algorithm)

**Duration**: 24 hours (4 days × 6 hours/day)
**Priority**: P1 (improves HippoRAG accuracy)

#### Objectives
1. Implement entity deduplication ("Tesla" = "Tesla Inc" = "Tesla Motors")
2. Add community detection using Leiden algorithm (Microsoft GraphRAG paper)
3. Create hierarchical entity clustering
4. Validate synonym merging (90% accuracy on 1000 entities)

#### Day-by-Day Breakdown

**Day 1-2: Entity Deduplication** (12 hours)

*Algorithm*: String similarity (Levenshtein distance) + embedding cosine similarity

*Files to Create*:
- `src/graph/entity_consolidator.py` (180 LOC)
- `tests/unit/test_entity_consolidator.py` (120 LOC)

*Implementation*:
```python
# src/graph/entity_consolidator.py (180 LOC, NASA-compliant)

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from loguru import logger

class EntityConsolidator:
    """
    Consolidate duplicate entities using string similarity + embeddings.

    Algorithm:
    1. String similarity (Levenshtein): Catch exact/near-exact matches
    2. Embedding similarity (cosine >0.90): Catch semantic equivalents
    3. Merge: Create canonical entity, add synonyms

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, embedding_model: str = 'all-MiniLM-L6-v2'):
        """Initialize entity consolidator."""
        self.model = SentenceTransformer(embedding_model)
        self.canonical_entities = {}  # {canonical: [synonyms]}

    def consolidate(self, entities: list) -> dict:
        """
        Consolidate list of entity strings into canonical forms.

        Args:
            entities: List of entity strings (e.g., ["Tesla", "Tesla Inc"])

        Returns:
            dict: {canonical: [synonyms]}
        """
        # Step 1: Compute embeddings for all entities
        embeddings = self.model.encode(entities)

        # Step 2: Compute pairwise cosine similarity
        similarity_matrix = cosine_similarity(embeddings)

        # Step 3: Find clusters (threshold: cosine >0.90)
        clusters = self._find_clusters(similarity_matrix, threshold=0.90)

        # Step 4: Select canonical entity (longest string in cluster)
        for cluster in clusters:
            canonical = max(cluster, key=len)
            self.canonical_entities[canonical] = cluster

        logger.info(f"Consolidated {len(entities)} entities into {len(self.canonical_entities)} canonical forms")
        return self.canonical_entities

    def _find_clusters(
        self,
        similarity_matrix: np.ndarray,
        threshold: float = 0.90
    ) -> list:
        """
        Find clusters using similarity threshold.

        Returns:
            list: List of clusters (each cluster is a list of entity indices)
        """
        n = len(similarity_matrix)
        visited = [False] * n
        clusters = []

        for i in range(n):
            if visited[i]:
                continue

            # Start new cluster
            cluster = [i]
            visited[i] = True

            # Find all entities similar to i
            for j in range(i + 1, n):
                if similarity_matrix[i][j] >= threshold:
                    cluster.append(j)
                    visited[j] = True

            clusters.append(cluster)

        return clusters
```

*Tests*:
```python
# tests/unit/test_entity_consolidator.py (120 LOC)

import pytest
from src.graph.entity_consolidator import EntityConsolidator

class TestEntityConsolidator:
    """Unit tests for entity consolidation."""

    def test_consolidate_exact_duplicates(self):
        """Test consolidating exact duplicates."""
        consolidator = EntityConsolidator()
        entities = ['Tesla', 'Tesla', 'SpaceX']

        canonical = consolidator.consolidate(entities)

        assert len(canonical) == 2  # Tesla and SpaceX
        assert 'Tesla' in canonical
        assert 'SpaceX' in canonical

    def test_consolidate_similar_entities(self):
        """Test consolidating semantically similar entities."""
        consolidator = EntityConsolidator()
        entities = ['Tesla', 'Tesla Inc', 'Tesla Motors', 'SpaceX']

        canonical = consolidator.consolidate(entities)

        # Tesla, Tesla Inc, Tesla Motors should merge
        tesla_canonical = [k for k in canonical.keys() if 'Tesla' in k][0]
        assert len(canonical[tesla_canonical]) == 3

    def test_consolidate_distinct_entities(self):
        """Test distinct entities remain separate."""
        consolidator = EntityConsolidator()
        entities = ['Apple', 'Microsoft', 'Google']

        canonical = consolidator.consolidate(entities)

        assert len(canonical) == 3  # All distinct
```

**Day 3-4: Leiden Community Detection** (12 hours)

*Algorithm*: Leiden algorithm from Microsoft GraphRAG paper (improves Louvain)

*Dependencies*:
- `pip install python-igraph leidenalg`

*Files to Create*:
- `src/graph/community_detector.py` (200 LOC)
- `tests/unit/test_community_detector.py` (100 LOC)

*Implementation*:
```python
# src/graph/community_detector.py (200 LOC)

import igraph as ig
import leidenalg
from loguru import logger

class CommunityDetector:
    """
    Detect entity communities using Leiden algorithm.

    Algorithm:
    1. Build igraph from NetworkX DiGraph
    2. Run Leiden algorithm (resolution parameter: 1.0)
    3. Extract communities (modularity score validation)
    4. Annotate entities with community IDs

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, graph_service):
        """Initialize community detector."""
        self.graph_service = graph_service

    def detect_communities(self, resolution: float = 1.0) -> dict:
        """
        Detect communities using Leiden algorithm.

        Args:
            resolution: Resolution parameter (higher = more communities)

        Returns:
            dict: {community_id: [entity_list]}
        """
        # Convert NetworkX to igraph
        igraph = self._nx_to_igraph(self.graph_service.graph)

        # Run Leiden algorithm
        partition = leidenalg.find_partition(
            igraph,
            leidenalg.RBConfigurationVertexPartition,
            resolution_parameter=resolution
        )

        # Extract communities
        communities = {}
        for community_id, members in enumerate(partition):
            community_entities = [igraph.vs[i]['name'] for i in members]
            communities[community_id] = community_entities

        # Calculate modularity (validation metric)
        modularity = partition.modularity
        logger.info(f"Detected {len(communities)} communities (modularity: {modularity:.3f})")

        return communities

    def _nx_to_igraph(self, nx_graph) -> ig.Graph:
        """Convert NetworkX DiGraph to igraph."""
        edges = [(u, v) for u, v in nx_graph.edges()]
        node_names = list(nx_graph.nodes())

        igraph = ig.Graph(directed=True)
        igraph.add_vertices(len(node_names))
        igraph.vs['name'] = node_names

        # Add edges (convert node names to indices)
        name_to_idx = {name: i for i, name in enumerate(node_names)}
        edge_indices = [(name_to_idx[u], name_to_idx[v]) for u, v in edges]
        igraph.add_edges(edge_indices)

        return igraph
```

**Week 8 Summary**:
- **LOC Added**: 380 production + 220 tests = 600 LOC
- **Tests Added**: 20 tests (15 unit + 5 integration)
- **Tests Passing**: 356/356 (336 + 20)
- **Key Features**:
  - Entity deduplication (90% accuracy target)
  - Leiden community detection (modularity >0.4 target)
  - Hierarchical clustering (3 levels: entities → communities → super-communities)

---

*(Continue with Weeks 9-14 in similar detail...)*

**Note**: Due to response length limits, I'll provide Week 9-14 in condensed format. Full day-by-day breakdowns available upon request.

---

### Week 9: RAPTOR Hierarchical Clustering (Condensed)

**Duration**: 22 hours
**Key Deliverables**:
- Recursive summarization (100 chunks → 10 summaries → 1 abstract)
- Bayesian Information Criterion (BIC) cluster quality validation
- Multi-level retrieval (query at chunk/summary/abstract level)
- 25 tests (clustering, summarization, multi-level queries)
- **LOC**: 420 production + 280 tests = 700 LOC

**Files**:
- `src/raptor/hierarchical_clusterer.py` (220 LOC)
- `src/raptor/recursive_summarizer.py` (200 LOC)
- `tests/unit/test_raptor_clustering.py` (150 LOC)
- `tests/integration/test_multi_level_retrieval.py` (130 LOC)

---

### Week 10: Bayesian Graph RAG (pgmpy Belief Networks) (Condensed)

**Duration**: 26 hours
**Key Deliverables**:
- Bayesian network construction from knowledge graph
- Probabilistic inference (variable elimination, belief propagation)
- Uncertainty quantification ("P(X|Y) = 0.73")
- Network size limit (max 1000 nodes to prevent complexity explosion)
- 30 tests (network construction, inference, uncertainty)
- **LOC**: 480 production + 320 tests = 800 LOC

**Files**:
- `src/bayesian/network_builder.py` (240 LOC)
- `src/bayesian/probabilistic_query_engine.py` (240 LOC)
- `tests/unit/test_bayesian_network.py` (180 LOC)
- `tests/integration/test_probabilistic_queries.py` (140 LOC)

**Complexity Mitigation**:
- Max 1000 nodes per network (prune low-frequency entities)
- Sparse graphs only (skip edges with confidence <0.3)
- Timeout: 1s (fallback to Vector + HippoRAG if Bayesian times out)

---

### Week 11: Nexus Processor 5-Step SOP Pipeline (Condensed)

**Duration**: 18 hours
**Key Deliverables**:
- 5-step pipeline (Recall → Filter → Deduplicate → Rank → Compress)
- Parallel tier execution (latency = max tier latency + 100ms Nexus overhead)
- Weighted ranking (Vector: 0.4, HippoRAG: 0.4, Bayesian: 0.2)
- Deduplication (cosine >0.95)
- 15 tests (pipeline, ranking, parallel execution)
- **LOC**: 320 production + 200 tests = 520 LOC

**Files**:
- `src/nexus/processor.py` (220 LOC)
- `src/nexus/ranker.py` (100 LOC)
- `tests/unit/test_nexus_processor.py` (120 LOC)
- `tests/integration/test_parallel_execution.py` (80 LOC)

---

### Week 12: Memory Forgetting & Consolidation (Condensed)

**Duration**: 20 hours
**Key Deliverables**:
- Exponential decay formula: `score = base_score * exp(-0.05 * days_old)`
- Weekly batch summarization (100 session chunks → 1 summary)
- Manual override ("never forget" flag for important chunks)
- Auto-trigger: Every Sunday at 2am (cron schedule)
- 20 tests (decay, consolidation, override, cron)
- **LOC**: 360 production + 240 tests = 600 LOC

**Files**:
- `src/memory/decay_manager.py` (180 LOC)
- `src/memory/consolidation_service.py` (180 LOC)
- `tests/unit/test_memory_decay.py` (140 LOC)
- `tests/unit/test_consolidation.py` (100 LOC)

---

### Week 13: Mode-Aware Context (Planning vs Execution) (Condensed)

**Duration**: 16 hours
**Key Deliverables**:
- Mode detection (planning, execution, brainstorming)
- Mode-specific retrieval (top-K: planning=20, execution=5, brainstorming=30)
- Explicit mode override (query parameter `mode=`)
- Detection accuracy ≥85% (100 test queries)
- 10 tests (mode detection, retrieval, override)
- **LOC**: 240 production + 160 tests = 400 LOC

**Files**:
- `src/modes/mode_detector.py` (140 LOC)
- `src/modes/context_retriever.py` (100 LOC)
- `tests/unit/test_mode_detection.py` (100 LOC)
- `tests/integration/test_mode_aware_retrieval.py` (60 LOC)

---

### Week 14: Two-Stage Retrieval Verification + Integration Testing (Condensed)

**Duration**: 28 hours
**Key Deliverables**:
- Ground truth database (Obsidian `/personal/ground-truth/` YAML)
- Verification stage (facts only, skip brainstorming)
- False positive rate <2% (hallucination detection)
- E2E integration tests (all 3 tiers + Nexus + MCP)
- 50 tests (verification, E2E, performance benchmarks)
- **LOC**: 380 production + 440 tests = 820 LOC

**Files**:
- `src/verification/ground_truth_db.py` (200 LOC)
- `src/verification/fact_verifier.py` (180 LOC)
- `tests/integration/test_e2e_workflow.py` (240 LOC)
- `tests/performance/test_latency_benchmarks.py` (200 LOC)

**E2E Test Scenarios**:
1. User saves Obsidian note → Auto-indexed <2s → Queryable
2. AI conversation → Auto-saved to `/sessions/` → Lifecycle tagged
3. Query "What is X?" → 3 tiers query in parallel → Nexus merges → Return top-K
4. Weekly curation → Review 100 chunks → Batch tag → <35 minutes
5. Migration from ChatGPT memory → Import JSON → Re-index → Validate

---

## Summary: Weeks 7-14

### Total LOC Added

| Week | Production LOC | Test LOC | Total LOC |
|------|----------------|----------|-----------|
| Week 7 (Obsidian MCP) | 490 | 360 | 850 |
| Week 8 (GraphRAG) | 380 | 220 | 600 |
| Week 9 (RAPTOR) | 420 | 280 | 700 |
| Week 10 (Bayesian RAG) | 480 | 320 | 800 |
| Week 11 (Nexus) | 320 | 200 | 520 |
| Week 12 (Forgetting) | 360 | 240 | 600 |
| Week 13 (Mode-Aware) | 240 | 160 | 400 |
| Week 14 (Verification) | 380 | 440 | 820 |
| **Total** | **3,070** | **2,220** | **5,290** |

### Test Coverage Growth

| Milestone | Unit Tests | Integration Tests | E2E Tests | Total |
|-----------|-----------|-------------------|-----------|-------|
| Weeks 1-6 Baseline | 207 | 89 | 25 | 321 |
| Week 7 | +10 | +5 | 0 | +15 |
| Week 8 | +15 | +5 | 0 | +20 |
| Week 9 | +18 | +7 | 0 | +25 |
| Week 10 | +20 | +10 | 0 | +30 |
| Week 11 | +12 | +3 | 0 | +15 |
| Week 12 | +15 | +5 | 0 | +20 |
| Week 13 | +8 | +2 | 0 | +10 |
| Week 14 | +20 | +10 | +20 | +50 |
| **Weeks 7-14 Total** | **+118** | **+47** | **+20** | **+185** |
| **Grand Total** | **325** | **136** | **45** | **506** |

---

## Performance Targets (Validation)

| Metric | Week 6 Baseline | Week 14 Target | Improvement |
|--------|-----------------|----------------|-------------|
| Query Latency (95th %) | <500ms | <1s | 2x budget |
| Indexing Latency | N/A | <2s | New |
| Curation Time | N/A | <35min/week | New |
| Test Coverage | 85-92% | ≥85% | Maintained |
| NASA Compliance | 99-100% | ≥95% | Maintained |
| Tests Passing | 321 | 506 | +185 (+58%) |

---

## Risk Mitigation Plan

**Top 3 Risks** (from PREMORTEM v6.0):

1. **Bayesian Network Complexity Explosion** (P=40%, Impact=High)
   - **Week 10 Mitigation**: Limit to 1000 nodes, timeout 1s, fallback to Vector+HippoRAG

2. **Obsidian Sync Latency >2s** (P=30%, Impact=Medium)
   - **Week 7 Mitigation**: Debouncing (500ms), incremental indexing, async processing

3. **Curation Time >35 minutes/week** (P=35%, Impact=High)
   - **Week 12-13 Mitigation**: Smart suggestions (80% accuracy), batch operations (20+ chunks), auto-archive low-confidence

---

## Success Criteria (Final Validation)

**Technical**:
- ✅ 506 tests passing (321 baseline + 185 new)
- ✅ ≥85% coverage (all modules)
- ✅ NASA Rule 10: ≥95% compliance
- ✅ Query latency: <1s (95th percentile)
- ✅ Indexing latency: <2s (file save to indexed)

**Functional**:
- ✅ 8 Memory Wall principles implemented (see SPEC v6.0 Appendix A)
- ✅ 3-tier RAG working (Vector + HippoRAG + Bayesian)
- ✅ MCP server responds to 3 LLM clients (ChatGPT, Claude, Gemini)
- ✅ Obsidian bidirectional sync (<2s indexing)
- ✅ Weekly curation <35 minutes (measured via analytics)

**Quality**:
- ✅ 0 critical security vulnerabilities (Bandit, Semgrep)
- ✅ 0 mypy errors (type safety)
- ✅ 0 ruff issues (linting)

---

## Next Steps (Loop 1 Iteration 2)

After PLAN v6.0 approval:

1. **Create PREMORTEM v6.0**: Detailed risk analysis (8 risks identified in SPEC v6.0)
2. **Refine to v6.1**: Address top P0/P1 risks, adjust timeline
3. **Refine to v6.2**: Optimize architecture, validate Memory Wall principles
4. **Refine to v6.3**: Production-ready, all risks mitigated

**Loop 1 Timeline**:
- Iteration 1 (v6.0): 3 hours (SPEC + PLAN + PREMORTEM creation)
- Iteration 2 (v6.1): 1 hour (risk mitigation)
- Iteration 3 (v6.2): 1 hour (optimization)
- Iteration 4 (v6.3): 1 hour (final validation)
- **Total**: 6 hours (Loop 1 planning phase)

---

**Version**: 6.0 (Loop 1 Iteration 1)
**Status**: Draft - Awaiting Review
**Next**: Create PREMORTEM v6.0 (risk analysis)

**Receipt**:
- **Run ID**: loop1-iter1-plan-v6.0
- **Timestamp**: 2025-10-18T19:15:00Z
- **Agent**: Strategic Planning (Loop 1)
- **Inputs**: SPEC v6.0, Weeks 1-6 baseline, Memory Wall principles
- **Tools Used**: Write (1 file), TodoWrite (1 update)
- **Changes**: Created PLAN-v6.0.md (8 weeks, 506 tests target, 5,290 LOC)
- **Status**: Ready for PREMORTEM v6.0 creation
