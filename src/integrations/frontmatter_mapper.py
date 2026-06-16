"""
Frontmatter Relationship Mapper - Extract relationships from Obsidian frontmatter.

Ported from Nexus-Properties indexer.ts extractRelationships() function.
Maps Obsidian frontmatter properties (parents, children, related) to Memory MCP
graph edges and vice versa.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import re
from loguru import logger


@dataclass
class FileRelationships:
    """
    Relationships extracted from a file's frontmatter.

    Ported from indexer.ts FileRelationships interface.
    """
    file_path: str
    mtime: float = 0.0
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    frontmatter: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationshipMapping:
    """Configuration for mapping frontmatter property to graph edge."""
    frontmatter_prop: str  # e.g., "parents"
    edge_type: str  # Memory MCP edge type
    reverse_prop: str  # Reverse relationship property
    reverse_edge_type: str  # Reverse edge type


# Default relationship mappings (matching Nexus-Properties)
DEFAULT_MAPPINGS = [
    RelationshipMapping("parents", "REFERENCES", "children", "RELATED_TO"),
    RelationshipMapping("children", "RELATED_TO", "parents", "REFERENCES"),
    RelationshipMapping("related", "MENTIONS", "related", "MENTIONS"),
]

# WHO/WHEN/PROJECT/WHY to frontmatter property mapping
TAGGING_PROPERTY_MAP = {
    "WHO": "who",
    "WHEN": "updated",
    "PROJECT": "project",
    "WHY": "why",
}


class FrontmatterMapper:
    """
    Map Obsidian frontmatter relationships to Memory MCP graph edges.

    Handles bidirectional mapping:
    - Frontmatter -> Graph: Extract relationships from YAML and create edges
    - Graph -> Frontmatter: Convert Memory MCP metadata to YAML properties

    Usage:
        mapper = FrontmatterMapper()
        relationships = mapper.extract_relationships(file_path, frontmatter)
        edges = mapper.relationships_to_edges(relationships)

        # Reverse mapping
        frontmatter = mapper.metadata_to_frontmatter(memory_metadata)
    """

    def __init__(
        self,
        mappings: Optional[List[RelationshipMapping]] = None,
        parent_prop: str = "parents",
        children_prop: str = "children",
        related_prop: str = "related"
    ):
        """
        Initialize frontmatter mapper.

        Args:
            mappings: Custom relationship mappings (or use defaults)
            parent_prop: Frontmatter property for parents
            children_prop: Frontmatter property for children
            related_prop: Frontmatter property for related
        """
        self.mappings = mappings or DEFAULT_MAPPINGS
        self.parent_prop = parent_prop
        self.children_prop = children_prop
        self.related_prop = related_prop

        logger.debug("FrontmatterMapper initialized")

    def extract_relationships(
        self,
        file_path: str,
        frontmatter: Dict[str, Any],
        mtime: float = 0.0
    ) -> FileRelationships:
        """
        Extract relationships from frontmatter.

        Ported from indexer.ts extractRelationships().

        Args:
            file_path: Path to the file
            frontmatter: Parsed YAML frontmatter dict
            mtime: File modification time

        Returns:
            FileRelationships with parent/children/related lists
        """
        relationships = FileRelationships(
            file_path=file_path,
            mtime=mtime,
            frontmatter=frontmatter
        )

        # Extract parents
        relationships.parents = self._normalize_property(
            frontmatter.get(self.parent_prop, [])
        )

        # Extract children
        relationships.children = self._normalize_property(
            frontmatter.get(self.children_prop, [])
        )

        # Extract related
        relationships.related = self._normalize_property(
            frontmatter.get(self.related_prop, [])
        )

        logger.debug(
            f"Extracted from {file_path}: "
            f"{len(relationships.parents)} parents, "
            f"{len(relationships.children)} children, "
            f"{len(relationships.related)} related"
        )

        return relationships

    def relationships_to_edges(
        self,
        relationships: FileRelationships,
        resolve_path: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert FileRelationships to Memory MCP graph edges.

        Args:
            relationships: Extracted relationships
            resolve_path: Optional function to resolve link names to paths

        Returns:
            List of edge dicts with source, target, type
        """
        edges = []
        source = relationships.file_path

        for mapping in self.mappings:
            links = self._get_relationship_links(relationships, mapping.frontmatter_prop)

            for link in links:
                target = link
                if resolve_path:
                    resolved = resolve_path(link)
                    if resolved:
                        target = resolved

                edges.append({
                    "source": source,
                    "target": target,
                    "type": mapping.edge_type,
                    "metadata": {
                        "from_frontmatter": True,
                        "property": mapping.frontmatter_prop
                    }
                })

        logger.debug(f"Created {len(edges)} edges from {source}")
        return edges

    def edges_to_relationships(
        self,
        node_id: str,
        edges: List[Dict[str, Any]]
    ) -> FileRelationships:
        """
        Convert Memory MCP graph edges to FileRelationships.

        Args:
            node_id: Source node ID
            edges: List of edge dicts from graph

        Returns:
            FileRelationships extracted from edges
        """
        relationships = FileRelationships(file_path=node_id)

        for edge in edges:
            if edge.get("source") != node_id:
                continue

            edge_type = edge.get("type", "")
            target = edge.get("target", "")

            # Map edge type to relationship category
            for mapping in self.mappings:
                if mapping.edge_type == edge_type:
                    if mapping.frontmatter_prop == "parents":
                        relationships.parents.append(target)
                    elif mapping.frontmatter_prop == "children":
                        relationships.children.append(target)
                    elif mapping.frontmatter_prop == "related":
                        relationships.related.append(target)

        return relationships

    def metadata_to_frontmatter(
        self,
        metadata: Dict[str, Any],
        existing_frontmatter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convert Memory MCP metadata to Obsidian frontmatter.

        Handles WHO/WHEN/PROJECT/WHY tagging protocol mapping.

        Args:
            metadata: Memory MCP chunk metadata
            existing_frontmatter: Existing frontmatter to merge into

        Returns:
            Frontmatter dict ready for YAML serialization
        """
        frontmatter = dict(existing_frontmatter) if existing_frontmatter else {}

        # Map tagging protocol
        for tag_key, prop_name in TAGGING_PROPERTY_MAP.items():
            if tag_key in metadata:
                value = metadata[tag_key]

                # Handle dict values (e.g., WHO: {name: "...", category: "..."})
                if isinstance(value, dict):
                    if tag_key == "WHO":
                        value = value.get("name", str(value))
                    elif tag_key == "WHEN":
                        value = value.get("iso", value.get("readable", str(value)))
                    else:
                        value = str(value)

                frontmatter[prop_name] = value

        # Map other metadata fields
        meta_mappings = {
            "title": "title",
            "source": "source",
            "decay_score": "decay_score",
            "ppr_score": "relevance",
            "created_at": "created",
        }

        for meta_key, prop_name in meta_mappings.items():
            if meta_key in metadata and metadata[meta_key]:
                frontmatter[prop_name] = metadata[meta_key]

        return frontmatter

    def frontmatter_to_metadata(
        self,
        frontmatter: Dict[str, Any],
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convert Obsidian frontmatter to Memory MCP metadata.

        Args:
            frontmatter: Parsed YAML frontmatter
            existing_metadata: Existing metadata to merge into

        Returns:
            Memory MCP metadata dict with WHO/WHEN/PROJECT/WHY
        """
        metadata = dict(existing_metadata) if existing_metadata else {}

        # Reverse map tagging protocol
        for tag_key, prop_name in TAGGING_PROPERTY_MAP.items():
            if prop_name in frontmatter:
                value = frontmatter[prop_name]

                # Build structured value for WHO/WHEN
                if tag_key == "WHO":
                    metadata[tag_key] = {"name": value, "category": "obsidian"}
                elif tag_key == "WHEN":
                    metadata[tag_key] = {"readable": value, "iso": value}
                else:
                    metadata[tag_key] = value

        # Map standard fields
        if "title" in frontmatter:
            metadata["title"] = frontmatter["title"]
        if "tags" in frontmatter:
            metadata["tags"] = frontmatter["tags"]

        return metadata

    def compute_relationship_diff(
        self,
        old_relationships: FileRelationships,
        new_relationships: FileRelationships
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Compute diff between old and new relationships.

        Args:
            old_relationships: Previous relationships
            new_relationships: New relationships

        Returns:
            Dict with added/removed for each relationship type
        """
        diff = {}

        for rel_type in ["parents", "children", "related"]:
            old_set = set(getattr(old_relationships, rel_type))
            new_set = set(getattr(new_relationships, rel_type))

            diff[rel_type] = {
                "added": list(new_set - old_set),
                "removed": list(old_set - new_set)
            }

        return diff

    def _normalize_property(self, value: Any) -> List[str]:
        """Normalize frontmatter property to list of link names."""
        if not value:
            return []

        if isinstance(value, str):
            return [self._extract_link_name(value)]

        if isinstance(value, list):
            return [self._extract_link_name(v) for v in value if v]

        return []

    def _extract_link_name(self, link: Any) -> str:
        """Extract name from wiki link [[Name|Alias]] -> Name."""
        if not isinstance(link, str):
            return str(link)

        # Match [[Name]] or [[Name|Alias]]
        match = re.match(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', link.strip())
        if match:
            return match.group(1)

        return link.strip()

    def _get_relationship_links(
        self,
        relationships: FileRelationships,
        prop_name: str
    ) -> List[str]:
        """Get links for a specific relationship type."""
        if prop_name == self.parent_prop or prop_name == "parents":
            return relationships.parents
        elif prop_name == self.children_prop or prop_name == "children":
            return relationships.children
        elif prop_name == self.related_prop or prop_name == "related":
            return relationships.related
        return []
