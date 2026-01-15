"""
Spec Validation Module.

A generalized validation framework for specification documents including
JSON schemas, markdown documents, and implementation plans.

This module provides:
- Configurable JSON schema validation
- Markdown section validation
- Implementation plan structure validation
- Extensible validator architecture with dependency injection

Usage:
    from spec_validation import (
        SpecValidator,
        SpecValidationResult,
        ValidationSchema,
        BaseValidator,
    )

    # Basic usage with defaults
    validator = SpecValidator(spec_dir="/path/to/specs")
    results = validator.validate_all()

    # Custom schema usage
    custom_schema = ValidationSchema(
        required_fields=["name", "version"],
        optional_fields=["description"],
    )
    validator = SpecValidator(
        spec_dir="/path/to/specs",
        context_schema=custom_schema,
    )

    # Injectable validators
    class CustomValidator(BaseValidator):
        def validate(self) -> SpecValidationResult:
            # Custom validation logic
            pass

    validator = SpecValidator(
        spec_dir="/path/to/specs",
        additional_validators={"custom": CustomValidator},
    )
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

# Optional async support
try:
    import aiofiles
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False

# LEGO Import: Use shared types from library for common validation types
try:
    from library.common.types import SpecValidationResult as BaseSpecValidationResult, Violation, Severity
except ImportError:
    try:
        from common.types import SpecValidationResult as BaseSpecValidationResult, Violation, Severity
    except ImportError:
        # Fallback for standalone use - BaseSpecValidationResult not needed, using SpecValidationResult
        BaseSpecValidationResult = None  # type: ignore
        Violation = None  # type: ignore
        Severity = None  # type: ignore


# ============================================================================
# Pre-compiled Regex Patterns (LOW-SPEC-01 fix)
# ============================================================================

def _compile_section_pattern(section: str) -> re.Pattern[str]:
    """Compile a regex pattern for matching markdown section headers."""
    return re.compile(rf"^#+\s*{re.escape(section)}", re.MULTILINE | re.IGNORECASE)


# Cache for compiled section patterns
_SECTION_PATTERN_CACHE: Dict[str, re.Pattern[str]] = {}


# ============================================================================
# Type Definitions
# ============================================================================

T = TypeVar("T")
ValidatorFactory = Callable[[Path], "BaseValidator"]


class Validatable(Protocol):
    """Protocol for objects that can be validated."""

    def validate(self) -> "SpecValidationResult":
        """
        Perform validation and return result.

        Returns:
            SpecValidationResult: The result of the validation containing
                valid status, errors, warnings, and suggested fixes.
        """
        ...


# ============================================================================
# Schema Configuration
# ============================================================================

@dataclass
class ValidationSchema:
    """
    Configuration schema for validation rules.

    Attributes:
        required_fields: Fields that must be present
        optional_fields: Fields that may be present
        allowed_values: Mapping of field names to allowed values
        nested_schemas: Mapping of field names to nested ValidationSchema
        custom_validators: Mapping of field names to validation functions
    """

    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    allowed_values: Dict[str, List[str]] = field(default_factory=dict)
    nested_schemas: Dict[str, "ValidationSchema"] = field(default_factory=dict)
    custom_validators: Dict[str, Callable[[Any], Optional[str]]] = field(
        default_factory=dict
    )
    required_fields_either: List[List[str]] = field(default_factory=list)

    def validate_data(
        self,
        data: Dict[str, Any],
        prefix: str = "",
    ) -> tuple[List[str], List[str]]:
        """
        Validate data against this schema.

        Args:
            data: Dictionary to validate
            prefix: Prefix for error messages (for nested validation)

        Returns:
            Tuple of (errors, warnings) lists
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Check required fields
        for req_field in self.required_fields:
            if req_field not in data:
                errors.append(f"{prefix}Missing required field: {req_field}")

        # Check required_fields_either (at least one from each group)
        for group in self.required_fields_either:
            if not any(f in data for f in group):
                errors.append(
                    f"{prefix}Missing one of required fields: {', '.join(group)}"
                )

        # Check allowed values
        for field_name, allowed in self.allowed_values.items():
            if field_name not in data:
                continue
            if data[field_name] in allowed:
                continue
            warnings.append(
                f"{prefix}Unknown value for {field_name}: {data[field_name]}"
            )

        # Run custom validators
        for field_name, validator_fn in self.custom_validators.items():
            if field_name in data:
                error = validator_fn(data[field_name])
                if error:
                    errors.append(f"{prefix}{field_name}: {error}")

        # Validate nested schemas
        for field_name, nested_schema in self.nested_schemas.items():
            if field_name not in data:
                continue
            nested_data = data[field_name]
            if isinstance(nested_data, dict):
                nested_errors, nested_warnings = nested_schema.validate_data(
                    nested_data, prefix=f"{prefix}{field_name}."
                )
                errors.extend(nested_errors)
                warnings.extend(nested_warnings)
                continue
            if not isinstance(nested_data, list):
                continue
            for i, item in enumerate(nested_data):
                if not isinstance(item, dict):
                    continue
                item_errors, item_warnings = nested_schema.validate_data(
                    item, prefix=f"{prefix}{field_name}[{i}]."
                )
                errors.extend(item_errors)
                warnings.extend(item_warnings)

        return errors, warnings


# ============================================================================
# Default Schemas
# ============================================================================

DEFAULT_SUBTASK_SCHEMA = ValidationSchema(
    required_fields=["id", "description", "status"],
    optional_fields=[
        "service",
        "all_services",
        "files_to_modify",
        "files_to_create",
        "patterns_from",
        "verification",
        "expected_output",
        "actual_output",
        "started_at",
        "completed_at",
        "session_id",
        "critique_result",
    ],
    allowed_values={
        "status": ["pending", "in_progress", "completed", "blocked", "failed"],
    },
)

DEFAULT_VERIFICATION_SCHEMA = ValidationSchema(
    required_fields=["type"],
    optional_fields=[
        "run",
        "url",
        "method",
        "expect_status",
        "expect_contains",
        "scenario",
        "steps",
    ],
    allowed_values={
        "type": ["command", "api", "browser", "component", "manual", "none", "e2e"],
    },
)

DEFAULT_PHASE_SCHEMA = ValidationSchema(
    required_fields=["name", "subtasks"],
    optional_fields=[
        "type",
        "depends_on",
        "parallel_safe",
        "description",
        "phase",
        "id",
    ],
    required_fields_either=[["phase", "id"]],
    allowed_values={
        "type": ["setup", "implementation", "investigation", "integration", "cleanup"],
    },
    nested_schemas={
        "subtasks": DEFAULT_SUBTASK_SCHEMA,
    },
)

DEFAULT_IMPLEMENTATION_PLAN_SCHEMA = ValidationSchema(
    required_fields=["feature", "workflow_type", "phases"],
    optional_fields=[
        "services_involved",
        "final_acceptance",
        "created_at",
        "updated_at",
        "spec_file",
        "qa_acceptance",
        "qa_signoff",
        "summary",
        "description",
        "workflow_rationale",
        "status",
    ],
    allowed_values={
        "workflow_type": [
            "feature",
            "refactor",
            "investigation",
            "migration",
            "simple",
            "bugfix",
            "bug_fix",
        ],
    },
    nested_schemas={
        "phases": DEFAULT_PHASE_SCHEMA,
    },
)

DEFAULT_CONTEXT_SCHEMA = ValidationSchema(
    required_fields=["task_description"],
    optional_fields=[
        "scoped_services",
        "files_to_modify",
        "files_to_reference",
        "patterns",
        "service_contexts",
        "created_at",
    ],
)

DEFAULT_REQUIREMENTS_SCHEMA = ValidationSchema(
    required_fields=["task_description"],
    optional_fields=[
        "workflow_type",
        "services_involved",
        "user_requirements",
        "acceptance_criteria",
        "constraints",
        "priority",
        "estimated_complexity",
        "created_at",
    ],
)

# Default markdown section requirements
DEFAULT_SPEC_REQUIRED_SECTIONS: List[str] = [
    "Overview",
    "Workflow Type",
    "Task Scope",
    "Success Criteria",
]

DEFAULT_SPEC_RECOMMENDED_SECTIONS: List[str] = [
    "Files to Modify",
    "Files to Reference",
    "Requirements",
    "QA Acceptance Criteria",
]


# ============================================================================
# Validation Result Model
# ============================================================================
# NOTE: This module uses a specialized SpecValidationResult with checkpoint and fixes
# fields. For simple validation needs, use library.common.types.SpecValidationResult.
# ============================================================================

@dataclass
class SpecValidationResult:
    """
    Result of a spec validation check.

    This is a specialized validation result for spec files that includes
    checkpoint tracking and fix suggestions. For simple validation,
    use library.common.types.SpecValidationResult instead.

    Attributes:
        valid: Whether validation passed
        checkpoint: Name of the validation checkpoint
        errors: List of error messages
        warnings: List of warning messages
        fixes: List of suggested fixes
        metadata: Additional metadata about the validation
    """

    valid: bool
    checkpoint: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.valid

    def __str__(self) -> str:
        """Format as human-readable string."""
        lines = [f"Checkpoint: {self.checkpoint}"]
        lines.append(f"Status: {'PASS' if self.valid else 'FAIL'}")

        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  [X] {err}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings:
                lines.append(f"  [!] {warn}")

        if self.fixes and not self.valid:
            lines.append("\nSuggested Fixes:")
            for fix in self.fixes:
                lines.append(f"  -> {fix}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "valid": self.valid,
            "checkpoint": self.checkpoint,
            "errors": self.errors,
            "warnings": self.warnings,
            "fixes": self.fixes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpecValidationResult":
        """Create SpecValidationResult from dictionary."""
        return cls(
            valid=data.get("valid", False),
            checkpoint=data.get("checkpoint", "unknown"),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            fixes=data.get("fixes", []),
            metadata=data.get("metadata", {}),
        )

    def merge(self, other: "SpecValidationResult") -> "SpecValidationResult":
        """
        Merge another SpecValidationResult into this one.

        Args:
            other: Another SpecValidationResult to merge

        Returns:
            New SpecValidationResult with combined data
        """
        return SpecValidationResult(
            valid=self.valid and other.valid,
            checkpoint=f"{self.checkpoint}+{other.checkpoint}",
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            fixes=self.fixes + other.fixes,
            metadata={**self.metadata, **other.metadata},
        )


# Backward compatibility aliases - prefer SpecValidationResult for new code
ValidationResult = SpecValidationResult
SpecSpecValidationResult = SpecValidationResult


# ============================================================================
# Base Validator Interface
# ============================================================================

class BaseValidator(ABC):
    """
    Abstract base class for validators.

    Subclasses must implement the validate() method.
    """

    def __init__(self, spec_dir: Path) -> None:
        """
        Initialize validator.

        Args:
            spec_dir: Path to the specification directory
        """
        self.spec_dir = Path(spec_dir)

    @abstractmethod
    def validate(self) -> SpecValidationResult:
        """
        Perform validation.

        Returns:
            SpecValidationResult with validation status and details
        """
        ...

    def _create_result(
        self,
        checkpoint: str,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        fixes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SpecValidationResult:
        """
        Helper to create SpecValidationResult.

        Args:
            checkpoint: Name of validation checkpoint
            errors: List of errors (empty = valid)
            warnings: List of warnings
            fixes: List of suggested fixes
            metadata: Additional metadata

        Returns:
            SpecValidationResult instance
        """
        errors = errors or []
        return SpecValidationResult(
            valid=len(errors) == 0,
            checkpoint=checkpoint,
            errors=errors,
            warnings=warnings or [],
            fixes=fixes or [],
            metadata=metadata or {},
        )


# ============================================================================
# Individual Validators
# ============================================================================

class PrereqsValidator(BaseValidator):
    """
    Validates that prerequisites exist.

    Checks:
    - Spec directory exists
    - Optional: requirements.json exists
    """

    def __init__(
        self,
        spec_dir: Path,
        required_files: Optional[List[str]] = None,
        optional_files: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize prerequisites validator.

        Args:
            spec_dir: Path to spec directory
            required_files: List of required file names
            optional_files: List of optional file names to check
        """
        super().__init__(spec_dir)
        self.required_files = required_files or []
        self.optional_files = optional_files or ["requirements.json"]

    def validate(self) -> SpecValidationResult:
        """Check that spec directory and required files exist."""
        errors: List[str] = []
        warnings: List[str] = []
        fixes: List[str] = []

        if not self.spec_dir.exists():
            errors.append(f"Spec directory does not exist: {self.spec_dir}")
            fixes.append("Create the spec directory first")
            return self._create_result(
                "prerequisites", errors=errors, warnings=warnings, fixes=fixes
            )

        # Check required files
        for filename in self.required_files:
            filepath = self.spec_dir / filename
            if not filepath.exists():
                errors.append(f"Required file not found: {filename}")
                fixes.append(f"Create {filename}")

        # Check optional files
        for filename in self.optional_files:
            filepath = self.spec_dir / filename
            if not filepath.exists():
                warnings.append(f"{filename} not found")

        return self._create_result(
            "prerequisites", errors=errors, warnings=warnings, fixes=fixes
        )


class JSONFileValidator(BaseValidator):
    """
    Validates a JSON file against a schema.

    Generic validator that can validate any JSON file.
    Supports both synchronous and asynchronous validation.
    """

    def __init__(
        self,
        spec_dir: Path,
        filename: str,
        schema: ValidationSchema,
        checkpoint_name: str,
        not_found_fix: str = "Create the required file",
    ) -> None:
        """
        Initialize JSON file validator.

        Args:
            spec_dir: Path to spec directory
            filename: Name of JSON file to validate
            schema: ValidationSchema to validate against
            checkpoint_name: Name for the validation checkpoint
            not_found_fix: Suggested fix when file is not found
        """
        super().__init__(spec_dir)
        self.filename = filename
        self.schema = schema
        self.checkpoint_name = checkpoint_name
        self.not_found_fix = not_found_fix

    def _process_json_data(
        self,
        data: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
        fixes: List[str],
    ) -> None:
        """Process and validate JSON data against schema."""
        schema_errors, schema_warnings = self.schema.validate_data(data)
        errors.extend(schema_errors)
        warnings.extend(schema_warnings)
        for error in schema_errors:
            fixes.append(f"Fix: {error}")

    def validate(self) -> SpecValidationResult:
        """Validate JSON file exists and matches schema (synchronous)."""
        errors: List[str] = []
        warnings: List[str] = []
        fixes: List[str] = []

        filepath = self.spec_dir / self.filename

        if not filepath.exists():
            errors.append(f"{self.filename} not found")
            fixes.append(self.not_found_fix)
            return self._create_result(
                self.checkpoint_name, errors=errors, warnings=warnings, fixes=fixes
            )

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            self._process_json_data(data, errors, warnings, fixes)

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
            fixes.append(f"Fix JSON syntax errors in {self.filename}")
        except OSError as e:
            errors.append(f"Could not read {self.filename}: {e}")

        return self._create_result(
            self.checkpoint_name,
            errors=errors,
            warnings=warnings,
            fixes=fixes,
            metadata={"filename": self.filename},
        )

    async def validate_async(self) -> SpecValidationResult:
        """
        Validate JSON file exists and matches schema (asynchronous).

        Requires aiofiles to be installed. Falls back to sync if unavailable.

        Returns:
            SpecValidationResult with validation status and details
        """
        if not ASYNC_AVAILABLE:
            # Fall back to synchronous validation
            return self.validate()

        errors: List[str] = []
        warnings: List[str] = []
        fixes: List[str] = []

        filepath = self.spec_dir / self.filename

        if not filepath.exists():
            errors.append(f"{self.filename} not found")
            fixes.append(self.not_found_fix)
            return self._create_result(
                self.checkpoint_name, errors=errors, warnings=warnings, fixes=fixes
            )

        try:
            async with aiofiles.open(filepath, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            self._process_json_data(data, errors, warnings, fixes)

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
            fixes.append(f"Fix JSON syntax errors in {self.filename}")
        except OSError as e:
            errors.append(f"Could not read {self.filename}: {e}")

        return self._create_result(
            self.checkpoint_name,
            errors=errors,
            warnings=warnings,
            fixes=fixes,
            metadata={"filename": self.filename},
        )


class ContextValidator(JSONFileValidator):
    """Validates context.json structure."""

    def __init__(
        self,
        spec_dir: Path,
        schema: Optional[ValidationSchema] = None,
    ) -> None:
        """
        Initialize context validator.

        Args:
            spec_dir: Path to spec directory
            schema: Optional custom schema (uses default if not provided)
        """
        super().__init__(
            spec_dir=spec_dir,
            filename="context.json",
            schema=schema or DEFAULT_CONTEXT_SCHEMA,
            checkpoint_name="context",
            not_found_fix="Run discovery phase to generate context.json",
        )


class MarkdownDocumentValidator(BaseValidator):
    """
    Validates a markdown document for required sections.

    Checks for presence of required and recommended sections.
    Supports both synchronous and asynchronous validation.
    """

    def __init__(
        self,
        spec_dir: Path,
        filename: str,
        checkpoint_name: str,
        required_sections: Optional[List[str]] = None,
        recommended_sections: Optional[List[str]] = None,
        min_length: int = 500,
        not_found_fix: str = "Create the required markdown file",
    ) -> None:
        """
        Initialize markdown document validator.

        Args:
            spec_dir: Path to spec directory
            filename: Name of markdown file
            checkpoint_name: Name for validation checkpoint
            required_sections: List of required section headers
            recommended_sections: List of recommended section headers
            min_length: Minimum content length (characters)
            not_found_fix: Suggested fix when file not found
        """
        super().__init__(spec_dir)
        self.filename = filename
        self.checkpoint_name = checkpoint_name
        self.required_sections = required_sections or []
        self.recommended_sections = recommended_sections or []
        self.min_length = min_length
        self.not_found_fix = not_found_fix

    @staticmethod
    def _get_section_pattern(section: str) -> re.Pattern[str]:
        """
        Get a compiled regex pattern for a section header.

        Uses module-level cache to avoid recompiling patterns.

        Args:
            section: Section name to match

        Returns:
            Compiled regex pattern
        """
        if section not in _SECTION_PATTERN_CACHE:
            _SECTION_PATTERN_CACHE[section] = _compile_section_pattern(section)
        return _SECTION_PATTERN_CACHE[section]

    def _validate_content(
        self,
        content: str,
        errors: List[str],
        warnings: List[str],
        fixes: List[str],
    ) -> None:
        """
        Validate markdown content against section requirements.

        Args:
            content: Markdown file content
            errors: List to append errors to
            warnings: List to append warnings to
            fixes: List to append fixes to
        """
        # Check for required sections using pre-compiled patterns
        for section in self.required_sections:
            pattern = self._get_section_pattern(section)
            if not pattern.search(content):
                errors.append(f"Missing required section: {section}")
                fixes.append(f"Add '## {section}' section to {self.filename}")

        # Check for recommended sections using pre-compiled patterns
        for section in self.recommended_sections:
            pattern = self._get_section_pattern(section)
            if not pattern.search(content):
                warnings.append(f"Missing recommended section: {section}")

        # Check minimum content length
        if len(content) < self.min_length:
            warnings.append(
                f"Document seems too short ({len(content)} chars, "
                f"recommended minimum: {self.min_length})"
            )

    def validate(self) -> SpecValidationResult:
        """Validate markdown file exists and has required sections (synchronous)."""
        errors: List[str] = []
        warnings: List[str] = []
        fixes: List[str] = []

        filepath = self.spec_dir / self.filename

        if not filepath.exists():
            errors.append(f"{self.filename} not found")
            fixes.append(self.not_found_fix)
            return self._create_result(
                self.checkpoint_name, errors=errors, warnings=warnings, fixes=fixes
            )

        try:
            content = filepath.read_text(encoding="utf-8")
            self._validate_content(content, errors, warnings, fixes)

        except OSError as e:
            errors.append(f"Could not read {self.filename}: {e}")

        return self._create_result(
            self.checkpoint_name,
            errors=errors,
            warnings=warnings,
            fixes=fixes,
            metadata={"filename": self.filename},
        )

    async def validate_async(self) -> SpecValidationResult:
        """
        Validate markdown file exists and has required sections (asynchronous).

        Requires aiofiles to be installed. Falls back to sync if unavailable.

        Returns:
            SpecValidationResult with validation status and details
        """
        if not ASYNC_AVAILABLE:
            # Fall back to synchronous validation
            return self.validate()

        errors: List[str] = []
        warnings: List[str] = []
        fixes: List[str] = []

        filepath = self.spec_dir / self.filename

        if not filepath.exists():
            errors.append(f"{self.filename} not found")
            fixes.append(self.not_found_fix)
            return self._create_result(
                self.checkpoint_name, errors=errors, warnings=warnings, fixes=fixes
            )

        try:
            async with aiofiles.open(filepath, encoding="utf-8") as f:
                content = await f.read()
            self._validate_content(content, errors, warnings, fixes)

        except OSError as e:
            errors.append(f"Could not read {self.filename}: {e}")

        return self._create_result(
            self.checkpoint_name,
            errors=errors,
            warnings=warnings,
            fixes=fixes,
            metadata={"filename": self.filename},
        )


class SpecDocumentValidator(MarkdownDocumentValidator):
    """Validates spec.md document."""

    def __init__(
        self,
        spec_dir: Path,
        required_sections: Optional[List[str]] = None,
        recommended_sections: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize spec document validator.

        Args:
            spec_dir: Path to spec directory
            required_sections: Override default required sections
            recommended_sections: Override default recommended sections
        """
        super().__init__(
            spec_dir=spec_dir,
            filename="spec.md",
            checkpoint_name="spec_document",
            required_sections=required_sections or DEFAULT_SPEC_REQUIRED_SECTIONS,
            recommended_sections=recommended_sections or DEFAULT_SPEC_RECOMMENDED_SECTIONS,
            min_length=500,
            not_found_fix="Run spec writing phase to generate spec.md",
        )


class ImplementationPlanValidator(BaseValidator):
    """
    Validates implementation_plan.json structure.

    Performs deep validation of phases and subtasks.
    Supports both synchronous and asynchronous validation.
    """

    def __init__(
        self,
        spec_dir: Path,
        schema: Optional[ValidationSchema] = None,
    ) -> None:
        """
        Initialize implementation plan validator.

        Args:
            spec_dir: Path to spec directory
            schema: Optional custom schema (uses default if not provided)
        """
        super().__init__(spec_dir)
        self.schema = schema or DEFAULT_IMPLEMENTATION_PLAN_SCHEMA

    def _process_plan_data(
        self,
        plan: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
        fixes: List[str],
    ) -> None:
        """Process and validate plan data against schema."""
        # Validate against schema
        schema_errors, schema_warnings = self.schema.validate_data(plan)
        errors.extend(schema_errors)
        warnings.extend(schema_warnings)

        # Deep validation of phases
        if "phases" in plan and isinstance(plan["phases"], list):
            self._validate_phases(plan["phases"], errors, warnings, fixes)

        for error in schema_errors:
            fixes.append(f"Fix: {error}")

    def validate(self) -> SpecValidationResult:
        """Validate implementation_plan.json exists and has valid schema (synchronous)."""
        errors: List[str] = []
        warnings: List[str] = []
        fixes: List[str] = []

        plan_file = self.spec_dir / "implementation_plan.json"

        if not plan_file.exists():
            errors.append("implementation_plan.json not found")
            fixes.append("Run planning phase to generate implementation_plan.json")
            return self._create_result(
                "implementation_plan", errors=errors, warnings=warnings, fixes=fixes
            )

        try:
            with open(plan_file, encoding="utf-8") as f:
                plan = json.load(f)

            self._process_plan_data(plan, errors, warnings, fixes)

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
            fixes.append("Fix JSON syntax errors in implementation_plan.json")

        return self._create_result(
            "implementation_plan", errors=errors, warnings=warnings, fixes=fixes
        )

    async def validate_async(self) -> SpecValidationResult:
        """
        Validate implementation_plan.json exists and has valid schema (asynchronous).

        Requires aiofiles to be installed. Falls back to sync if unavailable.

        Returns:
            SpecValidationResult with validation status and details
        """
        if not ASYNC_AVAILABLE:
            # Fall back to synchronous validation
            return self.validate()

        errors: List[str] = []
        warnings: List[str] = []
        fixes: List[str] = []

        plan_file = self.spec_dir / "implementation_plan.json"

        if not plan_file.exists():
            errors.append("implementation_plan.json not found")
            fixes.append("Run planning phase to generate implementation_plan.json")
            return self._create_result(
                "implementation_plan", errors=errors, warnings=warnings, fixes=fixes
            )

        try:
            async with aiofiles.open(plan_file, encoding="utf-8") as f:
                content = await f.read()
                plan = json.loads(content)

            self._process_plan_data(plan, errors, warnings, fixes)

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
            fixes.append("Fix JSON syntax errors in implementation_plan.json")

        return self._create_result(
            "implementation_plan", errors=errors, warnings=warnings, fixes=fixes
        )

    def _validate_phases(
        self,
        phases: List[Dict[str, Any]],
        errors: List[str],
        warnings: List[str],
        fixes: List[str],
    ) -> None:
        """
        Validate phase structure with detailed checks.

        Args:
            phases: List of phase dictionaries
            errors: List to append errors to
            warnings: List to append warnings to
            fixes: List to append fixes to
        """
        phase_schema = self.schema.nested_schemas.get("phases")
        if not phase_schema:
            return

        subtask_schema = phase_schema.nested_schemas.get("subtasks")

        for i, phase in enumerate(phases):
            phase_id = phase.get("id", phase.get("phase", f"index_{i}"))

            # Check for at least one identifier
            has_id = "id" in phase or "phase" in phase
            if not has_id:
                errors.append(
                    f"Phase {phase_id}: Missing identifier (need 'id' or 'phase')"
                )

            # Check required fields
            for req_field in phase_schema.required_fields:
                if req_field not in phase:
                    errors.append(
                        f"Phase {phase_id}: Missing required field '{req_field}'"
                    )

            # Validate subtasks
            if "subtasks" not in phase or not subtask_schema:
                continue

            for j, subtask in enumerate(phase["subtasks"]):
                subtask_id = subtask.get("id", f"subtask_{j}")
                for req_field in subtask_schema.required_fields:
                    if req_field not in subtask:
                        errors.append(
                            f"Phase {phase_id}, Subtask {subtask_id}: "
                            f"Missing required field '{req_field}'"
                        )

                # Validate status
                if "status" in subtask:
                    allowed_status = subtask_schema.allowed_values.get("status", [])
                    if allowed_status and subtask["status"] not in allowed_status:
                        warnings.append(
                            f"Phase {phase_id}, Subtask {subtask_id}: "
                            f"Unknown status '{subtask['status']}'"
                        )


# ============================================================================
# Main Validator Class
# ============================================================================

class SpecValidator:
    """
    Orchestrates all validation checkpoints.

    Provides a unified interface for validating spec directories with
    configurable validators and schemas. Supports optional caching of
    validation results based on file modification times.
    """

    # Files to track for cache invalidation
    _TRACKED_FILES = [
        "context.json",
        "spec.md",
        "implementation_plan.json",
        "requirements.json",
    ]

    def __init__(
        self,
        spec_dir: Union[str, Path],
        context_schema: Optional[ValidationSchema] = None,
        implementation_plan_schema: Optional[ValidationSchema] = None,
        spec_required_sections: Optional[List[str]] = None,
        spec_recommended_sections: Optional[List[str]] = None,
        additional_validators: Optional[Dict[str, Type[BaseValidator]]] = None,
        validator_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        enable_cache: bool = False,
    ) -> None:
        """
        Initialize the spec validator.

        Args:
            spec_dir: Path to the spec directory
            context_schema: Custom schema for context.json validation
            implementation_plan_schema: Custom schema for implementation_plan.json
            spec_required_sections: Custom required sections for spec.md
            spec_recommended_sections: Custom recommended sections for spec.md
            additional_validators: Dict mapping names to validator classes
            validator_configs: Dict mapping validator names to config kwargs
            enable_cache: Enable caching of validation results based on mtime
        """
        self.spec_dir = Path(spec_dir)
        self._validator_configs = validator_configs or {}
        self._enable_cache = enable_cache

        # Cache storage: {cache_key: (mtime_dict, results)}
        self._validation_cache: Dict[str, Tuple[Dict[str, float], List[SpecValidationResult]]] = {}

        # Initialize core validators
        self._prereqs = PrereqsValidator(
            self.spec_dir,
            **self._validator_configs.get("prereqs", {}),
        )
        self._context = ContextValidator(
            self.spec_dir,
            schema=context_schema,
        )
        self._spec_document = SpecDocumentValidator(
            self.spec_dir,
            required_sections=spec_required_sections,
            recommended_sections=spec_recommended_sections,
        )
        self._implementation_plan = ImplementationPlanValidator(
            self.spec_dir,
            schema=implementation_plan_schema,
        )

        # Store additional validators
        self._additional_validators: Dict[str, BaseValidator] = {}
        if additional_validators:
            for name, validator_class in additional_validators.items():
                config = self._validator_configs.get(name, {})
                self._additional_validators[name] = validator_class(
                    self.spec_dir, **config
                )

    def _get_file_mtimes(self) -> Dict[str, float]:
        """
        Get modification times for all tracked files.

        Returns:
            Dict mapping filename to mtime (0.0 if file doesn't exist)
        """
        mtimes: Dict[str, float] = {}
        for filename in self._TRACKED_FILES:
            filepath = self.spec_dir / filename
            if not filepath.exists():
                mtimes[filename] = 0.0
                continue

            mtimes[filename] = os.path.getmtime(filepath)
        return mtimes

    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if cached results are still valid.

        Args:
            cache_key: The cache key to check

        Returns:
            True if cache is valid, False otherwise
        """
        if not self._enable_cache or cache_key not in self._validation_cache:
            return False

        cached_mtimes, _ = self._validation_cache[cache_key]
        current_mtimes = self._get_file_mtimes()
        return cached_mtimes == current_mtimes

    def clear_cache(self) -> None:
        """Clear all cached validation results."""
        self._validation_cache.clear()

    def validate_all(self, use_cache: Optional[bool] = None) -> List[SpecValidationResult]:
        """
        Run all validations.

        Args:
            use_cache: Override instance cache setting for this call.
                       None uses instance setting, True/False overrides.

        Returns:
            List of validation results for all checkpoints
        """
        should_use_cache = use_cache if use_cache is not None else self._enable_cache
        cache_key = "validate_all"

        # Check cache if enabled
        if should_use_cache and self._is_cache_valid(cache_key):
            _, cached_results = self._validation_cache[cache_key]
            return cached_results

        # Run validations
        results = [
            self.validate_prereqs(),
            self.validate_context(),
            self.validate_spec_document(),
            self.validate_implementation_plan(),
        ]

        # Run additional validators
        for name, validator in self._additional_validators.items():
            results.append(validator.validate())

        # Cache results if enabled
        if should_use_cache:
            self._validation_cache[cache_key] = (self._get_file_mtimes(), results)

        return results

    def validate_prereqs(self) -> SpecValidationResult:
        """Validate prerequisites exist."""
        return self._prereqs.validate()

    def validate_context(self) -> SpecValidationResult:
        """Validate context.json."""
        return self._context.validate()

    def validate_spec_document(self) -> SpecValidationResult:
        """Validate spec.md."""
        return self._spec_document.validate()

    def validate_implementation_plan(self) -> SpecValidationResult:
        """Validate implementation_plan.json."""
        return self._implementation_plan.validate()

    def validate_checkpoint(self, checkpoint: str) -> SpecValidationResult:
        """
        Validate a specific checkpoint by name.

        Args:
            checkpoint: Name of checkpoint to validate

        Returns:
            SpecValidationResult for the checkpoint

        Raises:
            ValueError: If checkpoint name is unknown
        """
        validators = {
            "prerequisites": self._prereqs,
            "prereqs": self._prereqs,
            "context": self._context,
            "spec_document": self._spec_document,
            "spec": self._spec_document,
            "implementation_plan": self._implementation_plan,
            "plan": self._implementation_plan,
            **self._additional_validators,
        }

        if checkpoint not in validators:
            raise ValueError(
                f"Unknown checkpoint: {checkpoint}. "
                f"Available: {list(validators.keys())}"
            )

        return validators[checkpoint].validate()

    def is_valid(self) -> bool:
        """
        Check if all validations pass.

        Returns:
            True if all checkpoints are valid
        """
        results = self.validate_all()
        return all(r.valid for r in results)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get validation summary.

        Returns:
            Dictionary with validation status for each checkpoint
        """
        results = self.validate_all()
        return {
            "all_valid": all(r.valid for r in results),
            "checkpoints": {r.checkpoint: r.to_dict() for r in results},
            "total_errors": sum(len(r.errors) for r in results),
            "total_warnings": sum(len(r.warnings) for r in results),
            "spec_dir": str(self.spec_dir),
        }

    def add_validator(
        self,
        name: str,
        validator: BaseValidator,
    ) -> None:
        """
        Add a custom validator at runtime.

        Args:
            name: Name for the validator
            validator: Validator instance
        """
        self._additional_validators[name] = validator

    def remove_validator(self, name: str) -> bool:
        """
        Remove a custom validator.

        Args:
            name: Name of validator to remove

        Returns:
            True if validator was removed, False if not found
        """
        if name in self._additional_validators:
            del self._additional_validators[name]
            return True
        return False


# ============================================================================
# Utility Functions
# ============================================================================

def validate_spec_directory(
    spec_dir: Union[str, Path],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Convenience function to validate a spec directory.

    Args:
        spec_dir: Path to spec directory
        **kwargs: Additional arguments passed to SpecValidator

    Returns:
        Validation summary dictionary
    """
    validator = SpecValidator(spec_dir, **kwargs)
    return validator.get_summary()


def create_validator_from_config(
    spec_dir: Union[str, Path],
    config: Dict[str, Any],
) -> SpecValidator:
    """
    Create a SpecValidator from a configuration dictionary.

    Args:
        spec_dir: Path to spec directory
        config: Configuration dictionary with schema definitions

    Returns:
        Configured SpecValidator instance
    """
    context_schema = None
    if "context_schema" in config:
        context_schema = ValidationSchema(**config["context_schema"])

    plan_schema = None
    if "implementation_plan_schema" in config:
        plan_schema = ValidationSchema(**config["implementation_plan_schema"])

    return SpecValidator(
        spec_dir=spec_dir,
        context_schema=context_schema,
        implementation_plan_schema=plan_schema,
        spec_required_sections=config.get("spec_required_sections"),
        spec_recommended_sections=config.get("spec_recommended_sections"),
    )
