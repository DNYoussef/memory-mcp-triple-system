"""Outcome Measurement Service for IMPROVE-001.

Tracks outcomes from confidence scoring, user feedback, and agent execution.

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json

from src.services.improvement.outcome_schema import (
    Outcome,
    OutcomeType,
    OutcomeSource,
)

logger = logging.getLogger(__name__)


@dataclass
class OutcomeMeasurementConfig:
    """Configuration for outcome measurement."""

    max_outcomes_in_memory: int = 10000
    retention_days: int = 90
    batch_size: int = 100
    success_threshold: float = 0.7


class OutcomeMeasurementService:
    """Service for tracking and measuring outcomes.

    Captures outcomes from:
    - Confidence scoring results (CAPTURE-003)
    - User feedback (corrections, approvals)
    - Quality gate results
    - Agent execution results
    """

    def __init__(self, config: Optional[OutcomeMeasurementConfig] = None):
        """Initialize outcome measurement service.

        Args:
            config: Service configuration
        """
        self.config = config or OutcomeMeasurementConfig()

        # In-memory storage (would connect to Memory MCP in production)
        self._outcomes: Dict[str, Outcome] = {}
        self._by_category: Dict[str, List[str]] = defaultdict(list)
        self._by_type: Dict[str, List[str]] = defaultdict(list)
        self._by_session: Dict[str, List[str]] = defaultdict(list)

        # Statistics
        self._stats = {
            "total_recorded": 0,
            "by_type": defaultdict(int),
            "by_source": defaultdict(int),
            "by_category": defaultdict(int),
        }

    def record_outcome(self, outcome: Outcome) -> str:
        """Record a new outcome.

        Args:
            outcome: Outcome to record

        Returns:
            Outcome ID
        """
        # Store outcome
        self._outcomes[outcome.outcome_id] = outcome

        # Index by category
        if outcome.category:
            self._by_category[outcome.category].append(outcome.outcome_id)

        # Index by type
        self._by_type[outcome.outcome_type.value].append(outcome.outcome_id)

        # Index by session
        if outcome.session_id:
            self._by_session[outcome.session_id].append(outcome.outcome_id)

        # Update stats
        self._stats["total_recorded"] += 1
        self._stats["by_type"][outcome.outcome_type.value] += 1
        self._stats["by_source"][outcome.source.value] += 1
        if outcome.category:
            self._stats["by_category"][outcome.category] += 1

        # Cleanup if over limit
        if len(self._outcomes) > self.config.max_outcomes_in_memory:
            self._cleanup_old_outcomes()

        logger.debug(f"Recorded outcome {outcome.outcome_id}: {outcome.outcome_type.value}")

        return outcome.outcome_id

    def record_from_confidence_result(
        self,
        classification_result: Dict[str, Any],
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Record outcome from CAPTURE-003 confidence scoring result.

        Args:
            classification_result: Result from confidence coordinator
            session_id: Optional session ID
            task_id: Optional task ID

        Returns:
            Outcome ID
        """
        # Determine outcome type from confidence
        confidence = classification_result.get("confidence", {})
        score = confidence.get("score", 0.0)
        needs_escalation = confidence.get("needs_escalation", False)

        if needs_escalation:
            outcome_type = OutcomeType.ESCALATED
        elif score >= self.config.success_threshold:
            outcome_type = OutcomeType.SUCCESS
        elif score >= 0.4:
            outcome_type = OutcomeType.PARTIAL
        else:
            outcome_type = OutcomeType.FAILURE

        outcome = Outcome(
            outcome_type=outcome_type,
            source=OutcomeSource.CONFIDENCE_SCORING,
            session_id=session_id,
            task_id=task_id,
            input_text=classification_result.get("input_text", ""),
            output_text=str(classification_result.get("value", "")),
            confidence_score=score,
            category=classification_result.get("classification_type", ""),
            metadata={
                "confidence_level": confidence.get("level", ""),
                "alternatives": classification_result.get("alternatives", []),
                "components": classification_result.get("confidence_components", {}),
            },
        )

        return self.record_outcome(outcome)

    def record_user_feedback(
        self,
        input_text: str,
        output_text: str,
        feedback_type: str,
        correct_output: Optional[str] = None,
        category: str = "",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record user feedback as outcome.

        Args:
            input_text: Original input
            output_text: System output
            feedback_type: "correction", "approval", or "rejection"
            correct_output: Correct output if correction
            category: Category (e.g., "mode_detection")
            session_id: Session ID
            metadata: Additional metadata

        Returns:
            Outcome ID
        """
        type_map = {
            "correction": OutcomeType.CORRECTION,
            "approval": OutcomeType.APPROVAL,
            "rejection": OutcomeType.REJECTION,
        }

        outcome_type = type_map.get(feedback_type, OutcomeType.FAILURE)

        outcome = Outcome(
            outcome_type=outcome_type,
            source=OutcomeSource.USER_FEEDBACK,
            session_id=session_id,
            input_text=input_text,
            output_text=output_text,
            expected_output=correct_output,
            category=category,
            metadata=metadata or {},
        )

        return self.record_outcome(outcome)

    def record_quality_gate_result(
        self,
        gate_result: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> str:
        """Record quality gate result as outcome.

        Args:
            gate_result: Quality gate result
            session_id: Session ID

        Returns:
            Outcome ID
        """
        passed = gate_result.get("passed", False)
        score = gate_result.get("overall_score", 0.0)

        outcome_type = OutcomeType.SUCCESS if passed else OutcomeType.FAILURE

        outcome = Outcome(
            outcome_type=outcome_type,
            source=OutcomeSource.QUALITY_GATE,
            session_id=session_id,
            confidence_score=score,
            category="quality_gate",
            subcategory=gate_result.get("gate_name", ""),
            metadata={
                "gate_id": gate_result.get("gate_id", ""),
                "checks": gate_result.get("checks", []),
                "failed_checks": gate_result.get("failed_checks", []),
            },
        )

        return self.record_outcome(outcome)

    def get_outcome(self, outcome_id: str) -> Optional[Outcome]:
        """Get outcome by ID.

        Args:
            outcome_id: Outcome ID

        Returns:
            Outcome or None
        """
        return self._outcomes.get(outcome_id)

    def get_outcomes_by_category(
        self,
        category: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Outcome]:
        """Get outcomes for a specific category.

        Args:
            category: Category to filter by
            limit: Maximum results
            since: Only outcomes after this time

        Returns:
            List of outcomes
        """
        outcome_ids = self._by_category.get(category, [])
        return self._get_filtered_outcomes(outcome_ids, limit, since)

    def get_outcomes_by_type(
        self,
        outcome_type: OutcomeType,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Outcome]:
        """Get outcomes of a specific type.

        Args:
            outcome_type: Type to filter by
            limit: Maximum results
            since: Only outcomes after this time

        Returns:
            List of outcomes
        """
        outcome_ids = self._by_type.get(outcome_type.value, [])
        return self._get_filtered_outcomes(outcome_ids, limit, since)

    def _get_filtered_outcomes(
        self,
        outcome_ids: List[str],
        limit: int,
        since: Optional[datetime],
    ) -> List[Outcome]:
        """Scan indexed outcomes newest-first, applying filters before limit."""
        outcomes = []

        for oid in reversed(outcome_ids):
            outcome = self._outcomes.get(oid)
            if not outcome:
                continue

            if since:
                outcome_time = datetime.fromisoformat(outcome.timestamp.replace("Z", "+00:00"))
                if outcome_time < since:
                    continue

            outcomes.append(outcome)
            if len(outcomes) >= limit:
                break

        return outcomes

    def get_session_outcomes(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[Outcome]:
        """Get all outcomes for a session.

        Args:
            session_id: Session ID
            limit: Maximum results

        Returns:
            List of outcomes
        """
        outcome_ids = self._by_session.get(session_id, [])
        outcomes = []

        for oid in outcome_ids[-limit:]:
            outcome = self._outcomes.get(oid)
            if outcome:
                outcomes.append(outcome)

        return outcomes

    def get_recent_outcomes(
        self,
        limit: int = 100,
        hours: int = 24,
    ) -> List[Outcome]:
        """Get recent outcomes.

        Args:
            limit: Maximum results
            hours: Time window in hours

        Returns:
            List of recent outcomes
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        outcomes = []

        for outcome in sorted(
            self._outcomes.values(),
            key=lambda o: o.timestamp,
            reverse=True,
        ):
            outcome_time = datetime.fromisoformat(outcome.timestamp.replace("Z", "+00:00"))
            if outcome_time < cutoff:
                break

            outcomes.append(outcome)
            if len(outcomes) >= limit:
                break

        return outcomes

    def calculate_metrics(
        self,
        category: Optional[str] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Calculate metrics for outcomes.

        Args:
            category: Optional category filter
            hours: Time window in hours

        Returns:
            Metrics dictionary
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Filter outcomes
        if category:
            outcome_ids = self._by_category.get(category, [])
            outcomes = [self._outcomes.get(oid) for oid in outcome_ids]
            outcomes = [o for o in outcomes if o]
        else:
            outcomes = list(self._outcomes.values())

        # Filter by time
        recent = []
        for o in outcomes:
            outcome_time = datetime.fromisoformat(o.timestamp.replace("Z", "+00:00"))
            if outcome_time >= cutoff:
                recent.append(o)

        if not recent:
            return {
                "total": 0,
                "success_rate": 0.0,
                "average_confidence": 0.0,
                "escalation_rate": 0.0,
                "correction_rate": 0.0,
            }

        # Calculate metrics
        total = len(recent)
        successes = sum(1 for o in recent if o.outcome_type == OutcomeType.SUCCESS)
        escalations = sum(1 for o in recent if o.outcome_type == OutcomeType.ESCALATED)
        corrections = sum(1 for o in recent if o.outcome_type == OutcomeType.CORRECTION)
        avg_confidence = sum(o.confidence_score for o in recent) / total

        # Type distribution
        type_dist = defaultdict(int)
        for o in recent:
            type_dist[o.outcome_type.value] += 1

        return {
            "total": total,
            "success_rate": round(successes / total, 4) if total > 0 else 0.0,
            "average_confidence": round(avg_confidence, 4),
            "escalation_rate": round(escalations / total, 4) if total > 0 else 0.0,
            "correction_rate": round(corrections / total, 4) if total > 0 else 0.0,
            "type_distribution": dict(type_dist),
            "time_window_hours": hours,
            "category": category,
        }

    def export_for_analysis(
        self,
        limit: int = 1000,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Export outcomes for pattern analysis.

        Args:
            limit: Maximum outcomes to export
            category: Optional category filter

        Returns:
            List of outcome dictionaries
        """
        if category:
            outcome_ids = self._by_category.get(category, [])
            outcomes = [self._outcomes.get(oid) for oid in outcome_ids[-limit:]]
            outcomes = [o for o in outcomes if o]
        else:
            outcomes = sorted(
                self._outcomes.values(),
                key=lambda o: o.timestamp,
                reverse=True,
            )[:limit]

        return [o.to_dict() for o in outcomes]

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_recorded": self._stats["total_recorded"],
            "current_in_memory": len(self._outcomes),
            "by_type": dict(self._stats["by_type"]),
            "by_source": dict(self._stats["by_source"]),
            "by_category": dict(self._stats["by_category"]),
            "categories_tracked": list(self._by_category.keys()),
            "sessions_tracked": len(self._by_session),
        }

    def _cleanup_old_outcomes(self) -> int:
        """Remove old outcomes to stay under memory limit.

        Returns:
            Number of outcomes removed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)
        removed = 0

        to_remove = []
        for oid, outcome in self._outcomes.items():
            outcome_time = datetime.fromisoformat(outcome.timestamp.replace("Z", "+00:00"))
            if outcome_time < cutoff:
                to_remove.append(oid)

        for oid in to_remove:
            del self._outcomes[oid]
            removed += 1

        # Also trim indexes
        for category in self._by_category:
            self._by_category[category] = [
                oid for oid in self._by_category[category]
                if oid in self._outcomes
            ]

        for type_val in self._by_type:
            self._by_type[type_val] = [
                oid for oid in self._by_type[type_val]
                if oid in self._outcomes
            ]

        logger.info(f"Cleaned up {removed} old outcomes")
        return removed

    def clear(self) -> None:
        """Clear all outcomes."""
        self._outcomes.clear()
        self._by_category.clear()
        self._by_type.clear()
        self._by_session.clear()
