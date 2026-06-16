"""Ownership Registry - Drift Prevention for Components.

Defines explicit ownership rules to prevent drift and duplication:
- One canonical location per component
- Version tracking with SHA-256 hash
- Drift detection for CI integration
- Automatic sync on violation

WHO: ownership-registry:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (GRAPH-002)
"""

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from ..integrations.ontology_schema import (
    ComponentOwnership,
    ComponentType,
    OwnershipViolation,
    OwnershipViolationType,
)
from .graph_service import GraphService


class OwnershipRegistry:
    """Registry for tracking component ownership and detecting drift.

    Usage:
        registry = OwnershipRegistry(data_dir="./data")
        registry.initialize()

        # Register a component
        registry.register_component(
            component_id="skill:code",
            component_type=ComponentType.SKILL,
            canonical_path="/path/to/skill.md",
            owner_project="context-cascade",
            version="1.0.0"
        )

        # Detect drift
        violations = registry.detect_drift()

        # Auto-fix violations
        fixed = registry.fix_violations(violations, auto_fix=True)
    """

    NODE_TYPE_OWNERSHIP = "OWNERSHIP_ENTITY"
    EDGE_TYPE_OWNS = "OWNS_COMPONENT"
    EDGE_TYPE_COPY_OF = "COPY_OF"

    # Severity thresholds
    SEVERITY_MAP = {
        OwnershipViolationType.DUPLICATE_LOCATION: "high",
        OwnershipViolationType.HASH_MISMATCH: "medium",
        OwnershipViolationType.MISSING_CANONICAL: "critical",
        OwnershipViolationType.ORPHAN_COPY: "low",
        OwnershipViolationType.VERSION_DRIFT: "low",
    }

    def __init__(
        self,
        data_dir: str = "./data",
        graph_service: Optional[GraphService] = None,
    ):
        """Initialize ownership registry.

        Args:
            data_dir: Directory for persistence
            graph_service: Optional existing GraphService to use
        """
        self.data_dir = Path(data_dir)
        self.graph = graph_service or GraphService(data_dir=str(self.data_dir))
        self._components: Dict[str, ComponentOwnership] = {}
        self._violation_counter = 0
        logger.info("OwnershipRegistry initialized")

    def initialize(self) -> None:
        """Initialize registry, loading any existing data."""
        self.graph.load_graph()
        self._load_components_from_graph()
        logger.info(f"Loaded {len(self._components)} registered components")

    def _load_components_from_graph(self) -> None:
        """Load component registrations from graph nodes."""
        for node_id in self.graph.graph.nodes():
            node = self.graph.get_node(node_id)
            if not node:
                continue
            metadata = node.get("metadata", {})
            if metadata.get("type") == self.NODE_TYPE_OWNERSHIP:
                try:
                    component = ComponentOwnership(
                        id=node_id,
                        component_type=ComponentType(metadata.get("component_type", "skill")),
                        canonical_path=metadata.get("canonical_path", ""),
                        content_hash=metadata.get("content_hash", ""),
                        version=metadata.get("version", "0.0.0"),
                        owner_project=metadata.get("owner_project", ""),
                        allowed_copies=metadata.get("allowed_copies", []),
                        last_verified=datetime.fromisoformat(metadata["last_verified"])
                        if metadata.get("last_verified")
                        else None,
                        metadata=metadata.get("extra", {}),
                    )
                    self._components[node_id] = component
                except Exception as e:
                    logger.warning(f"Failed to load component {node_id}: {e}")

    def register_component(
        self,
        component_id: str,
        component_type: ComponentType,
        canonical_path: str,
        owner_project: str,
        version: str = "1.0.0",
        allowed_copies: Optional[List[str]] = None,
    ) -> bool:
        """Register a component with its canonical location.

        Args:
            component_id: Unique ID (e.g., "skill:code", "agent:coder")
            component_type: Type of component
            canonical_path: Absolute path to canonical file
            owner_project: Project that owns this component
            version: Semantic version
            allowed_copies: List of paths where copies are allowed

        Returns:
            True if registration successful
        """
        # Compute hash of canonical file
        content_hash = self._compute_file_hash(canonical_path)
        if not content_hash:
            logger.error(f"Cannot register {component_id}: file not found at {canonical_path}")
            return False

        component = ComponentOwnership(
            id=component_id,
            component_type=component_type,
            canonical_path=canonical_path,
            content_hash=content_hash,
            version=version,
            owner_project=owner_project,
            allowed_copies=allowed_copies or [],
            last_verified=datetime.utcnow(),
        )

        # Store in graph
        metadata = {
            "type": self.NODE_TYPE_OWNERSHIP,
            "component_type": component_type.value,
            "canonical_path": canonical_path,
            "content_hash": content_hash,
            "version": version,
            "owner_project": owner_project,
            "allowed_copies": allowed_copies or [],
            "last_verified": component.last_verified.isoformat(),
        }

        entity_type = f"ownership-{component_type.value}"
        self.graph.add_chunk_node(component_id, metadata)

        self._components[component_id] = component
        logger.info(f"Registered component: {component_id} at {canonical_path}")
        return True

    def get_component(self, component_id: str) -> Optional[ComponentOwnership]:
        """Get a registered component by ID."""
        return self._components.get(component_id)

    def list_components(
        self,
        component_type: Optional[ComponentType] = None,
        owner_project: Optional[str] = None,
    ) -> List[ComponentOwnership]:
        """List registered components with optional filtering."""
        components = list(self._components.values())

        if component_type:
            components = [c for c in components if c.component_type == component_type]

        if owner_project:
            components = [c for c in components if c.owner_project == owner_project]

        return components

    def verify_component(self, component_id: str) -> Optional[OwnershipViolation]:
        """Verify a single component's integrity.

        Returns:
            OwnershipViolation if drift detected, None if OK
        """
        component = self._components.get(component_id)
        if not component:
            logger.warning(f"Component {component_id} not registered")
            return None

        # Check if canonical file exists
        if not os.path.exists(component.canonical_path):
            return self._create_violation(
                component_id=component_id,
                violation_type=OwnershipViolationType.MISSING_CANONICAL,
                canonical_path=component.canonical_path,
                violating_path=component.canonical_path,
                canonical_hash=component.content_hash,
                violating_hash="",
                fix_action="restore",
            )

        # Check hash
        current_hash = self._compute_file_hash(component.canonical_path)
        if current_hash != component.content_hash:
            return self._create_violation(
                component_id=component_id,
                violation_type=OwnershipViolationType.HASH_MISMATCH,
                canonical_path=component.canonical_path,
                violating_path=component.canonical_path,
                canonical_hash=component.content_hash,
                violating_hash=current_hash or "",
                fix_action="update_hash",
            )

        # Update last verified
        self._update_last_verified(component_id)
        return None

    def detect_drift(
        self,
        scan_paths: Optional[List[str]] = None,
    ) -> List[OwnershipViolation]:
        """Detect all drift violations across registered components.

        Args:
            scan_paths: Optional paths to scan for duplicates

        Returns:
            List of detected violations
        """
        violations = []

        # Verify all registered components
        for component_id in self._components:
            violation = self.verify_component(component_id)
            if violation:
                violations.append(violation)

        # Scan for duplicate files if paths provided
        if scan_paths:
            violations.extend(self._scan_for_duplicates(scan_paths))

        logger.info(f"Drift detection complete: {len(violations)} violations found")
        return violations

    def _scan_for_duplicates(self, scan_paths: List[str]) -> List[OwnershipViolation]:
        """Scan paths for duplicate components."""
        violations = []

        # Build lookup by filename
        filename_to_component: Dict[str, ComponentOwnership] = {}
        for component in self._components.values():
            filename = os.path.basename(component.canonical_path)
            filename_to_component[filename] = component

        # Scan paths
        for scan_path in scan_paths:
            if not os.path.exists(scan_path):
                continue

            for root, dirs, files in os.walk(scan_path):
                for filename in files:
                    if filename not in filename_to_component:
                        continue

                    file_path = os.path.join(root, filename)
                    component = filename_to_component[filename]

                    # Skip if this IS the canonical path
                    if os.path.normpath(file_path) == os.path.normpath(component.canonical_path):
                        continue

                    # Skip if in allowed copies
                    if any(
                        os.path.normpath(file_path).startswith(os.path.normpath(allowed))
                        for allowed in component.allowed_copies
                    ):
                        continue

                    # Found duplicate - check if content matches
                    file_hash = self._compute_file_hash(file_path)
                    if file_hash == component.content_hash:
                        # Exact copy - DUPLICATE_LOCATION violation
                        violations.append(
                            self._create_violation(
                                component_id=component.id,
                                violation_type=OwnershipViolationType.DUPLICATE_LOCATION,
                                canonical_path=component.canonical_path,
                                violating_path=file_path,
                                canonical_hash=component.content_hash,
                                violating_hash=file_hash,
                                fix_action="delete",
                            )
                        )
                    else:
                        # Modified copy - HASH_MISMATCH violation
                        violations.append(
                            self._create_violation(
                                component_id=component.id,
                                violation_type=OwnershipViolationType.HASH_MISMATCH,
                                canonical_path=component.canonical_path,
                                violating_path=file_path,
                                canonical_hash=component.content_hash,
                                violating_hash=file_hash or "",
                                fix_action="sync",
                            )
                        )

        return violations

    def fix_violations(
        self,
        violations: List[OwnershipViolation],
        auto_fix: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, any]:
        """Fix detected violations.

        Args:
            violations: List of violations to fix
            auto_fix: If True, automatically fix auto-fixable violations
            dry_run: If True, only report what would be done

        Returns:
            Dict with fix results
        """
        results = {
            "fixed": [],
            "skipped": [],
            "failed": [],
            "dry_run": dry_run,
        }

        for violation in violations:
            if not auto_fix and not violation.auto_fixable:
                results["skipped"].append({
                    "id": violation.id,
                    "reason": "not_auto_fixable",
                })
                continue

            try:
                if dry_run:
                    results["fixed"].append({
                        "id": violation.id,
                        "action": violation.fix_action,
                        "would_fix": True,
                    })
                    continue

                success = self._apply_fix(violation)
                if success:
                    results["fixed"].append({
                        "id": violation.id,
                        "action": violation.fix_action,
                    })
                else:
                    results["failed"].append({
                        "id": violation.id,
                        "reason": "fix_failed",
                    })
            except Exception as e:
                results["failed"].append({
                    "id": violation.id,
                    "reason": str(e),
                })

        logger.info(
            f"Fix complete: {len(results['fixed'])} fixed, "
            f"{len(results['skipped'])} skipped, {len(results['failed'])} failed"
        )
        return results

    def _apply_fix(self, violation: OwnershipViolation) -> bool:
        """Apply fix for a single violation."""
        if violation.fix_action == "delete":
            # Delete the violating file
            if os.path.exists(violation.violating_path):
                os.remove(violation.violating_path)
                logger.info(f"Deleted duplicate: {violation.violating_path}")
                return True

        elif violation.fix_action == "sync":
            # Sync violating file to match canonical
            if os.path.exists(violation.canonical_path):
                shutil.copy2(violation.canonical_path, violation.violating_path)
                logger.info(f"Synced: {violation.violating_path} <- {violation.canonical_path}")
                return True

        elif violation.fix_action == "restore":
            # Cannot restore - need external action
            logger.warning(f"Cannot restore missing canonical: {violation.canonical_path}")
            return False

        elif violation.fix_action == "update_hash":
            # Update stored hash to current
            component = self._components.get(violation.component_id)
            if component:
                new_hash = self._compute_file_hash(violation.canonical_path)
                if new_hash:
                    self._update_component_hash(violation.component_id, new_hash)
                    logger.info(f"Updated hash for: {violation.component_id}")
                    return True

        return False

    def _create_violation(
        self,
        component_id: str,
        violation_type: OwnershipViolationType,
        canonical_path: str,
        violating_path: str,
        canonical_hash: str,
        violating_hash: str,
        fix_action: str,
    ) -> OwnershipViolation:
        """Create a new violation record."""
        self._violation_counter += 1
        violation_id = f"violation-{self._violation_counter}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        severity = self.SEVERITY_MAP.get(violation_type, "medium")
        auto_fixable = fix_action in ("delete", "sync", "update_hash")

        return OwnershipViolation(
            id=violation_id,
            component_id=component_id,
            violation_type=violation_type,
            severity=severity,
            canonical_path=canonical_path,
            violating_path=violating_path,
            canonical_hash=canonical_hash,
            violating_hash=violating_hash,
            detected_at=datetime.utcnow(),
            auto_fixable=auto_fixable,
            fix_action=fix_action,
        )

    def _compute_file_hash(self, file_path: str) -> Optional[str]:
        """Compute SHA-256 hash of a file."""
        if not os.path.exists(file_path):
            return None

        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash {file_path}: {e}")
            return None

    def _update_last_verified(self, component_id: str) -> None:
        """Update last verified timestamp for a component."""
        component = self._components.get(component_id)
        if not component:
            return

        # Update in graph
        node = self.graph.get_node(component_id)
        if node:
            metadata = node.get("metadata", {})
            metadata["last_verified"] = datetime.utcnow().isoformat()
            # Re-add node with updated metadata
            self.graph.add_chunk_node(component_id, metadata)

    def _update_component_hash(self, component_id: str, new_hash: str) -> None:
        """Update content hash for a component."""
        component = self._components.get(component_id)
        if not component:
            return

        # Update in graph
        node = self.graph.get_node(component_id)
        if node:
            metadata = node.get("metadata", {})
            metadata["content_hash"] = new_hash
            metadata["last_verified"] = datetime.utcnow().isoformat()
            self.graph.add_chunk_node(component_id, metadata)

        # Update local cache
        self._components[component_id] = ComponentOwnership(
            id=component.id,
            component_type=component.component_type,
            canonical_path=component.canonical_path,
            content_hash=new_hash,
            version=component.version,
            owner_project=component.owner_project,
            allowed_copies=component.allowed_copies,
            last_verified=datetime.utcnow(),
            metadata=component.metadata,
        )

    def save(self) -> bool:
        """Save registry to disk."""
        return self.graph.save_graph()

    def load(self) -> bool:
        """Load registry from disk."""
        success = self.graph.load_graph()
        if success:
            self._load_components_from_graph()
        return success

    def export_manifest(self, output_path: str) -> bool:
        """Export component manifest as JSON.

        Args:
            output_path: Path to write manifest

        Returns:
            True if successful
        """
        manifest = {
            "version": "1.0.0",
            "generated_at": datetime.utcnow().isoformat(),
            "components": [],
        }

        for component in self._components.values():
            manifest["components"].append({
                "id": component.id,
                "type": component.component_type.value,
                "canonical_path": component.canonical_path,
                "content_hash": component.content_hash,
                "version": component.version,
                "owner_project": component.owner_project,
                "allowed_copies": component.allowed_copies,
            })

        try:
            with open(output_path, "w") as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Exported manifest to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export manifest: {e}")
            return False

    def import_manifest(self, manifest_path: str) -> int:
        """Import components from manifest JSON.

        Args:
            manifest_path: Path to manifest file

        Returns:
            Number of components imported
        """
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read manifest: {e}")
            return 0

        imported = 0
        for entry in manifest.get("components", []):
            success = self.register_component(
                component_id=entry["id"],
                component_type=ComponentType(entry["type"]),
                canonical_path=entry["canonical_path"],
                owner_project=entry["owner_project"],
                version=entry.get("version", "1.0.0"),
                allowed_copies=entry.get("allowed_copies", []),
            )
            if success:
                imported += 1

        logger.info(f"Imported {imported} components from manifest")
        return imported


# Singleton instance
_registry_instance: Optional[OwnershipRegistry] = None


def get_ownership_registry(data_dir: str = "./data") -> OwnershipRegistry:
    """Get singleton ownership registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = OwnershipRegistry(data_dir=data_dir)
    return _registry_instance
