"""
Error Classifier - Focused component for error classification logic.

Extracted from ErrorAttribution to improve cohesion.
Single Responsibility: Classify errors into categories.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Optional
from enum import Enum
from loguru import logger


class ErrorType(Enum):
    """Error classification categories."""
    CONTEXT_BUG = "context_bug"
    MODEL_BUG = "model_bug"
    SYSTEM_ERROR = "system_error"


class ContextBugType(Enum):
    """Context bug subcategories."""
    WRONG_STORE_QUERIED = "wrong_store_queried"
    WRONG_MODE_DETECTED = "wrong_mode_detected"
    WRONG_LIFECYCLE_FILTER = "wrong_lifecycle_filter"
    RETRIEVAL_RANKING_ERROR = "retrieval_ranking_error"


class ErrorClassifier:
    """
    Classifies errors based on query trace analysis.

    Single Responsibility: Error classification logic.
    Cohesion: HIGH - all methods relate to classification.
    """

    def __init__(self, detection_rules: Optional["DetectionRules"] = None):
        """
        Initialize classifier with detection rules.

        Args:
            detection_rules: Rules for detecting error types
        """
        from .detection_rules import DetectionRules
        self.rules = detection_rules or DetectionRules()

    def classify(self, trace) -> ErrorType:
        """
        Classify failure based on query trace.

        Args:
            trace: QueryTrace instance

        Returns:
            ErrorType enum
        """
        # Check for pre-classified error
        if hasattr(trace, "error_type") and trace.error_type:
            try:
                return ErrorType(trace.error_type)
            except ValueError:
                logger.debug("Unknown error_type on trace: %s", trace.error_type)

        # Check for context bugs
        if self.rules.is_wrong_store(trace):
            return ErrorType.CONTEXT_BUG

        if self.rules.is_wrong_mode(trace):
            return ErrorType.CONTEXT_BUG

        if self.rules.is_wrong_lifecycle(trace):
            return ErrorType.CONTEXT_BUG

        # Check for system errors
        if self._is_system_error(trace):
            return ErrorType.SYSTEM_ERROR

        # Default to model bug
        return ErrorType.MODEL_BUG

    def classify_context_bug(self, trace) -> ContextBugType:
        """
        Classify context bug subcategory.

        Args:
            trace: QueryTrace instance

        Returns:
            ContextBugType enum
        """
        if self.rules.is_wrong_store(trace):
            return ContextBugType.WRONG_STORE_QUERIED

        if self.rules.is_wrong_mode(trace):
            return ContextBugType.WRONG_MODE_DETECTED

        if self.rules.is_wrong_lifecycle(trace):
            return ContextBugType.WRONG_LIFECYCLE_FILTER

        return ContextBugType.RETRIEVAL_RANKING_ERROR

    def _is_system_error(self, trace) -> bool:
        """Check if trace indicates system error."""
        if hasattr(trace, "error") and trace.error:
            error_lower = str(trace.error).lower()
            return "timeout" in error_lower or "exception" in error_lower
        return False
