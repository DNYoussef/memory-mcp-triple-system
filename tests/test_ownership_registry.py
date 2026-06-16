"""Tests for Ownership Registry.

WHO: ownership-registry:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (GRAPH-002)
"""

import os
import pytest
import tempfile
import shutil

from src.services.ownership_registry import OwnershipRegistry
from src.integrations.ontology_schema import (
    ComponentType,
    OwnershipViolationType,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


@pytest.fixture
def registry(temp_dir):
    """Create OwnershipRegistry instance."""
    return OwnershipRegistry(data_dir=temp_dir)


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample file for testing."""
    file_path = os.path.join(temp_dir, "sample_skill.md")
    with open(file_path, "w") as f:
        f.write("# Sample Skill\n\nThis is a test skill file.")
    return file_path


# ========== REGISTRATION TESTS ==========


def test_register_component(registry, sample_file):
    """Test registering a component."""
    success = registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
        version="1.0.0",
    )

    assert success
    component = registry.get_component("skill:sample")
    assert component is not None
    assert component.canonical_path == sample_file
    assert component.owner_project == "test-project"
    assert component.content_hash  # Hash should be computed


def test_register_nonexistent_file(registry, temp_dir):
    """Test registering a component with nonexistent file."""
    fake_path = os.path.join(temp_dir, "nonexistent.md")

    success = registry.register_component(
        component_id="skill:fake",
        component_type=ComponentType.SKILL,
        canonical_path=fake_path,
        owner_project="test-project",
    )

    assert not success
    assert registry.get_component("skill:fake") is None


def test_list_components(registry, temp_dir):
    """Test listing components."""
    # Create multiple files
    for i, comp_type in enumerate(
        [ComponentType.SKILL, ComponentType.AGENT, ComponentType.SKILL]
    ):
        file_path = os.path.join(temp_dir, f"component_{i}.md")
        with open(file_path, "w") as f:
            f.write(f"# Component {i}")

        registry.register_component(
            component_id=f"{comp_type.value}:test{i}",
            component_type=comp_type,
            canonical_path=file_path,
            owner_project="test-project",
        )

    # List all
    all_components = registry.list_components()
    assert len(all_components) == 3

    # Filter by type
    skills = registry.list_components(component_type=ComponentType.SKILL)
    assert len(skills) == 2

    agents = registry.list_components(component_type=ComponentType.AGENT)
    assert len(agents) == 1


# ========== VERIFICATION TESTS ==========


def test_verify_component_valid(registry, sample_file):
    """Test verifying a valid component."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    violation = registry.verify_component("skill:sample")
    assert violation is None  # No violation = valid


def test_verify_component_hash_mismatch(registry, sample_file):
    """Test detecting hash mismatch."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Modify the file
    with open(sample_file, "w") as f:
        f.write("# Modified content")

    violation = registry.verify_component("skill:sample")
    assert violation is not None
    assert violation.violation_type == OwnershipViolationType.HASH_MISMATCH


def test_verify_component_missing_canonical(registry, sample_file):
    """Test detecting missing canonical file."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Delete the file
    os.remove(sample_file)

    violation = registry.verify_component("skill:sample")
    assert violation is not None
    assert violation.violation_type == OwnershipViolationType.MISSING_CANONICAL


# ========== DRIFT DETECTION TESTS ==========


def test_detect_drift_no_violations(registry, sample_file):
    """Test drift detection with no violations."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    violations = registry.detect_drift()
    assert len(violations) == 0


def test_detect_drift_duplicate(registry, temp_dir, sample_file):
    """Test detecting duplicate files."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Create duplicate in different location
    scan_dir = os.path.join(temp_dir, "scan")
    os.makedirs(scan_dir)
    duplicate_path = os.path.join(scan_dir, "sample_skill.md")
    shutil.copy(sample_file, duplicate_path)

    violations = registry.detect_drift(scan_paths=[scan_dir])

    assert len(violations) > 0
    assert any(
        v.violation_type == OwnershipViolationType.DUPLICATE_LOCATION
        for v in violations
    )


def test_detect_drift_modified_copy(registry, temp_dir, sample_file):
    """Test detecting modified copies."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Create modified copy
    scan_dir = os.path.join(temp_dir, "scan")
    os.makedirs(scan_dir)
    modified_path = os.path.join(scan_dir, "sample_skill.md")
    with open(modified_path, "w") as f:
        f.write("# Modified copy")

    violations = registry.detect_drift(scan_paths=[scan_dir])

    assert len(violations) > 0
    assert any(
        v.violation_type == OwnershipViolationType.HASH_MISMATCH for v in violations
    )


# ========== FIX VIOLATION TESTS ==========


def test_fix_violations_delete_duplicate(registry, temp_dir, sample_file):
    """Test fixing duplicate by deletion."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Create duplicate
    scan_dir = os.path.join(temp_dir, "scan")
    os.makedirs(scan_dir)
    duplicate_path = os.path.join(scan_dir, "sample_skill.md")
    shutil.copy(sample_file, duplicate_path)

    violations = registry.detect_drift(scan_paths=[scan_dir])
    assert len(violations) > 0

    # Fix violations
    results = registry.fix_violations(violations, auto_fix=True)
    assert len(results["fixed"]) > 0

    # Verify duplicate is deleted
    assert not os.path.exists(duplicate_path)


def test_fix_violations_sync_modified(registry, temp_dir, sample_file):
    """Test fixing modified copy by sync."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Create modified copy
    scan_dir = os.path.join(temp_dir, "scan")
    os.makedirs(scan_dir)
    modified_path = os.path.join(scan_dir, "sample_skill.md")
    with open(modified_path, "w") as f:
        f.write("# Modified copy")

    violations = registry.detect_drift(scan_paths=[scan_dir])
    assert len(violations) > 0

    # Fix violations
    results = registry.fix_violations(violations, auto_fix=True)
    assert len(results["fixed"]) > 0

    # Verify modified copy matches canonical
    with open(modified_path, "r") as f:
        modified_content = f.read()
    with open(sample_file, "r") as f:
        canonical_content = f.read()
    assert modified_content == canonical_content


def test_fix_violations_dry_run(registry, temp_dir, sample_file):
    """Test dry run doesn't change files."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Create duplicate
    scan_dir = os.path.join(temp_dir, "scan")
    os.makedirs(scan_dir)
    duplicate_path = os.path.join(scan_dir, "sample_skill.md")
    shutil.copy(sample_file, duplicate_path)

    violations = registry.detect_drift(scan_paths=[scan_dir])

    # Dry run
    results = registry.fix_violations(  # noqa: F841
        violations, auto_fix=True, dry_run=True
    )

    # File should still exist
    assert os.path.exists(duplicate_path)


# ========== PERSISTENCE TESTS ==========


def test_save_and_load(registry, sample_file, temp_dir):
    """Test saving and loading registry."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
        version="1.0.0",
    )

    # Save
    assert registry.save()

    # Create new registry and load
    registry2 = OwnershipRegistry(data_dir=temp_dir)
    assert registry2.load()

    # Verify component loaded
    component = registry2.get_component("skill:sample")
    assert component is not None
    assert component.canonical_path == sample_file


def test_export_import_manifest(registry, sample_file, temp_dir):
    """Test exporting and importing manifest."""
    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
    )

    # Export
    manifest_path = os.path.join(temp_dir, "manifest.json")
    assert registry.export_manifest(manifest_path)

    # Create new registry and import
    registry2 = OwnershipRegistry(data_dir=temp_dir + "_new")
    os.makedirs(temp_dir + "_new", exist_ok=True)
    imported = registry2.import_manifest(manifest_path)

    assert imported == 1
    component = registry2.get_component("skill:sample")
    assert component is not None


# ========== ALLOWED COPIES TESTS ==========


def test_allowed_copies_not_flagged(registry, temp_dir, sample_file):
    """Test that allowed copies are not flagged as violations."""
    scan_dir = os.path.join(temp_dir, "allowed")
    os.makedirs(scan_dir)

    registry.register_component(
        component_id="skill:sample",
        component_type=ComponentType.SKILL,
        canonical_path=sample_file,
        owner_project="test-project",
        allowed_copies=[scan_dir],  # This directory is allowed
    )

    # Create copy in allowed location
    copy_path = os.path.join(scan_dir, "sample_skill.md")
    shutil.copy(sample_file, copy_path)

    violations = registry.detect_drift(scan_paths=[scan_dir])

    # Should not flag allowed copies
    assert len(violations) == 0
