"""Unified Ontology Bridge - Level 3 ORGANIZE layer.

Bridges three ontologies:
1. Life (People, Ideas, Admin)
2. Projects (18 exoskeleton projects)
3. Beads (Tasks, Dependencies, State)

Cross-links: Memory entity -> Beads task -> Project

Mode-aware routing:
- Execution: Beads FIRST (80%), Memory MCP (20%)
- Planning: Both (50/50) + Council
- Brainstorm: Memory MCP HEAVY (80%), Beads deps (20%)

WHO: ontology-bridge:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (GRAPH-001)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from ..integrations.beads_bridge import BeadsBridge, BeadTask
from ..integrations.ontology_schema import (
    BeadsEntity,
    BeadsStatus,
    CrossLink,
    CrossLinkType,
    LifeBucketType,
    LifeEntity,
    ONTOLOGY_REGISTRY,
    ProjectEntity,
    ProjectRole,
)
from .graph_service import GraphService


class OntologyBridge:
    """Unified bridge across Life, Projects, and Beads ontologies.

    Usage:
        bridge = OntologyBridge(data_dir="./data")
        await bridge.initialize()

        # Add entities
        bridge.add_life_entity(LifeEntity(...))
        bridge.add_project_entity(ProjectEntity(...))
        await bridge.sync_beads_tasks()

        # Query with mode-aware routing
        results = await bridge.query("implement auth", mode="execution")
    """

    # Node type constants
    NODE_TYPE_LIFE = "LIFE_ENTITY"
    NODE_TYPE_PROJECT = "PROJECT_ENTITY"
    NODE_TYPE_BEADS = "BEADS_ENTITY"

    # Cross-link edge types
    EDGE_LIFE_TO_BEADS = "LIFE_BEADS"
    EDGE_LIFE_TO_PROJECT = "LIFE_PROJECT"
    EDGE_BEADS_TO_PROJECT = "BEADS_PROJECT"
    EDGE_MEMORY_TO_BEADS = "MEMORY_BEADS"
    EDGE_MEMORY_TO_PROJECT = "MEMORY_PROJECT"

    def __init__(
        self,
        data_dir: str = "./data",
        beads_binary: str = "bd",
        graph_service: Optional[GraphService] = None,
    ):
        """Initialize OntologyBridge.

        Args:
            data_dir: Directory for graph persistence
            beads_binary: Path to Beads CLI (bd.exe)
            graph_service: Optional existing GraphService instance
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize GraphService (or use provided one)
        self.graph = graph_service or GraphService(data_dir=str(self.data_dir))

        # Initialize BeadsBridge
        self.beads = BeadsBridge(beads_binary=beads_binary)

        # Mode detection patterns (from ORGAN-MAP.md line 154-158)
        self._mode_routing = {
            "execution": {"beads": 0.8, "memory": 0.2},
            "planning": {"beads": 0.5, "memory": 0.5},
            "brainstorm": {"beads": 0.2, "memory": 0.8},
        }

        logger.info("OntologyBridge initialized")

    async def initialize(self) -> None:
        """Initialize ontology bridge: load graph, sync Beads."""
        # Load existing graph
        self.graph.load_graph()
        logger.info(
            f"Graph loaded: {self.graph.get_node_count()} nodes, "
            f"{self.graph.get_edge_count()} edges"
        )

        # Initial Beads sync
        await self.sync_beads_tasks()

    # ========== LIFE ONTOLOGY METHODS ==========

    def add_life_entity(self, entity: LifeEntity) -> bool:
        """Add entity to Life ontology."""
        metadata = {
            "type": self.NODE_TYPE_LIFE,
            "bucket": entity.bucket.value,
            "name": entity.name,
            "description": entity.description,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "tags": entity.tags,
            **entity.metadata,
        }
        return self.graph.add_entity_node(entity.id, entity.bucket.value, metadata)

    def get_life_entity(self, entity_id: str) -> Optional[LifeEntity]:
        """Get Life entity by ID."""
        node = self.graph.get_node(entity_id)
        if not node:
            return None

        # Check metadata for type (GraphService stores it there)
        metadata = node.get("metadata", {})
        if metadata.get("type") != self.NODE_TYPE_LIFE:
            return None

        return LifeEntity(
            id=entity_id,
            bucket=LifeBucketType(metadata.get("bucket", "admin")),
            name=metadata.get("name", entity_id),
            description=metadata.get("description"),
            metadata={k: v for k, v in metadata.items() if k not in ["type", "bucket", "name", "description", "created_at", "tags"]},
            created_at=datetime.fromisoformat(metadata["created_at"])
            if metadata.get("created_at")
            else None,
            tags=metadata.get("tags", []),
        )

    def list_life_entities(
        self, bucket: Optional[LifeBucketType] = None
    ) -> List[LifeEntity]:
        """List all Life entities, optionally filtered by bucket."""
        entities = []
        for node_id, data in self.graph.graph.nodes(data=True):
            metadata = data.get("metadata", {})
            if metadata.get("type") != self.NODE_TYPE_LIFE:
                continue
            if bucket and metadata.get("bucket") != bucket.value:
                continue

            entity = self.get_life_entity(node_id)
            if entity:
                entities.append(entity)

        return entities

    # ========== PROJECT ONTOLOGY METHODS ==========

    def add_project_entity(self, entity: ProjectEntity) -> bool:
        """Add entity to Project ontology."""
        metadata = {
            "type": self.NODE_TYPE_PROJECT,
            "name": entity.name,
            "role": entity.role.value,
            "location": entity.location,
            "status_percent": entity.status_percent,
            "repository": entity.repository,
            "tech_stack": entity.tech_stack,
            **entity.metadata,
        }
        return self.graph.add_entity_node(
            entity.id, f"project-{entity.role.value}", metadata
        )

    def get_project_entity(self, entity_id: str) -> Optional[ProjectEntity]:
        """Get Project entity by ID."""
        node = self.graph.get_node(entity_id)
        if not node:
            return None

        metadata = node.get("metadata", {})
        if metadata.get("type") != self.NODE_TYPE_PROJECT:
            return None

        return ProjectEntity(
            id=entity_id,
            name=metadata.get("name", entity_id),
            role=ProjectRole(metadata.get("role", "tool")),
            location=metadata.get("location", ""),
            status_percent=metadata.get("status_percent", 0),
            repository=metadata.get("repository"),
            tech_stack=metadata.get("tech_stack", []),
            metadata={k: v for k, v in metadata.items() if k not in ["type", "name", "role", "location", "status_percent", "repository", "tech_stack"]},
        )

    def list_project_entities(self) -> List[ProjectEntity]:
        """List all Project entities."""
        entities = []
        for node_id, data in self.graph.graph.nodes(data=True):
            metadata = data.get("metadata", {})
            if metadata.get("type") != self.NODE_TYPE_PROJECT:
                continue

            entity = self.get_project_entity(node_id)
            if entity:
                entities.append(entity)

        return entities

    # ========== BEADS ONTOLOGY METHODS ==========

    async def sync_beads_tasks(self, limit: int = 100) -> int:
        """Sync Beads tasks into the graph.

        Returns number of tasks synced.
        """
        tasks = await self.beads.query_tasks(limit=limit)
        synced = 0

        for task in tasks:
            entity = self._beads_task_to_entity(task)
            if self.add_beads_entity(entity):
                synced += 1

                # Add dependency edges
                for dep_id in entity.dependencies:
                    self.graph.add_relationship(
                        entity.id, "BLOCKS", dep_id, {"ontology": "beads"}
                    )

        logger.info(f"Synced {synced} Beads tasks")
        return synced

    def add_beads_entity(self, entity: BeadsEntity) -> bool:
        """Add entity to Beads ontology."""
        metadata = {
            "type": self.NODE_TYPE_BEADS,
            "title": entity.title,
            "status": entity.status.value,
            "project_id": entity.project_id,
            "dependencies": entity.dependencies,
            "dependents": entity.dependents,
            "estimated_minutes": entity.estimated_minutes,
            "labels": entity.labels,
            **entity.metadata,
        }
        return self.graph.add_entity_node(entity.id, "beads-task", metadata)

    def get_beads_entity(self, entity_id: str) -> Optional[BeadsEntity]:
        """Get Beads entity by ID."""
        node = self.graph.get_node(entity_id)
        if not node:
            return None

        metadata = node.get("metadata", {})
        if metadata.get("type") != self.NODE_TYPE_BEADS:
            return None

        return BeadsEntity(
            id=entity_id,
            title=metadata.get("title", entity_id),
            status=BeadsStatus(metadata.get("status", "open")),
            project_id=metadata.get("project_id"),
            dependencies=metadata.get("dependencies", []),
            dependents=metadata.get("dependents", []),
            estimated_minutes=metadata.get("estimated_minutes", 0),
            labels=metadata.get("labels", []),
            metadata={k: v for k, v in metadata.items() if k not in ["type", "title", "status", "project_id", "dependencies", "dependents", "estimated_minutes", "labels"]},
        )

    def list_beads_entities(
        self, status: Optional[BeadsStatus] = None
    ) -> List[BeadsEntity]:
        """List all Beads entities, optionally filtered by status."""
        entities = []
        for node_id, data in self.graph.graph.nodes(data=True):
            metadata = data.get("metadata", {})
            if metadata.get("type") != self.NODE_TYPE_BEADS:
                continue
            if status and metadata.get("status") != status.value:
                continue

            entity = self.get_beads_entity(node_id)
            if entity:
                entities.append(entity)

        return entities

    def _beads_task_to_entity(self, task: BeadTask) -> BeadsEntity:
        """Convert BeadTask to BeadsEntity."""
        return BeadsEntity(
            id=task.id,
            title=task.title,
            status=BeadsStatus(task.status),
            project_id=None,  # Will be inferred via cross-links
            dependencies=[dep.id for dep in task.dependencies],
            dependents=[],  # Not provided by BeadTask
            estimated_minutes=task.estimated_minutes,
            labels=task.labels,
            metadata={
                "description": task.description,
                "priority": task.priority,
                "assignee": task.assignee,
            },
        )

    # ========== CROSS-LINK METHODS ==========

    def add_cross_link(self, link: CrossLink) -> bool:
        """Add cross-ontology link."""
        edge_type = self._get_cross_link_edge_type(
            link.source_ontology, link.target_ontology
        )
        metadata = {
            "link_type": link.link_type.value,
            "confidence": link.confidence,
            "created_at": link.created_at.isoformat() if link.created_at else None,
            **link.metadata,
        }
        return self.graph.add_relationship(
            link.source_id, edge_type, link.target_id, metadata
        )

    def get_cross_links(
        self,
        entity_id: str,
        link_type: Optional[CrossLinkType] = None,
    ) -> List[CrossLink]:
        """Get all cross-links for an entity."""
        links = []
        node = self.graph.get_node(entity_id)
        if not node:
            return links

        source_ontology = self._infer_ontology(node)

        # Get all outgoing edges
        for neighbor in self.graph.get_neighbors(entity_id):
            neighbor_node = self.graph.get_node(neighbor)
            if not neighbor_node:
                continue

            target_ontology = self._infer_ontology(neighbor_node)

            # Get edge data. add_relationship nests our fields under "metadata"
            # (edge attrs are {"type": ..., "metadata": {...}}), so read from
            # there, not the top level. Use get_edge_data for a reliable attr
            # dict (EdgeView.get is not a Mapping.get).
            edge_data = self.graph.graph.get_edge_data(entity_id, neighbor) or {}
            edge_meta = edge_data.get("metadata", edge_data)
            edge_link_type = edge_meta.get("link_type")
            if link_type and edge_link_type != link_type.value:
                continue

            links.append(
                CrossLink(
                    source_id=entity_id,
                    source_ontology=source_ontology,
                    target_id=neighbor,
                    target_ontology=target_ontology,
                    link_type=CrossLinkType(edge_link_type)
                    if edge_link_type
                    else CrossLinkType.MEMORY_REFERENCES_TASK,
                    confidence=edge_meta.get("confidence", 1.0),
                    created_at=datetime.fromisoformat(edge_meta["created_at"])
                    if edge_meta.get("created_at")
                    else None,
                    metadata={
                        k: v
                        for k, v in edge_meta.items()
                        if k not in ["link_type", "confidence", "created_at"]
                    },
                )
            )

        return links

    def _get_cross_link_edge_type(
        self, source_ontology: str, target_ontology: str
    ) -> str:
        """Map ontology pair to edge type."""
        mapping = {
            ("life", "beads"): self.EDGE_LIFE_TO_BEADS,
            ("life", "project"): self.EDGE_LIFE_TO_PROJECT,
            ("beads", "project"): self.EDGE_BEADS_TO_PROJECT,
            ("memory", "beads"): self.EDGE_MEMORY_TO_BEADS,
            ("memory", "project"): self.EDGE_MEMORY_TO_PROJECT,
        }
        return mapping.get((source_ontology, target_ontology), "CROSS_LINK")

    def _infer_ontology(self, node_data: Dict) -> str:
        """Infer ontology from node data."""
        metadata = node_data.get("metadata", {})
        metadata_type = metadata.get("type")
        if metadata_type == self.NODE_TYPE_LIFE:
            return "life"
        elif metadata_type == self.NODE_TYPE_PROJECT:
            return "project"
        elif metadata_type == self.NODE_TYPE_BEADS:
            return "beads"
        else:
            return "memory"  # Default for CHUNK/ENTITY nodes

    # ========== MODE-AWARE QUERY ROUTING ==========

    async def query(
        self,
        query_text: str,
        mode: str = "execution",
        limit: int = 10,
    ) -> Dict[str, List]:
        """Mode-aware query across ontologies.

        Args:
            query_text: Search query
            mode: "execution" | "planning" | "brainstorm"
            limit: Max results per ontology

        Returns:
            Dict with keys: "beads", "memory", "life", "projects"
        """
        routing = self._mode_routing.get(mode, self._mode_routing["execution"])

        results = {
            "beads": [],
            "memory": [],
            "life": [],
            "projects": [],
        }

        # Query Beads (procedural)
        if routing.get("beads", 0) > 0:
            beads_tasks = await self._query_beads(query_text, limit)
            results["beads"] = beads_tasks

        # Query Memory MCP (semantic)
        if routing.get("memory", 0) > 0:
            memory_results = self._query_memory(query_text, limit)
            results["memory"] = memory_results

        # Query Life entities
        life_results = self._query_life(query_text, limit)
        results["life"] = life_results

        # Query Projects
        project_results = self._query_projects(query_text, limit)
        results["projects"] = project_results

        return results

    async def _query_beads(self, query_text: str, limit: int) -> List[Dict]:
        """Query Beads ontology entities stored in the graph.

        The mode-aware query searches the ontology graph (like _query_life /
        _query_projects); it must read the beads entities added via
        add_beads_entity, not the external bd CLI (self.beads is for live-task
        sync, and is unavailable in many contexts).
        """
        entities = self.list_beads_entities()
        results = []
        needle = query_text.lower()

        for entity in entities:
            description = getattr(entity, "description", None)
            if needle in entity.title.lower() or (
                description and needle in description.lower()
            ):
                status = entity.status
                results.append(
                    {
                        "id": entity.id,
                        "title": entity.title,
                        "status": status.value if hasattr(status, "value") else status,
                        "estimated_minutes": entity.estimated_minutes,
                        "labels": entity.labels,
                    }
                )

        return results[:limit]

    def _query_memory(self, query_text: str, limit: int) -> List[Dict]:
        """Query Memory MCP graph (semantic search via node metadata)."""
        results = []

        for node_id, data in self.graph.graph.nodes(data=True):
            node_type = data.get("type")
            if node_type in [
                self.NODE_TYPE_LIFE,
                self.NODE_TYPE_PROJECT,
                self.NODE_TYPE_BEADS,
            ]:
                continue  # Skip ontology nodes, focus on memory

            # Simple text matching in metadata
            text = data.get("text", "") or data.get("metadata", {}).get("text", "")
            if query_text.lower() in text.lower():
                results.append(
                    {
                        "id": node_id,
                        "type": node_type,
                        "text": text[:200],  # Truncate
                        "metadata": data.get("metadata", {}),
                    }
                )

        return results[:limit]

    def _query_life(self, query_text: str, limit: int) -> List[Dict]:
        """Query Life ontology entities."""
        entities = self.list_life_entities()
        results = []

        for entity in entities:
            if query_text.lower() in entity.name.lower() or (
                entity.description and query_text.lower() in entity.description.lower()
            ):
                results.append(
                    {
                        "id": entity.id,
                        "bucket": entity.bucket.value,
                        "name": entity.name,
                        "description": entity.description,
                    }
                )

        return results[:limit]

    def _query_projects(self, query_text: str, limit: int) -> List[Dict]:
        """Query Project ontology entities."""
        entities = self.list_project_entities()
        results = []

        for entity in entities:
            if query_text.lower() in entity.name.lower():
                results.append(
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "role": entity.role.value,
                        "status_percent": entity.status_percent,
                        "location": entity.location,
                    }
                )

        return results[:limit]

    # ========== PERSISTENCE ==========

    def save(self) -> bool:
        """Save graph to disk."""
        return self.graph.save_graph()

    def load(self) -> bool:
        """Load graph from disk."""
        return self.graph.load_graph()
