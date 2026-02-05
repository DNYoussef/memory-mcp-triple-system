"""
GraphService - Refactored Facade for Graph Operations

NetworkX-based graph database for entity relationships.
Manages in-memory graph with JSON persistence.

REFACTORED: Extracted into focused components for high cohesion:
- GraphNodeManager: Node CRUD
- GraphEdgeManager: Edge CRUD
- GraphQueryService: Graph queries
- GraphPersistence: Save/Load

This class now acts as a facade coordinating the components.

NASA Rule 10 Compliant: All functions <=60 LOC
Cohesion: HIGH (facade pattern - coordinates focused components)
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import networkx as nx
import numpy as np
from loguru import logger

from .graph_node_manager import GraphNodeManager
from .graph_edge_manager import GraphEdgeManager
from .graph_query_service import GraphQueryService
from .graph_persistence import GraphPersistence


class GraphService:
    """
    Facade for entity relationship graph operations.

    Coordinates focused components:
    - GraphNodeManager: Node operations
    - GraphEdgeManager: Edge operations
    - GraphQueryService: Queries
    - GraphPersistence: Save/Load

    Usage:
        service = GraphService(data_dir="./data")
        service.add_chunk_node("chunk1", {"text": "..."})
        service.add_relationship("chunk1", "mentions", "entity1")
    """

    # Expose constants for backward compatibility
    NODE_TYPE_CHUNK = GraphNodeManager.NODE_TYPE_CHUNK
    NODE_TYPE_ENTITY = GraphNodeManager.NODE_TYPE_ENTITY
    NODE_TYPE_CONCEPT = GraphNodeManager.NODE_TYPE_CONCEPT
    EDGE_REFERENCES = GraphEdgeManager.EDGE_REFERENCES
    EDGE_MENTIONS = GraphEdgeManager.EDGE_MENTIONS
    EDGE_SIMILAR_TO = GraphEdgeManager.EDGE_SIMILAR_TO
    EDGE_RELATED_TO = GraphEdgeManager.EDGE_RELATED_TO

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize GraphService facade.

        Args:
            data_dir: Directory for graph persistence
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize graph
        self.graph = nx.DiGraph()

        # Initialize focused components
        self._node_manager = GraphNodeManager(self.graph)
        self._edge_manager = GraphEdgeManager(self.graph)
        self._query_service = GraphQueryService(self.graph)
        self._persistence = GraphPersistence(self.graph, self.data_dir)

        logger.info("GraphService initialized")

    def _mutate(self, result: bool) -> bool:
        """P2-3: Mark graph dirty if mutation succeeded."""
        if result:
            self._persistence.mark_dirty()
        return result

    # Node operations (delegate to GraphNodeManager)
    def add_chunk_node(self, chunk_id: str, metadata: Optional[Dict] = None) -> bool:
        return self._mutate(self._node_manager.add_chunk(chunk_id, metadata))

    def add_entity_node(self, entity_id: str, entity_type: str, metadata: Optional[Dict] = None) -> bool:
        return self._mutate(self._node_manager.add_entity(entity_id, entity_type, metadata))

    def add_entity(self, entity_id: str, entity_type: str, metadata: Optional[Dict] = None) -> bool:
        return self._mutate(self._node_manager.add_entity(entity_id, entity_type, metadata))

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._node_manager.get_node(node_id)

    def remove_node(self, node_id: str) -> bool:
        return self._mutate(self._node_manager.remove_node(node_id))

    def get_node_count(self) -> int:
        return self._node_manager.get_node_count()

    # Bayesian node operations (delegate to GraphNodeManager)
    def increment_node_frequency(self, node_id: str) -> bool:
        """Increment frequency counter when node is accessed."""
        return self._mutate(self._node_manager.increment_frequency(node_id))

    def update_node_importance(self, node_id: str, explicit_weight: float = 0.5) -> bool:
        """Update node importance using weighted formula."""
        return self._mutate(self._node_manager.update_importance(node_id, explicit_weight))

    def update_node_decay_score(self, node_id: str) -> bool:
        """Update decay score based on time since last access."""
        return self._mutate(self._node_manager.update_decay_score(node_id))

    def get_nodes_by_importance(
        self,
        min_importance: float = 0.0,
        max_importance: float = 1.0
    ) -> List[tuple]:
        """Get nodes filtered by importance range."""
        return self._node_manager.get_nodes_by_importance(min_importance, max_importance)

    # Edge operations (delegate to GraphEdgeManager)
    def add_relationship(
        self,
        source: str,
        relationship_type: str,
        target: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        standard_types = {
            self.EDGE_REFERENCES,
            self.EDGE_MENTIONS,
            self.EDGE_SIMILAR_TO,
            self.EDGE_RELATED_TO
        }
        if relationship_type not in standard_types and target in standard_types:
            relationship_type, target = target, relationship_type
        return self._mutate(self._edge_manager.add_relationship(
            source,
            relationship_type,
            target,
            metadata
        ))

    def remove_edge(self, source: str, target: str) -> bool:
        return self._mutate(self._edge_manager.remove_edge(source, target))

    def get_neighbors(self, node_id: str, relationship_type: Optional[str] = None) -> List[str]:
        return self._edge_manager.get_neighbors(node_id, relationship_type)

    def get_edge_count(self) -> int:
        return self._edge_manager.get_edge_count()

    # Bayesian edge operations (delegate to GraphEdgeManager)
    def update_edge_confidence(
        self,
        source: str,
        target: str,
        new_confidence: float,
        evidence_chunk: Optional[str] = None
    ) -> bool:
        """Update edge confidence based on new evidence."""
        return self._mutate(self._edge_manager.update_edge_confidence(
            source, target, new_confidence, evidence_chunk
        ))

    def increment_edge_frequency(self, source: str, target: str) -> bool:
        """Increment frequency counter when edge is observed."""
        return self._mutate(self._edge_manager.increment_frequency(source, target))

    def get_edges_by_confidence(
        self,
        min_confidence: float = 0.0,
        max_confidence: float = 1.0
    ) -> List[tuple]:
        """Get edges filtered by confidence range."""
        return self._edge_manager.get_edges_by_confidence(min_confidence, max_confidence)

    def update_edge_from_bayesian(
        self,
        source: str,
        target: str,
        bayesian_posterior: float,
        prior_weight: float = 0.7,
        posterior_weight: float = 0.3
    ) -> bool:
        """
        Update edge confidence based on Bayesian inference result.

        BAY-003: Applies confidence update formula:
            new_confidence = prior_weight * prior + posterior_weight * posterior
            Clamped to [0.1, 0.95] to prevent certainty

        Args:
            source: Source node ID
            target: Target node ID
            bayesian_posterior: Posterior probability from Bayesian inference
            prior_weight: Weight for historical confidence (default 0.7)
            posterior_weight: Weight for new evidence (default 0.3)

        Returns:
            True if updated successfully
        """
        if not self.graph.has_edge(source, target):
            logger.warning(f"Edge not found for Bayesian update: {source} -> {target}")
            return False

        edge_data = self.graph.get_edge_data(source, target)
        prior_confidence = edge_data.get('confidence', 0.5)

        # Apply weighted update formula
        new_confidence = (
            prior_weight * prior_confidence +
            posterior_weight * bayesian_posterior
        )

        # Clamp to [0.1, 0.95] to prevent certainty
        new_confidence = max(0.1, min(0.95, new_confidence))

        return self._mutate(self._edge_manager.update_edge_confidence(source, target, new_confidence))

    # Query operations (delegate to GraphQueryService)
    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        return self._query_service.find_path(source, target)

    def get_subgraph(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        return self._query_service.get_subgraph(node_id, depth)

    # Persistence operations (delegate to GraphPersistence)
    def save_graph(self, file_path: Optional[Path] = None, force: bool = False) -> bool:
        return self._persistence.save(file_path, force=force)

    def load_graph(self, file_path: Optional[Path] = None) -> bool:
        loaded = self._persistence.load(file_path)
        if loaded is not None:
            self.graph = loaded
            # Re-initialize components with new graph
            self._node_manager = GraphNodeManager(self.graph)
            self._edge_manager = GraphEdgeManager(self.graph)
            self._query_service = GraphQueryService(self.graph)
            self._persistence = GraphPersistence(self.graph, self.data_dir)
            return True
        return False

    def get_graph(self) -> nx.DiGraph:
        """Return underlying NetworkX graph."""
        return self.graph

    def link_similar_entities(
        self,
        entity_id: str,
        embedder: Any,
        similarity_threshold: float = 0.85,
        max_links: int = 3
    ) -> int:
        """
        Link entity to similar entities across components.

        Uses embedding similarity to add SIMILAR_TO edges.
        """
        if embedder is None or not self.graph.has_node(entity_id):
            return 0
        return self._link_similar_entities(
            entity_id,
            embedder,
            similarity_threshold,
            max_links
        )

    def _link_similar_entities(
        self,
        entity_id: str,
        embedder: Any,
        similarity_threshold: float,
        max_links: int
    ) -> int:
        """
        Link entity to similar entities using embedding similarity.

        Returns number of links created.
        """
        entity_text = self._get_entity_text(entity_id)
        if not entity_text:
            return 0

        candidates = self._get_cross_component_entities(entity_id)
        if not candidates:
            return 0

        candidate_texts = [self._get_entity_text(cid) for cid in candidates]
        filtered = [(cid, text) for cid, text in zip(candidates, candidate_texts) if text]
        if not filtered:
            return 0

        ids, texts = zip(*filtered)
        embeddings = embedder.encode([entity_text] + list(texts))
        base = embeddings[0]
        scores = self._cosine_similarity(base, embeddings[1:])
        ranked = sorted(
            zip(ids, scores),
            key=lambda item: item[1],
            reverse=True
        )

        links_added = 0
        for candidate_id, score in ranked:
            if score < similarity_threshold or links_added >= max_links:
                break
            if self.graph.has_edge(entity_id, candidate_id):
                continue
            self.add_relationship(
                entity_id,
                self.EDGE_SIMILAR_TO,
                candidate_id,
                {"confidence": float(score)}
            )
            links_added += 1

        return links_added

    def _get_entity_text(self, entity_id: str) -> str:
        node_data = self.graph.nodes.get(entity_id, {})
        metadata = node_data.get("metadata", {})
        return metadata.get("text") or node_data.get("text") or entity_id

    def _get_cross_component_entities(self, entity_id: str) -> List[str]:
        components = list(nx.weakly_connected_components(self.graph))
        component_map = {node: idx for idx, comp in enumerate(components) for node in comp}
        source_component = component_map.get(entity_id)
        candidates = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") != self.NODE_TYPE_ENTITY:
                continue
            if component_map.get(node_id) == source_component:
                continue
            candidates.append(node_id)
        return candidates

    def _cosine_similarity(self, base: Any, vectors: Any) -> List[float]:
        base_vec = np.array(base)
        base_norm = np.linalg.norm(base_vec) or 1.0
        sims = []
        for vec in vectors:
            vec_arr = np.array(vec)
            denom = base_norm * (np.linalg.norm(vec_arr) or 1.0)
            sims.append(float(np.dot(base_vec, vec_arr) / denom))
        return sims
