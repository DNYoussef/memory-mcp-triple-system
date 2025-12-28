"""
Error Attribution - Refactored Facade for Error Classification

Classifies failures as context bugs vs model bugs.
Part of PREMORTEM Risk #13 mitigation.

REFACTORED: Extracted into focused components for high cohesion:
- ErrorClassifier: Classification logic
- DetectionRules: Pattern-based detection
- ErrorStatisticsService: Statistics aggregation

This class now acts as a facade coordinating the components.

NASA Rule 10 Compliant: All functions <=60 LOC
Cohesion: HIGH (facade pattern - coordinates focused components)
"""

from typing import Dict, Any, Optional
from loguru import logger

from .error_classifier import ErrorClassifier, ErrorType, ContextBugType
from .detection_rules import DetectionRules
from .error_statistics import ErrorStatisticsService


class ErrorAttribution:
    """
    Facade for error classification and statistics.

    Coordinates focused components:
    - ErrorClassifier: Classification logic
    - DetectionRules: Pattern detection
    - ErrorStatisticsService: Statistics

    Usage:
        attribution = ErrorAttribution(db=conn)
        error_type = attribution.classify_failure(trace)
        stats = attribution.get_statistics(days=30)
    """

    def __init__(self, db: Optional[Any] = None):
        """
        Initialize Error Attribution facade.

        Args:
            db: Database connection for statistics
        """
        self.db = db
        self.rules = DetectionRules()
        self.classifier = ErrorClassifier(detection_rules=self.rules)
        self.statistics = ErrorStatisticsService(db=db)

        logger.info("ErrorAttribution initialized")

    def classify_failure(self, trace: Any) -> ErrorType:
        """
        Classify failure based on query trace.

        Args:
            trace: QueryTrace instance

        Returns:
            ErrorType enum
        """
        return self.classifier.classify(trace)

    def classify_context_bug(self, trace: Any) -> ContextBugType:
        """
        Classify context bug subcategory.

        Args:
            trace: QueryTrace instance

        Returns:
            ContextBugType enum
        """
        return self.classifier.classify_context_bug(trace)

    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Aggregate error statistics.

        Args:
            days: Number of days to aggregate

        Returns:
            Statistics dictionary
        """
        return self.statistics.get_statistics(days)

    # Backward compatibility - expose detection rules
    def _is_wrong_store(self, trace: Any) -> bool:
        return self.rules.is_wrong_store(trace)

    def _is_wrong_mode(self, trace: Any) -> bool:
        return self.rules.is_wrong_mode(trace)

    def _is_wrong_lifecycle(self, trace: Any) -> bool:
        return self.rules.is_wrong_lifecycle(trace)

    def _empty_stats(self) -> Dict[str, Any]:
        return self.statistics._empty_stats()
