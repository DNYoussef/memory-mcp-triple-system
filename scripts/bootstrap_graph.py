#!/usr/bin/env python3
"""
Bootstrap Graph from Existing ChromaDB Memories

Processes all existing memories in ChromaDB to extract entities and build
the knowledge graph for HippoRAG and Bayesian tiers.

Usage:
    python scripts/bootstrap_graph.py [--batch-size 100] [--limit 0]
"""

import sys
import argparse
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.graph_service import GraphService
from services.entity_service import EntityService


def get_chromadb_client(chroma_dir: Path):
    """Get ChromaDB client."""
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    return client


def get_all_memories(client, collection_name: str = "memory_mcp", limit: int = 0) -> List[Dict[str, Any]]:
    """Retrieve all memories from ChromaDB."""
    try:
        collection = client.get_collection(collection_name)
        count = collection.count()
        logger.info(f"Found {count} memories in collection '{collection_name}'")

        # Get all documents
        if limit > 0:
            results = collection.get(limit=limit, include=["documents", "metadatas"])
        else:
            results = collection.get(include=["documents", "metadatas"])

        memories = []
        for i, doc in enumerate(results.get("documents", [])):
            memories.append({
                "id": results["ids"][i] if results.get("ids") else f"doc_{i}",
                "text": doc,
                "metadata": results["metadatas"][i] if results.get("metadatas") else {}
            })

        return memories

    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        return []


def bootstrap_graph(
    data_dir: Path,
    chroma_dir: Path,
    collection_name: str = "memory_chunks",
    batch_size: int = 100,
    limit: int = 0
) -> Dict[str, int]:
    """
    Bootstrap graph from existing ChromaDB memories.

    Args:
        data_dir: Data directory for graph storage
        chroma_dir: ChromaDB directory
        collection_name: ChromaDB collection name
        batch_size: Number of memories to process before saving
        limit: Max memories to process (0 = all)

    Returns:
        Stats dict with nodes_added, edges_added, errors
    """
    stats = {
        "memories_processed": 0,
        "chunks_added": 0,
        "entities_added": 0,
        "edges_added": 0,
        "errors": 0
    }

    # Initialize services
    logger.info("Initializing services...")
    graph_service = GraphService(data_dir=str(data_dir))
    entity_service = EntityService()

    # Load existing graph if present
    graph_file = data_dir / "graph.json"
    if graph_file.exists():
        graph_service.load_graph(graph_file)
        logger.info(f"Loaded existing graph: {graph_service.get_node_count()} nodes")

    # Get ChromaDB client and memories
    client = get_chromadb_client(chroma_dir)
    memories = get_all_memories(client, collection_name=collection_name, limit=limit)
    total = len(memories)
    logger.info(f"Processing {total} memories...")

    # Track existing entities to avoid duplicates
    existing_entities = set()
    for node_id in graph_service.graph.nodes():
        node_data = graph_service.get_node(node_id)
        if node_data and node_data.get("type") == "entity":
            existing_entities.add(node_id)

    # Process memories in batches
    for i, memory in enumerate(memories):
        try:
            text = memory.get("text", "")
            if not text or len(text.strip()) < 10:
                continue

            # Generate chunk_id
            chunk_id = hashlib.md5(text.encode()).hexdigest()[:16]

            # Check if chunk already exists
            if graph_service.get_node(chunk_id):
                continue

            # Extract entities
            entities = entity_service.extract_entities(text)
            if not entities:
                continue

            # Add chunk node
            graph_service.add_chunk_node(chunk_id, {
                "text": text[:500],
                "file_path": memory.get("metadata", {}).get("key", "chromadb"),
                "memory_id": memory.get("id")
            })
            stats["chunks_added"] += 1

            # Add entities and relationships
            for ent in entities:
                entity_id = ent["text"].lower().replace(" ", "_")

                # Add entity node if new
                if entity_id not in existing_entities:
                    graph_service.add_entity_node(
                        entity_id,
                        ent["type"],
                        {"text": ent["text"], "start": ent["start"], "end": ent["end"]}
                    )
                    existing_entities.add(entity_id)
                    stats["entities_added"] += 1

                # Add mention relationship
                graph_service.add_relationship(
                    chunk_id,
                    GraphService.EDGE_MENTIONS,
                    entity_id,
                    {"entity_type": ent["type"], "position": ent["start"], "confidence": 0.8}
                )
                stats["edges_added"] += 1

            stats["memories_processed"] += 1

            # Save periodically
            if (i + 1) % batch_size == 0:
                graph_service.save_graph()
                logger.info(
                    f"Progress: {i + 1}/{total} ({100 * (i + 1) // total}%) - "
                    f"Chunks: {stats['chunks_added']}, Entities: {stats['entities_added']}, Edges: {stats['edges_added']}"
                )

        except Exception as e:
            logger.error(f"Error processing memory {i}: {e}")
            stats["errors"] += 1

    # Final save
    graph_service.save_graph()
    logger.info(f"Graph saved to {graph_file}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Bootstrap graph from ChromaDB")
    parser.add_argument("--data-dir", type=str, default="./data", help="Data directory for graph")
    parser.add_argument("--chroma-dir", type=str, default="./chroma_data", help="ChromaDB directory")
    parser.add_argument("--collection", type=str, default="memory_chunks", help="Collection name")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for saves")
    parser.add_argument("--limit", type=int, default=0, help="Max memories (0 = all)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    chroma_dir = Path(args.chroma_dir)

    if not chroma_dir.exists():
        logger.error(f"ChromaDB directory not found: {chroma_dir}")
        sys.exit(1)

    data_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Memory MCP Graph Bootstrap")
    logger.info("=" * 60)

    stats = bootstrap_graph(data_dir, chroma_dir, args.collection, args.batch_size, args.limit)

    logger.info("=" * 60)
    logger.info("Bootstrap Complete!")
    logger.info(f"  Memories processed: {stats['memories_processed']}")
    logger.info(f"  Chunks added: {stats['chunks_added']}")
    logger.info(f"  Entities added: {stats['entities_added']}")
    logger.info(f"  Edges added: {stats['edges_added']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
