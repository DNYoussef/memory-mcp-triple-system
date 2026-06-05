"""Failure Pattern Analyzer for IMPROVE-003.

Analyzes failure patterns to identify fine-tuning opportunities.

WHO: finetune:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-003)
"""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from src.services.finetune.finetune_schema import (
    FailureRecord,
    FailureCategory,
)

logger = logging.getLogger(__name__)


class FailurePatternAnalyzer:
    """Analyzes failure patterns for fine-tuning opportunities.

    Tracks:
    - Error type frequency
    - Category distribution
    - Temporal patterns
    - Input characteristics
    """

    def __init__(self):
        """Initialize failure pattern analyzer."""
        self._failures: List[FailureRecord] = []
        self._pattern_cache: Dict[str, Any] = {}

    def record_failure(
        self,
        category: str,
        error_type: str,
        error_message: str,
        input_text: str,
        expected_output: Optional[str] = None,
        actual_output: Optional[str] = None,
        confidence: float = 0.0,
        context: Optional[Dict[str, Any]] = None,
        was_corrected: bool = False,
        correction: Optional[str] = None,
    ) -> FailureRecord:
        """Record a failure for analysis.

        Args:
            category: Failure category
            error_type: Type of error
            error_message: Error message
            input_text: Input that caused failure
            expected_output: What output was expected
            actual_output: What was actually produced
            confidence: Confidence at time of failure
            context: Additional context
            was_corrected: Whether user corrected
            correction: The correction if any

        Returns:
            Recorded failure
        """
        # Parse category
        try:
            cat = FailureCategory(category.lower())
        except ValueError:
            cat = FailureCategory.UNKNOWN

        failure = FailureRecord(
            category=cat,
            error_type=error_type,
            error_message=error_message,
            input_text=input_text,
            expected_output=expected_output,
            actual_output=actual_output,
            confidence=confidence,
            context=context or {},
            was_corrected=was_corrected,
            correction=correction,
        )

        self._failures.append(failure)
        self._invalidate_cache()

        return failure

    def analyze_patterns(
        self,
        days: int = 7,
        min_occurrences: int = 2,
    ) -> Dict[str, Any]:
        """Analyze failure patterns.

        Args:
            days: Days to analyze
            min_occurrences: Minimum occurrences to report

        Returns:
            Pattern analysis results
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent_failures = [
            f
            for f in self._failures
            if datetime.fromisoformat(f.timestamp.replace("Z", "+00:00")) >= cutoff
        ]

        if not recent_failures:
            return {
                "total_failures": 0,
                "by_category": {},
                "by_error_type": {},
                "temporal_pattern": {},
                "input_patterns": {},
                "correction_rate": 0.0,
            }

        # Category distribution
        by_category = Counter(f.category.value for f in recent_failures)

        # Error type distribution
        by_error_type = Counter(f.error_type for f in recent_failures if f.error_type)

        # Temporal pattern (failures per day)
        temporal = defaultdict(int)
        for f in recent_failures:
            day = f.timestamp[:10]
            temporal[day] += 1

        # Input patterns
        input_patterns = self._analyze_input_patterns(recent_failures)

        # Correction rate
        corrected = sum(1 for f in recent_failures if f.was_corrected)
        correction_rate = corrected / len(recent_failures) if recent_failures else 0.0

        # High-impact categories (frequency * severity proxy)
        high_impact = []
        for cat, count in by_category.items():
            if count >= min_occurrences:
                # Severity proxy: lower confidence = higher impact
                cat_failures = [f for f in recent_failures if f.category.value == cat]
                avg_conf = sum(f.confidence for f in cat_failures) / len(cat_failures)
                impact = count * (1 - avg_conf)
                high_impact.append(
                    {
                        "category": cat,
                        "count": count,
                        "avg_confidence": avg_conf,
                        "impact_score": impact,
                    }
                )

        high_impact.sort(key=lambda x: x["impact_score"], reverse=True)

        return {
            "total_failures": len(recent_failures),
            "by_category": dict(by_category),
            "by_error_type": dict(by_error_type),
            "temporal_pattern": dict(temporal),
            "input_patterns": input_patterns,
            "correction_rate": correction_rate,
            "high_impact_categories": high_impact[:5],
        }

    def _analyze_input_patterns(
        self,
        failures: List[FailureRecord],
    ) -> Dict[str, Any]:
        """Analyze patterns in failure inputs.

        Args:
            failures: Failures to analyze

        Returns:
            Input pattern analysis
        """
        patterns = {
            "avg_length": 0.0,
            "common_tokens": [],
            "length_distribution": {"short": 0, "medium": 0, "long": 0},
            "special_char_failures": 0,
        }

        if not failures:
            return patterns

        inputs = [f.input_text for f in failures if f.input_text]

        if not inputs:
            return patterns

        # Average length
        lengths = [len(i) for i in inputs]
        patterns["avg_length"] = sum(lengths) / len(lengths)

        # Length distribution
        for length in lengths:
            if length < 100:
                patterns["length_distribution"]["short"] += 1
            elif length < 500:
                patterns["length_distribution"]["medium"] += 1
            else:
                patterns["length_distribution"]["long"] += 1

        # Common tokens (simple word frequency)
        all_words = []
        for inp in inputs:
            words = re.findall(r"\b\w+\b", inp.lower())
            all_words.extend(words)

        word_counts = Counter(all_words)
        # Filter out common stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "to", "of", "and"}
        patterns["common_tokens"] = [
            {"token": word, "count": count}
            for word, count in word_counts.most_common(20)
            if word not in stopwords and len(word) > 2
        ][:10]

        # Special character failures
        special_chars = re.compile(r"[^\w\s.,!?-]")
        patterns["special_char_failures"] = sum(
            1 for inp in inputs if special_chars.search(inp)
        )

        return patterns

    def get_failures_by_category(
        self,
        category: FailureCategory,
        days: int = 7,
    ) -> List[FailureRecord]:
        """Get failures for a specific category.

        Args:
            category: Category to filter
            days: Days to look back

        Returns:
            List of failures
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        return [
            f
            for f in self._failures
            if f.category == category
            and datetime.fromisoformat(f.timestamp.replace("Z", "+00:00")) >= cutoff
        ]

    def get_corrected_failures(self, days: int = 7) -> List[FailureRecord]:
        """Get failures that were corrected by users.

        Args:
            days: Days to look back

        Returns:
            List of corrected failures
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        return [
            f
            for f in self._failures
            if f.was_corrected
            and datetime.fromisoformat(f.timestamp.replace("Z", "+00:00")) >= cutoff
        ]

    def identify_error_clusters(
        self,
        min_size: int = 3,
    ) -> List[Dict[str, Any]]:
        """Identify clusters of similar errors.

        Args:
            min_size: Minimum cluster size

        Returns:
            List of error clusters
        """
        # Group by error type and category
        clusters: Dict[Tuple[str, str], List[FailureRecord]] = defaultdict(list)

        for failure in self._failures:
            key = (failure.category.value, failure.error_type)
            clusters[key].append(failure)

        result = []
        for (category, error_type), failures in clusters.items():
            if len(failures) >= min_size:
                result.append(
                    {
                        "category": category,
                        "error_type": error_type,
                        "count": len(failures),
                        "failure_ids": [f.failure_id for f in failures],
                        "first_seen": min(f.timestamp for f in failures),
                        "last_seen": max(f.timestamp for f in failures),
                    }
                )

        return sorted(result, key=lambda x: x["count"], reverse=True)

    def _invalidate_cache(self) -> None:
        """Invalidate pattern cache."""
        self._pattern_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            "total_failures": len(self._failures),
            "categories_seen": len(set(f.category for f in self._failures)),
            "corrected_count": sum(1 for f in self._failures if f.was_corrected),
        }

    def clear(self) -> None:
        """Clear all failure records."""
        self._failures.clear()
        self._pattern_cache.clear()
