"""Pattern Detection Service for IMPROVE-001.

Analyzes outcomes to detect patterns that suggest rule updates.

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict
import statistics
import re

from src.services.improvement.outcome_schema import (
    Outcome,
    OutcomeType,
    Pattern,
)

logger = logging.getLogger(__name__)


# Pattern types
class PatternType:
    """Types of patterns to detect."""

    FAILURE_CLUSTER = "failure_cluster"        # Multiple failures in category
    CORRECTION_TREND = "correction_trend"      # Increasing corrections
    CONFIDENCE_DROP = "confidence_drop"        # Declining confidence
    ESCALATION_SPIKE = "escalation_spike"      # Too many escalations
    SUCCESS_DECLINE = "success_decline"        # Success rate dropping
    INPUT_PATTERN = "input_pattern"            # Common failing inputs
    CATEGORY_DRIFT = "category_drift"          # Category behavior changing


@dataclass
class PatternDetectionConfig:
    """Configuration for pattern detection."""

    min_sample_size: int = 10               # Minimum outcomes to detect pattern
    failure_threshold: float = 0.3          # Failure rate to flag
    correction_threshold: float = 0.2       # Correction rate to flag
    escalation_threshold: float = 0.25      # Escalation rate to flag
    confidence_drop_threshold: float = 0.1  # Confidence drop to flag
    pattern_confidence_min: float = 0.6     # Minimum pattern confidence
    lookback_hours: int = 168               # 7 days default


class PatternDetectionService:
    """Service for detecting patterns in outcomes.

    Analyzes outcomes to identify:
    - Failure clusters
    - Correction trends
    - Confidence degradation
    - Escalation spikes
    - Input patterns that cause issues
    """

    def __init__(self, config: Optional[PatternDetectionConfig] = None):
        """Initialize pattern detection service.

        Args:
            config: Service configuration
        """
        self.config = config or PatternDetectionConfig()

        # Detected patterns
        self._patterns: Dict[str, Pattern] = {}

        # Statistics
        self._stats = {
            "patterns_detected": 0,
            "by_type": defaultdict(int),
            "last_detection": None,
        }

    def detect_patterns(
        self,
        outcomes: List[Outcome],
        category: Optional[str] = None,
    ) -> List[Pattern]:
        """Detect all patterns in outcomes.

        Args:
            outcomes: List of outcomes to analyze
            category: Optional category filter

        Returns:
            List of detected patterns
        """
        if len(outcomes) < self.config.min_sample_size:
            logger.debug(f"Not enough outcomes for pattern detection: {len(outcomes)}")
            return []

        # Filter by category if specified
        if category:
            outcomes = [o for o in outcomes if o.category == category]

        patterns = []

        # Run all pattern detectors
        patterns.extend(self._detect_failure_clusters(outcomes))
        patterns.extend(self._detect_correction_trends(outcomes))
        patterns.extend(self._detect_confidence_drops(outcomes))
        patterns.extend(self._detect_escalation_spikes(outcomes))
        patterns.extend(self._detect_input_patterns(outcomes))
        patterns.extend(self._detect_category_drift(outcomes))

        # Filter by minimum confidence
        patterns = [
            p for p in patterns
            if p.confidence >= self.config.pattern_confidence_min
        ]

        # Store patterns
        for pattern in patterns:
            self._patterns[pattern.pattern_id] = pattern
            self._stats["patterns_detected"] += 1
            self._stats["by_type"][pattern.pattern_type] += 1

        self._stats["last_detection"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Detected {len(patterns)} patterns from {len(outcomes)} outcomes")

        return patterns

    def _detect_failure_clusters(self, outcomes: List[Outcome]) -> List[Pattern]:
        """Detect clusters of failures in specific categories.

        Args:
            outcomes: Outcomes to analyze

        Returns:
            List of failure cluster patterns
        """
        patterns = []

        # Group by category
        by_category: Dict[str, List[Outcome]] = defaultdict(list)
        for o in outcomes:
            if o.category:
                by_category[o.category].append(o)

        for category, cat_outcomes in by_category.items():
            if len(cat_outcomes) < self.config.min_sample_size:
                continue

            # Calculate failure rate
            failures = [
                o for o in cat_outcomes
                if o.outcome_type in (OutcomeType.FAILURE, OutcomeType.TIMEOUT)
            ]
            failure_rate = len(failures) / len(cat_outcomes)

            if failure_rate >= self.config.failure_threshold:
                # Calculate pattern confidence based on sample size and rate
                confidence = min(0.95, failure_rate * (len(cat_outcomes) / 100))

                pattern = Pattern(
                    pattern_type=PatternType.FAILURE_CLUSTER,
                    confidence=confidence,
                    sample_size=len(cat_outcomes),
                    description=f"High failure rate ({failure_rate:.1%}) in {category}",
                    affected_category=category,
                    frequency=failure_rate,
                    impact=failure_rate,
                    outcome_ids=[o.outcome_id for o in failures[:20]],
                    evidence={
                        "failure_rate": round(failure_rate, 4),
                        "failure_count": len(failures),
                        "total_count": len(cat_outcomes),
                    },
                )
                patterns.append(pattern)

        return patterns

    def _detect_correction_trends(self, outcomes: List[Outcome]) -> List[Pattern]:
        """Detect trends of increasing corrections.

        Args:
            outcomes: Outcomes to analyze

        Returns:
            List of correction trend patterns
        """
        patterns = []

        # Filter to corrections
        corrections = [o for o in outcomes if o.outcome_type == OutcomeType.CORRECTION]

        if len(corrections) < 5:
            return patterns

        # Calculate correction rate
        correction_rate = len(corrections) / len(outcomes)

        if correction_rate >= self.config.correction_threshold:
            # Group by category to find where corrections are happening
            by_category: Dict[str, int] = defaultdict(int)
            for c in corrections:
                by_category[c.category] += 1

            top_category = max(by_category.keys(), key=lambda k: by_category[k]) if by_category else ""

            confidence = min(0.9, correction_rate * 2)

            pattern = Pattern(
                pattern_type=PatternType.CORRECTION_TREND,
                confidence=confidence,
                sample_size=len(outcomes),
                description=f"High correction rate ({correction_rate:.1%}), mostly in {top_category}",
                affected_category=top_category,
                frequency=correction_rate,
                impact=correction_rate * 0.8,
                trend="increasing" if correction_rate > 0.15 else "stable",
                outcome_ids=[o.outcome_id for o in corrections[:20]],
                evidence={
                    "correction_rate": round(correction_rate, 4),
                    "correction_count": len(corrections),
                    "by_category": dict(by_category),
                },
            )
            patterns.append(pattern)

        return patterns

    def _detect_confidence_drops(self, outcomes: List[Outcome]) -> List[Pattern]:
        """Detect drops in confidence scores over time.

        Args:
            outcomes: Outcomes to analyze

        Returns:
            List of confidence drop patterns
        """
        patterns = []

        # Sort by timestamp
        sorted_outcomes = sorted(outcomes, key=lambda o: o.timestamp)

        if len(sorted_outcomes) < self.config.min_sample_size * 2:
            return patterns

        # Split into first and second half
        mid = len(sorted_outcomes) // 2
        first_half = sorted_outcomes[:mid]
        second_half = sorted_outcomes[mid:]

        # Calculate average confidence for each half
        first_avg = statistics.mean([o.confidence_score for o in first_half])
        second_avg = statistics.mean([o.confidence_score for o in second_half])

        drop = first_avg - second_avg

        if drop >= self.config.confidence_drop_threshold:
            confidence = min(0.85, drop * 5)

            pattern = Pattern(
                pattern_type=PatternType.CONFIDENCE_DROP,
                confidence=confidence,
                sample_size=len(sorted_outcomes),
                description=f"Confidence dropped {drop:.1%} (from {first_avg:.2f} to {second_avg:.2f})",
                frequency=drop,
                impact=drop,
                trend="decreasing",
                evidence={
                    "first_half_avg": round(first_avg, 4),
                    "second_half_avg": round(second_avg, 4),
                    "drop": round(drop, 4),
                    "sample_first": len(first_half),
                    "sample_second": len(second_half),
                },
            )
            patterns.append(pattern)

        return patterns

    def _detect_escalation_spikes(self, outcomes: List[Outcome]) -> List[Pattern]:
        """Detect spikes in escalation rates.

        Args:
            outcomes: Outcomes to analyze

        Returns:
            List of escalation spike patterns
        """
        patterns = []

        # Group by category
        by_category: Dict[str, List[Outcome]] = defaultdict(list)
        for o in outcomes:
            if o.category:
                by_category[o.category].append(o)

        for category, cat_outcomes in by_category.items():
            if len(cat_outcomes) < self.config.min_sample_size:
                continue

            escalations = [
                o for o in cat_outcomes
                if o.outcome_type == OutcomeType.ESCALATED
            ]
            escalation_rate = len(escalations) / len(cat_outcomes)

            if escalation_rate >= self.config.escalation_threshold:
                confidence = min(0.9, escalation_rate * 2.5)

                pattern = Pattern(
                    pattern_type=PatternType.ESCALATION_SPIKE,
                    confidence=confidence,
                    sample_size=len(cat_outcomes),
                    description=f"High escalation rate ({escalation_rate:.1%}) in {category}",
                    affected_category=category,
                    frequency=escalation_rate,
                    impact=escalation_rate * 0.9,
                    outcome_ids=[o.outcome_id for o in escalations[:20]],
                    evidence={
                        "escalation_rate": round(escalation_rate, 4),
                        "escalation_count": len(escalations),
                        "total_count": len(cat_outcomes),
                    },
                )
                patterns.append(pattern)

        return patterns

    def _detect_input_patterns(self, outcomes: List[Outcome]) -> List[Pattern]:
        """Detect common patterns in failing inputs.

        Args:
            outcomes: Outcomes to analyze

        Returns:
            List of input pattern findings
        """
        patterns = []

        # Get failures
        failures = [
            o for o in outcomes
            if o.outcome_type in (
                OutcomeType.FAILURE,
                OutcomeType.CORRECTION,
                OutcomeType.ESCALATED,
            )
        ]

        if len(failures) < 5:
            return patterns

        # Extract common words/phrases from failing inputs
        word_counts: Dict[str, int] = defaultdict(int)

        for f in failures:
            words = re.findall(r'\b\w{3,}\b', f.input_text.lower())
            for word in set(words):
                word_counts[word] += 1

        # Find words that appear in >30% of failures
        threshold = len(failures) * 0.3
        common_words = [
            (word, count)
            for word, count in word_counts.items()
            if count >= threshold
        ]

        if common_words:
            top_words = sorted(common_words, key=lambda x: x[1], reverse=True)[:5]
            word_list = [w[0] for w in top_words]

            confidence = min(0.75, len(top_words) * 0.15)

            pattern = Pattern(
                pattern_type=PatternType.INPUT_PATTERN,
                confidence=confidence,
                sample_size=len(failures),
                description=f"Common failing input patterns: {', '.join(word_list)}",
                frequency=len(failures) / len(outcomes),
                impact=0.5,
                evidence={
                    "common_words": dict(top_words),
                    "failure_count": len(failures),
                    "sample_inputs": [f.input_text[:100] for f in failures[:5]],
                },
            )
            patterns.append(pattern)

        return patterns

    def _detect_category_drift(self, outcomes: List[Outcome]) -> List[Pattern]:
        """Detect drift in category behavior over time.

        Args:
            outcomes: Outcomes to analyze

        Returns:
            List of category drift patterns
        """
        patterns = []

        # Sort by timestamp
        sorted_outcomes = sorted(outcomes, key=lambda o: o.timestamp)

        if len(sorted_outcomes) < self.config.min_sample_size * 2:
            return patterns

        # Split into first and second half
        mid = len(sorted_outcomes) // 2
        first_half = sorted_outcomes[:mid]
        second_half = sorted_outcomes[mid:]

        # Calculate success rates per category for each half
        def calc_success_by_category(outcomes_list: List[Outcome]) -> Dict[str, float]:
            by_cat: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
            for o in outcomes_list:
                if not o.category:
                    continue
                success, total = by_cat[o.category]
                total += 1
                if o.outcome_type == OutcomeType.SUCCESS:
                    success += 1
                by_cat[o.category] = (success, total)

            return {
                cat: success / total if total > 0 else 0.0
                for cat, (success, total) in by_cat.items()
            }

        first_rates = calc_success_by_category(first_half)
        second_rates = calc_success_by_category(second_half)

        # Find categories with significant drift. Only categories present in
        # BOTH halves have a comparable baseline; a category in just one half
        # (H5) used to default the missing rate to 0.5 and fabricate drift.
        for category in set(first_rates.keys()) & set(second_rates.keys()):
            first_rate = first_rates[category]
            second_rate = second_rates[category]
            drift = first_rate - second_rate

            if abs(drift) >= 0.15:
                confidence = min(0.8, abs(drift) * 2)

                pattern = Pattern(
                    pattern_type=PatternType.CATEGORY_DRIFT,
                    confidence=confidence,
                    sample_size=len([o for o in outcomes if o.category == category]),
                    description=f"{category} success rate {'dropped' if drift > 0 else 'improved'} by {abs(drift):.1%}",
                    affected_category=category,
                    frequency=abs(drift),
                    impact=abs(drift) * 0.7,
                    trend="decreasing" if drift > 0 else "increasing",
                    evidence={
                        "first_rate": round(first_rate, 4),
                        "second_rate": round(second_rate, 4),
                        "drift": round(drift, 4),
                    },
                )
                patterns.append(pattern)

        return patterns

    def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Get pattern by ID.

        Args:
            pattern_id: Pattern ID

        Returns:
            Pattern or None
        """
        return self._patterns.get(pattern_id)

    def get_patterns_by_type(
        self,
        pattern_type: str,
        limit: int = 50,
    ) -> List[Pattern]:
        """Get patterns of a specific type.

        Args:
            pattern_type: Type to filter by
            limit: Maximum results

        Returns:
            List of patterns
        """
        patterns = [
            p for p in self._patterns.values()
            if p.pattern_type == pattern_type
        ]
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)[:limit]

    def get_high_impact_patterns(
        self,
        impact_threshold: float = 0.5,
        limit: int = 20,
    ) -> List[Pattern]:
        """Get high-impact patterns.

        Args:
            impact_threshold: Minimum impact score
            limit: Maximum results

        Returns:
            List of high-impact patterns
        """
        patterns = [
            p for p in self._patterns.values()
            if p.impact >= impact_threshold
        ]
        return sorted(patterns, key=lambda p: p.impact * p.confidence, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "patterns_detected": self._stats["patterns_detected"],
            "patterns_stored": len(self._patterns),
            "by_type": dict(self._stats["by_type"]),
            "last_detection": self._stats["last_detection"],
        }

    def clear(self) -> None:
        """Clear all patterns."""
        self._patterns.clear()
