#!/usr/bin/env python3
"""
Memory MCP CLI - Simple interface for storing and recalling memories.

Usage:
    python memory_cli.py store "Text to store" --project "my-project" --who "agent-name" --why "reason"
    python memory_cli.py recall "search query" --top-k 5
    python memory_cli.py stats

Examples:
    # Store a reflection
    python memory_cli.py store "REFLECTION: code-review - Learned to check imports first" --project dnyoussef-portfolio --who reflect-skill --why session-learning

    # Recall related memories
    python memory_cli.py recall "code review patterns" --top-k 10

    # Get stats
    python memory_cli.py stats
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def get_config():
    """Load configuration."""
    import yaml
    config_path = Path(__file__).parent.parent / "config" / "memory-mcp.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def store_memory(
    text: str,
    project: str = "default",
    who: str = "memory-cli",
    why: str = "manual-entry",
    namespace: Optional[str] = None
) -> Dict[str, Any]:
    """
    Store a memory in ChromaDB with proper tagging.

    Args:
        text: The text content to store
        project: Project name for tagging
        who: Agent/source identifier
        why: Intent/reason for storage
        namespace: Optional namespace for categorization

    Returns:
        Dict with storage result
    """
    import chromadb
    from chromadb.config import Settings
    import hashlib

    config = get_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    # Initialize ChromaDB
    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )

    collection = client.get_or_create_collection(name=collection_name)

    # Generate ID
    timestamp = datetime.now().isoformat()
    doc_id = hashlib.md5(f"{text}{timestamp}".encode()).hexdigest()[:16]

    # Build metadata with WHO/WHEN/PROJECT/WHY protocol
    metadata = {
        "WHO": who,
        "WHEN": timestamp,
        "PROJECT": project,
        "WHY": why,
        "namespace": namespace or f"{project}/{why}",
        "category": why,
        "text_length": len(text)
    }

    # Store
    collection.add(
        documents=[text],
        metadatas=[metadata],
        ids=[doc_id]
    )

    return {
        "success": True,
        "id": doc_id,
        "timestamp": timestamp,
        "text_preview": text[:100] + "..." if len(text) > 100 else text
    }


def recall_memory(
    query: str,
    top_k: int = 5,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    Recall memories matching a query.

    Args:
        query: Search query text
        top_k: Number of results to return
        project: Optional project filter

    Returns:
        Dict with matching memories
    """
    import chromadb
    from chromadb.config import Settings

    config = get_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    # Initialize ChromaDB
    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        return {"success": False, "error": "Collection not found", "results": []}

    # Build filter if project specified
    where_filter = None
    if project:
        where_filter = {"PROJECT": project}

    # Query
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )

    # Format results
    formatted = []
    for i, doc in enumerate(results.get("documents", [[]])[0]):
        metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
        distance = results.get("distances", [[]])[0][i] if results.get("distances") else 0

        formatted.append({
            "id": results.get("ids", [[]])[0][i] if results.get("ids") else f"doc_{i}",
            "text": doc[:500] + "..." if len(doc) > 500 else doc,
            "score": 1 - distance,  # Convert distance to similarity
            "project": metadata.get("PROJECT", "unknown"),
            "who": metadata.get("WHO", "unknown"),
            "when": metadata.get("WHEN", "unknown"),
            "why": metadata.get("WHY", "unknown")
        })

    return {
        "success": True,
        "query": query,
        "count": len(formatted),
        "results": formatted
    }


def get_stats() -> Dict[str, Any]:
    """Get memory statistics."""
    import chromadb
    from chromadb.config import Settings

    config = get_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )

    collections = client.list_collections()
    stats = {
        "success": True,
        "collections": []
    }

    for c in collections:
        count = c.count()
        stats["collections"].append({
            "name": c.name,
            "count": count
        })

    # Also check graph
    graph_file = Path(config['storage']['data_dir']) / "graph.json"
    if graph_file.exists():
        import json
        with open(graph_file) as f:
            graph_data = json.load(f)
            stats["graph"] = {
                "nodes": len(graph_data.get("nodes", [])),
                "edges": len(graph_data.get("links", []))
            }

    return stats


def main():
    parser = argparse.ArgumentParser(description="Memory MCP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Store command
    store_parser = subparsers.add_parser("store", help="Store a memory")
    store_parser.add_argument("text", help="Text content to store")
    store_parser.add_argument("--project", default="default", help="Project name")
    store_parser.add_argument("--who", default="memory-cli", help="Agent/source identifier")
    store_parser.add_argument("--why", default="manual-entry", help="Intent/reason")
    store_parser.add_argument("--namespace", help="Optional namespace")

    # Recall command
    recall_parser = subparsers.add_parser("recall", help="Recall memories")
    recall_parser.add_argument("query", help="Search query")
    recall_parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    recall_parser.add_argument("--project", help="Filter by project")

    # Stats command
    subparsers.add_parser("stats", help="Get memory statistics")

    args = parser.parse_args()

    import json

    if args.command == "store":
        result = store_memory(
            args.text,
            project=args.project,
            who=args.who,
            why=args.why,
            namespace=args.namespace
        )
    elif args.command == "recall":
        result = recall_memory(
            args.query,
            top_k=args.top_k,
            project=args.project
        )
    elif args.command == "stats":
        result = get_stats()

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
