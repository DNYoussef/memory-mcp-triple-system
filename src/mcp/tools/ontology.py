"""MCP Tools for Unified Ontology Bridge.

Provides MCP-compatible tools for querying and managing the three ontologies:
- Life (People, Ideas, Admin)
- Projects (18 exoskeleton projects)
- Beads (Tasks, Dependencies, State)

WHO: ontology-bridge:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (GRAPH-001)
"""

from typing import Dict, Any, Optional
from loguru import logger

from ...services.ontology_bridge import OntologyBridge


class OntologyTools:
    """MCP tools for ontology bridge operations.

    Tools:
    - ontology_query: Mode-aware query across all ontologies
    - ontology_life_list: List Life entities
    - ontology_projects_list: List all projects
    - ontology_beads_list: List Beads tasks
    - ontology_cross_links: Get cross-links for an entity
    - ontology_sync: Sync Beads tasks from CLI
    """

    def __init__(self, bridge: OntologyBridge):
        """Initialize ontology tools.

        Args:
            bridge: OntologyBridge instance
        """
        self.bridge = bridge
        logger.info("OntologyTools initialized")

    async def query(
        self,
        query_text: str,
        mode: str = "execution",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Mode-aware query across all ontologies.

        Args:
            query_text: Search query
            mode: "execution" | "planning" | "brainstorm"
            limit: Max results per ontology

        Returns:
            Dict with results from all ontologies

        Example:
            result = await tools.query("implement auth", mode="execution")
            # Returns: {"beads": [...], "memory": [...], "life": [...], "projects": [...]}
        """
        try:
            results = await self.bridge.query(query_text, mode=mode, limit=limit)
            return {
                "success": True,
                "mode": mode,
                "query": query_text,
                "results": results,
            }
        except Exception as e:
            logger.error(f"Ontology query failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_life_entities(
        self,
        bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List Life entities, optionally filtered by bucket.

        Args:
            bucket: Filter by "people" | "ideas" | "admin" (optional)

        Returns:
            Dict with life entities

        Example:
            result = tools.list_life_entities(bucket="people")
            # Returns: {"success": True, "entities": [...]}
        """
        try:
            from ...integrations.ontology_schema import LifeBucketType

            bucket_filter = LifeBucketType(bucket) if bucket else None
            entities = self.bridge.list_life_entities(bucket=bucket_filter)

            return {
                "success": True,
                "bucket": bucket,
                "count": len(entities),
                "entities": [
                    {
                        "id": e.id,
                        "bucket": e.bucket.value,
                        "name": e.name,
                        "description": e.description,
                        "tags": e.tags,
                    }
                    for e in entities
                ],
            }
        except Exception as e:
            logger.error(f"List life entities failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_project_entities(self) -> Dict[str, Any]:
        """List all Project entities.

        Returns:
            Dict with project entities

        Example:
            result = tools.list_project_entities()
            # Returns: {"success": True, "projects": [...]}
        """
        try:
            entities = self.bridge.list_project_entities()

            return {
                "success": True,
                "count": len(entities),
                "projects": [
                    {
                        "id": e.id,
                        "name": e.name,
                        "role": e.role.value,
                        "location": e.location,
                        "status_percent": e.status_percent,
                        "repository": e.repository,
                        "tech_stack": e.tech_stack,
                    }
                    for e in entities
                ],
            }
        except Exception as e:
            logger.error(f"List project entities failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_beads_entities(
        self,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List Beads tasks, optionally filtered by status.

        Args:
            status: Filter by "open" | "in_progress" | "blocked" | "closed" | "deferred"

        Returns:
            Dict with beads tasks

        Example:
            result = tools.list_beads_entities(status="open")
            # Returns: {"success": True, "tasks": [...]}
        """
        try:
            from ...integrations.ontology_schema import BeadsStatus

            status_filter = BeadsStatus(status) if status else None
            entities = self.bridge.list_beads_entities(status=status_filter)

            return {
                "success": True,
                "status": status,
                "count": len(entities),
                "tasks": [
                    {
                        "id": e.id,
                        "title": e.title,
                        "status": e.status.value,
                        "project_id": e.project_id,
                        "estimated_minutes": e.estimated_minutes,
                        "labels": e.labels,
                        "dependencies": e.dependencies,
                        "dependents": e.dependents,
                    }
                    for e in entities
                ],
            }
        except Exception as e:
            logger.error(f"List beads entities failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_cross_links(
        self,
        entity_id: str,
        link_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get cross-links for an entity.

        Args:
            entity_id: Entity ID to get links for
            link_type: Optional filter by link type

        Returns:
            Dict with cross-links

        Example:
            result = tools.get_cross_links("task:auth-impl")
            # Returns: {"success": True, "links": [...]}
        """
        try:
            from ...integrations.ontology_schema import CrossLinkType

            link_type_filter = CrossLinkType(link_type) if link_type else None
            links = self.bridge.get_cross_links(entity_id, link_type=link_type_filter)

            return {
                "success": True,
                "entity_id": entity_id,
                "count": len(links),
                "links": [
                    {
                        "source_id": link.source_id,
                        "source_ontology": link.source_ontology,
                        "target_id": link.target_id,
                        "target_ontology": link.target_ontology,
                        "link_type": link.link_type.value,
                        "confidence": link.confidence,
                    }
                    for link in links
                ],
            }
        except Exception as e:
            logger.error(f"Get cross-links failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def sync_beads_tasks(
        self,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Sync Beads tasks from CLI into the graph.

        Args:
            limit: Max tasks to sync

        Returns:
            Dict with sync results

        Example:
            result = await tools.sync_beads_tasks(limit=50)
            # Returns: {"success": True, "synced": 50}
        """
        try:
            synced = await self.bridge.sync_beads_tasks(limit=limit)

            return {
                "success": True,
                "synced": synced,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Sync beads tasks failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }


def register_ontology_tools(server: Any, bridge: OntologyBridge) -> None:
    """Register ontology tools with MCP server.

    Args:
        server: MCP server instance
        bridge: OntologyBridge instance
    """
    tools = OntologyTools(bridge)

    # Register tools
    server.add_tool(
        name="ontology_query",
        description="Mode-aware query across Life, Projects, and Beads ontologies. Returns results prioritized by mode (execution/planning/brainstorm).",
        handler=tools.query,
        input_schema={
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "Search query text",
                },
                "mode": {
                    "type": "string",
                    "enum": ["execution", "planning", "brainstorm"],
                    "description": "Query mode for result prioritization",
                    "default": "execution",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results per ontology",
                    "default": 10,
                },
            },
            "required": ["query_text"],
        },
    )

    server.add_tool(
        name="ontology_life_list",
        description="List Life entities (People, Ideas, Admin). Optionally filter by bucket.",
        handler=tools.list_life_entities,
        input_schema={
            "type": "object",
            "properties": {
                "bucket": {
                    "type": "string",
                    "enum": ["people", "ideas", "admin"],
                    "description": "Filter by bucket type",
                },
            },
        },
    )

    server.add_tool(
        name="ontology_projects_list",
        description="List all 18 AI Exoskeleton projects with status and metadata.",
        handler=tools.list_project_entities,
        input_schema={"type": "object", "properties": {}},
    )

    server.add_tool(
        name="ontology_beads_list",
        description="List Beads tasks. Optionally filter by status.",
        handler=tools.list_beads_entities,
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "blocked", "closed", "deferred"],
                    "description": "Filter by task status",
                },
            },
        },
    )

    server.add_tool(
        name="ontology_cross_links",
        description="Get cross-ontology links for an entity (Memory -> Beads -> Project).",
        handler=tools.get_cross_links,
        input_schema={
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Entity ID to get links for",
                },
                "link_type": {
                    "type": "string",
                    "description": "Optional filter by link type",
                },
            },
            "required": ["entity_id"],
        },
    )

    server.add_tool(
        name="ontology_sync",
        description="Sync Beads tasks from CLI (bd.exe) into the ontology graph.",
        handler=tools.sync_beads_tasks,
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max tasks to sync",
                    "default": 100,
                },
            },
        },
    )

    logger.info("Ontology tools registered with MCP server")
