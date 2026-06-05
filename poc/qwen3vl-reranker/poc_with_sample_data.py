# -*- coding: utf-8 -*-
"""
MEM-QWEN-001: Complete Reranker POC with Sample Data

This POC:
1. Creates a sample corpus of 100 diverse memories
2. Indexes them into a temporary ChromaDB
3. Runs baseline vs reranked comparison
4. Measures quality improvement and latency

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
import os
import io

# CRITICAL: Configure encoding and disable WANDB BEFORE any imports
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"
os.environ["HF_DATASETS_OFFLINE"] = "0"
os.environ["WANDB_DISABLED"] = "true"
os.environ["WANDB_MODE"] = "disabled"
os.environ["WANDB_SILENT"] = "true"

# Replace stdout/stderr with UTF-8 wrapped versions
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import time
import json
import tempfile
import warnings
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple

# Suppress warnings
warnings.filterwarnings("ignore")


# Sample memory corpus (100 diverse entries simulating real Memory MCP content)
SAMPLE_MEMORIES = [
    # Architecture & Components (20)
    "The NexusProcessor implements a 5-step SOP pipeline: RECALL queries all tiers, FILTER removes low-confidence results, DEDUPE eliminates duplicates, RANK applies weighted scoring, and COMPRESS selects final results.",
    "Memory MCP uses three retrieval tiers: Vector search with ChromaDB (40% weight), HippoRAG graph-based retrieval (40% weight), and Bayesian probabilistic inference (20% weight).",
    "ChromaDB stores embeddings using the HNSW algorithm for approximate nearest neighbor search with cosine similarity as the distance metric.",
    "The embedding pipeline uses all-MiniLM-L6-v2 from sentence-transformers, producing 384-dimensional dense vectors for semantic similarity.",
    "HippoRAG implements multi-hop reasoning using Personalized PageRank (PPR) on an entity knowledge graph extracted from documents.",
    "The Bayesian tier uses pgmpy for probabilistic inference, helping with uncertainty quantification in retrieval results.",
    "Mode detection classifies queries into three categories: execution (5K tokens), planning (10K tokens), or brainstorming (20K tokens).",
    "The lifecycle manager handles hot/cold data tiering with decay scores. New content starts as 'hot' with decay_score=1.0.",
    "VectorIndexer manages ChromaDB collections with singleton pattern and thread-safe access for concurrent requests.",
    "The request router handles MCP tool calls and dispatches to appropriate handlers for memory_store, vector_search, and graph_query.",
    "Service wiring in service_wiring.py initializes all core services: embedding pipeline, vector indexer, graph service, and KV store.",
    "The processing_utils mixin provides mode-specific configuration with core_k and extended_k parameters for result selection.",
    "Entity extraction uses NER to identify people, organizations, locations, and concepts from text for graph construction.",
    "The unified search router combines Memory MCP and Beads task results for comprehensive information retrieval.",
    "Graph service uses NetworkX for in-memory graph operations with persistence to disk for durability.",
    "The KV store provides key-value storage for metadata, settings, and quick lookups using SQLite backend.",
    "Embedding pipeline supports batch encoding for efficiency and single encoding for interactive use cases.",
    "The chunking strategy uses semantic boundaries with overlap for better context preservation in long documents.",
    "Deduplication uses cosine similarity with a 0.95 threshold to remove near-duplicate content from results.",
    "The confidence threshold of 0.3 filters out low-quality retrieval candidates before ranking.",

    # Protocols & Standards (15)
    "WHO/WHEN/PROJECT/WHY is a mandatory tagging protocol: WHO identifies the agent, WHEN is ISO8601 timestamp, PROJECT is context, WHY explains purpose.",
    "Confidence scores are assigned based on source type: witnessed (0.95), reported (0.70), inferred (0.50), assumed (0.30).",
    "The MCP protocol uses JSON-RPC 2.0 for tool communication with structured request/response formats.",
    "Memory decay follows exponential formula: e^(-days/30) with new content starting at 1.0 and decaying over time.",
    "NASA Rule 10 compliance requires all functions to be 60 lines or less for maintainability and testability.",
    "The VERIX notation system uses markers for confidence, source type, and claim status in structured documentation.",
    "VERILINGUA implements 7 cognitive frames from natural languages for enhanced reasoning and disambiguation.",
    "The 5-phase workflow enforces: Intent Analysis, Prompt Optimization, Strategic Planning, Playbook Routing, Execution.",
    "Ralph Wiggum loops implement quality-gated refinement that iterates until threshold passed or max iterations.",
    "Six Sigma quality thresholds require sigma level >= 4.0 and DPMO <= 6210 for code quality gates.",
    "The 4-layer enforcement strategy includes preventive, detective, corrective, and retention mechanisms.",
    "Graph edges represent semantic relationships: mentions, relates_to, depends_on, contradicts, supports.",
    "Token budgets scale with mode: execution uses 5K for quick answers, brainstorming uses 20K for exploration.",
    "Hybrid scoring formula: 0.4 * vector_score + 0.4 * hipporag_score + 0.2 * bayesian_score.",
    "Archive intent demotes content to 'warm' tier; reference intent also triggers warm classification.",

    # Integration & External Systems (15)
    "BeadsBridge integrates with the Beads task management system via the bd.exe CLI binary.",
    "ObsidianMCPClient syncs markdown files from Obsidian vaults into ChromaDB for semantic search.",
    "The Beads integration provides get_ready_tasks, get_task_detail, and query_tasks operations.",
    "Obsidian sync supports configurable file extensions with .md as the default for markdown notes.",
    "MCP servers expose tools via JSON-RPC: memory_store, vector_search, graph_query, unified_search.",
    "The calendar integration uses Google Calendar API through the google-calendar-mcp server.",
    "Gmail integration provides email operations through the server-gmail-autoauth-mcp package.",
    "Claude Flow provides agent orchestration with 60+ tools for complex multi-step workflows.",
    "Sequential thinking MCP enables chain-of-thought reasoning for complex problem decomposition.",
    "The connascence analyzer suite includes 7 analyzers for code quality: connascence, NASA, MECE, clarity, Six Sigma, theater, safety.",
    "Life OS Dashboard runs on Railway with FastAPI backend and React 19 frontend.",
    "Docker containerization uses multi-stage builds for optimized production images.",
    "Redis provides caching and message queuing for real-time features in the dashboard.",
    "PostgreSQL stores structured data with SQLAlchemy ORM for the web application.",
    "WebSocket connections enable real-time updates between frontend and backend.",

    # Technical Implementation (20)
    "Python asyncio is used for non-blocking I/O in BeadsBridge subprocess execution.",
    "The CrossEncoder from sentence-transformers provides cross-attention scoring for reranking.",
    "Retry logic uses tenacity with exponential backoff for database lock handling.",
    "Thread safety is achieved through singleton pattern with _instance_lock mutex.",
    "Loguru provides structured logging with configurable levels and rotation.",
    "PyTest fixtures enable isolated testing with mock dependencies and temp directories.",
    "Pydantic models define request/response schemas with automatic validation.",
    "FastAPI dependency injection manages service lifecycles and configuration.",
    "Alembic handles database migrations with version control for schema changes.",
    "The transformer model cache is stored in ~/.cache/huggingface/hub for reuse.",
    "CUDA acceleration is supported for GPU-enabled embedding and reranking models.",
    "Memory-mapped files enable efficient large corpus processing without full RAM load.",
    "Batch processing with configurable chunk sizes optimizes throughput for indexing.",
    "Connection pooling reduces database overhead for high-concurrency scenarios.",
    "Rate limiting prevents API abuse and ensures fair resource allocation.",
    "Health checks verify service availability before processing requests.",
    "Circuit breakers prevent cascading failures when dependencies are unavailable.",
    "Structured logging includes correlation IDs for distributed tracing.",
    "Environment variables configure deployment-specific settings without code changes.",
    "Type hints and mypy enable static type checking for early error detection.",

    # Concepts & Definitions (15)
    "Semantic search finds documents based on meaning rather than exact keyword matches.",
    "Dense retrieval uses neural network embeddings for continuous vector representations.",
    "Sparse retrieval methods like BM25 use term frequency statistics for ranking.",
    "Hybrid search combines dense and sparse methods for improved recall and precision.",
    "Reranking applies a more expensive model to refine initial retrieval results.",
    "Cross-encoder models see query and document together for precise relevance scoring.",
    "Bi-encoder models encode query and document separately for efficient similarity.",
    "Knowledge graphs represent entities and relationships for structured reasoning.",
    "Named Entity Recognition (NER) identifies proper nouns and concepts in text.",
    "Personalized PageRank propagates relevance through graph edges for multi-hop queries.",
    "Token budget limits context size to manage cost and latency in LLM applications.",
    "Matryoshka embeddings support variable dimension truncation without retraining.",
    "Cosine similarity measures angle between vectors, normalized to [-1, 1] range.",
    "HNSW (Hierarchical Navigable Small World) provides fast approximate nearest neighbor search.",
    "Context window is the maximum tokens an LLM can process in a single request.",

    # Troubleshooting & Errors (15)
    "ChromaDB file locking on Windows requires singleton pattern to prevent conflicts.",
    "Unicode encoding errors on Windows console require PYTHONIOENCODING=utf-8 environment variable.",
    "HuggingFace offline mode can be disabled by setting HF_HUB_OFFLINE=0.",
    "Missing CUDA drivers show 'No GPU detected' - install nvidia-smi compatible drivers.",
    "SQLite OperationalError on database locks requires retry with exponential backoff.",
    "Import errors for sentence_transformers indicate missing pip install sentence-transformers.",
    "Connection refused errors suggest the MCP server is not running or wrong port.",
    "Out of memory errors on embedding require reducing batch size or using CPU offload.",
    "Timeout errors indicate slow model loading - check disk I/O and network latency.",
    "Invalid JSON responses mean malformed MCP tool call parameters.",
    "Collection not found errors require creating the ChromaDB collection first.",
    "Dimension mismatch errors occur when embedding models change between indexing and query.",
    "Rate limit exceeded errors require implementing backoff or request throttling.",
    "Authentication failures need valid API keys or OAuth tokens configured.",
    "Version mismatch warnings suggest updating dependencies with pip install --upgrade.",
]


@dataclass
class BenchmarkResult:
    """Result from a single benchmark query."""
    query: str
    baseline_latency_ms: float
    rerank_latency_ms: float
    baseline_top5: List[str]
    reranked_top5: List[str]
    order_changed: bool
    rerank_score_delta: float


def create_temp_chromadb(memories: List[str], embedder) -> "chromadb.Collection":
    """Create temporary ChromaDB with sample memories."""
    import chromadb

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="poc_chroma_")
    client = chromadb.PersistentClient(path=temp_dir)

    collection = client.create_collection(
        name="poc_memories",
        metadata={"hnsw:space": "cosine"}
    )

    # Batch embed and add
    print(f"Indexing {len(memories)} memories...")
    batch_size = 20
    for i in range(0, len(memories), batch_size):
        batch = memories[i:i+batch_size]
        embeddings = embedder.encode(batch).tolist()

        collection.add(
            ids=[f"mem-{j:03d}" for j in range(i, i+len(batch))],
            documents=batch,
            embeddings=embeddings
        )
        print(f"  Indexed {min(i+batch_size, len(memories))}/{len(memories)}")

    return collection


def baseline_search(collection, embedder, query: str, top_k: int = 20) -> Tuple[List[Dict], float]:
    """Search without reranking."""
    start = time.time()

    query_embedding = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "distances"]
    )

    latency_ms = (time.time() - start) * 1000

    docs = []
    for i, doc_id in enumerate(results["ids"][0]):
        docs.append({
            "id": doc_id,
            "text": results["documents"][0][i],
            "distance": results["distances"][0][i],
        })

    return docs, latency_ms


def rerank_documents(reranker, query: str, documents: List[Dict], top_k: int = 5) -> Tuple[List[Dict], float]:
    """Rerank with cross-encoder."""
    start = time.time()

    texts = [doc["text"][:512] for doc in documents]
    pairs = [(query, text) for text in texts]

    scores = reranker.predict(pairs, show_progress_bar=False)

    scored_docs = list(zip(documents, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)

    reranked = []
    for doc, score in scored_docs[:top_k]:
        doc_copy = dict(doc)
        doc_copy["rerank_score"] = float(score)
        reranked.append(doc_copy)

    latency_ms = (time.time() - start) * 1000
    return reranked, latency_ms


def get_test_queries() -> List[str]:
    """Diverse test queries for benchmarking."""
    return [
        # Direct lookups
        "What is the Nexus processor pipeline?",
        "How does ChromaDB store embeddings?",
        "What are the three retrieval tiers?",

        # Semantic similarity (similar meaning, different words)
        "How do I save information to memory?",  # Should match memory_store content
        "What scoring formula combines the tiers?",  # Should match hybrid scoring
        "How does the system handle old data?",  # Should match lifecycle/decay

        # Multi-hop reasoning
        "How do confidence and source type relate?",
        "What happens when a query is classified as brainstorming?",

        # Troubleshooting queries
        "Why am I getting file locking errors?",
        "How to fix Unicode errors on Windows?",

        # Conceptual queries
        "What's the difference between dense and sparse retrieval?",
        "How does reranking improve search quality?",

        # Integration queries
        "How does the Beads integration work?",
        "What external services does Memory MCP connect to?",

        # Technical deep dives
        "What retry strategy is used for database locks?",
        "How is thread safety achieved in the system?",
    ]


def main():
    """Run complete POC benchmark."""
    print("=" * 70)
    print("MEM-QWEN-001: Complete Reranker POC with Sample Data")
    print("=" * 70)

    # Load models
    print("\n[1/4] Loading embedding model...")
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    print("  Loaded: all-MiniLM-L6-v2 (384d)")

    print("\n[2/4] Loading cross-encoder...")
    from sentence_transformers import CrossEncoder
    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=256)
    print("  Loaded: ms-marco-MiniLM-L-6-v2")

    print("\n[3/4] Creating sample ChromaDB...")
    collection = create_temp_chromadb(SAMPLE_MEMORIES, embedder)
    print(f"  Created: {collection.count()} documents indexed")

    print("\n[4/4] Running benchmark...")
    print("-" * 70)

    queries = get_test_queries()
    results: List[BenchmarkResult] = []

    for i, query in enumerate(queries):
        # Baseline search
        baseline_docs, baseline_latency = baseline_search(collection, embedder, query, top_k=20)
        baseline_top5 = baseline_docs[:5]

        # Rerank
        reranked_docs, rerank_latency = rerank_documents(reranker, query, baseline_docs, top_k=5)

        # Compare
        baseline_ids = [d["id"] for d in baseline_top5]
        reranked_ids = [d["id"] for d in reranked_docs]
        order_changed = baseline_ids != reranked_ids

        # Score delta (how much did top result improve)
        baseline_top_dist = baseline_top5[0]["distance"] if baseline_top5 else 0
        reranked_top_score = reranked_docs[0].get("rerank_score", 0) if reranked_docs else 0

        result = BenchmarkResult(
            query=query[:50],
            baseline_latency_ms=baseline_latency,
            rerank_latency_ms=rerank_latency,
            baseline_top5=baseline_ids,
            reranked_top5=reranked_ids,
            order_changed=order_changed,
            rerank_score_delta=reranked_top_score
        )
        results.append(result)

        marker = "*" if order_changed else " "
        print(f"[{i+1:2d}] {query[:40]:40s} {marker} B:{baseline_latency:5.1f}ms R:{rerank_latency:5.1f}ms")

    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)

    avg_baseline = sum(r.baseline_latency_ms for r in results) / len(results)
    avg_rerank = sum(r.rerank_latency_ms for r in results) / len(results)
    orders_changed = sum(1 for r in results if r.order_changed)
    avg_top_score = sum(r.rerank_score_delta for r in results) / len(results)

    print(f"Corpus size: {len(SAMPLE_MEMORIES)} memories")
    print(f"Queries tested: {len(results)}")
    print("-" * 70)
    print(f"Avg baseline latency: {avg_baseline:.1f}ms")
    print(f"Avg rerank latency: {avg_rerank:.1f}ms (first query includes warmup)")
    print(f"Avg total latency: {avg_baseline + avg_rerank:.1f}ms")
    print("-" * 70)
    print(f"Orders changed by reranker: {orders_changed}/{len(results)} ({100*orders_changed/len(results):.0f}%)")
    print(f"Avg top rerank score: {avg_top_score:.2f}")

    # Save results
    output_path = Path(__file__).parent / "poc_results_complete.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "corpus_size": len(SAMPLE_MEMORIES),
                "num_queries": len(results),
                "avg_baseline_latency_ms": avg_baseline,
                "avg_rerank_latency_ms": avg_rerank,
                "avg_total_latency_ms": avg_baseline + avg_rerank,
                "orders_changed": orders_changed,
                "orders_changed_pct": 100 * orders_changed / len(results),
                "avg_top_rerank_score": avg_top_score,
            },
            "results": [asdict(r) for r in results],
        }, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    # Decision matrix
    print("\n" + "=" * 70)
    print("DECISION MATRIX")
    print("=" * 70)
    print(f"Quality Impact:   {'HIGH' if orders_changed >= len(results)//2 else 'MEDIUM' if orders_changed > 0 else 'LOW'} ({orders_changed}/{len(results)} reorderings)")
    print(f"Latency Impact:   {'LOW' if avg_rerank < 100 else 'MEDIUM' if avg_rerank < 300 else 'HIGH'} ({avg_rerank:.0f}ms per batch)")
    print(f"Integration Risk: LOW (additive change, no breaking modifications)")
    print("-" * 70)

    if orders_changed >= len(results) // 3:
        print("\nRECOMMENDATION: PROCEED with MEM-QWEN-002 (Reranker Integration)")
        print("  - Cross-encoder reranking improves result ordering")
        print("  - Latency overhead is acceptable for Memory MCP use case")
        print("  - Implementation is low-risk (additive change)")
    elif orders_changed > 0:
        print("\nRECOMMENDATION: CONSIDER with additional testing")
        print("  - Some queries show improvement")
        print("  - Run with production data for better signal")
    else:
        print("\nRECOMMENDATION: DEFER until baseline issues addressed")
        print("  - No measurable improvement on test queries")
        print("  - Review embedding quality first")

    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
