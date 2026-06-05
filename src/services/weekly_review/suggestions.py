"""Suggestions Generator for IMPROVE-002.

Generates actionable improvement suggestions.

WHO: weekly-review:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-002)
"""

import logging
from typing import Dict, Any, List, Optional

from src.services.weekly_review.review_schema import (
    UsageSummary,
    QualityTrend,
    CostAnalysis,
    ImprovementSuggestion,
    SuggestionPriority,
    TrendDirection,
)

logger = logging.getLogger(__name__)


# Suggestion templates
SUGGESTION_TEMPLATES = {
    "low_cache_hit": {
        "title": "Improve cache hit rate",
        "description": "Cache hit rate is below optimal levels, increasing retrieval latency.",
        "action_type": "config_change",
        "specific_action": "Review cache configuration and consider increasing cache size or TTL.",
        "expected_benefit": "Reduced retrieval latency and lower API costs",
        "estimated_effort": "small",
    },
    "high_escalation": {
        "title": "Reduce escalation rate",
        "description": "High escalation rate indicates classification confidence issues.",
        "action_type": "code_change",
        "specific_action": "Review and adjust classification thresholds or add training data.",
        "expected_benefit": "Fewer manual reviews, faster processing",
        "estimated_effort": "medium",
    },
    "declining_confidence": {
        "title": "Address declining confidence scores",
        "description": "Confidence scores are trending downward, suggesting model drift.",
        "action_type": "process_change",
        "specific_action": "Analyze recent inputs for new patterns and update classification rules.",
        "expected_benefit": "Improved classification accuracy",
        "estimated_effort": "medium",
    },
    "high_cost": {
        "title": "Optimize token usage",
        "description": "Token costs are higher than expected.",
        "action_type": "config_change",
        "specific_action": "Review prompt templates for verbosity and consider using smaller models where appropriate.",
        "expected_benefit": "Reduced API costs",
        "estimated_effort": "small",
    },
    "low_memory_utilization": {
        "title": "Increase memory utilization",
        "description": "Memory system is underutilized, missing opportunities for context enhancement.",
        "action_type": "process_change",
        "specific_action": "Enable proactive memory retrieval and expand memory capture triggers.",
        "expected_benefit": "Better context awareness and task performance",
        "estimated_effort": "medium",
    },
    "high_correction_rate": {
        "title": "Reduce user corrections",
        "description": "High correction rate indicates systematic output issues.",
        "action_type": "code_change",
        "specific_action": "Review correction patterns and update classification rules accordingly.",
        "expected_benefit": "Improved user satisfaction and efficiency",
        "estimated_effort": "large",
    },
}


class SuggestionsGenerator:
    """Generates improvement suggestions based on metrics.

    Analyzes:
    - Usage patterns
    - Quality trends
    - Cost data
    And generates actionable suggestions.
    """

    def __init__(self):
        """Initialize suggestions generator."""
        self._generated_suggestions: List[ImprovementSuggestion] = []

    def generate(
        self,
        usage: Optional[UsageSummary] = None,
        quality_trends: Optional[List[QualityTrend]] = None,
        cost_analysis: Optional[CostAnalysis] = None,
    ) -> List[ImprovementSuggestion]:
        """Generate suggestions based on metrics.

        Args:
            usage: Usage summary
            quality_trends: Quality trend data
            cost_analysis: Cost analysis

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Analyze usage
        if usage:
            suggestions.extend(self._analyze_usage(usage))

        # Analyze quality trends
        if quality_trends:
            suggestions.extend(self._analyze_quality(quality_trends))

        # Analyze costs
        if cost_analysis:
            suggestions.extend(self._analyze_costs(cost_analysis))

        # Sort by priority
        suggestions.sort(key=lambda s: s.priority.value)

        self._generated_suggestions.extend(suggestions)

        return suggestions

    def _analyze_usage(self, usage: UsageSummary) -> List[ImprovementSuggestion]:
        """Generate suggestions from usage data."""
        suggestions = []

        # Check cache hit rate
        if usage.cache_hit_rate < 0.6:
            template = SUGGESTION_TEMPLATES["low_cache_hit"]
            priority = SuggestionPriority.HIGH if usage.cache_hit_rate < 0.4 else SuggestionPriority.MEDIUM

            suggestions.append(ImprovementSuggestion(
                priority=priority,
                title=template["title"],
                description=template["description"],
                rationale=f"Current cache hit rate is {usage.cache_hit_rate:.1%}",
                action_type=template["action_type"],
                specific_action=template["specific_action"],
                expected_benefit=template["expected_benefit"],
                estimated_effort=template["estimated_effort"],
                source_metric="cache_hit_rate",
                source_value=usage.cache_hit_rate,
            ))

        # Check memory utilization
        total_ops = usage.total_stores + usage.total_retrievals + usage.total_searches
        if total_ops > 0:
            retrieval_ratio = usage.total_retrievals / total_ops
            if retrieval_ratio < 0.3:
                template = SUGGESTION_TEMPLATES["low_memory_utilization"]
                suggestions.append(ImprovementSuggestion(
                    priority=SuggestionPriority.LOW,
                    title=template["title"],
                    description=template["description"],
                    rationale=f"Retrieval ratio is only {retrieval_ratio:.1%}",
                    action_type=template["action_type"],
                    specific_action=template["specific_action"],
                    expected_benefit=template["expected_benefit"],
                    estimated_effort=template["estimated_effort"],
                    source_metric="retrieval_ratio",
                    source_value=retrieval_ratio,
                ))

        return suggestions

    def _analyze_quality(
        self,
        trends: List[QualityTrend],
    ) -> List[ImprovementSuggestion]:
        """Generate suggestions from quality trends."""
        suggestions = []

        for trend in trends:
            # Check critical trends
            if trend.is_critical:
                if trend.metric_name == "escalation_rate":
                    template = SUGGESTION_TEMPLATES["high_escalation"]
                    suggestions.append(ImprovementSuggestion(
                        priority=SuggestionPriority.CRITICAL,
                        title=template["title"],
                        description=template["description"],
                        rationale=f"Escalation rate is at critical level: {trend.current_value:.1%}",
                        action_type=template["action_type"],
                        specific_action=template["specific_action"],
                        expected_benefit=template["expected_benefit"],
                        estimated_effort=template["estimated_effort"],
                        source_metric=trend.metric_name,
                        source_value=trend.current_value,
                    ))

                elif trend.metric_name == "correction_rate":
                    template = SUGGESTION_TEMPLATES["high_correction_rate"]
                    suggestions.append(ImprovementSuggestion(
                        priority=SuggestionPriority.HIGH,
                        title=template["title"],
                        description=template["description"],
                        rationale=f"Correction rate is high: {trend.current_value:.1%}",
                        action_type=template["action_type"],
                        specific_action=template["specific_action"],
                        expected_benefit=template["expected_benefit"],
                        estimated_effort=template["estimated_effort"],
                        source_metric=trend.metric_name,
                        source_value=trend.current_value,
                    ))

            # Check declining trends
            elif trend.direction == TrendDirection.DECLINING:
                if trend.metric_name == "confidence_avg":
                    template = SUGGESTION_TEMPLATES["declining_confidence"]
                    suggestions.append(ImprovementSuggestion(
                        priority=SuggestionPriority.MEDIUM,
                        title=template["title"],
                        description=template["description"],
                        rationale=f"Confidence dropped {abs(trend.change_percent):.1f}% this week",
                        action_type=template["action_type"],
                        specific_action=template["specific_action"],
                        expected_benefit=template["expected_benefit"],
                        estimated_effort=template["estimated_effort"],
                        source_metric=trend.metric_name,
                        source_value=trend.current_value,
                    ))

        return suggestions

    def _analyze_costs(self, cost: CostAnalysis) -> List[ImprovementSuggestion]:
        """Generate suggestions from cost analysis."""
        suggestions = []

        # High cost increase
        if cost.cost_change_percent > 25:
            template = SUGGESTION_TEMPLATES["high_cost"]
            priority = SuggestionPriority.HIGH if cost.cost_change_percent > 50 else SuggestionPriority.MEDIUM

            suggestions.append(ImprovementSuggestion(
                priority=priority,
                title=template["title"],
                description=template["description"],
                rationale=f"Costs increased {cost.cost_change_percent:.1f}% from previous period",
                action_type=template["action_type"],
                specific_action=template["specific_action"],
                expected_benefit=template["expected_benefit"],
                estimated_effort=template["estimated_effort"],
                source_metric="cost_change",
                source_value=cost.cost_change_percent,
            ))

        # High absolute cost
        if cost.estimated_cost > 20.0:
            suggestions.append(ImprovementSuggestion(
                priority=SuggestionPriority.MEDIUM,
                title="Review high-cost operations",
                description="Weekly costs are significant.",
                rationale=f"Estimated weekly cost: ${cost.estimated_cost:.2f}",
                action_type="process_change",
                specific_action="Audit top token consumers and optimize or batch operations.",
                expected_benefit="Cost reduction of 10-30%",
                estimated_effort="medium",
                source_metric="estimated_cost",
                source_value=cost.estimated_cost,
            ))

        return suggestions

    def get_by_priority(
        self,
        priority: SuggestionPriority,
    ) -> List[ImprovementSuggestion]:
        """Get suggestions by priority."""
        return [s for s in self._generated_suggestions if s.priority == priority]

    def get_critical(self) -> List[ImprovementSuggestion]:
        """Get critical suggestions."""
        return self.get_by_priority(SuggestionPriority.CRITICAL)

    def get_stats(self) -> Dict[str, Any]:
        """Get generator statistics."""
        by_priority = {}
        for p in SuggestionPriority:
            by_priority[p.name] = len(self.get_by_priority(p))

        return {
            "total_generated": len(self._generated_suggestions),
            "by_priority": by_priority,
        }

    def clear(self) -> None:
        """Clear generated suggestions."""
        self._generated_suggestions.clear()
