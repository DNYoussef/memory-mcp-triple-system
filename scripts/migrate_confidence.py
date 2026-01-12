"""Migration script to backfill confidence scores."""

from __future__ import annotations

import argparse
import logging
from typing import Any, Dict, List

import chromadb

from src.mcp.stdio_server import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill confidence scores")
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def _compute_confidence(metadata: Dict[str, Any]) -> float:
    existing = metadata.get("confidence")
    if existing is not None:
        return float(existing)
    source_type = metadata.get("source_type") or metadata.get("source") or ""
    source_type = str(source_type).lower()
    mapping = {
        "witnessed": 0.95,
        "reported": 0.70,
        "inferred": 0.50,
        "assumed": 0.30,
    }
    return mapping.get(source_type, 0.5)


def migrate_confidence(batch_size: int) -> int:
    config = load_config()
    vector_config = config["storage"]["vector_db"]
    client = chromadb.PersistentClient(path=vector_config["persist_directory"])
    collection = client.get_collection(vector_config["collection_name"])

    total = collection.count()
    updated = 0
    offset = 0

    while offset < total:
        results = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas"],
        )
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        if not ids:
            break

        ids_to_update: List[str] = []
        metas_to_update: List[Dict[str, Any]] = []

        for doc_id, meta in zip(ids, metadatas):
            meta = dict(meta or {})
            if meta.get("confidence") is not None:
                continue
            meta["confidence"] = _compute_confidence(meta)
            ids_to_update.append(doc_id)
            metas_to_update.append(meta)

        if ids_to_update:
            collection.update(ids=ids_to_update, metadatas=metas_to_update)
            updated += len(ids_to_update)

        offset += batch_size

    logger.info("Confidence migration complete: %s updated", updated)
    return updated


def main() -> None:
    args = _parse_args()
    migrate_confidence(args.batch_size)


if __name__ == "__main__":
    main()
