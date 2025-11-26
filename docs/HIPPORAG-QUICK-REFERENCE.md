# HippoRAG Quick Reference

**Status**: Production-Ready
**Version**: 1.4.0

---

## What is HippoRAG?

Graph-based retrieval using Personalized PageRank instead of vector similarity.

**Key Benefit**: Context-aware retrieval through knowledge graph relationships.

---

## Usage

### MCP Tool (via Claude Code)

```json
{
  "name": "hipporag_retrieve",
  "arguments": {
    "query": "Python machine learning",
    "limit": 10,
    "mode": "execution"
  }
}
```

**Modes**:
- `execution`: Fast, precise results (default)
- `planning`: Broader context, more results
- `brainstorming`: Maximum exploration, creative connections

---

### Python API

```python
from services.hipporag_service import HippoRagService
from services.graph_service import GraphService
from services.entity_service import EntityService

# Initialize
graph = GraphService(data_dir="./data")
entity_svc = EntityService()
hipporag = HippoRagService(graph, entity_svc)

# Single-hop retrieval
results = hipporag.retrieve(
    query="Python machine learning",
    top_k=5,
    alpha=0.85  # PPR damping factor
)

# Multi-hop retrieval (broader context)
results = hipporag.retrieve_multi_hop(
    query="Python machine learning",
    max_hops=3,
    top_k=10
)

# Process results
for result in results:
    print(f"Rank {result.rank}: {result.text}")
    print(f"Score: {result.score:.4f}")
    print(f"Entities: {result.entities}")
```

---

## How It Works

```
Query: "Python machine learning"
    |
    v
1. Extract entities -> ["python", "machine_learning"]
    |
    v
2. Match to graph nodes
    |
    v
3. Run Personalized PageRank
    |
    v
4. Rank chunks by aggregated scores
    |
    v
Results: [RetrievalResult(...), ...]
```

---

## When to Use

**Use HippoRAG when**:
- Query needs multi-hop reasoning
- Want to explore related concepts
- Need context-aware retrieval
- Graph has rich relationship data

**Use Vector Search when**:
- Query needs fast exact match
- Keyword-based lookup
- No graph relationships available
- Latency is critical (<50ms)

---

## Parameters

### retrieve()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | - | Query text |
| `top_k` | int | 5 | Number of results |
| `alpha` | float | 0.85 | PPR damping factor |

### retrieve_multi_hop()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | - | Query text |
| `max_hops` | int | 3 | Maximum BFS hops |
| `top_k` | int | 5 | Number of results |

---

## Performance

**Typical Latency**: 100-600ms

**Breakdown**:
- Entity extraction: 10-50ms
- PPR computation: 50-500ms
- Chunk ranking: <10ms

**Tip**: Use `mode="execution"` for faster results (fewer tiers).

---

## Graph Schema

**Nodes**:
- `chunk`: Text chunks from documents
- `entity`: Named entities (PERSON, ORG, CONCEPT)

**Edges**:
- `mentions`: chunk -> entity
- `related_to`: entity <-> entity
- `similar_to`: entity <-> entity (synonyms)

---

## Example Results

```python
RetrievalResult(
    chunk_id="chunk_ml_intro",
    text="Python is widely used for machine learning...",
    score=0.65,
    rank=1,
    entities=["python", "machine_learning"],
    metadata={
        "file_path": "ml_guide.txt",
        "chunk_index": 0,
        "timestamp": "2025-11-26T10:00:00Z"
    }
)
```

---

## Troubleshooting

**No results returned?**
- Check if entities exist in graph
- Verify graph has chunks and mention edges
- Try multi-hop retrieval for broader search

**Slow queries?**
- Reduce `max_hops` (default: 3)
- Use `mode="execution"` (faster)
- Check graph size (>10K nodes = slower)

**Entity not matched?**
- Entities are normalized (lowercase, underscore)
- Check graph node IDs match normalized form
- Example: "Machine Learning" -> "machine_learning"

---

## Integration with NexusProcessor

HippoRAG is the **Graph Tier** in the Triple System:

```
NexusProcessor
    |
    +-- Vector Tier (fast, broad)
    +-- Graph Tier (HippoRAG, context-aware)
    +-- Bayesian Tier (probabilistic)
    |
    v
Hybrid Results (tier-weighted scores)
```

**Auto-routing**: `vector_search` MCP tool uses NexusProcessor with all tiers.

---

## Advanced: Building Knowledge Graph

```python
# Add entities
graph.add_entity_node("python", "CONCEPT")
graph.add_entity_node("machine_learning", "CONCEPT")

# Add chunks
graph.add_chunk_node("chunk1", {
    "text": "Python is great for ML",
    "file_path": "ml_intro.txt"
})

# Link chunks to entities
graph.add_relationship("chunk1", "mentions", "python")
graph.add_relationship("chunk1", "mentions", "machine_learning")

# Link related entities
graph.add_relationship("python", "related_to", "machine_learning")

# Save graph
graph.save_graph()
```

---

## References

- **Architecture**: `docs/HIPPORAG-ARCHITECTURE.md`
- **Investigation Report**: `REM-006-INVESTIGATION-REPORT.md`
- **NeurIPS'24 Paper**: "Hippocampal Indexing for Long-Context Retrieval"

---

**Status**: Production-ready, fully tested, no known issues.
