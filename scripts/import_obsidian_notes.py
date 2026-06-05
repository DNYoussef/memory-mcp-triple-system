#!/usr/bin/env python3
"""
Import Obsidian Notes to ChromaDB

VEC-001: Create import script for stable Obsidian notes.

Purpose:
- Scan Obsidian vault for stable notes (exclude daily/journal)
- Extract text and metadata
- Generate embeddings and index in ChromaDB
- Expected: ~200-300 documents

Usage:
    python scripts/import_obsidian_notes.py --vault-path /path/to/vault --dry-run
    python scripts/import_obsidian_notes.py --vault-path /path/to/vault --apply

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import argparse
import re
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Patterns to exclude (daily notes, journals, templates)
EXCLUDE_PATTERNS = [
    r"daily[/-]",
    r"journal[/-]",
    r"template[s]?[/-]",
    r"\d{4}-\d{2}-\d{2}",  # Date-named files like 2026-01-20.md
    r"inbox[/-]",
    r"archive[/-]trash",
    r"\.trash",
    r"_templates",
]

# Minimum content length to import
MIN_CONTENT_LENGTH = 100

# Maximum content length (truncate)
MAX_CONTENT_LENGTH = 10000


def should_exclude(file_path: Path) -> bool:
    """
    Check if file should be excluded from import.

    Args:
        file_path: Path to check

    Returns:
        True if should exclude

    NASA Rule 10: 12 LOC (<=60)
    """
    path_str = str(file_path).lower().replace("\\", "/")

    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, path_str, re.IGNORECASE):
            return True

    return False


def extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter from markdown content.

    Args:
        content: Full markdown content

    Returns:
        (frontmatter_dict, content_without_frontmatter)

    NASA Rule 10: 25 LOC (<=60)
    """
    import yaml

    frontmatter = {}
    body = content

    # Check for YAML frontmatter (starts with ---)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
            except yaml.YAMLError:
                pass

    return frontmatter, body


def scan_vault(vault_path: Path) -> List[Path]:
    """
    Scan vault for markdown files to import.

    Args:
        vault_path: Path to Obsidian vault

    Returns:
        List of markdown file paths

    NASA Rule 10: 20 LOC (<=60)
    """
    if not vault_path.exists():
        logger.error(f"Vault path does not exist: {vault_path}")
        return []

    files = []
    for md_file in vault_path.rglob("*.md"):
        if should_exclude(md_file):
            logger.debug(f"Excluding: {md_file}")
            continue
        files.append(md_file)

    logger.info(f"Found {len(files)} stable notes in {vault_path}")
    return files


def process_note(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Process a single markdown note.

    Args:
        file_path: Path to markdown file

    Returns:
        Document dict or None if invalid

    NASA Rule 10: 40 LOC (<=60)
    """
    try:
        content = file_path.read_text(encoding="utf-8")

        # Extract frontmatter
        frontmatter, body = extract_frontmatter(content)

        # Check minimum length
        if len(body) < MIN_CONTENT_LENGTH:
            logger.debug(f"Skipping short note: {file_path}")
            return None

        # Truncate if needed
        if len(body) > MAX_CONTENT_LENGTH:
            body = body[:MAX_CONTENT_LENGTH] + "..."

        # Generate document ID from file path
        doc_id = hashlib.md5(str(file_path).encode()).hexdigest()[:16]

        # Extract title from frontmatter or filename
        title = frontmatter.get("title") or file_path.stem

        # Build metadata
        metadata = {
            "file_path": str(file_path),
            "title": title,
            "tags": frontmatter.get("tags", []),
            "created": frontmatter.get("created"),
            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            "is_fact": True,  # VEC-005 metadata
            "source": "obsidian",
        }

        return {
            "id": doc_id,
            "text": body,
            "metadata": metadata
        }

    except Exception as e:
        logger.error(f"Failed to process {file_path}: {e}")
        return None


def import_to_chromadb(
    documents: List[Dict[str, Any]],
    chroma_path: str,
    collection_name: str = "obsidian_notes",
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Import documents to ChromaDB.

    Args:
        documents: List of document dicts
        chroma_path: Path to ChromaDB directory
        collection_name: Collection name
        dry_run: If True, don't actually import

    Returns:
        Import report dict

    NASA Rule 10: 55 LOC (<=60)
    """
    from src.indexing.vector_indexer import VectorIndexer
    from src.services.embedding_pipeline import EmbeddingPipeline

    report = {
        "total_documents": len(documents),
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "dry_run": dry_run
    }

    if dry_run:
        logger.info(f"[DRY RUN] Would import {len(documents)} documents")
        report["imported"] = len(documents)
        return report

    # Initialize services
    indexer = VectorIndexer(
        persist_directory=chroma_path,
        collection_name=collection_name
    )

    embedder = EmbeddingPipeline()

    # Batch import
    batch_size = 50
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
                report["imported"] += 1

            logger.info(f"Imported batch {i//batch_size + 1}: {len(batch)} documents")

        except Exception as e:
            logger.error(f"Batch import failed: {e}")
            report["errors"] += len(batch)

    return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import Obsidian notes to ChromaDB"
    )
    parser.add_argument(
        "--vault-path",
        default=r"C:\Users\17175\OneDrive\ObsidianVault",
        help="Path to Obsidian vault"
    )
    parser.add_argument(
        "--chroma-path",
        default=r"C:\Users\17175\.claude\memory-mcp-data\chroma_data",
        help="Path to ChromaDB directory"
    )
    parser.add_argument(
        "--collection",
        default="obsidian_notes",
        help="ChromaDB collection name"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only report what would be imported (default: True)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually import documents (overrides --dry-run)"
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
    print(f"OBSIDIAN IMPORT {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print(f"{'='*60}")
    print(f"Vault: {args.vault_path}")
    print(f"ChromaDB: {args.chroma_path}")
    print(f"Collection: {args.collection}")
    print()

    # Scan vault
    vault_path = Path(args.vault_path)
    files = scan_vault(vault_path)

    if not files:
        print("No files found to import")
        return 1

    # Process notes
    documents = []
    for file_path in files:
        doc = process_note(file_path)
        if doc:
            documents.append(doc)

    print(f"Processed: {len(documents)} valid documents")
    print()

    # Show sample
    if documents:
        print("Sample documents:")
        for doc in documents[:5]:
            print(f"  - {doc['metadata']['title']} ({len(doc['text'])} chars)")
        print()

    # Import
    report = import_to_chromadb(
        documents=documents,
        chroma_path=args.chroma_path,
        collection_name=args.collection,
        dry_run=dry_run
    )

    # Print report
    print(f"\n{'='*60}")
    print("IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Total documents: {report['total_documents']}")
    print(f"Imported: {report['imported']}")
    print(f"Errors: {report['errors']}")
    print(f"Mode: {'DRY RUN' if report['dry_run'] else 'APPLIED'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
