"""Confidence Coordinator for CAPTURE-003.

Coordinates all confidence scoring components into a unified interface.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.integrations.confidence_scoring_schema import (
    ClassificationResult,
    ClassificationType,
    EscalationRequest,
    EscalationReason,
    QualityGateScore,
    ConfidenceStats,
    ESCALATION_THRESHOLD,
)
from src.services.confidence.mode_detector import ModeDetectionScorer
from src.services.confidence.entity_extractor import EntityExtractionScorer
from src.services.confidence.quality_gate import (
    QualityGateAggregator,
    GateType,
)
from src.services.confidence.tag_scorer import TagAssignmentScorer
from src.services.confidence.escalation_service import EscalationService

logger = logging.getLogger(__name__)


@dataclass
class CoordinatorConfig:
    """Configuration for confidence coordinator."""

    escalation_threshold: float = ESCALATION_THRESHOLD
    enable_auto_escalation: bool = True
    enable_quality_gates: bool = True
    track_stats: bool = True


@dataclass
class ScoringResult:
    """Result of a comprehensive scoring operation."""

    mode: ClassificationResult
    entities: ClassificationResult
    tags: ClassificationResult
    quality_gate: QualityGateScore
    escalation: Optional[EscalationRequest] = None
    overall_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "mode": self.mode.to_dict(),
            "entities": self.entities.to_dict(),
            "tags": self.tags.to_dict(),
            "quality_gate": self.quality_gate.to_dict(),
            "escalation": self.escalation.to_dict() if self.escalation else None,
            "overall_confidence": round(self.overall_confidence, 4),
            "needs_human_review": self.escalation is not None,
        }


class ConfidenceCoordinator:
    """Coordinates confidence scoring across all classification types.

    Provides a unified interface to:
    - Mode detection
    - Entity extraction
    - Tag assignment
    - Quality gate aggregation
    - Human escalation
    """

    def __init__(self, config: Optional[CoordinatorConfig] = None):
        """Initialize confidence coordinator.

        Args:
            config: Coordinator configuration
        """
        self.config = config or CoordinatorConfig()

        # Initialize components
        self.mode_scorer = ModeDetectionScorer()
        self.entity_scorer = EntityExtractionScorer()
        self.tag_scorer = TagAssignmentScorer()
        self.escalation_service = EscalationService()

        # Statistics
        self._stats = ConfidenceStats()

    def score_text(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoringResult:
        """Perform comprehensive confidence scoring on text.

        Runs all scorers and aggregates results through quality gate.

        Args:
            text: Input text to score
            context: Optional context (timestamps, user info, etc.)

        Returns:
            Comprehensive scoring result
        """
        context = context or {}

        # 1. Mode detection
        mode_result = self.mode_scorer.detect_mode(text)

        # 2. Entity extraction
        entity_result = self.entity_scorer.extract_with_result(text)

        # 3. Tag assignment
        tag_result = self.tag_scorer.assign_tags_with_result(text, context)

        # 4. Quality gate aggregation
        quality_gate = self._run_quality_gate(
            mode_result, entity_result, tag_result
        )

        # Calculate overall confidence
        overall = self._calculate_overall_confidence(
            mode_result, entity_result, tag_result
        )

        # 5. Check for escalation
        escalation = None
        if self.config.enable_auto_escalation:
            escalation = self._check_escalation(
                mode_result, entity_result, tag_result, quality_gate, context
            )

        # Update stats
        if self.config.track_stats:
            self._update_stats(mode_result, entity_result, tag_result, quality_gate)

        return ScoringResult(
            mode=mode_result,
            entities=entity_result,
            tags=tag_result,
            quality_gate=quality_gate,
            escalation=escalation,
            overall_confidence=overall,
        )

    def score_mode(self, text: str) -> ClassificationResult:
        """Score mode detection only.

        Args:
            text: Input text

        Returns:
            Mode classification result
        """
        result = self.mode_scorer.detect_mode(text)

        if self.config.track_stats:
            self._stats.total_classifications += 1
            self._stats.by_type[ClassificationType.MODE_DETECTION.value] = (
                self._stats.by_type.get(ClassificationType.MODE_DETECTION.value, 0) + 1
            )

        return result

    def score_entities(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
    ) -> ClassificationResult:
        """Score entity extraction only.

        Args:
            text: Input text
            entity_types: Optional types to extract

        Returns:
            Entity extraction result
        """
        result = self.entity_scorer.extract_with_result(text, entity_types)

        if self.config.track_stats:
            self._stats.total_classifications += 1
            self._stats.by_type[ClassificationType.ENTITY_EXTRACTION.value] = (
                self._stats.by_type.get(ClassificationType.ENTITY_EXTRACTION.value, 0) + 1
            )

        return result

    def score_tags(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ClassificationResult:
        """Score tag assignment only.

        Args:
            content: Content to analyze
            context: Optional context

        Returns:
            Tag assignment result
        """
        result = self.tag_scorer.assign_tags_with_result(content, context)

        if self.config.track_stats:
            self._stats.total_classifications += 1
            self._stats.by_type[ClassificationType.TAG_ASSIGNMENT.value] = (
                self._stats.by_type.get(ClassificationType.TAG_ASSIGNMENT.value, 0) + 1
            )

        return result

    def run_quality_gate(
        self,
        results: List[ClassificationResult],
    ) -> QualityGateScore:
        """Run quality gate on multiple classification results.

        Args:
            results: Classification results to aggregate

        Returns:
            Quality gate score
        """
        gate = QualityGateAggregator()

        for result in results:
            gate.add_classification_result(result)

        return gate.evaluate()

    def create_escalation(
        self,
        result: ClassificationResult,
        reason: EscalationReason,
        context: Optional[Dict[str, Any]] = None,
    ) -> EscalationRequest:
        """Create an escalation request.

        Args:
            result: Classification result to escalate
            reason: Reason for escalation
            context: Additional context

        Returns:
            Created escalation request
        """
        escalation = self.escalation_service.create_escalation(
            result, reason, context
        )

        if self.config.track_stats:
            self._stats.escalations_created += 1
            self._stats.escalations_pending += 1

        return escalation

    def resolve_escalation(
        self,
        request_id: str,
        resolved_value: Any,
        resolved_by: str,
        notes: str = "",
    ) -> Optional[EscalationRequest]:
        """Resolve an escalation.

        Args:
            request_id: Escalation request ID
            resolved_value: Correct value
            resolved_by: Resolver identifier
            notes: Resolution notes

        Returns:
            Resolved escalation or None
        """
        escalation = self.escalation_service.resolve(
            request_id, resolved_value, resolved_by, notes
        )

        if escalation and self.config.track_stats:
            self._stats.escalations_resolved += 1
            self._stats.escalations_pending = max(0, self._stats.escalations_pending - 1)

        return escalation

    def get_pending_escalations(
        self,
        limit: int = 50,
    ) -> List[EscalationRequest]:
        """Get pending escalations for review.

        Args:
            limit: Maximum results

        Returns:
            List of pending escalations
        """
        return self.escalation_service.get_pending(limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics.

        Returns:
            Statistics from all components
        """
        return {
            "coordinator": self._stats.to_dict(),
            "mode_scorer": self.mode_scorer.get_stats(),
            "entity_scorer": self.entity_scorer.get_stats(),
            "tag_scorer": self.tag_scorer.get_stats(),
            "escalation_service": self.escalation_service.get_stats(),
        }

    def clear_caches(self) -> None:
        """Clear all scorer caches."""
        self.mode_scorer.clear_cache()
        self.entity_scorer.clear_cache()
        self.tag_scorer.clear_cache()

    def _run_quality_gate(
        self,
        mode_result: ClassificationResult,
        entity_result: ClassificationResult,
        tag_result: ClassificationResult,
    ) -> QualityGateScore:
        """Run quality gate on all results."""
        if not self.config.enable_quality_gates:
            # Return a passing gate if disabled
            return QualityGateScore(
                gate_id="",
                gate_name="disabled",
                passed=True,
                overall_score=1.0,
            )

        gate = QualityGateAggregator()

        # Add all results
        gate.add_classification_result(mode_result, GateType.MODE_DETECTION)
        gate.add_classification_result(entity_result, GateType.ENTITY_EXTRACTION)
        gate.add_classification_result(tag_result, GateType.TAG_ASSIGNMENT)

        result = gate.evaluate()

        # Update stats
        if self.config.track_stats:
            self._stats.quality_gates_run += 1
            if result.passed:
                self._stats.quality_gates_passed += 1
            else:
                self._stats.quality_gates_failed += 1

        return result

    def _calculate_overall_confidence(
        self,
        mode_result: ClassificationResult,
        entity_result: ClassificationResult,
        tag_result: ClassificationResult,
    ) -> float:
        """Calculate overall confidence from all results."""
        scores = [
            mode_result.confidence.score,
            entity_result.confidence.score,
            tag_result.confidence.score,
        ]

        # Geometric mean (penalizes low scores)
        product = 1.0
        for s in scores:
            product *= max(0.001, s)

        return product ** (1 / len(scores))

    def _check_escalation(
        self,
        mode_result: ClassificationResult,
        entity_result: ClassificationResult,
        tag_result: ClassificationResult,
        quality_gate: QualityGateScore,
        context: Dict[str, Any],
    ) -> Optional[EscalationRequest]:
        """Check if any result needs escalation."""
        threshold = self.config.escalation_threshold

        # Check mode detection
        if mode_result.confidence.score < threshold:
            reason = self.mode_scorer.get_escalation_reason(mode_result)
            if reason:
                return self.create_escalation(mode_result, reason, context)

        # Check entity extraction (only if very low)
        if entity_result.confidence.score < threshold * 0.8:
            return self.create_escalation(
                entity_result,
                EscalationReason.LOW_CONFIDENCE,
                context,
            )

        # Check tag assignment (use overall confidence)
        if tag_result.confidence.score < threshold:
            return self.create_escalation(
                tag_result,
                EscalationReason.AMBIGUOUS_CLASSIFICATION,
                context,
            )

        # Check quality gate
        if not quality_gate.passed:
            reason = EscalationReason.QUALITY_GATE_FAILED
            # Create escalation for the lowest scoring result
            min_result = min(
                [mode_result, entity_result, tag_result],
                key=lambda r: r.confidence.score
            )
            return self.create_escalation(min_result, reason, context)

        return None

    def _update_stats(
        self,
        mode_result: ClassificationResult,
        entity_result: ClassificationResult,
        tag_result: ClassificationResult,
        quality_gate: QualityGateScore,
    ) -> None:
        """Update statistics after scoring."""
        # Count classifications
        self._stats.total_classifications += 3

        # By type
        for result in [mode_result, entity_result, tag_result]:
            type_key = result.classification_type.value
            self._stats.by_type[type_key] = (
                self._stats.by_type.get(type_key, 0) + 1
            )

        # By level
        for result in [mode_result, entity_result, tag_result]:
            level_key = result.confidence.level.value
            self._stats.by_level[level_key] = (
                self._stats.by_level.get(level_key, 0) + 1
            )

        # Update average confidence (running average)
        all_scores = [
            mode_result.confidence.score,
            entity_result.confidence.score,
            tag_result.confidence.score,
        ]
        new_avg = sum(all_scores) / len(all_scores)

        total = self._stats.total_classifications
        current_avg = self._stats.average_confidence

        self._stats.average_confidence = (
            (current_avg * (total - 3) + new_avg * 3) / total
        )


# Singleton instance for convenience
_coordinator: Optional[ConfidenceCoordinator] = None


def get_coordinator() -> ConfidenceCoordinator:
    """Get the global confidence coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = ConfidenceCoordinator()
    return _coordinator


def initialize_coordinator(
    config: Optional[CoordinatorConfig] = None,
) -> ConfidenceCoordinator:
    """Initialize the global confidence coordinator.

    Args:
        config: Coordinator configuration

    Returns:
        Initialized coordinator
    """
    global _coordinator
    _coordinator = ConfidenceCoordinator(config)
    return _coordinator
