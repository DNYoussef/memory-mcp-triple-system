"""MCP Tools for Ownership Registry.

Provides MCP-compatible tools for managing component ownership:
- Register components with canonical locations
- Detect drift violations
- Fix violations automatically
- Export/import manifests

WHO: ownership-registry:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (GRAPH-002)
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from ...services.ownership_registry import OwnershipRegistry
from ...integrations.ontology_schema import ComponentType


class OwnershipTools:
    """MCP tools for ownership registry operations.

    Tools:
    - ownership_register: Register a component
    - ownership_list: List registered components
    - ownership_verify: Verify a single component
    - ownership_detect_drift: Detect all drift violations
    - ownership_fix: Fix violations
    - ownership_export: Export manifest
    - ownership_import: Import manifest
    """

    def __init__(self, registry: OwnershipRegistry):
        """Initialize ownership tools.

        Args:
            registry: OwnershipRegistry instance
        """
        self.registry = registry
        logger.info("OwnershipTools initialized")

    def register_component(
        self,
        component_id: str,
        component_type: str,
        canonical_path: str,
        owner_project: str,
        version: str = "1.0.0",
        allowed_copies: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a component with its canonical location.

        Args:
            component_id: Unique ID (e.g., "skill:code")
            component_type: Type (skill, agent, command, hook, etc.)
            canonical_path: Absolute path to canonical file
            owner_project: Project that owns this component
            version: Semantic version
            allowed_copies: Paths where copies are allowed

        Returns:
            Dict with registration result
        """
        try:
            comp_type = ComponentType(component_type)
            success = self.registry.register_component(
                component_id=component_id,
                component_type=comp_type,
                canonical_path=canonical_path,
                owner_project=owner_project,
                version=version,
                allowed_copies=allowed_copies or [],
            )

            return {
                "success": success,
                "component_id": component_id,
                "canonical_path": canonical_path,
            }
        except Exception as e:
            logger.error(f"Failed to register component: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_components(
        self,
        component_type: Optional[str] = None,
        owner_project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List registered components.

        Args:
            component_type: Filter by type
            owner_project: Filter by owner project

        Returns:
            Dict with components list
        """
        try:
            comp_type = ComponentType(component_type) if component_type else None
            components = self.registry.list_components(
                component_type=comp_type,
                owner_project=owner_project,
            )

            return {
                "success": True,
                "count": len(components),
                "components": [
                    {
                        "id": c.id,
                        "type": c.component_type.value,
                        "canonical_path": c.canonical_path,
                        "content_hash": c.content_hash[:16] + "...",  # Truncate hash
                        "version": c.version,
                        "owner_project": c.owner_project,
                    }
                    for c in components
                ],
            }
        except Exception as e:
            logger.error(f"Failed to list components: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def verify_component(self, component_id: str) -> Dict[str, Any]:
        """Verify a single component's integrity.

        Args:
            component_id: Component ID to verify

        Returns:
            Dict with verification result
        """
        try:
            violation = self.registry.verify_component(component_id)

            if violation:
                return {
                    "success": True,
                    "valid": False,
                    "violation": {
                        "type": violation.violation_type.value,
                        "severity": violation.severity,
                        "canonical_path": violation.canonical_path,
                        "violating_path": violation.violating_path,
                        "fix_action": violation.fix_action,
                    },
                }
            else:
                return {
                    "success": True,
                    "valid": True,
                    "component_id": component_id,
                }
        except Exception as e:
            logger.error(f"Failed to verify component: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def detect_drift(
        self,
        scan_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Detect all drift violations.

        Args:
            scan_paths: Optional paths to scan for duplicates

        Returns:
            Dict with detection results
        """
        try:
            violations = self.registry.detect_drift(scan_paths=scan_paths)

            # Categorize by severity
            by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for v in violations:
                by_severity[v.severity] = by_severity.get(v.severity, 0) + 1

            return {
                "success": True,
                "total_violations": len(violations),
                "by_severity": by_severity,
                "violations": [
                    {
                        "id": v.id,
                        "component_id": v.component_id,
                        "type": v.violation_type.value,
                        "severity": v.severity,
                        "canonical_path": v.canonical_path,
                        "violating_path": v.violating_path,
                        "fix_action": v.fix_action,
                        "auto_fixable": v.auto_fixable,
                    }
                    for v in violations
                ],
            }
        except Exception as e:
            logger.error(f"Failed to detect drift: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def fix_violations(
        self,
        violation_ids: Optional[List[str]] = None,
        auto_fix: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Fix detected violations.

        Args:
            violation_ids: Specific violations to fix (None = all)
            auto_fix: Auto-fix without confirmation
            dry_run: Preview without changing files

        Returns:
            Dict with fix results
        """
        try:
            # First detect violations
            all_violations = self.registry.detect_drift()

            # Filter if specific IDs provided
            if violation_ids:
                violations = [v for v in all_violations if v.id in violation_ids]
            else:
                violations = all_violations

            results = self.registry.fix_violations(
                violations,
                auto_fix=auto_fix,
                dry_run=dry_run,
            )

            return {
                "success": True,
                "dry_run": dry_run,
                "fixed": len(results["fixed"]),
                "skipped": len(results["skipped"]),
                "failed": len(results["failed"]),
                "details": results,
            }
        except Exception as e:
            logger.error(f"Failed to fix violations: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def export_manifest(self, output_path: str) -> Dict[str, Any]:
        """Export component manifest to JSON.

        Args:
            output_path: Path to write manifest

        Returns:
            Dict with export result
        """
        try:
            success = self.registry.export_manifest(output_path)
            component_count = len(self.registry.list_components())

            return {
                "success": success,
                "output_path": output_path,
                "component_count": component_count,
            }
        except Exception as e:
            logger.error(f"Failed to export manifest: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def import_manifest(self, manifest_path: str) -> Dict[str, Any]:
        """Import components from manifest JSON.

        Args:
            manifest_path: Path to manifest file

        Returns:
            Dict with import result
        """
        try:
            imported = self.registry.import_manifest(manifest_path)

            return {
                "success": imported > 0,
                "imported_count": imported,
                "manifest_path": manifest_path,
            }
        except Exception as e:
            logger.error(f"Failed to import manifest: {e}")
            return {
                "success": False,
                "error": str(e),
            }


def register_ownership_tools(server: Any, registry: OwnershipRegistry) -> None:
    """Register ownership tools with MCP server.

    Args:
        server: MCP server instance
        registry: OwnershipRegistry instance
    """
    tools = OwnershipTools(registry)

    # Register component
    server.add_tool(
        name="ownership_register",
        description="Register a component with its canonical location for drift prevention.",
        handler=tools.register_component,
        input_schema={
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "string",
                    "description": "Unique component ID (e.g., 'skill:code')",
                },
                "component_type": {
                    "type": "string",
                    "enum": [
                        "skill",
                        "agent",
                        "command",
                        "hook",
                        "playbook",
                        "service",
                        "schema",
                        "config",
                        "script",
                        "documentation",
                    ],
                    "description": "Type of component",
                },
                "canonical_path": {
                    "type": "string",
                    "description": "Absolute path to canonical file",
                },
                "owner_project": {
                    "type": "string",
                    "description": "Project that owns this component",
                },
                "version": {
                    "type": "string",
                    "description": "Semantic version",
                    "default": "1.0.0",
                },
                "allowed_copies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths where copies are allowed",
                },
            },
            "required": [
                "component_id",
                "component_type",
                "canonical_path",
                "owner_project",
            ],
        },
    )

    # List components
    server.add_tool(
        name="ownership_list",
        description="List registered components with optional filtering.",
        handler=tools.list_components,
        input_schema={
            "type": "object",
            "properties": {
                "component_type": {
                    "type": "string",
                    "enum": [
                        "skill",
                        "agent",
                        "command",
                        "hook",
                        "playbook",
                        "service",
                        "schema",
                        "config",
                        "script",
                        "documentation",
                    ],
                    "description": "Filter by component type",
                },
                "owner_project": {
                    "type": "string",
                    "description": "Filter by owner project",
                },
            },
        },
    )

    # Verify component
    server.add_tool(
        name="ownership_verify",
        description="Verify a single component's integrity against its canonical.",
        handler=tools.verify_component,
        input_schema={
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "string",
                    "description": "Component ID to verify",
                },
            },
            "required": ["component_id"],
        },
    )

    # Detect drift
    server.add_tool(
        name="ownership_detect_drift",
        description="Detect all drift violations across registered components.",
        handler=tools.detect_drift,
        input_schema={
            "type": "object",
            "properties": {
                "scan_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths to scan for duplicates",
                },
            },
        },
    )

    # Fix violations
    server.add_tool(
        name="ownership_fix",
        description="Fix detected drift violations.",
        handler=tools.fix_violations,
        input_schema={
            "type": "object",
            "properties": {
                "violation_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific violation IDs to fix (empty = all)",
                },
                "auto_fix": {
                    "type": "boolean",
                    "description": "Auto-fix without confirmation",
                    "default": False,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview without changing files",
                    "default": False,
                },
            },
        },
    )

    # Export manifest
    server.add_tool(
        name="ownership_export",
        description="Export component manifest to JSON file.",
        handler=tools.export_manifest,
        input_schema={
            "type": "object",
            "properties": {
                "output_path": {
                    "type": "string",
                    "description": "Path to write manifest JSON",
                },
            },
            "required": ["output_path"],
        },
    )

    # Import manifest
    server.add_tool(
        name="ownership_import",
        description="Import components from manifest JSON file.",
        handler=tools.import_manifest,
        input_schema={
            "type": "object",
            "properties": {
                "manifest_path": {
                    "type": "string",
                    "description": "Path to manifest JSON file",
                },
            },
            "required": ["manifest_path"],
        },
    )

    logger.info("Ownership tools registered with MCP server")
