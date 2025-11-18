#!/usr/bin/env python3
"""
Memory Store Wrapper
Store information in memory-mcp-triple-system with automatic layer assignment.

Usage:
    python memory-store.py --key "tech_stack" --value "React 18 with TypeScript" --namespace "chrome-ext" --layer "mid_term"
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indexing.embedding_pipeline import EmbeddingPipeline
from src.indexing.vector_indexer import VectorIndexer
from src.chunking.semantic_chunker import SemanticChunker


def store_memory(key: str, value: str, namespace: str = "default", layer: str = "mid_term", category: str = "general"):
    """
    Store memory in vector database.

    Args:
        key: Identifier for retrieval
        value: Content to store
        namespace: Namespace for organization
        layer: Memory layer (short_term, mid_term, long_term)
        category: Category tag
    """
    # Initialize components
    embedder = EmbeddingPipeline()
    indexer = VectorIndexer(persist_directory="./chroma_data")
    indexer.create_collection()

    # Create chunk with metadata
    chunks = [{
        'text': value,
        'file_path': f"{namespace}/{key}",
        'chunk_index': 0,
        'metadata': {
            'key': key,
            'namespace': namespace,
            'layer': layer,
            'category': category
        }
    }]

    # Generate embedding and index
    embeddings = embedder.encode([value])
    indexer.index_chunks(chunks, embeddings.tolist())

    print(f"✅ Stored memory: {key}")
    print(f"   Namespace: {namespace}")
    print(f"   Layer: {layer}")
    print(f"   Content: {value[:100]}{'...' if len(value) > 100 else ''}")


def main():
    parser = argparse.ArgumentParser(description="Store memory in vector database")
    parser.add_argument("--key", required=True, help="Memory key/identifier")
    parser.add_argument("--value", required=True, help="Content to store")
    parser.add_argument("--namespace", default="default", help="Namespace for organization")
    parser.add_argument("--layer", default="mid_term", choices=["short_term", "mid_term", "long_term"], help="Memory layer")
    parser.add_argument("--category", default="general", help="Category tag")

    args = parser.parse_args()

    try:
        store_memory(args.key, args.value, args.namespace, args.layer, args.category)
    except Exception as e:
        print(f"❌ Error storing memory: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
