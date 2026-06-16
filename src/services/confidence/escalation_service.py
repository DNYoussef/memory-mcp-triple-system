"""Human Escalation Service for CAPTURE-003.

Manages escalation of low-confidence classifications to human review.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import uuid

from src.integrations.confidence_scoring_schema import (
    ClassificationResult,
    EscalationRequest,
    EscalationReason,
    EscalationStatus,
    ESCALATION_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass
class EscalationQueueConfig:
    """Configuration for escalation queue."""

    max_pending: int = 1000
    auto_resolve_threshold: float = 0.8
    stale_after_hours: int = 24
    max_priority: int = 10
    enable_auto_resolution: bool = True
    resolution_callbacks: List[str] = field(default_factory=list)


class EscalationService:
    """Service for managing human escalation of classifications.

    Handles creating, queuing, reviewing, and resolving escalations.
    """

    def __init__(self, config: Optional[EscalationQueueConfig] = None):
        """Initialize escalation service.

        Args:
            config: Service configuration
        """
        self.config = config or EscalationQueueConfig()
        self._pending: Dict[str, EscalationRequest] = {}
        self._resolved: Dict[str, EscalationRequest] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._stats = {
            "total_created": 0,
            "total_resolved": 0,
            "total_dismissed": 0,
            "total_auto_resolved": 0,
            "by_reason": defaultdict(int),
            "by_priority": defaultdict(int),
            "avg_resolution_time_hours": 0.0,
        }

    def create_escalation(
        self,
        result: ClassificationResult,
        reason: EscalationReason,
        context: Optional[Dict[str, Any]] = None,
    ) -> EscalationRequest:
        """Create a new escalation request.

        Args:
            result: Classification result needing review
            reason: Reason for escalation
            context: Additional context for reviewer

        Returns:
            Created escalation request
        """
        # Check queue limit
        if len(self._pending) >= self.config.max_pending:
            self._evict_lowest_priority()

        escalation = EscalationRequest.create(
            classification_result=result,
            reason=reason,
            context=context,
        )

        self._pending[escalation.request_id] = escalation

        # Update stats
        self._stats["total_created"] += 1
        self._stats["by_reason"][reason.value] += 1
        self._stats["by_priority"][escalation.priority] += 1

        logger.info(
            f"Created escalation {escalation.request_id} "
            f"(reason: {reason.value}, priority: {escalation.priority})"
        )

        return escalation

    def should_escalate(
        self,
        result: ClassificationResult,
        threshold: Optional[float] = None,
    ) -> bool:
        """Check if a classification result should be escalated.

        Args:
            result: Classification result to check
            threshold: Optional custom threshold

        Returns:
            True if escalation is needed
        """
        threshold = threshold or ESCALATION_THRESHOLD
        return result.confidence.needs_escalation(threshold)

    def get_escalation_reason(
        self,
        result: ClassificationResult,
    ) -> EscalationReason:
        """Determine the appropriate escalation reason.

        Args:
            result: Classification result

        Returns:
            Appropriate escalation reason
        """
        if result.confidence.score < 0.3:
            return EscalationReason.LOW_CONFIDENCE

        if result.is_ambiguous():
            return EscalationReason.AMBIGUOUS_CLASSIFICATION

        if result.confidence.score < 0.5:
            return EscalationReason.MODEL_UNCERTAINTY

        return EscalationReason.EDGE_CASE

    def maybe_escalate(
        self,
        result: ClassificationResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[EscalationRequest]:
        """Create escalation if needed based on confidence score.

        Args:
            result: Classification result
            context: Additional context

        Returns:
            Created escalation or None if not needed
        """
        if not self.should_escalate(result):
            return None

        reason = self.get_escalation_reason(result)
        return self.create_escalation(result, reason, context)

    def resolve(
        self,
        request_id: str,
        resolved_value: Any,
        resolved_by: str,
        notes: str = "",
    ) -> Optional[EscalationRequest]:
        """Resolve an escalation with a human decision.

        Args:
            request_id: Escalation request ID
            resolved_value: The correct value
            resolved_by: Resolver identifier
            notes: Resolution notes

        Returns:
            Resolved escalation or None if not found
        """
        if request_id not in self._pending:
            logger.warning(f"Escalation not found: {request_id}")
            return None

        escalation = self._pending.pop(request_id)
        escalation.resolve(resolved_value, resolved_by, notes)
        self._resolved[request_id] = escalation

        # Update stats
        self._stats["total_resolved"] += 1
        self._update_avg_resolution_time(escalation)

        # Trigger callbacks
        self._trigger_callbacks("resolved", escalation)

        logger.info(f"Resolved escalation {request_id} by {resolved_by}")

        return escalation

    def dismiss(
        self,
        request_id: str,
        notes: str = "",
    ) -> Optional[EscalationRequest]:
        """Dismiss an escalation without resolution.

        Args:
            request_id: Escalation request ID
            notes: Dismissal notes

        Returns:
            Dismissed escalation or None if not found
        """
        if request_id not in self._pending:
            logger.warning(f"Escalation not found: {request_id}")
            return None

        escalation = self._pending.pop(request_id)
        escalation.dismiss(notes)
        self._resolved[request_id] = escalation

        # Update stats
        self._stats["total_dismissed"] += 1

        # Trigger callbacks
        self._trigger_callbacks("dismissed", escalation)

        logger.info(f"Dismissed escalation {request_id}")

        return escalation

    def auto_resolve(
        self,
        request_id: str,
        resolved_value: Any,
    ) -> Optional[EscalationRequest]:
        """Auto-resolve an escalation based on new information.

        Args:
            request_id: Escalation request ID
            resolved_value: Auto-resolved value

        Returns:
            Resolved escalation or None
        """
        if not self.config.enable_auto_resolution:
            return None

        if request_id not in self._pending:
            return None

        escalation = self._pending.pop(request_id)
        escalation.status = EscalationStatus.AUTO_RESOLVED
        escalation.resolved_at = datetime.now(timezone.utc)
        escalation.resolved_value = resolved_value
        escalation.resolved_by = "auto_resolution"
        escalation.resolution_notes = "Automatically resolved by system"

        self._resolved[request_id] = escalation

        # Update stats
        self._stats["total_auto_resolved"] += 1

        # Trigger callbacks
        self._trigger_callbacks("auto_resolved", escalation)

        logger.info(f"Auto-resolved escalation {request_id}")

        return escalation

    def get_pending(
        self,
        priority_min: int = 0,
        reason: Optional[EscalationReason] = None,
        limit: int = 50,
    ) -> List[EscalationRequest]:
        """Get pending escalations.

        Args:
            priority_min: Minimum priority filter
            reason: Optional reason filter
            limit: Maximum results

        Returns:
            List of pending escalations
        """
        pending = list(self._pending.values())

        # Filter by priority
        pending = [e for e in pending if e.priority >= priority_min]

        # Filter by reason
        if reason:
            pending = [e for e in pending if e.reason == reason]

        # Sort by priority (descending) then by created_at (ascending)
        pending.sort(key=lambda e: (-e.priority, e.created_at))

        return pending[:limit]

    def get_next_for_review(self) -> Optional[EscalationRequest]:
        """Get the next escalation for human review.

        Returns the highest priority pending escalation.

        Returns:
            Next escalation or None if queue is empty
        """
        if not self._pending:
            return None

        # Get highest priority
        pending = sorted(
            self._pending.values(), key=lambda e: (-e.priority, e.created_at)
        )

        if pending:
            escalation = pending[0]
            escalation.status = EscalationStatus.IN_REVIEW
            return escalation

        return None

    def get_escalation(self, request_id: str) -> Optional[EscalationRequest]:
        """Get an escalation by ID.

        Args:
            request_id: Escalation request ID

        Returns:
            Escalation or None if not found
        """
        return self._pending.get(request_id) or self._resolved.get(request_id)

    def get_resolved(
        self,
        limit: int = 100,
    ) -> List[EscalationRequest]:
        """Get recently resolved escalations.

        Args:
            limit: Maximum results

        Returns:
            List of resolved escalations
        """
        resolved = sorted(
            self._resolved.values(),
            key=lambda e: e.resolved_at or e.created_at,
            reverse=True,
        )
        return resolved[:limit]

    def get_stale_escalations(self) -> List[EscalationRequest]:
        """Get escalations that have been pending too long.

        Returns:
            List of stale escalations
        """
        now = datetime.now(timezone.utc)
        stale_cutoff = self.config.stale_after_hours * 3600

        stale = []
        for escalation in self._pending.values():
            age_seconds = (now - escalation.created_at).total_seconds()
            if age_seconds > stale_cutoff:
                stale.append(escalation)

        return stale

    def cleanup_stale(self) -> int:
        """Auto-dismiss stale escalations.

        Returns:
            Number of escalations dismissed
        """
        stale = self.get_stale_escalations()

        for escalation in stale:
            self.dismiss(
                escalation.request_id,
                notes=f"Auto-dismissed after {self.config.stale_after_hours} hours",
            )

        return len(stale)

    def register_callback(
        self,
        event: str,
        callback: Callable[[EscalationRequest], None],
    ) -> str:
        """Register a callback for escalation events.

        Args:
            event: Event type (resolved, dismissed, auto_resolved)
            callback: Callback function

        Returns:
            Callback ID
        """
        callback_id = str(uuid.uuid4())
        self._callbacks[f"{event}:{callback_id}"] = callback
        return callback_id

    def unregister_callback(self, callback_id: str) -> bool:
        """Unregister a callback.

        Args:
            callback_id: Callback ID to remove

        Returns:
            True if removed, False if not found
        """
        # Find and remove callback
        to_remove = None
        for key in self._callbacks:
            if callback_id in key:
                to_remove = key
                break

        if to_remove:
            del self._callbacks[to_remove]
            return True

        return False

    def _trigger_callbacks(
        self,
        event: str,
        escalation: EscalationRequest,
    ) -> None:
        """Trigger callbacks for an event.

        Args:
            event: Event type
            escalation: Escalation request
        """
        for key, callback in self._callbacks.items():
            if key.startswith(f"{event}:"):
                try:
                    callback(escalation)
                except Exception as e:
                    logger.error(f"Callback failed: {e}")

    def _evict_lowest_priority(self) -> None:
        """Evict lowest priority escalation when queue is full."""
        if not self._pending:
            return

        # Find lowest priority
        lowest = min(
            self._pending.values(),
            key=lambda e: (e.priority, -e.created_at.timestamp()),
        )

        self.dismiss(lowest.request_id, notes="Auto-dismissed due to queue limit")

    def _update_avg_resolution_time(
        self,
        escalation: EscalationRequest,
    ) -> None:
        """Update average resolution time statistic."""
        if escalation.resolved_at is None:
            return

        resolution_time = (
            escalation.resolved_at - escalation.created_at
        ).total_seconds() / 3600  # Convert to hours

        # Running average
        total_resolved = self._stats["total_resolved"]
        current_avg = self._stats["avg_resolution_time_hours"]

        new_avg = (
            current_avg * (total_resolved - 1) + resolution_time
        ) / total_resolved
        self._stats["avg_resolution_time_hours"] = new_avg

    def get_stats(self) -> Dict[str, Any]:
        """Get escalation statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "queue_size": len(self._pending),
            "resolved_count": len(self._resolved),
            "total_created": self._stats["total_created"],
            "total_resolved": self._stats["total_resolved"],
            "total_dismissed": self._stats["total_dismissed"],
            "total_auto_resolved": self._stats["total_auto_resolved"],
            "by_reason": dict(self._stats["by_reason"]),
            "by_priority": dict(self._stats["by_priority"]),
            "avg_resolution_time_hours": round(
                self._stats["avg_resolution_time_hours"], 2
            ),
            "resolution_rate": (
                self._stats["total_resolved"] / self._stats["total_created"]
                if self._stats["total_created"] > 0
                else 0.0
            ),
        }

    def clear_resolved(self) -> int:
        """Clear resolved escalations from memory.

        Returns:
            Number of escalations cleared
        """
        count = len(self._resolved)
        self._resolved.clear()
        return count

    def export_for_training(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Export resolved escalations for model training.

        Returns resolved escalations in a format suitable for
        retraining classification models.

        Args:
            limit: Maximum records to export

        Returns:
            List of training examples
        """
        training_data = []

        resolved = sorted(
            self._resolved.values(),
            key=lambda e: e.resolved_at or e.created_at,
            reverse=True,
        )[:limit]

        for escalation in resolved:
            if escalation.status != EscalationStatus.RESOLVED:
                continue

            training_data.append(
                {
                    "input_text": escalation.classification_result.input_text,
                    "original_value": escalation.classification_result.value,
                    "original_confidence": escalation.classification_result.confidence.score,
                    "corrected_value": escalation.resolved_value,
                    "classification_type": escalation.classification_result.classification_type.value,
                    "reason": escalation.reason.value,
                    "resolution_notes": escalation.resolution_notes,
                }
            )

        return training_data
