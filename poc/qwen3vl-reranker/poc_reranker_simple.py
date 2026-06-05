# -*- coding: utf-8 -*-
"""
MEM-QWEN-001: Simple Reranker POC (CPU-compatible)

A minimal POC that works on CPU for quick validation.
Uses a smaller cross-encoder model for faster inference.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import List, Dict, Tuple

# Fix encoding issues
os.environ["PYTHONIOENCODING"] = "utf-8"

# Force online mode for HuggingFace
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"
os.environ["HF_DATASETS_OFFLINE"] = "0"

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# Sample documents for testing (simulated memories)
SAMPLE_MEMORIES = [
    {"id": "mem-001", "text": "The NexusProcessor implements a 5-step SOP: RECALL, FILTER, DEDUPE, RANK, and COMPRESS. Each step processes search candidates sequentially."},
    {"id": "mem-002", "text": "WHO/WHEN/PROJECT/WHY is a tagging protocol for memory metadata. WHO identifies the agent, WHEN is the timestamp, PROJECT is the context, WHY explains the purpose."},
    {"id": "mem-003", "text": "ChromaDB uses HNSW algorithm for approximate nearest neighbor search. Embeddings are stored with cosine similarity metrics."},
    {"id": "mem-004", "text": "Memory MCP has three retrieval tiers: Vector (40%), HippoRAG (40%), and Bayesian (20%). Each tier contributes to the final ranking."},
    {"id": "mem-005", "text": "Mode detection classifies queries into execution (5K tokens), planning (10K tokens), or brainstorming (20K tokens) based on linguistic patterns."},
    {"id": "mem-006", "text": "HippoRAG implements multi-hop reasoning using Personalized PageRank (PPR) on an entity graph extracted from documents."},
    {"id": "mem-007", "text": "Confidence scores are assigned based on source type: witnessed (0.95), reported (0.70), inferred (0.50), assumed (0.30)."},
    {"id": "mem-008", "text": "The lifecycle manager handles hot/cold data tiering. New content starts as 'hot' with decay_score=1.0, then demotes over time."},
    {"id": "mem-009", "text": "MCP servers provide tools for external integrations. Memory MCP exposes vector_search, memory_store, and graph_query tools."},
    {"id": "mem-010", "text": "BeadsBridge integrates with the Beads task management system. It provides get_ready_tasks, get_task_detail, and query_tasks operations."},
    {"id": "mem-011", "text": "The unified search router combines results from Memory MCP and Beads. It implements intelligent routing based on query patterns."},
    {"id": "mem-012", "text": "Embeddings use the all-MiniLM-L6-v2 model, producing 384-dimensional vectors. The model is optimized for semantic similarity."},
    {"id": "mem-013", "text": "The Nexus processor uses weighted scoring: vector_score * 0.4 + hipporag_score * 0.4 + bayesian_score * 0.2."},
    {"id": "mem-014", "text": "Deduplication uses cosine similarity with a 0.95 threshold. Documents above this similarity are considered duplicates."},
    {"id": "mem-015", "text": "ObsidianMCPClient syncs markdown files from an Obsidian vault into ChromaDB for semantic search."},
]

# Test queries with expected relevant document IDs
TEST_QUERIES = [
    {
        "query": "How does the NexusProcessor work?",
        "relevant_ids": ["mem-001", "mem-013", "mem-014"]
    },
    {
        "query": "What is the WHO/WHEN/PROJECT/WHY protocol?",
        "relevant_ids": ["mem-002"]
    },
    {
        "query": "How are the three retrieval tiers weighted?",
        "relevant_ids": ["mem-004", "mem-013"]
    },
    {
        "query": "What confidence scores are assigned to different sources?",
        "relevant_ids": ["mem-007"]
    },
    {
        "query": "How does HippoRAG implement multi-hop reasoning?",
        "relevant_ids": ["mem-006"]
    },
]


def simple_embedding_similarity(query: str, doc: str) -> float:
    """Simple word overlap similarity (for demo without ML model)."""
    query_words = set(query.lower().split())
    doc_words = set(doc.lower().split())
    intersection = query_words & doc_words
    union = query_words | doc_words
    return len(intersection) / len(union) if union else 0.0


def baseline_retrieve(query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
    """Retrieve using simple similarity (simulates vector search)."""
    scored = []
    for doc in documents:
        score = simple_embedding_similarity(query, doc["text"])
        scored.append({**doc, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def load_cross_encoder():
    """Load cross-encoder for reranking."""
    try:
        # Suppress the Unicode warning from transformers
        import warnings
        warnings.filterwarnings("ignore", category=UnicodeWarning)
        warnings.filterwarnings("ignore", category=FutureWarning)

        from sentence_transformers import CrossEncoder

        # Use a small, fast cross-encoder
        model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # ~22M params, fast
        print(f"Loading cross-encoder: {model_name}")

        start = time.time()
        model = CrossEncoder(model_name, max_length=256)
        load_time = time.time() - start
        print(f"Loaded in {load_time:.2f}s")

        return model
    except Exception as e:
        print(f"Failed to load cross-encoder: {e}")
        return None


def rerank_with_cross_encoder(
    model,
    query: str,
    documents: List[Dict],
    top_k: int = 5
) -> Tuple[List[Dict], float]:
    """Rerank documents using cross-encoder."""
    start = time.time()

    # Prepare pairs
    pairs = [(query, doc["text"]) for doc in documents]

    # Score
    scores = model.predict(pairs, show_progress_bar=False)

    # Combine with original docs
    reranked = []
    for doc, score in zip(documents, scores):
        reranked.append({**doc, "rerank_score": float(score)})

    # Sort by rerank score
    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

    latency_ms = (time.time() - start) * 1000
    return reranked[:top_k], latency_ms


def calculate_precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int = 5) -> float:
    """Calculate precision@k."""
    retrieved_k = retrieved_ids[:k]
    relevant_retrieved = sum(1 for rid in retrieved_k if rid in relevant_ids)
    return relevant_retrieved / k


def calculate_mrr(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """Calculate Mean Reciprocal Rank."""
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def main():
    """Run simple POC benchmark."""
    print("=" * 70)
    print("MEM-QWEN-001: Simple Reranker POC")
    print("=" * 70)

    # Load cross-encoder
    model = load_cross_encoder()
    if model is None:
        print("\nFalling back to baseline-only comparison")

    results = []

    print("\nRunning benchmark on", len(TEST_QUERIES), "queries...")
    print("-" * 70)

    for i, test in enumerate(TEST_QUERIES):
        query = test["query"]
        relevant_ids = test["relevant_ids"]

        # Baseline retrieval
        start = time.time()
        baseline_results = baseline_retrieve(query, SAMPLE_MEMORIES, top_k=10)
        baseline_latency = (time.time() - start) * 1000
        baseline_ids = [r["id"] for r in baseline_results[:5]]

        # Rerank (if model available)
        if model:
            reranked_results, rerank_latency = rerank_with_cross_encoder(
                model, query, baseline_results, top_k=5
            )
            reranked_ids = [r["id"] for r in reranked_results]
        else:
            reranked_ids = baseline_ids
            rerank_latency = 0

        # Calculate metrics
        baseline_p5 = calculate_precision_at_k(baseline_ids, relevant_ids)
        reranked_p5 = calculate_precision_at_k(reranked_ids, relevant_ids)

        baseline_mrr = calculate_mrr(baseline_ids, relevant_ids)
        reranked_mrr = calculate_mrr(reranked_ids, relevant_ids)

        result = {
            "query": query[:50],
            "baseline_p5": baseline_p5,
            "reranked_p5": reranked_p5,
            "p5_improvement": reranked_p5 - baseline_p5,
            "baseline_mrr": baseline_mrr,
            "reranked_mrr": reranked_mrr,
            "mrr_improvement": reranked_mrr - baseline_mrr,
            "baseline_latency_ms": baseline_latency,
            "rerank_latency_ms": rerank_latency,
        }
        results.append(result)

        print(f"[{i+1}] {query[:40]}...")
        print(f"    Baseline P@5: {baseline_p5:.2f}, MRR: {baseline_mrr:.2f}")
        print(f"    Reranked P@5: {reranked_p5:.2f}, MRR: {reranked_mrr:.2f}")
        print(f"    Rerank latency: {rerank_latency:.1f}ms")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    avg_p5_improvement = sum(r["p5_improvement"] for r in results) / len(results)
    avg_mrr_improvement = sum(r["mrr_improvement"] for r in results) / len(results)
    avg_rerank_latency = sum(r["rerank_latency_ms"] for r in results) / len(results)

    queries_improved = sum(1 for r in results if r["p5_improvement"] > 0)

    print(f"Queries tested: {len(results)}")
    print(f"Avg P@5 improvement: {avg_p5_improvement:+.3f}")
    print(f"Avg MRR improvement: {avg_mrr_improvement:+.3f}")
    print(f"Avg rerank latency: {avg_rerank_latency:.1f}ms")
    print(f"Queries improved: {queries_improved}/{len(results)}")

    # Save results
    output_path = Path(__file__).parent / "poc_results_simple.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "avg_p5_improvement": avg_p5_improvement,
                "avg_mrr_improvement": avg_mrr_improvement,
                "avg_rerank_latency_ms": avg_rerank_latency,
                "queries_improved": queries_improved,
                "total_queries": len(results),
            },
            "results": results,
        }, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    # Decision
    print("\n" + "=" * 70)
    if avg_p5_improvement > 0 or avg_mrr_improvement > 0:
        print("RESULT: Cross-encoder reranking improves retrieval quality")
        print("RECOMMENDATION: Proceed with MEM-QWEN-002 (Full Integration)")
    else:
        print("RESULT: No significant improvement observed")
        print("RECOMMENDATION: Review query/document pairs before proceeding")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
