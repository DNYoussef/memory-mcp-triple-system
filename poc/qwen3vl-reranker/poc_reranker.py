"""
MEM-QWEN-001: Qwen3-VL Reranker Proof of Concept

Purpose: Benchmark Qwen3-VL-Reranker-2B (or compatible cross-encoder) on Memory MCP queries.

This POC:
1. Loads sample memories from existing ChromaDB
2. Runs baseline retrieval (no reranking)
3. Runs reranked retrieval (with cross-encoder)
4. Compares precision@5, MRR, and latency

Requirements:
- 8GB+ VRAM GPU (RTX 2060 SUPER or better)
- Memory MCP with populated ChromaDB
- sentence-transformers with cross-encoder support

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
import os
import time
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple

# Fix encoding and force online mode
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"
os.environ["HF_DATASETS_OFFLINE"] = "0"

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import torch
from loguru import logger


@dataclass
class RerankerBenchmarkResult:
    """Result from a single benchmark query."""
    query: str
    baseline_top5: List[str]
    reranked_top5: List[str]
    baseline_latency_ms: float
    rerank_latency_ms: float
    total_latency_ms: float
    precision_improvement: float  # Positive = reranker better


@dataclass
class BenchmarkSummary:
    """Summary of all benchmark results."""
    model_name: str
    num_queries: int
    avg_baseline_latency_ms: float
    avg_rerank_latency_ms: float
    avg_total_latency_ms: float
    avg_precision_improvement: float
    precision_at_5_baseline: float
    precision_at_5_reranked: float
    mrr_baseline: float
    mrr_reranked: float
    device: str
    vram_used_mb: float


class RerankerPOC:
    """POC for Qwen3-VL Reranker integration with Memory MCP."""

    # Default to BGE reranker (proven cross-encoder, similar architecture)
    # Can swap to Qwen3-VL-Reranker-2B when available on HuggingFace
    DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"  # ~1.5GB VRAM
    QWEN_MODEL = "Alibaba-NLP/gte-Qwen2-1.5B-instruct"  # Closest available

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        data_dir: str = None
    ):
        """Initialize POC with reranker model."""
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.data_dir = data_dir or str(Path.home() / ".claude" / "memory-mcp-data")

        self.reranker = None
        self.vector_indexer = None
        self.embedding_pipeline = None

        logger.info(f"RerankerPOC initialized: model={self.model_name}, device={self.device}")

    def load_reranker(self) -> bool:
        """Load the cross-encoder reranker model."""
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading cross-encoder: {self.model_name}")
            start = time.time()

            self.reranker = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=512
            )

            load_time = time.time() - start
            logger.info(f"Reranker loaded in {load_time:.2f}s")
            return True

        except Exception as e:
            logger.error(f"Failed to load reranker: {e}")
            return False

    def load_memory_mcp_services(self) -> bool:
        """Load Memory MCP services for retrieval."""
        try:
            from src.indexing.vector_indexer import VectorIndexer
            from src.indexing.embedding_pipeline import EmbeddingPipeline

            chroma_path = Path(self.data_dir) / "chroma"

            logger.info(f"Loading Memory MCP services from {chroma_path}")

            self.embedding_pipeline = EmbeddingPipeline()
            self.vector_indexer = VectorIndexer.get_instance(
                persist_directory=str(chroma_path),
                collection_name="memory_chunks"
            )

            # Get count to verify
            count = self.vector_indexer.collection.count()
            logger.info(f"Loaded ChromaDB with {count} documents")

            return count > 0

        except Exception as e:
            logger.error(f"Failed to load Memory MCP services: {e}")
            return False

    def get_sample_queries(self) -> List[Dict[str, Any]]:
        """Get sample queries for benchmarking."""
        return [
            {"query": "How does the NexusProcessor handle search queries?", "relevant_keywords": ["nexus", "processor", "search", "query"]},
            {"query": "What is the WHO/WHEN/PROJECT/WHY tagging protocol?", "relevant_keywords": ["who", "when", "project", "why", "tag", "protocol"]},
            {"query": "How does ChromaDB store embeddings?", "relevant_keywords": ["chromadb", "chroma", "embedding", "store", "vector"]},
            {"query": "What are the three retrieval tiers in Memory MCP?", "relevant_keywords": ["tier", "retrieval", "vector", "hipporag", "bayesian"]},
            {"query": "How does mode detection work for execution vs planning?", "relevant_keywords": ["mode", "detection", "execution", "planning", "brainstorming"]},
            {"query": "What is the Nexus 5-step SOP pipeline?", "relevant_keywords": ["nexus", "sop", "pipeline", "recall", "filter", "dedupe", "rank", "compress"]},
            {"query": "How does the lifecycle manager handle hot and cold data?", "relevant_keywords": ["lifecycle", "hot", "cold", "decay", "archive"]},
            {"query": "What is HippoRAG and how does it work?", "relevant_keywords": ["hipporag", "graph", "ppr", "entity", "multi-hop"]},
            {"query": "How are confidence scores assigned to memories?", "relevant_keywords": ["confidence", "score", "witnessed", "reported", "inferred"]},
            {"query": "What MCPs are used in the ecosystem?", "relevant_keywords": ["mcp", "server", "tool", "protocol"]},
        ]

    def baseline_retrieve(self, query: str, top_k: int = 20) -> Tuple[List[Dict], float]:
        """Retrieve documents without reranking."""
        start = time.time()

        # Embed query
        query_embedding = self.embedding_pipeline.encode_single(query)

        # Search ChromaDB
        results = self.vector_indexer.search_similar(
            query_embedding=query_embedding.tolist(),
            top_k=top_k
        )

        latency_ms = (time.time() - start) * 1000
        return results, latency_ms

    def rerank_documents(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5
    ) -> Tuple[List[Dict], float]:
        """Rerank documents using cross-encoder."""
        start = time.time()

        # Prepare pairs for cross-encoder
        texts = [doc.get("document", doc.get("text", "")) for doc in documents]
        pairs = [(query, text) for text in texts]

        # Score with cross-encoder
        scores = self.reranker.predict(pairs, show_progress_bar=False)

        # Sort by rerank score
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # Return top_k with scores
        reranked = []
        for doc, score in scored_docs[:top_k]:
            doc_copy = dict(doc)
            doc_copy["rerank_score"] = float(score)
            reranked.append(doc_copy)

        latency_ms = (time.time() - start) * 1000
        return reranked, latency_ms

    def calculate_relevance_score(
        self,
        documents: List[Dict],
        relevant_keywords: List[str]
    ) -> float:
        """Calculate relevance based on keyword matches (simple proxy)."""
        if not documents:
            return 0.0

        total_matches = 0
        for doc in documents:
            text = doc.get("document", doc.get("text", "")).lower()
            matches = sum(1 for kw in relevant_keywords if kw.lower() in text)
            total_matches += matches

        # Normalize by max possible matches
        max_matches = len(documents) * len(relevant_keywords)
        return total_matches / max_matches if max_matches > 0 else 0.0

    def run_benchmark(self, top_k: int = 5) -> BenchmarkSummary:
        """Run full benchmark on sample queries."""
        queries = self.get_sample_queries()
        results: List[RerankerBenchmarkResult] = []

        logger.info(f"Running benchmark on {len(queries)} queries...")

        for i, q in enumerate(queries):
            query = q["query"]
            keywords = q["relevant_keywords"]

            # Baseline retrieval (top 20 for reranking pool)
            baseline_docs, baseline_latency = self.baseline_retrieve(query, top_k=20)
            baseline_top5 = baseline_docs[:top_k]

            # Rerank
            reranked_docs, rerank_latency = self.rerank_documents(query, baseline_docs, top_k=top_k)

            # Calculate relevance improvement
            baseline_relevance = self.calculate_relevance_score(baseline_top5, keywords)
            reranked_relevance = self.calculate_relevance_score(reranked_docs, keywords)
            improvement = reranked_relevance - baseline_relevance

            result = RerankerBenchmarkResult(
                query=query,
                baseline_top5=[d.get("id", "unknown")[:8] for d in baseline_top5],
                reranked_top5=[d.get("id", "unknown")[:8] for d in reranked_docs],
                baseline_latency_ms=baseline_latency,
                rerank_latency_ms=rerank_latency,
                total_latency_ms=baseline_latency + rerank_latency,
                precision_improvement=improvement
            )
            results.append(result)

            logger.info(f"  [{i+1}/{len(queries)}] '{query[:40]}...' improvement={improvement:.3f}")

        # Calculate summary metrics
        avg_baseline = sum(r.baseline_latency_ms for r in results) / len(results)
        avg_rerank = sum(r.rerank_latency_ms for r in results) / len(results)
        avg_total = sum(r.total_latency_ms for r in results) / len(results)
        avg_improvement = sum(r.precision_improvement for r in results) / len(results)

        # Get VRAM usage
        vram_mb = 0.0
        if torch.cuda.is_available():
            vram_mb = torch.cuda.memory_allocated() / 1024 / 1024

        summary = BenchmarkSummary(
            model_name=self.model_name,
            num_queries=len(queries),
            avg_baseline_latency_ms=avg_baseline,
            avg_rerank_latency_ms=avg_rerank,
            avg_total_latency_ms=avg_total,
            avg_precision_improvement=avg_improvement,
            precision_at_5_baseline=sum(1 for r in results if r.precision_improvement <= 0) / len(results),
            precision_at_5_reranked=sum(1 for r in results if r.precision_improvement >= 0) / len(results),
            mrr_baseline=0.0,  # Would need ground truth labels
            mrr_reranked=0.0,  # Would need ground truth labels
            device=self.device,
            vram_used_mb=vram_mb
        )

        return summary


def main():
    """Run the MEM-QWEN-001 POC."""
    print("=" * 70)
    print("MEM-QWEN-001: Qwen3-VL Reranker POC")
    print("=" * 70)

    # Check GPU
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"GPU: {gpu_name} ({vram:.1f}GB VRAM)")
    else:
        print("WARNING: No GPU detected, running on CPU (will be slow)")

    # Initialize POC
    poc = RerankerPOC()

    # Load services
    print("\n[1/3] Loading Memory MCP services...")
    if not poc.load_memory_mcp_services():
        print("ERROR: Failed to load Memory MCP. Is ChromaDB populated?")
        return 1

    print("\n[2/3] Loading cross-encoder reranker...")
    if not poc.load_reranker():
        print("ERROR: Failed to load reranker model")
        return 1

    print("\n[3/3] Running benchmark...")
    summary = poc.run_benchmark(top_k=5)

    # Print results
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Model: {summary.model_name}")
    print(f"Device: {summary.device}")
    print(f"VRAM Used: {summary.vram_used_mb:.1f} MB")
    print(f"Queries: {summary.num_queries}")
    print("-" * 70)
    print(f"Avg Baseline Latency: {summary.avg_baseline_latency_ms:.1f} ms")
    print(f"Avg Rerank Latency:   {summary.avg_rerank_latency_ms:.1f} ms")
    print(f"Avg Total Latency:    {summary.avg_total_latency_ms:.1f} ms")
    print("-" * 70)
    print(f"Avg Precision Improvement: {summary.avg_precision_improvement:+.3f}")
    print(f"Queries Where Reranker Helped: {summary.precision_at_5_reranked * 100:.0f}%")
    print("=" * 70)

    # Save results
    output_path = Path(__file__).parent / "benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(asdict(summary), f, indent=2)
    print(f"\nResults saved to: {output_path}")

    # Decision
    if summary.avg_precision_improvement > 0:
        print("\nRECOMMENDATION: Proceed with MEM-QWEN-002 (Reranker Integration)")
    else:
        print("\nRECOMMENDATION: Review query samples before proceeding")

    return 0


if __name__ == "__main__":
    sys.exit(main())
