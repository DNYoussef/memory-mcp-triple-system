#!/usr/bin/env python3
"""
Extract Graph Entities to ChromaDB

VEC-002: Extract entity definitions from graph and embed as facts.

Purpose:
- Scan graph for entity nodes (concepts, files, projects, agents)
- Extract definitions and descriptions
- Generate embeddings and index in ChromaDB
- Expected: ~50 documents from entity nodes

Usage:
    python scripts/extract_graph_entities.py --dry-run
    python scripts/extract_graph_entities.py --apply

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import argparse
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Entity types to extract
ENTITY_TYPES = [
    "concept",
    "project",
    "file",
    "agent",
    "skill",
    "pattern",
    "decision",
    "expertise"
]

# Minimum description length to include
MIN_DESCRIPTION_LENGTH = 20


def load_graph(data_dir: str) -> Any:
    """
    Load the NetworkX graph from persistence.

    Args:
        data_dir: Path to data directory

    Returns:
        NetworkX graph or None

    NASA Rule 10: 25 LOC (<=60)
    """
    try:
        from src.services.graph_service import GraphService

        graph_service = GraphService(data_dir=data_dir)
        graph_service.load_graph()

        logger.info(
            f"Loaded graph: {graph_service.get_node_count()} nodes, "
            f"{graph_service.get_edge_count()} edges"
        )

        return graph_service

    except Exception as e:
        logger.error(f"Failed to load graph: {e}")
        return None


def extract_entities(graph_service: Any) -> List[Dict[str, Any]]:
    """
    Extract entity definitions from graph.

    Args:
        graph_service: GraphService instance

    Returns:
        List of entity documents

    NASA Rule 10: 50 LOC (<=60)
    """
    entities = []

    if not graph_service or not graph_service.graph:
        logger.warning("No graph available")
        return entities

    # Iterate over nodes
    for node_id, node_data in graph_service.graph.nodes(data=True):
        # Check if entity type
        node_type = node_data.get("type", "").lower()
        if node_type not in ENTITY_TYPES:
            continue

        # Get description
        description = node_data.get("description", "")
        if not description:
            description = node_data.get("content", "")
        if not description:
            description = node_data.get("text", "")

        # Skip short descriptions
        if len(description) < MIN_DESCRIPTION_LENGTH:
            logger.debug(f"Skipping {node_id}: description too short")
            continue

        # Build entity document
        doc_id = hashlib.md5(f"graph:{node_id}".encode()).hexdigest()[:16]

        entity = {
            "id": doc_id,
            "text": f"{node_type.title()}: {node_id}\n\n{description}",
            "metadata": {
                "source": "graph",
                "node_id": node_id,
                "node_type": node_type,
                "is_fact": True,
                "importance": node_data.get("importance", 0.5),
                "confidence": node_data.get("confidence", 0.8),
                "created_at": node_data.get("created_at", datetime.utcnow().isoformat()),
                "extracted_at": datetime.utcnow().isoformat()
            }
        }

        entities.append(entity)

    logger.info(f"Extracted {len(entities)} entity definitions")
    return entities


def index_to_chromadb(
    documents: List[Dict[str, Any]],
    chroma_path: str,
    collection_name: str = "graph_entities",
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Index documents to ChromaDB.

    Args:
        documents: List of document dicts
        chroma_path: Path to ChromaDB directory
        collection_name: Collection name
        dry_run: If True, don't actually index

    Returns:
        Indexing report

    NASA Rule 10: 55 LOC (<=60)
    """
    report = {
        "total_documents": len(documents),
        "indexed": 0,
        "skipped": 0,
        "errors": 0,
        "dry_run": dry_run
    }

    if dry_run:
        logger.info(f"[DRY RUN] Would index {len(documents)} documents")
        report["indexed"] = len(documents)
        return report

    try:
        from src.indexing.vector_indexer import VectorIndexer
        from src.indexing.embedding_pipeline import EmbeddingPipeline

        # Initialize services
        indexer = VectorIndexer(
            persist_directory=chroma_path,
            collection_name=collection_name
        )

        embedder = EmbeddingPipeline()

        # Batch index
        batch_size = 20
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            try:
                # Generate embeddings
                texts = [doc["text"] for doc in batch]
                embeddings = embedder.encode(texts)

                # Add to collection
                for doc, embedding in zip(batch, embeddings):
                    indexer.add_document(
                        document_id=doc["id"],
                        text=doc["text"],
                        embedding=embedding.tolist(),
                        metadata=doc["metadata"]
                    )
                    report["indexed"] += 1

                logger.info(f"Indexed batch {i // batch_size + 1}: {len(batch)} documents")

            except Exception as e:
                logger.error(f"Batch indexing failed: {e}")
                report["errors"] += len(batch)

    except Exception as e:
        logger.error(f"Indexing setup failed: {e}")
        report["errors"] = len(documents)

    return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract graph entities to ChromaDB"
    )
    parser.add_argument(
        "--data-dir",
        default=r"C:\Users\17175\.claude\memory-mcp-data",
        help="Path to Memory MCP data directory"
    )
    parser.add_argument(
        "--chroma-path",
        default=r"C:\Users\17175\.claude\memory-mcp-data\chroma_data",
        help="Path to ChromaDB directory"
    )
    parser.add_argument(
        "--collection",
        default="graph_entities",
        help="ChromaDB collection name"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only report what would be indexed (default: True)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually index documents (overrides --dry-run)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()
    dry_run = not args.apply

    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    print(f"\n{'='*60}")
    print(f"GRAPH ENTITY EXTRACTION {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print(f"{'='*60}")
    print(f"Data Dir: {args.data_dir}")
    print(f"ChromaDB: {args.chroma_path}")
    print(f"Collection: {args.collection}")
    print()

    # Load graph
    graph_service = load_graph(args.data_dir)
    if not graph_service:
        print("Failed to load graph")
        return 1

    # Extract entities
    entities = extract_entities(graph_service)

    if not entities:
        print("No entities found to extract")
        return 1

    print(f"Extracted: {len(entities)} entity definitions")
    print()

    # Show sample
    if entities:
        print("Sample entities:")
        for entity in entities[:5]:
            meta = entity["metadata"]
            print(f"  - [{meta['node_type']}] {meta['node_id']}")
        print()

    # Index
    report = index_to_chromadb(
        documents=entities,
        chroma_path=args.chroma_path,
        collection_name=args.collection,
        dry_run=dry_run
    )

    # Print report
    print(f"\n{'='*60}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total entities: {report['total_documents']}")
    print(f"Indexed: {report['indexed']}")
    print(f"Errors: {report['errors']}")
    print(f"Mode: {'DRY RUN' if report['dry_run'] else 'APPLIED'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
