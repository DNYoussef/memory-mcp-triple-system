"""
Memory Schema Validator

Validates memory-schema.yaml against specification requirements.
Part of Memory-as-Code philosophy (Week 7).

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationError:
    """Validation error with context."""

    field: str
    message: str
    severity: str  # "error" | "warning"


class SchemaValidator:
    """
    Validate memory schema YAML against spec requirements.

    Usage:
        validator = SchemaValidator()
        result = validator.validate("config/memory-schema.yaml")
        if result.valid:
            print("✅ Schema valid")
        else:
            for error in result.errors:
                print(f"❌ {error.field}: {error.message}")
    """

    REQUIRED_ROOT_FIELDS = [
        "version",
        "storage_tiers",
        "lifecycle",
        "query_processing"
    ]

    REQUIRED_TIER_FIELDS = [
        "type",
        "backend",
        "use_cases",
        "performance"
    ]

    REQUIRED_LIFECYCLE_FIELDS = [
        "stages",
        "rekindling"
    ]

    REQUIRED_QUERY_PROCESSING_FIELDS = [
        "mode_detection",
        "routing",
        "curated_core",
        "verification"
    ]

    VALID_STORAGE_TYPES = [
        "key-value",
        "sql",
        "embedding",
        "networkx",
        "temporal"
    ]

    def __init__(self) -> None:
        """Initialize schema validator."""
        self.errors: List[ValidationError] = []

    def validate(self, schema_path: str) -> "ValidationResult":
        """
        Validate schema YAML file.

        Args:
            schema_path: Path to memory-schema.yaml

        Returns:
            ValidationResult with errors if invalid

        NASA Rule 10: 38 LOC (≤60) ✅
        """
        self.errors = []
        path = Path(schema_path)

        if not path.exists():
            self.errors.append(ValidationError(
                field="file",
                message=f"Schema file not found: {schema_path}",
                severity="error"
            ))
            return ValidationResult(valid=False, errors=self.errors)

        try:
            with open(path, "r", encoding="utf-8") as f:
                schema = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.errors.append(ValidationError(
                field="yaml",
                message=f"Invalid YAML syntax: {str(e)}",
                severity="error"
            ))
            return ValidationResult(valid=False, errors=self.errors)

        # Run validation checks
        self._validate_root_fields(schema)
        self._validate_storage_tiers(schema.get("storage_tiers", {}))
        self._validate_lifecycle(schema.get("lifecycle", {}))
        self._validate_query_processing(schema.get("query_processing", {}))
        self._validate_performance_targets(schema.get("performance_targets", {}))

        return ValidationResult(
            valid=len(self.errors) == 0,
            errors=self.errors,
            schema=schema if len(self.errors) == 0 else None
        )

    def _validate_root_fields(self, schema: Dict[str, Any]) -> None:
        """
        Validate required root-level fields.

        NASA Rule 10: 12 LOC (≤60) ✅
        """
        for field in self.REQUIRED_ROOT_FIELDS:
            if field not in schema:
                self.errors.append(ValidationError(
                    field=f"root.{field}",
                    message=f"Missing required field: {field}",
                    severity="error"
                ))

    def _validate_storage_tiers(self, tiers: Dict[str, Any]) -> None:
        """
        Validate storage tier definitions.

        NASA Rule 10: 32 LOC (≤60) ✅
        """
        if not tiers:
            self.errors.append(ValidationError(
                field="storage_tiers",
                message="No storage tiers defined",
                severity="error"
            ))
            return

        for tier_name, tier_config in tiers.items():
            # Check required fields
            for field in self.REQUIRED_TIER_FIELDS:
                if field not in tier_config:
                    self.errors.append(ValidationError(
                        field=f"storage_tiers.{tier_name}.{field}",
                        message=f"Missing required field: {field}",
                        severity="error"
                    ))

            # Validate storage type
            tier_type = tier_config.get("type")
            if tier_type and tier_type not in self.VALID_STORAGE_TYPES:
                self.errors.append(ValidationError(
                    field=f"storage_tiers.{tier_name}.type",
                    message=f"Invalid type: {tier_type}. Must be one of {self.VALID_STORAGE_TYPES}",
                    severity="error"
                ))

    def _validate_lifecycle(self, lifecycle: Dict[str, Any]) -> None:
        """
        Validate lifecycle configuration.

        NASA Rule 10: 30 LOC (≤60) ✅
        """
        if not lifecycle:
            self.errors.append(ValidationError(
                field="lifecycle",
                message="Lifecycle configuration missing",
                severity="error"
            ))
            return

        # Check required fields
        for field in self.REQUIRED_LIFECYCLE_FIELDS:
            if field not in lifecycle:
                self.errors.append(ValidationError(
                    field=f"lifecycle.{field}",
                    message=f"Missing required field: {field}",
                    severity="error"
                ))

        # Validate stages
        stages = lifecycle.get("stages", [])
        if not stages:
            self.errors.append(ValidationError(
                field="lifecycle.stages",
                message="No lifecycle stages defined",
                severity="error"
            ))

        # Check expected stages
        expected_stages = ["active", "demoted", "archived", "rehydratable"]
        stage_names = [s.get("name") for s in stages if isinstance(s, dict)]
        for expected in expected_stages:
            if expected not in stage_names:
                self.errors.append(ValidationError(
                    field=f"lifecycle.stages.{expected}",
                    message=f"Missing expected stage: {expected}",
                    severity="warning"
                ))

    def _validate_query_processing(self, query_proc: Dict[str, Any]) -> None:
        """
        Validate query processing configuration.

        NASA Rule 10: 22 LOC (≤60) ✅
        """
        if not query_proc:
            self.errors.append(ValidationError(
                field="query_processing",
                message="Query processing configuration missing",
                severity="error"
            ))
            return

        # Check required fields
        for field in self.REQUIRED_QUERY_PROCESSING_FIELDS:
            if field not in query_proc:
                self.errors.append(ValidationError(
                    field=f"query_processing.{field}",
                    message=f"Missing required field: {field}",
                    severity="error"
                ))

    def _validate_performance_targets(self, targets: Dict[str, Any]) -> None:
        """
        Validate performance target values.

        NASA Rule 10: 20 LOC (≤60) ✅
        """
        if not targets:
            return  # Optional section

        # Validate numeric targets
        numeric_fields = [
            "query_latency_p95_ms",
            "indexing_latency_ms",
            "kv_lookup_latency_ms"
        ]

        for field in numeric_fields:
            value = targets.get(field)
            if value is not None and not isinstance(value, (int, float)):
                self.errors.append(ValidationError(
                    field=f"performance_targets.{field}",
                    message=f"Must be numeric, got: {type(value).__name__}",
                    severity="error"
                ))


@dataclass
class ValidationResult:
    """Result of schema validation."""

    valid: bool
    errors: List[ValidationError]
    schema: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        """String representation of validation result."""
        if self.valid:
            return "✅ Schema validation passed"

        error_lines = [
            f"❌ Schema validation failed ({len(self.errors)} errors):"
        ]
        for error in self.errors:
            severity_icon = "🔴" if error.severity == "error" else "🟡"
            error_lines.append(
                f"  {severity_icon} {error.field}: {error.message}"
            )

        return "\n".join(error_lines)
