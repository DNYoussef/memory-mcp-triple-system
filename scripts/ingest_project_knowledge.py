"""
Ingest Project Knowledge into Memory-MCP Triple System

Indexes documentation from:
1. Memory-MCP Triple System (self-reference)
2. Claude Code Plugins (ruv-sparc-three-loop-system)
3. Terminal Manager
4. Connascence Analyzer

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import os
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import hashlib

# Fix Windows encoding issues BEFORE any imports
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Project paths
PROJECTS = {
    "memory-mcp": {
        "path": Path("C:/Users/17175/Desktop/memory-mcp-triple-system"),
        "description": "Memory-MCP Triple System - 3-tier RAG with Vector/Graph/Bayesian",
        "doc_patterns": ["docs/**/*.md", "README.md", "CLAUDE.md"],
    },
    "claude-code-plugins": {
        "path": Path("C:/Users/17175/claude-code-plugins/ruv-sparc-three-loop-system"),
        "description": "Claude Code Plugins - SPARC methodology, agents, playbooks",
        "doc_patterns": ["docs/**/*.md", "agents/**/*.md", "README.md"],
    },
    "terminal-manager": {
        "path": Path("C:/Users/17175/terminal-manager"),
        "description": "Terminal Manager - Multi-terminal orchestration dashboard",
        "doc_patterns": ["**/*.md", "backend/**/*.md", "frontend/**/*.md"],
    },
    "connascence-analyzer": {
        "path": Path("C:/Users/17175/Desktop/connascence"),
        "description": "Connascence Analyzer - Code quality analysis MCP server",
        "doc_patterns": ["docs/**/*.md", "README.md", "CLAUDE.md"],
    },
}


def find_docs(project_path: Path, patterns: List[str]) -> List[Path]:
    """Find all documentation files matching patterns."""
    docs = []
    for pattern in patterns:
        found = list(project_path.glob(pattern))
        docs.extend(found)
    # Deduplicate and filter
    seen = set()
    unique = []
    for doc in docs:
        if doc.is_file() and doc not in seen:
            seen.add(doc)
            unique.append(doc)
    return unique


def chunk_document(text: str, file_path: str, max_chars: int = 1500) -> List[Dict[str, Any]]:
    """Split document into chunks for embedding. NASA Rule 10: 28 LOC"""
    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""
    chunk_index = 0

    for para in paragraphs:
        if len(current_chunk) + len(para) > max_chars and current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "file_path": file_path,
                "chunk_index": chunk_index,
            })
            chunk_index += 1
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "file_path": file_path,
            "chunk_index": chunk_index,
        })

    return chunks


def compute_doc_hash(text: str) -> str:
    """Compute hash for deduplication."""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def ingest_project(
    project_name: str,
    project_config: Dict[str, Any],
    indexer,
    embedder
) -> Dict[str, int]:
    """Ingest a single project's documentation. NASA Rule 10: 45 LOC"""
    project_path = project_config["path"]
    description = project_config["description"]
    patterns = project_config["doc_patterns"]

    if not project_path.exists():
        logger.warning(f"Project path not found: {project_path}")
        return {"files": 0, "chunks": 0}

    docs = find_docs(project_path, patterns)
    logger.info(f"Found {len(docs)} docs for {project_name}")

    all_chunks = []
    all_embeddings = []

    for doc_path in docs:
        try:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
            if len(text) < 50:
                continue

            rel_path = str(doc_path.relative_to(project_path))
            chunks = chunk_document(text, f"{project_name}/{rel_path}")

            for chunk in chunks:
                chunk["metadata"] = {
                    "project": project_name,
                    "project_description": description,
                    "doc_hash": compute_doc_hash(chunk["text"]),
                    "ingested_at": datetime.utcnow().isoformat(),
                    "source": "project_knowledge_ingestion",
                }
                all_chunks.append(chunk)

        except Exception as e:
            logger.warning(f"Failed to read {doc_path}: {e}")
            continue

    if not all_chunks:
        return {"files": len(docs), "chunks": 0}

    # Generate embeddings and index in batches (ChromaDB max batch ~5000)
    chroma_batch_size = 2000
    embed_batch_size = 32

    for batch_start in range(0, len(all_chunks), chroma_batch_size):
        batch_chunks = all_chunks[batch_start:batch_start + chroma_batch_size]
        batch_embeddings = []

        # Generate embeddings in smaller batches
        for i in range(0, len(batch_chunks), embed_batch_size):
            embed_batch = batch_chunks[i:i + embed_batch_size]
            texts = [c["text"] for c in embed_batch]
            embeddings = embedder.encode(texts)
            batch_embeddings.extend([e.tolist() for e in embeddings])

        # Index this batch
        indexer.index_chunks(batch_chunks, batch_embeddings)
        logger.info(f"  Indexed batch {batch_start//chroma_batch_size + 1}: {len(batch_chunks)} chunks")

    return {"files": len(docs), "chunks": len(all_chunks)}


def main():
    """Main ingestion entry point."""
    from src.indexing.vector_indexer import VectorIndexer
    from src.indexing.embedding_pipeline import EmbeddingPipeline

    logger.info("Starting project knowledge ingestion")

    # Initialize components
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    indexer = VectorIndexer(persist_directory=persist_dir)
    embedder = EmbeddingPipeline()

    total_files = 0
    total_chunks = 0

    for project_name, config in PROJECTS.items():
        logger.info(f"Ingesting: {project_name}")
        result = ingest_project(project_name, config, indexer, embedder)
        total_files += result["files"]
        total_chunks += result["chunks"]
        logger.info(f"  -> {result['files']} files, {result['chunks']} chunks")

    logger.info(f"Ingestion complete: {total_files} files, {total_chunks} chunks")

    # Verify with a test query
    query = "How does the Memory-MCP triple system work?"
    query_embedding = embedder.encode([query])[0]
    results = indexer.search_similar(query_embedding.tolist(), top_k=3)

    logger.info("Test query results:")
    for r in results:
        logger.info(f"  - {r.get('file_path', 'unknown')}: {r.get('document', '')[:100]}...")

    return {"total_files": total_files, "total_chunks": total_chunks}


if __name__ == "__main__":
    result = main()
    print(f"\nIngestion Summary:")
    print(f"  Total files processed: {result['total_files']}")
    print(f"  Total chunks indexed: {result['total_chunks']}")
