"""Confidence Scoring Schema for CAPTURE-003.

Defines data models for confidence scoring on all classifications.
Features: Mode detection, entity extraction, quality gates, tag assignment.
Threshold: <0.6 escalates to human review.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
import uuid
import math


class ConfidenceLevel(Enum):
    """Categorical confidence levels."""

    VERY_HIGH = "very_high"    # >= 0.9
    HIGH = "high"              # >= 0.8
    MEDIUM = "medium"          # >= 0.6
    LOW = "low"                # >= 0.4
    VERY_LOW = "very_low"      # < 0.4

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Convert numeric score to categorical level."""
        if score >= 0.9:
            return cls.VERY_HIGH
        elif score >= 0.8:
            return cls.HIGH
        elif score >= 0.6:
            return cls.MEDIUM
        elif score >= 0.4:
            return cls.LOW
        else:
            return cls.VERY_LOW


class EscalationReason(Enum):
    """Reasons for escalating to human review."""

    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_CLASSIFICATION = "ambiguous_classification"
    CONFLICTING_SIGNALS = "conflicting_signals"
    EDGE_CASE = "edge_case"
    QUALITY_GATE_FAILED = "quality_gate_failed"
    MODEL_UNCERTAINTY = "model_uncertainty"
    MANUAL_REVIEW_REQUESTED = "manual_review_requested"


class ClassificationType(Enum):
    """Types of classifications that receive confidence scores."""

    MODE_DETECTION = "mode_detection"
    ENTITY_EXTRACTION = "entity_extraction"
    TAG_ASSIGNMENT = "tag_assignment"
    QUALITY_GATE = "quality_gate"
    INTENT_CLASSIFICATION = "intent_classification"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    TOPIC_CLASSIFICATION = "topic_classification"
    RELEVANCE_SCORING = "relevance_scoring"


class EscalationStatus(Enum):
    """Status of escalation requests."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    AUTO_RESOLVED = "auto_resolved"


# Default escalation threshold
ESCALATION_THRESHOLD = 0.6


@dataclass
class ConfidenceScore:
    """A confidence score for a classification."""

    score: float  # 0.0 to 1.0
    level: ConfidenceLevel
    classification_type: ClassificationType

    # Score components (for explainability)
    components: Dict[str, float] = field(default_factory=dict)

    # Metadata
    model_name: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Calibration info
    calibrated: bool = False
    calibration_method: str = ""

    @classmethod
    def create(
        cls,
        score: float,
        classification_type: ClassificationType,
        components: Optional[Dict[str, float]] = None,
        model_name: str = "",
    ) -> "ConfidenceScore":
        """Create a confidence score with automatic level assignment."""
        # Clamp score to valid range
        score = max(0.0, min(1.0, score))

        return cls(
            score=score,
            level=ConfidenceLevel.from_score(score),
            classification_type=classification_type,
            components=components or {},
            model_name=model_name,
        )

    def needs_escalation(self, threshold: float = ESCALATION_THRESHOLD) -> bool:
        """Check if score is below escalation threshold."""
        return self.score < threshold

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "score": round(self.score, 4),
            "level": self.level.value,
            "classification_type": self.classification_type.value,
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "calibrated": self.calibrated,
            "needs_escalation": self.needs_escalation(),
        }


@dataclass
class ClassificationResult:
    """Result of a classification with confidence scoring."""

    result_id: str
    classification_type: ClassificationType
    value: Any  # The actual classification result
    confidence: ConfidenceScore

    # Alternative classifications (for ambiguity detection)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    # Context
    input_text: str = ""
    input_metadata: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        classification_type: ClassificationType,
        value: Any,
        confidence_score: float,
        input_text: str = "",
        alternatives: Optional[List[Dict[str, Any]]] = None,
        confidence_components: Optional[Dict[str, float]] = None,
    ) -> "ClassificationResult":
        """Create a classification result."""
        confidence = ConfidenceScore.create(
            score=confidence_score,
            classification_type=classification_type,
            components=confidence_components,
        )

        return cls(
            result_id=str(uuid.uuid4()),
            classification_type=classification_type,
            value=value,
            confidence=confidence,
            alternatives=alternatives or [],
            input_text=input_text,
        )

    def is_ambiguous(self, margin: float = 0.1) -> bool:
        """Check if classification is ambiguous (close alternatives)."""
        if not self.alternatives:
            return False

        for alt in self.alternatives:
            alt_score = alt.get("confidence", 0.0)
            if abs(self.confidence.score - alt_score) < margin:
                return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "result_id": self.result_id,
            "classification_type": self.classification_type.value,
            "value": self.value,
            "confidence": self.confidence.to_dict(),
            "alternatives": self.alternatives,
            "input_text": self.input_text[:500] if self.input_text else "",
            "is_ambiguous": self.is_ambiguous(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EscalationRequest:
    """Request for human review of a classification."""

    request_id: str
    classification_result: ClassificationResult
    reason: EscalationReason
    status: EscalationStatus

    # Priority (based on confidence gap)
    priority: int = 0  # 0-10, higher = more urgent

    # Context for reviewer
    context: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    # Resolution
    resolved_value: Optional[Any] = None
    resolved_by: str = ""
    resolution_notes: str = ""

    @classmethod
    def create(
        cls,
        classification_result: ClassificationResult,
        reason: EscalationReason,
        context: Optional[Dict[str, Any]] = None,
    ) -> "EscalationRequest":
        """Create an escalation request."""
        # Calculate priority based on confidence gap from threshold
        gap = ESCALATION_THRESHOLD - classification_result.confidence.score
        priority = min(10, max(0, int(gap * 20)))

        return cls(
            request_id=str(uuid.uuid4()),
            classification_result=classification_result,
            reason=reason,
            status=EscalationStatus.PENDING,
            priority=priority,
            context=context or {},
        )

    def resolve(
        self,
        resolved_value: Any,
        resolved_by: str,
        notes: str = "",
    ) -> None:
        """Mark escalation as resolved."""
        self.status = EscalationStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)
        self.resolved_value = resolved_value
        self.resolved_by = resolved_by
        self.resolution_notes = notes

    def dismiss(self, notes: str = "") -> None:
        """Dismiss escalation without resolution."""
        self.status = EscalationStatus.DISMISSED
        self.resolved_at = datetime.now(timezone.utc)
        self.resolution_notes = notes

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "classification": self.classification_result.to_dict(),
            "reason": self.reason.value,
            "status": self.status.value,
            "priority": self.priority,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_value": self.resolved_value,
            "resolved_by": self.resolved_by,
            "resolution_notes": self.resolution_notes,
        }


@dataclass
class QualityGateScore:
    """Aggregate score for a quality gate check."""

    gate_id: str
    gate_name: str
    passed: bool
    overall_score: float

    # Individual check scores
    checks: List[ConfidenceScore] = field(default_factory=list)

    # Thresholds
    pass_threshold: float = 0.6
    fail_threshold: float = 0.4

    # Metadata
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        gate_name: str,
        checks: List[ConfidenceScore],
        pass_threshold: float = 0.6,
    ) -> "QualityGateScore":
        """Create a quality gate score from individual checks."""
        if not checks:
            return cls(
                gate_id=str(uuid.uuid4()),
                gate_name=gate_name,
                passed=False,
                overall_score=0.0,
                checks=[],
                pass_threshold=pass_threshold,
            )

        # Calculate weighted average (lower scores weighted higher)
        weights = [1.0 / (score.score + 0.1) for score in checks]
        total_weight = sum(weights)
        weighted_sum = sum(
            score.score * weight for score, weight in zip(checks, weights)
        )
        overall = weighted_sum / total_weight if total_weight > 0 else 0.0

        return cls(
            gate_id=str(uuid.uuid4()),
            gate_name=gate_name,
            passed=overall >= pass_threshold,
            overall_score=overall,
            checks=checks,
            pass_threshold=pass_threshold,
        )

    def get_failing_checks(self) -> List[ConfidenceScore]:
        """Get checks that failed the threshold."""
        return [c for c in self.checks if c.score < self.pass_threshold]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "passed": self.passed,
            "overall_score": round(self.overall_score, 4),
            "checks": [c.to_dict() for c in self.checks],
            "failing_checks": len(self.get_failing_checks()),
            "pass_threshold": self.pass_threshold,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class ConfidenceCalibration:
    """Calibration data for confidence scores."""

    calibration_id: str
    classification_type: ClassificationType

    # Calibration curve (predicted -> actual)
    bins: List[float] = field(default_factory=list)
    actual_accuracies: List[float] = field(default_factory=list)

    # Statistics
    ece: float = 0.0  # Expected Calibration Error
    mce: float = 0.0  # Maximum Calibration Error
    sample_count: int = 0

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_name: str = ""

    def calibrate_score(self, raw_score: float) -> float:
        """Apply calibration to a raw score."""
        if not self.bins or not self.actual_accuracies:
            return raw_score

        # Find the appropriate bin
        for i, bin_edge in enumerate(self.bins[:-1]):
            if raw_score <= self.bins[i + 1]:
                return self.actual_accuracies[i]

        return self.actual_accuracies[-1] if self.actual_accuracies else raw_score


@dataclass
class ConfidenceStats:
    """Statistics for confidence scoring system."""

    total_classifications: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_level: Dict[str, int] = field(default_factory=dict)

    escalations_created: int = 0
    escalations_resolved: int = 0
    escalations_pending: int = 0

    average_confidence: float = 0.0
    median_confidence: float = 0.0

    quality_gates_run: int = 0
    quality_gates_passed: int = 0
    quality_gates_failed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "classifications": {
                "total": self.total_classifications,
                "by_type": self.by_type,
                "by_level": self.by_level,
                "average_confidence": round(self.average_confidence, 4),
                "median_confidence": round(self.median_confidence, 4),
            },
            "escalations": {
                "created": self.escalations_created,
                "resolved": self.escalations_resolved,
                "pending": self.escalations_pending,
            },
            "quality_gates": {
                "run": self.quality_gates_run,
                "passed": self.quality_gates_passed,
                "failed": self.quality_gates_failed,
                "pass_rate": (
                    round(self.quality_gates_passed / self.quality_gates_run, 4)
                    if self.quality_gates_run > 0 else 0.0
                ),
            },
        }


# Helper functions for confidence calculation

def combine_confidences(
    scores: List[float],
    method: str = "geometric_mean",
) -> float:
    """Combine multiple confidence scores."""
    if not scores:
        return 0.0

    if method == "geometric_mean":
        # Geometric mean (penalizes low scores more)
        product = 1.0
        for s in scores:
            product *= max(0.001, s)
        return product ** (1 / len(scores))

    elif method == "harmonic_mean":
        # Harmonic mean (heavily penalizes low scores)
        try:
            return len(scores) / sum(1 / max(0.001, s) for s in scores)
        except ZeroDivisionError:
            return 0.0

    elif method == "min":
        # Minimum (most conservative)
        return min(scores)

    elif method == "weighted_min":
        # Weighted combination favoring minimum
        min_score = min(scores)
        avg_score = sum(scores) / len(scores)
        return 0.7 * min_score + 0.3 * avg_score

    else:  # "arithmetic_mean"
        return sum(scores) / len(scores)


def entropy_based_confidence(probabilities: List[float]) -> float:
    """Calculate confidence from probability distribution using entropy.

    Lower entropy = higher confidence.
    """
    if not probabilities:
        return 0.0

    # Normalize probabilities
    total = sum(probabilities)
    if total == 0:
        return 0.0

    probs = [p / total for p in probabilities]

    # Calculate entropy
    entropy = 0.0
    for p in probs:
        if p > 0:
            entropy -= p * math.log2(p)

    # Max entropy for uniform distribution
    max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0

    # Convert to confidence (0 entropy = 1.0 confidence)
    if max_entropy == 0:
        return 1.0

    return 1.0 - (entropy / max_entropy)


def margin_based_confidence(
    top_score: float,
    second_score: float,
) -> float:
    """Calculate confidence from margin between top predictions."""
    margin = top_score - second_score
    # Sigmoid to convert margin to 0-1 confidence
    return 1.0 / (1.0 + math.exp(-5 * margin))


def agreement_based_confidence(
    predictions: List[Any],
) -> float:
    """Calculate confidence from agreement among multiple predictions."""
    if not predictions:
        return 0.0

    # Count unique predictions
    unique = set(str(p) for p in predictions)
    agreement_ratio = 1.0 - (len(unique) - 1) / len(predictions)

    return agreement_ratio


def calibrate_confidence(
    raw_score: float,
    calibration: Optional[ConfidenceCalibration] = None,
) -> float:
    """Apply calibration to a raw confidence score."""
    if calibration is None:
        return raw_score

    return calibration.calibrate_score(raw_score)
