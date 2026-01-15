"""
Quality Validator - Evidence-Based Quality Gate System

Provides threshold-based confidence scoring and pass/fail quality gate logic.
Extracted from Connascence Analyzer unified quality gate system.

Zero external dependencies - stdlib only.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# LEGO Import: Use shared types from library for common validation types
try:
    from library.common.types import (
        ValidationResult as BaseValidationResult,
        Violation as BaseViolation,
        Severity,
    )
except ImportError:
    try:
        from common.types import (
            ValidationResult as BaseValidationResult,
            Violation as BaseViolation,
            Severity,
        )
    except ImportError:
        # Fallback for standalone usage (Enum already imported at module level)
        BaseValidationResult = None  # type: ignore
        BaseViolation = None  # type: ignore

        class Severity(Enum):  # type: ignore[no-redef]
            """Violation severity levels - FALLBACK (prefer library.common.types)"""
            CRITICAL = "critical"
            HIGH = "high"
            MEDIUM = "medium"
            LOW = "low"
            INFO = "info"


class EvidenceQuality(Enum):
    """Evidence quality categories"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    INSUFFICIENT = "insufficient"


class RiskLevel(Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class QualityClaim:
    """
    Quality improvement claim to be validated.

    Represents a claim about quality metrics that needs evidence-based validation.
    """
    claim_id: str
    description: str
    metric_name: str
    baseline_value: float
    improved_value: float
    improvement_percent: float
    measurement_method: str
    evidence_files: List[str]
    timestamp: float
    claim_type: str = "quality"  # quality, performance, security, maintainability
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert claim to dictionary"""
        return {
            "claim_id": self.claim_id,
            "description": self.description,
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "improved_value": self.improved_value,
            "improvement_percent": self.improvement_percent,
            "measurement_method": self.measurement_method,
            "evidence_files": self.evidence_files,
            "timestamp": self.timestamp,
            "claim_type": self.claim_type,
            "metadata": self.metadata,
        }


# NOTE: This module uses a specialized QualityValidationResult for quality claim validation.
# For simple validation needs, use library.common.types.ValidationResult.

@dataclass
class QualityValidationResult:
    """
    Result of quality claim validation.

    This is a specialized validation result for quality claims that includes
    confidence scoring, evidence quality assessment, and theater detection.
    For simple validation, use library.common.types.ValidationResult instead.

    Contains validation outcome, confidence score, and recommendations.
    """
    claim_id: str
    is_valid: bool
    confidence_score: float
    validation_method: str
    evidence_quality: str
    theater_indicators: List[str]
    genuine_indicators: List[str]
    recommendation: str
    risk_level: str  # low, medium, high

    def __bool__(self) -> bool:
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "claim_id": self.claim_id,
            "is_valid": self.is_valid,
            "confidence_score": self.confidence_score,
            "validation_method": self.validation_method,
            "evidence_quality": self.evidence_quality,
            "theater_indicators": self.theater_indicators,
            "genuine_indicators": self.genuine_indicators,
            "recommendation": self.recommendation,
            "risk_level": self.risk_level,
        }

    @property
    def passed(self) -> bool:
        """Alias for is_valid for gate-style usage"""
        return self.is_valid


# Backward compatibility alias - prefer QualityValidationResult for new code
ValidationResult = QualityValidationResult


# Note: This module defines a specialized Violation class for quality validation.
# The base Violation from library.common.types has a different field structure.
# This version is tailored for QualityValidator with category and source_analyzer fields.
# For interoperability, use to_dict()/from_dict() methods.

# Use BaseViolation if available, otherwise define fallback
if BaseViolation is not None:
    # Import succeeded - we can reference base types for compatibility
    _BaseViolationAvailable = True
else:
    _BaseViolationAvailable = False

@dataclass
class Violation:
    """
    Represents a quality violation for the QualityValidator.

    Note: This is a specialized version with fields tailored for quality validation:
    - category field for violation categorization
    - source_analyzer field for tracking which analyzer found the issue
    - Different field names than library.common.types.Violation for backward compatibility

    For conversion to the base Violation type, use:
        base_violation = BaseViolation(
            severity=Severity.from_string(self.severity),
            message=self.message,
            file_path=self.file,
            line=self.line,
            column=self.column,
            rule_id=self.rule_id,
            suggestion=self.fix_suggestion,
            metadata=self.metadata
        )
    """
    rule_id: str
    message: str
    file: str
    line: int
    column: Optional[int] = None
    severity: str = "medium"
    category: str = "quality"
    code_snippet: Optional[str] = None
    fix_suggestion: Optional[str] = None
    source_analyzer: str = "quality_validator"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert violation to dictionary"""
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "severity": self.severity,
            "category": self.category,
            "code_snippet": self.code_snippet,
            "fix_suggestion": self.fix_suggestion,
            "source_analyzer": self.source_analyzer,
            "metadata": self.metadata,
        }

    def to_base_violation(self) -> Any:
        """
        Convert to library.common.types.Violation for interoperability.

        Returns:
            BaseViolation instance if library is available, else dict representation

        Note:
            Some fields are mapped: fix_suggestion -> suggestion, category -> metadata
        """
        if BaseViolation is not None:
            return BaseViolation(
                severity=Severity.from_string(self.severity) if isinstance(self.severity, str) else self.severity,
                message=self.message,
                file_path=self.file,
                line=self.line,
                column=self.column,
                rule_id=self.rule_id,
                suggestion=self.fix_suggestion,
                metadata={
                    "category": self.category,
                    "source_analyzer": self.source_analyzer,
                    "code_snippet": self.code_snippet,
                    **self.metadata,
                },
            )
        # Fallback: return dict representation
        return self.to_dict()

    @classmethod
    def from_base_violation(
        cls,
        base: Any,
        category: str = "quality",
        source_analyzer: str = "quality_validator",
    ) -> "Violation":
        """
        Create from library.common.types.Violation.

        Args:
            base: BaseViolation instance or dict
            category: Override category
            source_analyzer: Override source_analyzer

        Returns:
            Violation instance
        """
        if hasattr(base, "to_dict"):
            data = base.to_dict()
        else:
            data = base

        return cls(
            rule_id=data.get("rule_id") or data.get("rule_name") or "unknown",
            message=data.get("message") or "",
            file=data.get("file_path") or "",
            line=data.get("line") or 0,
            column=data.get("column"),
            severity=data.get("severity", "medium"),
            category=category or data.get("metadata", {}).get("category", "quality"),
            code_snippet=data.get("metadata", {}).get("code_snippet"),
            fix_suggestion=data.get("suggestion"),
            source_analyzer=source_analyzer or data.get("metadata", {}).get("source_analyzer", "quality_validator"),
            metadata={k: v for k, v in data.get("metadata", {}).items() if k not in ("category", "source_analyzer", "code_snippet")},
        )


@dataclass
class AnalysisResult:
    """Results from quality analysis"""
    violations: List[Violation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    overall_score: float = 0.0
    quality_gate_passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "violations": [v.to_dict() for v in self.violations],
            "metadata": self.metadata,
            "metrics": self.metrics,
            "overall_score": self.overall_score,
            "quality_gate_passed": self.quality_gate_passed,
        }


class QualityValidator:
    """
    Evidence-based quality validation system.

    Provides:
    - Threshold-based confidence scoring
    - Pass/fail quality gate logic
    - Violation tracking and metrics
    - Configurable severity thresholds
    """

    DEFAULT_CONFIG = {
        "thresholds": {
            "max_critical": 0,
            "max_high": 5,
            "max_medium": 10,
            "max_low": 20,
        },
        "scoring": {
            "penalties": {
                "critical": 10,
                "high": 5,
                "medium": 2,
                "low": 1,
                "info": 0,
            },
            "base_score": 100.0,
        },
        "validation": {
            "minimum_improvement": 1.0,
            "maximum_believable": 95.0,
            "confidence_threshold": 0.65,
            "sample_size_minimum": 5,
            "measurement_variance_max": 0.4,
            "evidence_completeness": 0.6,
            # Claim validation thresholds (moved from magic numbers)
            "max_theater_indicators": 2,
            "min_genuine_indicators": 2,
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the quality validator.

        Args:
            config: Optional configuration dictionary
        """
        self.config = self._merge_config(config or {})
        self.violations: List[Violation] = []
        self.validation_history: List[ValidationResult] = []

    def _merge_config(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge user config with defaults"""
        merged = {}
        for key, default_value in self.DEFAULT_CONFIG.items():
            if key not in user_config:
                merged[key] = default_value
                continue
            if not isinstance(default_value, dict):
                merged[key] = user_config[key]
                continue
            merged[key] = {**default_value, **user_config[key]}
        return merged

    def add_violation(
        self,
        rule_id: str,
        message: str,
        file: str,
        line: int,
        severity: str = "medium",
        category: str = "quality",
        column: Optional[int] = None,
        code_snippet: Optional[str] = None,
        fix_suggestion: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Violation:
        """
        Add a violation to the validator.

        Args:
            rule_id: Unique identifier for the rule
            message: Human-readable violation message
            file: File path where violation occurred
            line: Line number
            severity: Severity level (critical, high, medium, low, info)
            category: Category of violation
            column: Optional column number
            code_snippet: Optional code snippet
            fix_suggestion: Optional fix suggestion
            metadata: Optional additional metadata

        Returns:
            The created Violation object
        """
        # Validate severity against allowed values
        valid_severities = {"critical", "high", "medium", "low", "info"}
        severity_normalized = severity.lower()
        if severity_normalized not in valid_severities:
            raise ValueError(
                f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(valid_severities))}"
            )
        violation = Violation(
            rule_id=rule_id,
            message=message,
            file=file,
            line=line,
            column=column,
            severity=severity_normalized,
            category=category,
            code_snippet=code_snippet,
            fix_suggestion=fix_suggestion,
            metadata=metadata or {},
        )
        self.violations.append(violation)
        return violation

    def clear_violations(self) -> None:
        """Clear all recorded violations"""
        self.violations.clear()

    def calculate_score(self) -> float:
        """
        Calculate quality score based on violations.

        Returns:
            Score from 0.0 to 100.0
        """
        penalties = self.config["scoring"]["penalties"]
        base_score = self.config["scoring"]["base_score"]

        total_penalty = sum(
            penalties.get(v.severity, 0) for v in self.violations
        )

        return max(0.0, base_score - total_penalty)

    def check_gate(self, fail_on: str = "high") -> bool:
        """
        Check if quality gate passes.

        Args:
            fail_on: Severity threshold to fail on (critical, high, medium, low)

        Returns:
            True if gate passes, False otherwise
        """
        severity_order = ["critical", "high", "medium", "low", "info"]
        # Normalize input and validate membership before index lookup
        fail_on_normalized = fail_on.lower()
        if fail_on_normalized not in severity_order:
            raise ValueError(
                f"Invalid severity '{fail_on}'. Must be one of: {', '.join(severity_order)}"
            )
        fail_index = severity_order.index(fail_on_normalized)

        # Count violations by severity
        counts = self._count_by_severity()
        thresholds = self.config["thresholds"]

        # Check if any severity at or above threshold is exceeded
        for i in range(fail_index + 1):
            severity = severity_order[i]
            count = counts.get(severity, 0)
            threshold = thresholds.get(f"max_{severity}", 0)

            if count > threshold:
                return False

        return True

    def _count_by_severity(self) -> Dict[str, int]:
        """Count violations by severity"""
        counts: Dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        for v in self.violations:
            if v.severity in counts:
                counts[v.severity] += 1
        return counts

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get quality metrics.

        Returns:
            Dictionary with metrics
        """
        severity_counts = self._count_by_severity()

        category_counts: Dict[str, int] = {}
        files_affected: set = set()

        for v in self.violations:
            category_counts[v.category] = category_counts.get(v.category, 0) + 1
            files_affected.add(v.file)

        return {
            "total_violations": len(self.violations),
            "severity_counts": severity_counts,
            "category_counts": category_counts,
            "files_affected": len(files_affected),
            "score": self.calculate_score(),
        }

    def analyze(
        self,
        fail_on: str = "high",
        project_path: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Run analysis and return results.

        Args:
            fail_on: Severity to fail on
            project_path: Optional project path for metadata

        Returns:
            AnalysisResult with all data
        """
        metrics = self.get_metrics()
        gate_passed = self.check_gate(fail_on)
        score = self.calculate_score()

        result = AnalysisResult(
            violations=list(self.violations),
            metadata={
                "project_path": project_path or "unknown",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "fail_on": fail_on,
            },
            metrics=metrics,
            overall_score=score,
            quality_gate_passed=gate_passed,
        )

        return result

    def validate_claim(self, claim: QualityClaim) -> ValidationResult:
        """
        Validate a quality improvement claim.

        Args:
            claim: The quality claim to validate

        Returns:
            ValidationResult with validation outcome
        """
        # Step 1: Statistical plausibility check
        statistical_score = self._validate_statistical_plausibility(claim)

        # Step 2: Evidence quality assessment
        evidence_score = self._assess_evidence_quality(claim)

        # Step 3: Theater pattern detection
        theater_indicators = self._detect_theater_patterns(claim)

        # Step 4: Genuine improvement indicators
        genuine_indicators = self._detect_genuine_indicators(claim)

        # Calculate overall confidence score
        confidence_score = self._calculate_confidence_score(
            statistical_score,
            evidence_score,
            theater_indicators,
            genuine_indicators,
        )

        # Determine validity using configurable thresholds
        validation_config = self.config["validation"]
        threshold = validation_config["confidence_threshold"]
        max_theater = validation_config.get("max_theater_indicators", 2)
        min_genuine = validation_config.get("min_genuine_indicators", 2)
        is_valid = (
            confidence_score >= threshold
            and len(theater_indicators) < max_theater
            and len(genuine_indicators) >= min_genuine
        )

        # Determine risk level
        risk_level = self._assess_risk_level(confidence_score, theater_indicators)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            claim,
            statistical_score,
            evidence_score,
            theater_indicators,
            genuine_indicators,
        )

        result = ValidationResult(
            claim_id=claim.claim_id,
            is_valid=is_valid,
            confidence_score=confidence_score,
            validation_method="comprehensive_analysis",
            evidence_quality=self._categorize_evidence_quality(evidence_score),
            theater_indicators=theater_indicators,
            genuine_indicators=genuine_indicators,
            recommendation=recommendation,
            risk_level=risk_level,
        )

        self.validation_history.append(result)
        return result

    def _validate_statistical_plausibility(self, claim: QualityClaim) -> float:
        """Validate statistical plausibility of quality claim"""
        thresholds = self.config["validation"]
        plausibility_score = 1.0

        improvement = abs(claim.improvement_percent)

        if improvement < thresholds["minimum_improvement"]:
            plausibility_score *= 0.3
        elif improvement > thresholds["maximum_believable"]:
            plausibility_score *= 0.1
        elif improvement > 70.0:
            plausibility_score *= 0.6

        # Check for suspicious round numbers
        if improvement in [10.0, 20.0, 25.0, 50.0, 75.0, 90.0, 95.0, 100.0]:
            plausibility_score *= 0.5

        if claim.baseline_value <= 0:
            plausibility_score *= 0.2

        return max(0.0, min(1.0, plausibility_score))

    def _assess_evidence_quality(self, claim: QualityClaim) -> float:
        """Assess quality of evidence provided"""
        if not claim.evidence_files:
            return 0.1

        evidence_score = 0.0
        evidence_components: List[float] = []

        if claim.measurement_method:
            method = claim.measurement_method.lower()
            good_keywords = [
                "baseline", "before", "after", "comparison",
                "measured", "analyzed", "files", "modules",
            ]
            keyword_score = sum(1 for kw in good_keywords if kw in method)
            evidence_components.append(min(0.3, keyword_score * 0.05))

            if any(char.isdigit() for char in method):
                evidence_components.append(0.1)

            if len(method) > 50:
                evidence_components.append(0.1)

        for evidence_file in claim.evidence_files:
            report_keywords = ["report", "analysis", "metrics", "before", "after"]
            if any(kw in evidence_file.lower() for kw in report_keywords):
                evidence_components.append(0.1)

            if Path(evidence_file).suffix in [".json", ".xml", ".csv", ".log", ".txt", ".md"]:
                evidence_components.append(0.05)

        if len(claim.evidence_files) >= 2:
            evidence_components.append(0.1)
        if len(claim.evidence_files) >= 3:
            evidence_components.append(0.1)

        evidence_score = min(1.0, sum(evidence_components))
        return evidence_score

    def _detect_theater_patterns(self, claim: QualityClaim) -> List[str]:
        """Detect patterns that indicate quality theater"""
        detected: List[str] = []

        # Perfect metrics pattern
        if claim.improved_value == 0 or claim.improvement_percent in {100.0, 0.0}:
            detected.append("perfect_metrics")

        # Vanity metrics pattern
        metric = claim.metric_name.lower()
        vanity_keywords = ["lines", "files", "comments", "whitespace", "format"]
        if any(kw in metric for kw in vanity_keywords):
            detected.append("vanity_metrics")

        # Measurement gaming pattern
        method = claim.measurement_method.lower()
        gaming_keywords = ["selected", "best", "excluding", "only", "subset"]
        if any(kw in method for kw in gaming_keywords):
            detected.append("measurement_gaming")

        # Fake refactoring pattern
        if "refactor" in claim.description.lower() and claim.improvement_percent < 5.0:
            detected.append("fake_refactoring")

        return detected

    def _detect_genuine_indicators(self, claim: QualityClaim) -> List[str]:
        """Detect indicators of genuine quality improvements"""
        genuine: List[str] = []

        improvement = abs(claim.improvement_percent)

        if 5.0 <= improvement <= 60.0:
            genuine.append("realistic_improvement_magnitude")

        if improvement != round(improvement, 0) or improvement % 5 != 0:
            genuine.append("precise_measurement")

        if len(claim.evidence_files) >= 2:
            genuine.append("multiple_evidence_sources")

        if claim.measurement_method and len(claim.measurement_method) > 100:
            genuine.append("detailed_methodology")

        if "gradual" in claim.description.lower() or "iterative" in claim.description.lower():
            genuine.append("gradual_improvement")

        return genuine

    def _calculate_confidence_score(
        self,
        statistical_score: float,
        evidence_score: float,
        theater_indicators: List[str],
        genuine_indicators: List[str],
    ) -> float:
        """Calculate overall confidence score"""
        base_score = (statistical_score * 0.4 + evidence_score * 0.6)

        theater_penalty = len(theater_indicators) * 0.25
        base_score = max(0.0, base_score - theater_penalty)

        genuine_bonus = min(0.3, len(genuine_indicators) * 0.08)
        confidence_score = min(1.0, base_score + genuine_bonus)

        return round(confidence_score, 3)

    def _assess_risk_level(
        self,
        confidence_score: float,
        theater_indicators: List[str],
    ) -> str:
        """Assess risk level of accepting the claim"""
        if len(theater_indicators) >= 3 or confidence_score < 0.3:
            return "high"
        if len(theater_indicators) >= 1 or confidence_score < 0.6:
            return "medium"
        return "low"

    def _categorize_evidence_quality(self, evidence_score: float) -> str:
        """Categorize evidence quality based on score"""
        if evidence_score >= 0.8:
            return "excellent"
        elif evidence_score >= 0.6:
            return "good"
        elif evidence_score >= 0.4:
            return "fair"
        elif evidence_score >= 0.2:
            return "poor"
        else:
            return "insufficient"

    def _generate_recommendation(
        self,
        claim: QualityClaim,
        statistical_score: float,
        evidence_score: float,
        theater_indicators: List[str],
        genuine_indicators: List[str],
    ) -> str:
        """Generate actionable recommendation"""
        if len(theater_indicators) >= 2:
            return (
                f"REJECT: Multiple theater patterns detected ({', '.join(theater_indicators)}). "
                f"Provide genuine evidence with comprehensive methodology."
            )

        if evidence_score < 0.3:
            return (
                "INSUFFICIENT EVIDENCE: Provide comprehensive analysis reports, "
                "before/after metrics, and detailed methodology."
            )

        if statistical_score < 0.4:
            return (
                "STATISTICAL CONCERNS: Improvement claims appear unrealistic. "
                "Verify measurements and provide additional validation."
            )

        if len(genuine_indicators) < 2:
            return (
                "NEEDS VALIDATION: Provide additional evidence such as "
                "progressive improvement data or third-party verification."
            )

        confidence = statistical_score * 0.4 + evidence_score * 0.6

        if confidence >= 0.8 and len(genuine_indicators) >= 4:
            return "ACCEPT: Quality improvement validated with high confidence."
        elif confidence >= 0.65:
            return "CONDITIONAL ACCEPT: Quality improvement appears genuine but requires monitoring."
        else:
            return "REVIEW REQUIRED: Additional review needed before acceptance."

    def export_json(self, output_path: Union[str, Path]) -> None:
        """Export analysis results to JSON file"""
        result = self.analyze()
        try:
            Path(output_path).write_text(json.dumps(result.to_dict(), indent=2))
        except (OSError, IOError) as e:
            raise IOError(f"Failed to write JSON to '{output_path}': {e}") from e

    def export_sarif(self, output_path: Union[str, Path]) -> None:
        """Export results in SARIF format for code scanning integration"""
        sarif = {
            "version": "2.1.0",
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "Quality Validator",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/quality-validator",
                    }
                },
                "results": [
                    {
                        "ruleId": v.rule_id,
                        "message": {"text": v.message},
                        "level": self._sarif_level(v.severity),
                        "locations": [{
                            "physicalLocation": {
                                "artifactLocation": {"uri": v.file},
                                "region": {
                                    "startLine": v.line,
                                    "startColumn": v.column or 1,
                                },
                            }
                        }],
                        "properties": {
                            "category": v.category,
                            "fix_suggestion": v.fix_suggestion,
                        } if v.fix_suggestion else {"category": v.category}
                    }
                    for v in self.violations
                ],
            }]
        }
        try:
            Path(output_path).write_text(json.dumps(sarif, indent=2))
        except (OSError, IOError) as e:
            raise IOError(f"Failed to write SARIF to '{output_path}': {e}") from e

    def _sarif_level(self, severity: str) -> str:
        """Map severity to SARIF level"""
        mapping = {
            "critical": "error",
            "high": "error",
            "medium": "warning",
            "low": "note",
            "info": "note",
        }
        return mapping.get(severity, "warning")
