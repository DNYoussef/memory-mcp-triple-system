"""Ontology schemas for the Unified Ontology Bridge.

Defines three ontologies:
1. Life: People, Ideas, Admin (personal knowledge)
2. Projects: 18 exoskeleton projects (technical artifacts)
3. Beads: Tasks, Dependencies, State (procedural memory)

Cross-links: Memory entity -> Beads task -> Project

WHO: ontology-bridge:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (GRAPH-001)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


# ========== LIFE ONTOLOGY ==========


class LifeBucketType(str, Enum):
    """Life bucket categories for personal knowledge."""

    PEOPLE = "people"
    IDEAS = "ideas"
    ADMIN = "admin"


@dataclass(frozen=True)
class LifeEntity:
    """Entity in the Life ontology.

    Examples:
    - People: "John Doe", "Alice Smith"
    - Ideas: "RAG Pipeline Pattern", "Byzantine Consensus"
    - Admin: "Tax Filing 2026", "Health Insurance"
    """

    id: str
    bucket: LifeBucketType
    name: str
    description: Optional[str] = None
    metadata: Dict[str, any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> LifeEntity:
        return cls(
            id=data["id"],
            bucket=LifeBucketType(data["bucket"]),
            name=data["name"],
            description=data.get("description"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            tags=data.get("tags", []),
        )


# ========== PROJECT ONTOLOGY ==========


class ProjectRole(str, Enum):
    """Biological metaphor roles for projects."""

    CENTRAL_NERVOUS_SYSTEM = "central-nervous-system"
    MOTOR_CORTEX = "motor-cortex"
    IMMUNE_SYSTEM = "immune-system"
    EYES_EARS = "eyes-ears"
    INTESTINES_LEGS = "intestines-legs"
    ARMS = "arms"
    MEDIA_RECEPTORS = "media-receptors"
    FINANCIAL_ORGANS = "financial-organs"
    LIVER = "liver"
    CEREBELLUM = "cerebellum"
    FACE = "face"
    EXTENDED_REACH = "extended-reach"
    COMPETITION_ARMOR = "competition-armor"
    SIDE_PROJECT = "side-project"
    RESEARCH = "research"
    TOOL = "tool"
    BONE_MARROW = "bone-marrow"


@dataclass(frozen=True)
class ProjectEntity:
    """Entity in the Project ontology.

    Represents one of the 18 AI Exoskeleton projects.
    """

    id: str
    name: str
    role: ProjectRole
    location: str
    status_percent: int
    repository: Optional[str] = None
    tech_stack: List[str] = field(default_factory=list)
    metadata: Dict[str, any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> ProjectEntity:
        return cls(
            id=data["id"],
            name=data["name"],
            role=ProjectRole(data["role"]),
            location=data["location"],
            status_percent=data["status_percent"],
            repository=data.get("repository"),
            tech_stack=data.get("tech_stack", []),
            metadata=data.get("metadata", {}),
        )


# ========== BEADS ONTOLOGY ==========


class BeadsStatus(str, Enum):
    """Beads task status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    CLOSED = "closed"
    DEFERRED = "deferred"


@dataclass(frozen=True)
class BeadsEntity:
    """Entity in the Beads ontology.

    Represents a task in the Beads dependency graph.
    """

    id: str
    title: str
    status: BeadsStatus
    project_id: Optional[str] = None  # Link to ProjectEntity.id
    dependencies: List[str] = field(default_factory=list)  # Other BeadsEntity IDs
    dependents: List[str] = field(default_factory=list)
    estimated_minutes: int = 0
    labels: List[str] = field(default_factory=list)
    metadata: Dict[str, any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> BeadsEntity:
        return cls(
            id=data["id"],
            title=data["title"],
            status=BeadsStatus(data["status"]),
            project_id=data.get("project_id"),
            dependencies=data.get("dependencies", []),
            dependents=data.get("dependents", []),
            estimated_minutes=data.get("estimated_minutes", 0),
            labels=data.get("labels", []),
            metadata=data.get("metadata", {}),
        )


# ========== CROSS-LINK RELATIONSHIPS ==========


class CrossLinkType(str, Enum):
    """Types of cross-ontology relationships."""

    # Life -> Beads
    PERSON_OWNS_TASK = "person-owns-task"
    IDEA_INSPIRES_TASK = "idea-inspires-task"
    ADMIN_TRIGGERS_TASK = "admin-triggers-task"

    # Life -> Project
    PERSON_CONTRIBUTES_PROJECT = "person-contributes-project"
    IDEA_INFLUENCES_PROJECT = "idea-influences-project"

    # Beads -> Project
    TASK_BELONGS_TO_PROJECT = "task-belongs-to-project"

    # Memory -> Beads (explicit cross-reference)
    MEMORY_REFERENCES_TASK = "memory-references-task"

    # Memory -> Project
    MEMORY_DOCUMENTS_PROJECT = "memory-documents-project"


@dataclass(frozen=True)
class CrossLink:
    """Cross-ontology relationship link."""

    source_id: str
    source_ontology: str  # "life" | "project" | "beads" | "memory"
    target_id: str
    target_ontology: str
    link_type: CrossLinkType
    confidence: float = 1.0
    created_at: Optional[datetime] = None
    metadata: Dict[str, any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> CrossLink:
        return cls(
            source_id=data["source_id"],
            source_ontology=data["source_ontology"],
            target_id=data["target_id"],
            target_ontology=data["target_ontology"],
            link_type=CrossLinkType(data["link_type"]),
            confidence=data.get("confidence", 1.0),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            metadata=data.get("metadata", {}),
        )


# ========== ONTOLOGY REGISTRY ==========


# ========== OWNERSHIP ONTOLOGY (GRAPH-002) ==========


class ComponentType(str, Enum):
    """Types of components that can be owned."""

    SKILL = "skill"
    AGENT = "agent"
    COMMAND = "command"
    HOOK = "hook"
    PLAYBOOK = "playbook"
    SERVICE = "service"
    SCHEMA = "schema"
    CONFIG = "config"
    SCRIPT = "script"
    DOCUMENTATION = "documentation"


class OwnershipViolationType(str, Enum):
    """Types of ownership violations."""

    DUPLICATE_LOCATION = "duplicate-location"  # Same component in multiple places
    HASH_MISMATCH = "hash-mismatch"  # Content changed from canonical
    MISSING_CANONICAL = "missing-canonical"  # Canonical file deleted
    ORPHAN_COPY = "orphan-copy"  # Copy exists without canonical
    VERSION_DRIFT = "version-drift"  # Version out of sync


@dataclass
class ComponentOwnership:
    """Defines canonical ownership of a component.

    WHO: ownership-registry:1.0.0
    WHEN: 2026-01-15
    PROJECT: memory-mcp-triple-system
    WHY: implementation (GRAPH-002)
    """

    id: str  # Unique component ID (e.g., "skill:code", "agent:coder")
    component_type: ComponentType
    canonical_path: str  # Absolute path to the canonical file
    content_hash: str  # SHA-256 hash of canonical content
    version: str  # Semantic version
    owner_project: str  # Project that owns this component
    allowed_copies: List[str] = field(default_factory=list)  # Paths allowed to have copies
    last_verified: Optional[datetime] = None
    metadata: Dict[str, any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> ComponentOwnership:
        return cls(
            id=data["id"],
            component_type=ComponentType(data["component_type"]),
            canonical_path=data["canonical_path"],
            content_hash=data["content_hash"],
            version=data["version"],
            owner_project=data["owner_project"],
            allowed_copies=data.get("allowed_copies", []),
            last_verified=datetime.fromisoformat(data["last_verified"])
            if data.get("last_verified")
            else None,
            metadata=data.get("metadata", {}),
        )


@dataclass
class OwnershipViolation:
    """A detected violation of ownership rules."""

    id: str  # Violation ID
    component_id: str  # Reference to ComponentOwnership.id
    violation_type: OwnershipViolationType
    severity: str  # "low", "medium", "high", "critical"
    canonical_path: str
    violating_path: str  # Path of the violating file
    canonical_hash: str
    violating_hash: str
    detected_at: datetime
    auto_fixable: bool = True
    fix_action: Optional[str] = None  # "sync", "delete", "restore"
    metadata: Dict[str, any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> OwnershipViolation:
        return cls(
            id=data["id"],
            component_id=data["component_id"],
            violation_type=OwnershipViolationType(data["violation_type"]),
            severity=data["severity"],
            canonical_path=data["canonical_path"],
            violating_path=data["violating_path"],
            canonical_hash=data["canonical_hash"],
            violating_hash=data["violating_hash"],
            detected_at=datetime.fromisoformat(data["detected_at"]),
            auto_fixable=data.get("auto_fixable", True),
            fix_action=data.get("fix_action"),
            metadata=data.get("metadata", {}),
        )


ONTOLOGY_REGISTRY = {
    "life": {
        "node_type": "LIFE_ENTITY",
        "entity_class": LifeEntity,
        "buckets": ["people", "ideas", "admin"],
    },
    "project": {
        "node_type": "PROJECT_ENTITY",
        "entity_class": ProjectEntity,
        "count": 18,
    },
    "beads": {
        "node_type": "BEADS_ENTITY",
        "entity_class": BeadsEntity,
        "graph_backed": True,
    },
    "memory": {
        "node_type": "MEMORY_CHUNK",  # Existing node type in GraphService
        "cross_ref_only": True,  # Memory MCP doesn't create new entities, just links
    },
    "ownership": {
        "node_type": "OWNERSHIP_ENTITY",
        "entity_class": ComponentOwnership,
        "graph_backed": True,
    },
}
