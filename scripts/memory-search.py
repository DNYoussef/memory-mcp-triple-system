#!/usr/bin/env python3
"""
Memory Search Wrapper
Search memory using semantic similarity with mode detection.

Usage:
    python memory-search.py --query "authentication patterns" --namespace "chrome-ext" --limit 10
"""

import argparse
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indexing.embedding_pipeline import EmbeddingPipeline
from src.indexing.vector_indexer import VectorIndexer
from src.modes.mode_detector import ModeDetector


def search_memory(query: str, namespace: str = None, limit: int = 5, verbose: bool = False):
    """
    Search memory using semantic similarity.

    Args:
        query: Search query text
        namespace: Optional namespace filter
        limit: Number of results
        verbose: Print detailed information

    Returns:
        List of search results
    """
    # Initialize components
    embedder = EmbeddingPipeline()
    indexer = VectorIndexer(persist_directory="./chroma_data")
    indexer.create_collection()  # Initialize collection
    detector = ModeDetector()

    # Detect mode
    mode_profile, confidence = detector.detect(query)

    if verbose:
        print(f"[SEARCH] Query: {query}")
        print(f"[MODE] Mode: {mode_profile.name} (confidence: {confidence:.2f})")
        print(f"[RESULTS] Results: {limit}")
        if namespace:
            print(f"[NAMESPACE] Namespace: {namespace}")
        print()

    # Generate query embedding
    query_embedding = embedder.encode_single(query)

    # Build filter
    where_filter = {}
    if namespace:
        where_filter['namespace'] = namespace

    # Search
    search_results = indexer.collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=limit,
        where=where_filter if where_filter else None
    )

    # Format results
    results = []
    if search_results['ids'] and len(search_results['ids'][0]) > 0:
        for i in range(len(search_results['ids'][0])):
            metadata = search_results['metadatas'][0][i]
            result = {
                'text': search_results['documents'][0][i],
                'file_path': metadata.get('file_path', ''),
                'score': 1.0 - search_results['distances'][0][i],
                'metadata': metadata
            }
            results.append(result)

            if verbose:
                print(f"Result {i+1}:")
                print(f"  Score: {result['score']:.4f}")
                print(f"  File: {result['file_path']}")
                print(f"  Text: {result['text'][:200]}{'...' if len(result['text']) > 200 else ''}")
                print()

    if not verbose:
        # Print JSON for programmatic use
        print(json.dumps(results, indent=2))

    return results


def main():
    parser = argparse.ArgumentParser(description="Search memory using semantic similarity")
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--namespace", help="Filter by namespace")
    parser.add_argument("--limit", type=int, default=5, help="Number of results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        search_memory(args.query, args.namespace, args.limit, args.verbose)
    except Exception as e:
        print(f"[ERROR] Error searching memory: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
