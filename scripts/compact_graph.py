"""Compact graph by linking similar entities across components."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

from src.indexing.embedding_pipeline import EmbeddingPipeline
from src.services.graph_service import GraphService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact graph connectivity")
    parser.add_argument("--data-dir", default="./data", help="Data directory")
    parser.add_argument("--threshold", type=float, default=0.85, help="Similarity threshold")
    parser.add_argument("--max-links", type=int, default=3, help="Max links per entity")
    return parser.parse_args()


def compact_graph(data_dir: str, threshold: float, max_links: int) -> int:
    graph_service = GraphService(data_dir=data_dir)
    graph_file = Path(data_dir) / "graph.json"
    if graph_file.exists():
        graph_service.load_graph(graph_file)

    embedder = EmbeddingPipeline()
    entities = [
        node_id
        for node_id, data in graph_service.graph.nodes(data=True)
        if data.get("type") == GraphService.NODE_TYPE_ENTITY
    ]

    links_added = 0
    for entity_id in entities:
        links_added += graph_service.link_similar_entities(
            entity_id,
            embedder=embedder,
            similarity_threshold=threshold,
            max_links=max_links,
        )

    graph_service.save_graph()
    logger.info("Compaction complete: %s links added", links_added)
    return links_added


def main() -> None:
    args = _parse_args()
    compact_graph(args.data_dir, args.threshold, args.max_links)


if __name__ == "__main__":
    main()
