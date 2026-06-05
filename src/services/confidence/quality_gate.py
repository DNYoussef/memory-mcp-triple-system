"""Quality Gate Score Aggregator for CAPTURE-003.

Aggregates multiple confidence scores into overall quality gate decisions.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.integrations.confidence_scoring_schema import (
    ConfidenceScore,
    ClassificationResult,
    ClassificationType,
    QualityGateScore,
    EscalationReason,
    EscalationStatus,
    combine_confidences,
    ESCALATION_THRESHOLD,
)

logger = logging.getLogger(__name__)


class GateStatus(Enum):
    """Status of a quality gate check."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class GateType(Enum):
    """Types of quality gates."""
    MODE_DETECTION = "mode_detection"
    ENTITY_EXTRACTION = "entity_extraction"
    TAG_ASSIGNMENT = "tag_assignment"
    CONTENT_QUALITY = "content_quality"
    MEMORY_RELEVANCE = "memory_relevance"
    CLASSIFICATION_AGREEMENT = "classification_agreement"
    CUSTOM = "custom"


@dataclass
class GateCheck:
    """A single quality gate check."""

    gate_type: GateType
    name: str
    score: ConfidenceScore
    status: GateStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        gate_type: GateType,
        name: str,
        confidence: float,
        pass_threshold: float = ESCALATION_THRESHOLD,
        warn_threshold: float = 0.5,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> "GateCheck":
        """Create a gate check with automatic status determination."""
        score = ConfidenceScore.create(
            score=confidence,
            classification_type=ClassificationType.QUALITY_GATE,
            components={"raw_score": confidence},
        )

        if confidence >= pass_threshold:
            status = GateStatus.PASSED
        elif confidence >= warn_threshold:
            status = GateStatus.WARNING
        else:
            status = GateStatus.FAILED

        return cls(
            gate_type=gate_type,
            name=name,
            score=score,
            status=status,
            message=message or f"Score: {confidence:.2%}",
            details=details or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "gate_type": self.gate_type.value,
            "name": self.name,
            "score": self.score.to_dict(),
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class QualityGateConfig:
    """Configuration for quality gate aggregator."""

    pass_threshold: float = ESCALATION_THRESHOLD
    warn_threshold: float = 0.5
    fail_threshold: float = 0.3
    require_all_pass: bool = False
    min_checks: int = 1
    aggregation_method: str = "weighted_min"
    gate_weights: Dict[str, float] = field(default_factory=dict)


class QualityGateAggregator:
    """Aggregates multiple confidence scores into quality gate decisions.

    Supports weighted aggregation, threshold-based pass/fail, and
    configurable gate requirements.
    """

    def __init__(self, config: Optional[QualityGateConfig] = None):
        """Initialize quality gate aggregator.

        Args:
            config: Aggregator configuration
        """
        self.config = config or QualityGateConfig()
        self._checks: List[GateCheck] = []
        self._custom_validators: Dict[str, Callable] = {}
        self._stats = {
            "total_evaluations": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
        }

    def add_check(self, check: GateCheck) -> None:
        """Add a check to the gate.

        Args:
            check: Gate check to add
        """
        self._checks.append(check)

    def add_confidence_score(
        self,
        gate_type: GateType,
        name: str,
        confidence: float,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> GateCheck:
        """Add a confidence score as a gate check.

        Args:
            gate_type: Type of gate
            name: Check name
            confidence: Confidence score (0-1)
            message: Optional message
            details: Optional details

        Returns:
            Created GateCheck
        """
        check = GateCheck.create(
            gate_type=gate_type,
            name=name,
            confidence=confidence,
            pass_threshold=self.config.pass_threshold,
            warn_threshold=self.config.warn_threshold,
            message=message,
            details=details,
        )
        self._checks.append(check)
        return check

    def add_classification_result(
        self,
        result: ClassificationResult,
        gate_type: Optional[GateType] = None,
    ) -> GateCheck:
        """Add a classification result as a gate check.

        Args:
            result: Classification result
            gate_type: Optional gate type override

        Returns:
            Created GateCheck
        """
        # Map classification type to gate type
        if gate_type is None:
            type_mapping = {
                ClassificationType.MODE_DETECTION: GateType.MODE_DETECTION,
                ClassificationType.ENTITY_EXTRACTION: GateType.ENTITY_EXTRACTION,
                ClassificationType.TAG_ASSIGNMENT: GateType.TAG_ASSIGNMENT,
                ClassificationType.QUALITY_GATE: GateType.CONTENT_QUALITY,
            }
            gate_type = type_mapping.get(
                result.classification_type,
                GateType.CUSTOM
            )

        return self.add_confidence_score(
            gate_type=gate_type,
            name=result.classification_type.value,
            confidence=result.confidence.score,
            message=f"Classification: {result.value}",
            details={
                "result_id": result.result_id,
                "alternatives": result.alternatives,
                "is_ambiguous": result.is_ambiguous(),
            },
        )

    def evaluate(self) -> QualityGateScore:
        """Evaluate all checks and return aggregate score.

        Returns:
            QualityGateScore with overall result
        """
        if len(self._checks) < self.config.min_checks:
            return QualityGateScore(
                gate_id="",
                gate_name="quality_gate",
                passed=False,
                overall_score=0.0,
                checks=[],
                pass_threshold=self.config.pass_threshold,
            )

        # Collect all confidence scores
        scores = [check.score for check in self._checks]

        # Get weights
        weights = []
        for check in self._checks:
            weight = self.config.gate_weights.get(check.name, 1.0)
            weights.append(weight)

        # Calculate overall score
        if self.config.aggregation_method == "weighted_min":
            # Weighted minimum (conservative)
            weighted_scores = [
                s.score * w for s, w in zip(scores, weights)
            ]
            min_idx = weighted_scores.index(min(weighted_scores))
            overall_score = scores[min_idx].score
        elif self.config.aggregation_method == "weighted_avg":
            # Weighted average
            total_weight = sum(weights)
            overall_score = sum(
                s.score * w for s, w in zip(scores, weights)
            ) / total_weight if total_weight > 0 else 0.0
        else:
            # Default: geometric mean
            overall_score = combine_confidences(
                [s.score for s in scores],
                method="geometric_mean",
            )

        # Determine pass/fail
        if self.config.require_all_pass:
            passed = all(
                check.status == GateStatus.PASSED
                for check in self._checks
            )
        else:
            passed = overall_score >= self.config.pass_threshold

        # Create result
        result = QualityGateScore.create(
            gate_name="quality_gate",
            checks=scores,
            pass_threshold=self.config.pass_threshold,
        )

        # Override with our calculation
        result.passed = passed
        result.overall_score = overall_score

        # Update stats
        self._update_stats(result)

        return result

    def evaluate_with_details(self) -> Dict[str, Any]:
        """Evaluate and return detailed results.

        Returns:
            Detailed evaluation results
        """
        result = self.evaluate()

        # Count by status
        status_counts = {
            GateStatus.PASSED: 0,
            GateStatus.FAILED: 0,
            GateStatus.WARNING: 0,
            GateStatus.SKIPPED: 0,
        }
        for check in self._checks:
            status_counts[check.status] += 1

        # Find failing checks
        failing_checks = [
            check.to_dict() for check in self._checks
            if check.status == GateStatus.FAILED
        ]

        # Find warning checks
        warning_checks = [
            check.to_dict() for check in self._checks
            if check.status == GateStatus.WARNING
        ]

        return {
            "passed": result.passed,
            "overall_score": round(result.overall_score, 4),
            "threshold": self.config.pass_threshold,
            "total_checks": len(self._checks),
            "status_counts": {
                k.value: v for k, v in status_counts.items()
            },
            "failing_checks": failing_checks,
            "warning_checks": warning_checks,
            "all_checks": [check.to_dict() for check in self._checks],
            "needs_escalation": result.overall_score < self.config.pass_threshold,
        }

    def register_validator(
        self,
        name: str,
        validator: Callable[[Any], float],
    ) -> None:
        """Register a custom validator function.

        Args:
            name: Validator name
            validator: Function that takes input and returns confidence (0-1)
        """
        self._custom_validators[name] = validator

    def run_custom_validator(
        self,
        name: str,
        input_data: Any,
    ) -> Optional[GateCheck]:
        """Run a custom validator and add result as check.

        Args:
            name: Validator name
            input_data: Input for validator

        Returns:
            Created GateCheck or None if validator not found
        """
        if name not in self._custom_validators:
            logger.warning(f"Validator not found: {name}")
            return None

        validator = self._custom_validators[name]
        try:
            confidence = validator(input_data)
            return self.add_confidence_score(
                gate_type=GateType.CUSTOM,
                name=name,
                confidence=confidence,
                message=f"Custom validator: {name}",
            )
        except Exception as e:
            logger.error(f"Validator {name} failed: {e}")
            return self.add_confidence_score(
                gate_type=GateType.CUSTOM,
                name=name,
                confidence=0.0,
                message=f"Validator failed: {e}",
            )

    def reset(self) -> None:
        """Reset all checks."""
        self._checks.clear()

    def _update_stats(self, result: QualityGateScore) -> None:
        """Update internal statistics."""
        self._stats["total_evaluations"] += 1

        if result.passed:
            self._stats["passed"] += 1
        else:
            self._stats["failed"] += 1

        # Count warnings
        warnings = sum(
            1 for check in self._checks
            if check.status == GateStatus.WARNING
        )
        self._stats["warnings"] += warnings

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics."""
        return {
            **self._stats,
            "pass_rate": (
                self._stats["passed"] / self._stats["total_evaluations"]
                if self._stats["total_evaluations"] > 0 else 0.0
            ),
        }

    def get_escalation_reason(
        self,
        result: QualityGateScore,
    ) -> Optional[EscalationReason]:
        """Determine escalation reason if gate failed."""
        if result.passed:
            return None

        # Check for specific failure patterns
        failing_checks = [
            check for check in self._checks
            if check.status == GateStatus.FAILED
        ]

        if not failing_checks:
            return None

        # Multiple failures suggest conflicting signals
        if len(failing_checks) > 1:
            return EscalationReason.CONFLICTING_SIGNALS

        # Single low confidence failure
        lowest_check = min(failing_checks, key=lambda c: c.score.score)
        if lowest_check.score.score < 0.3:
            return EscalationReason.LOW_CONFIDENCE

        return EscalationReason.QUALITY_GATE_FAILED


# Pre-configured gate templates

def create_memory_quality_gate() -> QualityGateAggregator:
    """Create a quality gate for memory operations."""
    config = QualityGateConfig(
        pass_threshold=0.6,
        warn_threshold=0.5,
        aggregation_method="weighted_min",
        gate_weights={
            "mode_detection": 1.0,
            "entity_extraction": 0.8,
            "tag_assignment": 0.9,
            "memory_relevance": 1.2,
        },
    )
    return QualityGateAggregator(config)


def create_strict_quality_gate() -> QualityGateAggregator:
    """Create a strict quality gate (all must pass)."""
    config = QualityGateConfig(
        pass_threshold=0.7,
        warn_threshold=0.6,
        require_all_pass=True,
        aggregation_method="weighted_min",
    )
    return QualityGateAggregator(config)


def create_lenient_quality_gate() -> QualityGateAggregator:
    """Create a lenient quality gate (average-based)."""
    config = QualityGateConfig(
        pass_threshold=0.5,
        warn_threshold=0.4,
        aggregation_method="weighted_avg",
    )
    return QualityGateAggregator(config)
