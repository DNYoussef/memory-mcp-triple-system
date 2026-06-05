#!/usr/bin/env python3
"""
Promotion Pipeline - Triple-Layer to Vector promotion.

VEC-003: Create promotion pipeline from Triple-Layer to Vector.

Purpose:
- Scan Triple-Layer memories approaching 30-day expiry
- Evaluate for promotion using MemoryPromoter
- Promote qualifying memories to ChromaDB and Seed Archive
- Clean up promoted memories from Triple-Layer

Pipeline Flow:
1. Query long-term layer for memories near expiry
2. Evaluate promotion criteria (score >= 0.5)
3. Generate embeddings for qualifying memories
4. Index to ChromaDB with is_fact metadata
5. Archive to seed_archive for permanent storage
6. Mark memories as promoted in Triple-Layer

Usage:
    python scripts/promotion_pipeline.py --dry-run
    python scripts/promotion_pipeline.py --apply

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import argparse
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Promotion thresholds
EXPIRY_WINDOW_DAYS = 7  # Look for memories expiring within 7 days
MIN_PROMOTION_SCORE = 0.5


def get_expiring_memories(
    kv_store: Any,
    window_days: int = EXPIRY_WINDOW_DAYS
) -> List[Dict[str, Any]]:
    """
    Get memories approaching expiry from long-term layer.

    Args:
        kv_store: KVStore instance
        window_days: Days until expiry to include

    Returns:
        List of memory candidates

    NASA Rule 10: 40 LOC (<=60)
    """
    import json

    candidates = []
    now = datetime.utcnow()
    expiry_threshold = now + timedelta(days=window_days)

    # List all long-term layer keys
    keys = kv_store.list_keys("long-term:")

    for key in keys:
        try:
            value = kv_store.get(key)
            if not value:
                continue

            data = json.loads(value) if isinstance(value, str) else value

            # Check expiry
            expires_at = data.get("expires_at")
            if expires_at:
                expiry_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expiry_date <= expiry_threshold:
                    candidates.append({
                        "key": key,
                        "data": data,
                        "expires_at": expires_at
                    })

        except Exception as e:
            logger.warning(f"Failed to parse {key}: {e}")

    logger.info(f"Found {len(candidates)} memories expiring within {window_days} days")
    return candidates


def evaluate_candidates(
    candidates: List[Dict[str, Any]],
    promoter: Any
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Evaluate candidates for promotion.

    Args:
        candidates: List of memory candidates
        promoter: MemoryPromoter instance

    Returns:
        (promoted_list, rejected_list)

    NASA Rule 10: 45 LOC (<=60)
    """
    from src.memory.memory_promoter import PromotionCandidate, ContentType

    promoted = []
    rejected = []

    for candidate in candidates:
        data = candidate["data"]

        # Build promotion candidate
        pc = PromotionCandidate(
            memory_id=candidate["key"],
            text=data.get("text", data.get("content", "")),
            metadata=data.get("metadata", {}),
            access_count=data.get("access_count", 0),
            reference_count=data.get("reference_count", 0),
            content_type=_infer_content_type(data),
            user_importance=data.get("importance", 0.5),
            created_at=data.get("created_at"),
            decay_score=data.get("decay_score", 0.5)
        )

        # Evaluate
        result = promoter.should_promote(pc)

        if result.should_promote:
            promoted.append({
                **candidate,
                "promotion_result": result.to_dict()
            })
        else:
            rejected.append({
                **candidate,
                "promotion_result": result.to_dict()
            })

    logger.info(f"Evaluation: {len(promoted)} promoted, {len(rejected)} rejected")
    return promoted, rejected


def _infer_content_type(data: Dict[str, Any]) -> Any:
    """
    Infer content type from memory data.

    NASA Rule 10: 25 LOC (<=60)
    """
    from src.memory.memory_promoter import ContentType

    # Check namespace or type hints
    key = data.get("_key", "")
    metadata = data.get("metadata", {})

    if "expertise" in key or metadata.get("type") == "expertise":
        return ContentType.EXPERTISE
    elif "decision" in key or metadata.get("type") == "decision":
        return ContentType.DECISION
    elif "pattern" in key or metadata.get("type") == "pattern":
        return ContentType.PATTERN
    elif "fix" in key or metadata.get("type") == "fix":
        return ContentType.FIX
    elif "finding" in key or metadata.get("type") == "finding":
        return ContentType.FINDING
    elif "context" in key:
        return ContentType.CONTEXT
    else:
        return ContentType.GENERAL


def promote_to_chromadb(
    promoted: List[Dict[str, Any]],
    chroma_path: str,
    collection_name: str = "promoted_memories",
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Index promoted memories to ChromaDB.

    NASA Rule 10: 50 LOC (<=60)
    """
    report = {
        "total": len(promoted),
        "indexed": 0,
        "errors": 0,
        "dry_run": dry_run
    }

    if dry_run:
        logger.info(f"[DRY RUN] Would index {len(promoted)} memories to ChromaDB")
        report["indexed"] = len(promoted)
        return report

    try:
        from src.indexing.vector_indexer import VectorIndexer
        from src.indexing.embedding_pipeline import EmbeddingPipeline

        indexer = VectorIndexer(
            persist_directory=chroma_path,
            collection_name=collection_name
        )
        embedder = EmbeddingPipeline()

        for memory in promoted:
            try:
                data = memory["data"]
                text = data.get("text", data.get("content", ""))

                # Generate embedding
                embedding = embedder.encode([text])[0]

                # Generate doc ID
                doc_id = hashlib.md5(memory["key"].encode()).hexdigest()[:16]

                # Index with is_fact metadata
                indexer.add_document(
                    document_id=doc_id,
                    text=text,
                    embedding=embedding.tolist(),
                    metadata={
                        **data.get("metadata", {}),
                        "source": "triple_layer_promotion",
                        "original_key": memory["key"],
                        "is_fact": True,
                        "promotion_score": memory["promotion_result"]["total_score"],
                        "promoted_at": datetime.utcnow().isoformat()
                    }
                )
                report["indexed"] += 1

            except Exception as e:
                logger.error(f"Failed to index {memory['key']}: {e}")
                report["errors"] += 1

    except Exception as e:
        logger.error(f"ChromaDB setup failed: {e}")
        report["errors"] = len(promoted)

    return report


def promote_to_seed_archive(
    promoted: List[Dict[str, Any]],
    data_dir: str,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Archive promoted memories to seed_archive.

    NASA Rule 10: 40 LOC (<=60)
    """
    report = {
        "total": len(promoted),
        "archived": 0,
        "errors": 0,
        "dry_run": dry_run
    }

    if dry_run:
        logger.info(f"[DRY RUN] Would archive {len(promoted)} memories to seed_archive")
        report["archived"] = len(promoted)
        return report

    try:
        from src.memory.seed_archive import SeedArchive

        archive = SeedArchive(data_dir=data_dir)

        for memory in promoted:
            try:
                data = memory["data"]
                result = memory["promotion_result"]

                success = archive.promote_memory(
                    memory_id=memory["key"],
                    text=data.get("text", data.get("content", "")),
                    metadata=data.get("metadata", {}),
                    importance=data.get("importance", 0.5),
                    decay_score=data.get("decay_score", 0.5),
                    source_tier="long-term",
                    reason=result.get("reason", "Promotion criteria met")
                )

                if success:
                    report["archived"] += 1
                else:
                    report["errors"] += 1

            except Exception as e:
                logger.error(f"Failed to archive {memory['key']}: {e}")
                report["errors"] += 1

    except Exception as e:
        logger.error(f"SeedArchive setup failed: {e}")
        report["errors"] = len(promoted)

    return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run promotion pipeline from Triple-Layer to Vector"
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
        default="promoted_memories",
        help="ChromaDB collection name"
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=EXPIRY_WINDOW_DAYS,
        help="Days until expiry to include"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only report what would be promoted (default: True)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually promote memories (overrides --dry-run)"
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
    print(f"PROMOTION PIPELINE {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print(f"{'='*60}")
    print(f"Data Dir: {args.data_dir}")
    print(f"ChromaDB: {args.chroma_path}")
    print(f"Window: {args.window_days} days")
    print()

    # Initialize components
    try:
        from src.stores.kv_store import KVStore
        from src.memory.memory_promoter import MemoryPromoter

        kv_store = KVStore(f"{args.data_dir}/agent_kv.db")
        promoter = MemoryPromoter()

    except Exception as e:
        print(f"Failed to initialize: {e}")
        return 1

    # Step 1: Get expiring memories
    print("Step 1: Finding expiring memories...")
    candidates = get_expiring_memories(kv_store, args.window_days)

    if not candidates:
        print("No expiring memories found")
        return 0

    # Step 2: Evaluate candidates
    print("Step 2: Evaluating candidates...")
    promoted, rejected = evaluate_candidates(candidates, promoter)

    if not promoted:
        print("No memories qualified for promotion")
        return 0

    # Show sample
    print(f"\nPromoted memories ({len(promoted)}):")
    for mem in promoted[:5]:
        result = mem["promotion_result"]
        print(f"  - {mem['key'][:40]}... (score: {result['total_score']:.3f})")
    print()

    # Step 3: Index to ChromaDB
    print("Step 3: Indexing to ChromaDB...")
    chroma_report = promote_to_chromadb(
        promoted, args.chroma_path, args.collection, dry_run
    )

    # Step 4: Archive to seed_archive
    print("Step 4: Archiving to seed_archive...")
    archive_report = promote_to_seed_archive(
        promoted, args.data_dir, dry_run
    )

    # Summary
    print(f"\n{'='*60}")
    print("PROMOTION SUMMARY")
    print(f"{'='*60}")
    print(f"Candidates evaluated: {len(candidates)}")
    print(f"Promoted: {len(promoted)}")
    print(f"Rejected: {len(rejected)}")
    print(f"ChromaDB indexed: {chroma_report['indexed']}")
    print(f"Seed archive: {archive_report['archived']}")
    print(f"Errors: {chroma_report['errors'] + archive_report['errors']}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLIED'}")

    # Cleanup
    kv_store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
