"""Tests for Unified Ontology Bridge.

WHO: ontology-bridge:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (GRAPH-001)
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from src.integrations.ontology_schema import (
    LifeEntity,
    LifeBucketType,
    ProjectEntity,
    ProjectRole,
    BeadsEntity,
    BeadsStatus,
    CrossLink,
    CrossLinkType,
)
from src.services.ontology_bridge import OntologyBridge


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def bridge(temp_data_dir):
    """Create OntologyBridge instance."""
    return OntologyBridge(data_dir=temp_data_dir)


# ========== LIFE ONTOLOGY TESTS ==========


def test_add_life_entity_people(bridge):
    """Test adding a person to Life ontology."""
    entity = LifeEntity(
        id="person:alice",
        bucket=LifeBucketType.PEOPLE,
        name="Alice Smith",
        description="Senior Engineer at TechCorp",
        tags=["colleague", "engineer"],
    )

    assert bridge.add_life_entity(entity)

    # Verify retrieval
    retrieved = bridge.get_life_entity("person:alice")
    assert retrieved is not None
    assert retrieved.name == "Alice Smith"
    assert retrieved.bucket == LifeBucketType.PEOPLE
    assert "colleague" in retrieved.tags


def test_add_life_entity_ideas(bridge):
    """Test adding an idea to Life ontology."""
    entity = LifeEntity(
        id="idea:rag-pipeline",
        bucket=LifeBucketType.IDEAS,
        name="RAG Pipeline Pattern",
        description="Retrieval-Augmented Generation with 3-tier ranking",
        metadata={"source": "research", "confidence": 0.95},
    )

    assert bridge.add_life_entity(entity)

    # Verify retrieval
    retrieved = bridge.get_life_entity("idea:rag-pipeline")
    assert retrieved is not None
    assert retrieved.name == "RAG Pipeline Pattern"
    assert retrieved.metadata.get("confidence") == 0.95


def test_list_life_entities_filtered_by_bucket(bridge):
    """Test listing Life entities filtered by bucket."""
    # Add multiple entities
    bridge.add_life_entity(
        LifeEntity(
            id="person:bob",
            bucket=LifeBucketType.PEOPLE,
            name="Bob Jones",
        )
    )
    bridge.add_life_entity(
        LifeEntity(
            id="idea:consensus",
            bucket=LifeBucketType.IDEAS,
            name="Byzantine Consensus",
        )
    )
    bridge.add_life_entity(
        LifeEntity(
            id="admin:tax",
            bucket=LifeBucketType.ADMIN,
            name="Tax Filing 2026",
        )
    )

    # List all
    all_entities = bridge.list_life_entities()
    assert len(all_entities) == 3

    # Filter by PEOPLE
    people = bridge.list_life_entities(bucket=LifeBucketType.PEOPLE)
    assert len(people) == 1
    assert people[0].id == "person:bob"

    # Filter by IDEAS
    ideas = bridge.list_life_entities(bucket=LifeBucketType.IDEAS)
    assert len(ideas) == 1
    assert ideas[0].name == "Byzantine Consensus"


# ========== PROJECT ONTOLOGY TESTS ==========


def test_add_project_entity(bridge):
    """Test adding a project to Project ontology."""
    entity = ProjectEntity(
        id="project:memory-mcp",
        name="memory-mcp",
        role=ProjectRole.CENTRAL_NERVOUS_SYSTEM,
        location="D:\\Projects\\memory-mcp-triple-system",
        status_percent=90,
        repository="github.com/DNYoussef/memory-mcp-triple-system",
        tech_stack=["Python", "NetworkX", "ChromaDB"],
    )

    assert bridge.add_project_entity(entity)

    # Verify retrieval
    retrieved = bridge.get_project_entity("project:memory-mcp")
    assert retrieved is not None
    assert retrieved.name == "memory-mcp"
    assert retrieved.role == ProjectRole.CENTRAL_NERVOUS_SYSTEM
    assert retrieved.status_percent == 90
    assert "Python" in retrieved.tech_stack


def test_list_project_entities(bridge):
    """Test listing all projects."""
    # Add multiple projects
    bridge.add_project_entity(
        ProjectEntity(
            id="project:memory-mcp",
            name="memory-mcp",
            role=ProjectRole.CENTRAL_NERVOUS_SYSTEM,
            location="D:\\Projects\\memory-mcp-triple-system",
            status_percent=90,
        )
    )
    bridge.add_project_entity(
        ProjectEntity(
            id="project:trader-ai",
            name="trader-ai",
            role=ProjectRole.FINANCIAL_ORGANS,
            location="D:\\Projects\\trader-ai",
            status_percent=45,
        )
    )

    projects = bridge.list_project_entities()
    assert len(projects) == 2
    assert any(p.name == "memory-mcp" for p in projects)
    assert any(p.name == "trader-ai" for p in projects)


# ========== BEADS ONTOLOGY TESTS ==========


def test_add_beads_entity(bridge):
    """Test adding a Beads task."""
    entity = BeadsEntity(
        id="task:auth-impl",
        title="Implement JWT authentication",
        status=BeadsStatus.IN_PROGRESS,
        project_id="project:trader-ai",
        dependencies=["task:db-setup"],
        estimated_minutes=240,
        labels=["auth", "security"],
    )

    assert bridge.add_beads_entity(entity)

    # Verify retrieval
    retrieved = bridge.get_beads_entity("task:auth-impl")
    assert retrieved is not None
    assert retrieved.title == "Implement JWT authentication"
    assert retrieved.status == BeadsStatus.IN_PROGRESS
    assert retrieved.project_id == "project:trader-ai"
    assert "auth" in retrieved.labels


def test_list_beads_entities_filtered_by_status(bridge):
    """Test listing Beads tasks filtered by status."""
    # Add multiple tasks
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:1",
            title="Task 1",
            status=BeadsStatus.OPEN,
        )
    )
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:2",
            title="Task 2",
            status=BeadsStatus.IN_PROGRESS,
        )
    )
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:3",
            title="Task 3",
            status=BeadsStatus.CLOSED,
        )
    )

    # List all
    all_tasks = bridge.list_beads_entities()
    assert len(all_tasks) == 3

    # Filter by IN_PROGRESS
    in_progress = bridge.list_beads_entities(status=BeadsStatus.IN_PROGRESS)
    assert len(in_progress) == 1
    assert in_progress[0].id == "task:2"


# ========== CROSS-LINK TESTS ==========


def test_add_cross_link_life_to_beads(bridge):
    """Test cross-linking Life entity to Beads task."""
    # Add entities
    bridge.add_life_entity(
        LifeEntity(
            id="person:alice",
            bucket=LifeBucketType.PEOPLE,
            name="Alice Smith",
        )
    )
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:auth",
            title="Implement auth",
            status=BeadsStatus.OPEN,
        )
    )

    # Add cross-link
    link = CrossLink(
        source_id="person:alice",
        source_ontology="life",
        target_id="task:auth",
        target_ontology="beads",
        link_type=CrossLinkType.PERSON_OWNS_TASK,
        confidence=0.95,
    )
    assert bridge.add_cross_link(link)

    # Verify cross-link
    links = bridge.get_cross_links("person:alice")
    assert len(links) > 0
    assert links[0].target_id == "task:auth"
    assert links[0].link_type == CrossLinkType.PERSON_OWNS_TASK


def test_add_cross_link_beads_to_project(bridge):
    """Test cross-linking Beads task to Project."""
    # Add entities
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:feature",
            title="Add feature",
            status=BeadsStatus.OPEN,
        )
    )
    bridge.add_project_entity(
        ProjectEntity(
            id="project:trader-ai",
            name="trader-ai",
            role=ProjectRole.FINANCIAL_ORGANS,
            location="D:\\Projects\\trader-ai",
            status_percent=45,
        )
    )

    # Add cross-link
    link = CrossLink(
        source_id="task:feature",
        source_ontology="beads",
        target_id="project:trader-ai",
        target_ontology="project",
        link_type=CrossLinkType.TASK_BELONGS_TO_PROJECT,
    )
    assert bridge.add_cross_link(link)

    # Verify cross-link
    links = bridge.get_cross_links("task:feature")
    assert len(links) > 0
    assert links[0].target_id == "project:trader-ai"


def test_cross_link_chain_memory_beads_project(bridge):
    """Test cross-link chain: Memory -> Beads -> Project."""
    # Add entities
    bridge.graph.add_chunk_node("memory:doc1", {"text": "Auth implementation notes"})
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:auth",
            title="Implement auth",
            status=BeadsStatus.OPEN,
        )
    )
    bridge.add_project_entity(
        ProjectEntity(
            id="project:trader-ai",
            name="trader-ai",
            role=ProjectRole.FINANCIAL_ORGANS,
            location="D:\\Projects\\trader-ai",
            status_percent=45,
        )
    )

    # Add cross-links
    bridge.add_cross_link(
        CrossLink(
            source_id="memory:doc1",
            source_ontology="memory",
            target_id="task:auth",
            target_ontology="beads",
            link_type=CrossLinkType.MEMORY_REFERENCES_TASK,
        )
    )
    bridge.add_cross_link(
        CrossLink(
            source_id="task:auth",
            source_ontology="beads",
            target_id="project:trader-ai",
            target_ontology="project",
            link_type=CrossLinkType.TASK_BELONGS_TO_PROJECT,
        )
    )

    # Verify chain
    memory_links = bridge.get_cross_links("memory:doc1")
    assert len(memory_links) > 0
    assert memory_links[0].target_id == "task:auth"

    beads_links = bridge.get_cross_links("task:auth")
    assert len(beads_links) > 0
    assert beads_links[0].target_id == "project:trader-ai"


# ========== MODE-AWARE QUERY TESTS ==========


@pytest.mark.asyncio
async def test_query_execution_mode(bridge):
    """Test query in execution mode (Beads priority)."""
    # Add entities
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:auth",
            title="Implement authentication",
            status=BeadsStatus.OPEN,
        )
    )
    bridge.graph.add_chunk_node("memory:auth", {"text": "Authentication pattern notes"})

    # Query in execution mode
    results = await bridge.query("authentication", mode="execution")

    # Should prioritize Beads (80%)
    assert "beads" in results
    assert len(results["beads"]) > 0


@pytest.mark.asyncio
async def test_query_planning_mode(bridge):
    """Test query in planning mode (balanced)."""
    # Add entities
    bridge.add_beads_entity(
        BeadsEntity(
            id="task:plan",
            title="Plan architecture",
            status=BeadsStatus.OPEN,
        )
    )
    bridge.add_project_entity(
        ProjectEntity(
            id="project:trader-ai",
            name="trader-ai",
            role=ProjectRole.FINANCIAL_ORGANS,
            location="D:\\Projects\\trader-ai",
            status_percent=45,
        )
    )

    # Query in planning mode
    results = await bridge.query("architecture", mode="planning")

    # Should balance Beads and Memory (50/50)
    assert "beads" in results
    assert "projects" in results


@pytest.mark.asyncio
async def test_query_brainstorm_mode(bridge):
    """Test query in brainstorm mode (Memory priority)."""
    # Add entities
    bridge.add_life_entity(
        LifeEntity(
            id="idea:pattern",
            bucket=LifeBucketType.IDEAS,
            name="Design Pattern",
            description="Architectural pattern for microservices",
        )
    )
    bridge.graph.add_chunk_node("memory:pattern", {"text": "Design pattern notes"})

    # Query in brainstorm mode
    results = await bridge.query("pattern", mode="brainstorm")

    # Should prioritize Memory (80%)
    assert "life" in results
    assert "memory" in results


# ========== PERSISTENCE TESTS ==========


def test_save_and_load(bridge):
    """Test saving and loading graph."""
    # Add entities
    bridge.add_life_entity(
        LifeEntity(
            id="person:test",
            bucket=LifeBucketType.PEOPLE,
            name="Test Person",
        )
    )
    bridge.add_project_entity(
        ProjectEntity(
            id="project:test",
            name="test-project",
            role=ProjectRole.TOOL,
            location="/test/path",
            status_percent=50,
        )
    )

    # Save
    assert bridge.save()

    # Create new bridge and load
    bridge2 = OntologyBridge(data_dir=bridge.data_dir)
    assert bridge2.load()

    # Verify entities
    assert bridge2.get_life_entity("person:test") is not None
    assert bridge2.get_project_entity("project:test") is not None
