"""Migration script to backfill WHO/WHEN/PROJECT/WHY tags."""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import chromadb

from src.mcp.stdio_server import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill tagging protocol")
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def _defaults() -> Dict[str, str]:
    project = os.environ.get("MEMORY_MCP_PROJECT", "default")
    when = datetime.utcnow().isoformat() + "Z"
    return {
        "WHO": "unknown-agent:1.0.0",
        "WHEN": when,
        "PROJECT": project,
        "WHY": "storage",
    }


def migrate_tagging(batch_size: int) -> int:
    config = load_config()
    vector_config = config["storage"]["vector_db"]
    client = chromadb.PersistentClient(path=vector_config["persist_directory"])
    collection = client.get_collection(vector_config["collection_name"])

    total = collection.count()
    updated = 0
    offset = 0
    defaults = _defaults()

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
            changed = False
            for key, value in defaults.items():
                if not meta.get(key):
                    meta[key] = value
                    changed = True
            if changed:
                ids_to_update.append(doc_id)
                metas_to_update.append(meta)

        if ids_to_update:
            collection.update(ids=ids_to_update, metadatas=metas_to_update)
            updated += len(ids_to_update)

        offset += batch_size

    logger.info("Tagging migration complete: %s updated", updated)
    return updated


def main() -> None:
    args = _parse_args()
    migrate_tagging(args.batch_size)


if __name__ == "__main__":
    main()
