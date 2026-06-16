"""Weekly Review Coordinator for IMPROVE-002.

Orchestrates generation of weekly review reports.

WHO: weekly-review:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-002)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from src.services.weekly_review.review_schema import (
    WeeklyReview,
    UsageSummary,
    QualityTrend,
    CostAnalysis,
    ImprovementSuggestion,
    TrendDirection,
)
from src.services.weekly_review.usage_aggregator import UsageAggregator
from src.services.weekly_review.quality_trends import QualityTrendsAnalyzer
from src.services.weekly_review.cost_analyzer import CostTokenAnalyzer
from src.services.weekly_review.suggestions import SuggestionsGenerator

logger = logging.getLogger(__name__)


@dataclass
class WeeklyReviewConfig:
    """Configuration for weekly review."""

    auto_generate_suggestions: bool = True
    health_score_weights: Dict[str, float] = None

    def __post_init__(self):
        if self.health_score_weights is None:
            self.health_score_weights = {
                "success_rate": 0.3,
                "confidence_avg": 0.25,
                "escalation_rate": 0.2,
                "cache_hit_rate": 0.15,
                "cost_efficiency": 0.1,
            }


class WeeklyReviewCoordinator:
    """Coordinates weekly review generation.

    Orchestrates:
    - Usage aggregation
    - Quality trend analysis
    - Cost analysis
    - Suggestion generation
    """

    def __init__(self, config: Optional[WeeklyReviewConfig] = None):
        """Initialize weekly review coordinator.

        Args:
            config: Coordinator configuration
        """
        self.config = config or WeeklyReviewConfig()

        # Initialize components
        self.usage_aggregator = UsageAggregator()
        self.quality_analyzer = QualityTrendsAnalyzer()
        self.cost_analyzer = CostTokenAnalyzer()
        self.suggestions_generator = SuggestionsGenerator()

        # Review history
        self._reviews: List[WeeklyReview] = []

    def generate_review(
        self,
        week_start: Optional[datetime] = None,
        week_end: Optional[datetime] = None,
    ) -> WeeklyReview:
        """Generate a weekly review.

        Args:
            week_start: Start of week
            week_end: End of week

        Returns:
            Complete weekly review
        """
        # Determine period
        if week_end is None:
            week_end = datetime.now(timezone.utc)

        if week_start is None:
            week_start = week_end - timedelta(days=7)

        # Calculate week number
        week_number = week_start.isocalendar()[1]

        logger.info(f"Generating weekly review for week {week_number}")

        # Aggregate usage
        usage = self.usage_aggregator.aggregate(
            start_date=week_start,
            end_date=week_end,
        )

        # Analyze quality trends
        quality_trends = self.quality_analyzer.analyze_trends(days=7)

        # Analyze costs
        cost_analysis = self.cost_analyzer.analyze(
            start_date=week_start,
            end_date=week_end,
        )

        # Generate suggestions
        suggestions = []
        if self.config.auto_generate_suggestions:
            suggestions = self.suggestions_generator.generate(
                usage=usage,
                quality_trends=quality_trends,
                cost_analysis=cost_analysis,
            )

        # Calculate health score
        health_score = self._calculate_health_score(
            usage, quality_trends, cost_analysis
        )

        # Generate summary
        executive_summary = self._generate_summary(
            usage, quality_trends, cost_analysis, suggestions
        )

        # Identify highlights and concerns
        highlights = self._identify_highlights(usage, quality_trends, cost_analysis)
        concerns = self._identify_concerns(
            usage, quality_trends, cost_analysis, suggestions
        )

        # Create review
        review = WeeklyReview(
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            week_number=week_number,
            usage=usage,
            quality_trends=quality_trends,
            cost_analysis=cost_analysis,
            suggestions=suggestions,
            executive_summary=executive_summary,
            health_score=health_score,
            key_highlights=highlights,
            areas_of_concern=concerns,
        )

        self._reviews.append(review)

        logger.info(
            f"Generated review {review.review_id} with health score {health_score:.0f}"
        )

        return review

    def _calculate_health_score(
        self,
        usage: UsageSummary,
        trends: List[QualityTrend],
        cost: CostAnalysis,
    ) -> float:
        """Calculate overall health score (0-100)."""
        scores = []
        weights = self.config.health_score_weights

        # Get trend values
        trend_map = {t.metric_name: t for t in trends}

        # Success rate
        success_trend = trend_map.get("success_rate")
        if success_trend:
            score = min(100, success_trend.current_value * 100)
            scores.append(("success_rate", score, weights.get("success_rate", 0.3)))

        # Confidence average
        conf_trend = trend_map.get("confidence_avg")
        if conf_trend:
            score = min(100, conf_trend.current_value * 100)
            scores.append(
                ("confidence_avg", score, weights.get("confidence_avg", 0.25))
            )

        # Escalation rate (inverse - lower is better)
        esc_trend = trend_map.get("escalation_rate")
        if esc_trend:
            score = max(0, 100 - (esc_trend.current_value * 200))
            scores.append(
                ("escalation_rate", score, weights.get("escalation_rate", 0.2))
            )

        # Cache hit rate
        if usage.cache_hit_rate > 0:
            score = min(100, usage.cache_hit_rate * 100)
            scores.append(
                ("cache_hit_rate", score, weights.get("cache_hit_rate", 0.15))
            )

        # Cost efficiency (inverse of cost change)
        if cost.cost_change_percent != 0:
            if cost.cost_change_percent < 0:
                score = min(100, 70 + abs(cost.cost_change_percent))
            else:
                score = max(0, 70 - cost.cost_change_percent)
            scores.append(
                ("cost_efficiency", score, weights.get("cost_efficiency", 0.1))
            )

        # Calculate weighted average
        if not scores:
            return 70.0  # Default neutral score

        total_weight = sum(w for _, _, w in scores)
        weighted_sum = sum(s * w for _, s, w in scores)

        return weighted_sum / total_weight

    def _generate_summary(
        self,
        usage: UsageSummary,
        trends: List[QualityTrend],
        cost: CostAnalysis,
        suggestions: List[ImprovementSuggestion],
    ) -> str:
        """Generate executive summary."""
        parts = []

        # Usage summary
        total_ops = usage.total_stores + usage.total_retrievals + usage.total_searches
        parts.append(
            f"This week saw {total_ops:,} memory operations with {usage.memories_created:,} new memories created."
        )

        # Quality summary
        declining = [t for t in trends if t.direction == TrendDirection.DECLINING]
        improving = [t for t in trends if t.direction == TrendDirection.IMPROVING]

        if improving:
            parts.append(
                f"Quality improved in {len(improving)} metric(s): {', '.join(t.metric_name for t in improving)}."
            )

        if declining:
            parts.append(
                f"Quality declined in {len(declining)} metric(s): {', '.join(t.metric_name for t in declining)}."
            )

        # Cost summary
        if cost.estimated_cost > 0:
            change = ""
            if cost.cost_change_percent > 0:
                change = f", up {cost.cost_change_percent:.1f}%"
            elif cost.cost_change_percent < 0:
                change = f", down {abs(cost.cost_change_percent):.1f}%"
            parts.append(f"Estimated cost: ${cost.estimated_cost:.2f}{change}.")

        # Suggestions summary
        critical = [s for s in suggestions if s.priority.value <= 2]
        if critical:
            parts.append(
                f"There are {len(critical)} high-priority improvement(s) recommended."
            )

        return " ".join(parts)

    def _identify_highlights(
        self,
        usage: UsageSummary,
        trends: List[QualityTrend],
        cost: CostAnalysis,
    ) -> List[str]:
        """Identify positive highlights."""
        highlights = []

        # Improving trends
        for trend in trends:
            if trend.direction == TrendDirection.IMPROVING:
                highlights.append(
                    f"{trend.metric_name} improved by {abs(trend.change_percent):.1f}%"
                )

        # Good cache performance
        if usage.cache_hit_rate >= 0.8:
            highlights.append(f"Excellent cache hit rate: {usage.cache_hit_rate:.1%}")

        # Cost reduction
        if cost.cost_change_percent < -10:
            highlights.append(f"Cost reduced by {abs(cost.cost_change_percent):.1f}%")

        # High memory activity
        if usage.memories_created > 100:
            highlights.append(
                f"Active memory growth: {usage.memories_created} new memories"
            )

        return highlights[:5]

    def _identify_concerns(
        self,
        usage: UsageSummary,
        trends: List[QualityTrend],
        cost: CostAnalysis,
        suggestions: List[ImprovementSuggestion],
    ) -> List[str]:
        """Identify areas of concern."""
        concerns = []

        # Critical quality issues
        for trend in trends:
            if trend.is_critical:
                concerns.append(
                    f"Critical: {trend.metric_name} at {trend.current_value:.2f}"
                )
            elif (
                trend.direction == TrendDirection.DECLINING
                and trend.change_percent < -10
            ):
                concerns.append(
                    f"{trend.metric_name} declining ({trend.change_percent:.1f}%)"
                )

        # Low cache performance
        if usage.cache_hit_rate < 0.5:
            concerns.append(f"Low cache hit rate: {usage.cache_hit_rate:.1%}")

        # Cost increase
        if cost.cost_change_percent > 25:
            concerns.append(
                f"Significant cost increase: +{cost.cost_change_percent:.1f}%"
            )

        # Critical suggestions
        critical_suggestions = [s for s in suggestions if s.priority.value == 1]
        for sug in critical_suggestions:
            concerns.append(f"Action needed: {sug.title}")

        return concerns[:5]

    def get_recent_reviews(self, count: int = 4) -> List[WeeklyReview]:
        """Get recent reviews.

        Args:
            count: Number of reviews to return

        Returns:
            List of recent reviews
        """
        return self._reviews[-count:]

    def get_review(self, review_id: str) -> Optional[WeeklyReview]:
        """Get review by ID.

        Args:
            review_id: Review ID

        Returns:
            Review or None
        """
        for review in self._reviews:
            if review.review_id == review_id:
                return review
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get coordinator statistics."""
        return {
            "reviews_generated": len(self._reviews),
            "usage_aggregator": self.usage_aggregator.get_stats(),
            "quality_analyzer": self.quality_analyzer.get_stats(),
            "cost_analyzer": self.cost_analyzer.get_stats(),
            "suggestions_generator": self.suggestions_generator.get_stats(),
        }


# Singleton instance
_coordinator: Optional[WeeklyReviewCoordinator] = None


def get_weekly_review_coordinator() -> WeeklyReviewCoordinator:
    """Get the global weekly review coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = WeeklyReviewCoordinator()
    return _coordinator


def initialize_weekly_review_coordinator(
    config: Optional[WeeklyReviewConfig] = None,
) -> WeeklyReviewCoordinator:
    """Initialize the global coordinator.

    Args:
        config: Coordinator configuration

    Returns:
        Initialized coordinator
    """
    global _coordinator
    _coordinator = WeeklyReviewCoordinator(config)
    return _coordinator
