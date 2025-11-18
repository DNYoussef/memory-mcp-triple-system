#!/usr/bin/env python3
"""
Ingest SPARC Documentation into Memory System
Ingests all SPARC skills, commands, and documentation with proper metadata.

Usage:
    python ingest-sparc-docs.py --source-dir /path/to/ai-chrome-extension/.claude --verbose
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indexing.embedding_pipeline import EmbeddingPipeline
from src.indexing.vector_indexer import VectorIndexer
from src.chunking.semantic_chunker import SemanticChunker


def categorize_file(file_path: Path) -> Dict[str, str]:
    """Categorize file and determine metadata."""
    path_str = str(file_path)

    # Determine category and layer based on path
    if '/skills/' in path_str:
        category = 'sparc_skills'
        layer = 'long_term'
    elif '/commands/' in path_str:
        category = 'slash_commands'
        layer = 'long_term'
    elif '/agents/' in path_str:
        category = 'agent_registry'
        layer = 'long_term'
    elif 'README' in file_path.name:
        category = 'documentation'
        layer = 'long_term'
    elif 'SPARC' in file_path.name or 'INSTALLATION' in file_path.name:
        category = 'system_documentation'
        layer = 'long_term'
    elif 'QUICK-REFERENCE' in file_path.name:
        category = 'quick_reference'
        layer = 'long_term'
    else:
        category = 'general'
        layer = 'mid_term'

    # Extract namespace from path
    namespace = 'sparc'
    if '/skills/' in path_str:
        namespace = 'sparc/skills'
    elif '/commands/' in path_str:
        namespace = 'sparc/commands'
    elif '/agents/' in path_str:
        namespace = 'sparc/agents'

    return {
        'category': category,
        'layer': layer,
        'namespace': namespace
    }


def extract_frontmatter(content: str) -> Dict[str, Any]:
    """Extract YAML frontmatter from markdown files."""
    frontmatter = {}

    # Check for frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            # Simple key: value extraction
            for line in fm_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()

    return frontmatter


def ingest_file(file_path: Path, embedder: EmbeddingPipeline, indexer: VectorIndexer, chunker: SemanticChunker, verbose: bool = False) -> int:
    """
    Ingest a single file.

    Returns:
        Number of chunks indexed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            return 0

        # Get file metadata
        file_meta = categorize_file(file_path)

        # Extract frontmatter if markdown
        if file_path.suffix == '.md':
            frontmatter = extract_frontmatter(content)
            if frontmatter:
                file_meta.update(frontmatter)

        # Chunk the content
        chunks = chunker.chunk_text(content, str(file_path))

        if not chunks:
            return 0

        # Add metadata to all chunks
        for chunk in chunks:
            chunk['metadata'].update(file_meta)

        # Generate embeddings
        texts = [c['text'] for c in chunks]
        embeddings = embedder.encode(texts)

        # Index chunks
        indexer.index_chunks(chunks, embeddings.tolist())

        if verbose:
            print(f"[OK] Ingested: {file_path.name}")
            print(f"   Chunks: {len(chunks)}")
            print(f"   Category: {file_meta['category']}")
            print(f"   Namespace: {file_meta['namespace']}")

        return len(chunks)

    except Exception as e:
        print(f"[ERROR] Error ingesting {file_path}: {e}", file=sys.stderr)
        return 0


def ingest_directory(source_dir: Path, file_pattern: str = "*.md", verbose: bool = False) -> Dict[str, int]:
    """
    Ingest all matching files from directory.

    Returns:
        Statistics dictionary
    """
    # Initialize components
    embedder = EmbeddingPipeline()
    indexer = VectorIndexer(persist_directory="./chroma_data")
    indexer.create_collection()
    chunker = SemanticChunker(
        min_chunk_size=128,
        max_chunk_size=512,
        overlap=50
    )

    stats = {
        'files_processed': 0,
        'total_chunks': 0,
        'files_skipped': 0
    }

    # Find all matching files
    files = list(source_dir.rglob(file_pattern))

    if verbose:
        print(f"[SCAN] Found {len(files)} files matching '{file_pattern}'")
        print()

    # Process each file
    for file_path in files:
        # Skip certain directories
        skip_dirs = ['.git', '__pycache__', 'node_modules', 'dist', 'build']
        if any(skip_dir in str(file_path) for skip_dir in skip_dirs):
            stats['files_skipped'] += 1
            continue

        chunks = ingest_file(file_path, embedder, indexer, chunker, verbose)
        if chunks > 0:
            stats['files_processed'] += 1
            stats['total_chunks'] += chunks

    return stats


def main():
    parser = argparse.ArgumentParser(description="Ingest SPARC documentation into memory system")
    parser.add_argument("--source-dir", required=True, help="Source directory (e.g., .claude)")
    parser.add_argument("--pattern", default="*.md", help="File pattern to match")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        print(f"[ERROR] Source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[SPARC] Starting SPARC documentation ingestion")
    print(f"   Source: {source_dir}")
    print(f"   Pattern: {args.pattern}")
    print()

    try:
        stats = ingest_directory(source_dir, args.pattern, args.verbose)

        print()
        print("=" * 60)
        print("[COMPLETE] Ingestion Complete!")
        print(f"   Files processed: {stats['files_processed']}")
        print(f"   Total chunks: {stats['total_chunks']}")
        print(f"   Files skipped: {stats['files_skipped']}")
        print(f"   Average chunks/file: {stats['total_chunks'] / max(stats['files_processed'], 1):.1f}")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
