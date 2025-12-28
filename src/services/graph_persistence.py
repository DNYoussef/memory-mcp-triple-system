"""
Graph Persistence - Focused component for graph save/load.

Extracted from GraphService to improve cohesion.
Single Responsibility: Graph persistence operations.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from pathlib import Path
from typing import Optional
import json
import networkx as nx
from loguru import logger


class GraphPersistence:
    """
    Handles graph save/load operations.

    Single Responsibility: Graph persistence.
    Cohesion: HIGH - all methods are I/O operations.
    """

    def __init__(self, graph: nx.DiGraph, data_dir: Path):
        """
        Initialize with graph reference and data directory.

        Args:
            graph: NetworkX DiGraph reference
            data_dir: Directory for persistence
        """
        self.graph = graph
        self.data_dir = data_dir

    def save(self, file_path: Optional[Path] = None) -> bool:
        """Save graph to JSON file."""
        try:
            if file_path is None:
                file_path = self.data_dir / 'graph.json'
            else:
                file_path = Path(file_path)

            data = nx.node_link_data(self.graph)

            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved graph to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Save failed: {e}")
            return False

    def load(self, file_path: Optional[Path] = None) -> Optional[nx.DiGraph]:
        """Load graph from JSON file."""
        try:
            if file_path is None:
                file_path = self.data_dir / 'graph.json'
            else:
                file_path = Path(file_path)

            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                return None

            with open(file_path, 'r') as f:
                data = json.load(f)

            loaded_graph = nx.node_link_graph(data, directed=True)
            logger.info(f"Loaded graph from {file_path}")
            return loaded_graph
        except Exception as e:
            logger.error(f"Load failed: {e}")
            return None
