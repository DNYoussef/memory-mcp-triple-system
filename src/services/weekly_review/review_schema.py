"""Weekly Review Schema for IMPROVE-002.

Defines data structures for weekly review reports.

WHO: weekly-review:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-002)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid


class SuggestionPriority(Enum):
    """Priority levels for improvement suggestions."""

    CRITICAL = 1  # Must address immediately
    HIGH = 2  # Address this week
    MEDIUM = 3  # Address when possible
    LOW = 4  # Nice to have


class TrendDirection(Enum):
    """Direction of a trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


@dataclass
class UsageSummary:
    """Memory MCP usage summary."""

    # Time period
    period_start: str = ""
    period_end: str = ""

    # Memory operations
    total_stores: int = 0
    total_retrievals: int = 0
    total_searches: int = 0
    total_graph_queries: int = 0

    # Data volume
    memories_created: int = 0
    memories_updated: int = 0
    memories_expired: int = 0
    current_memory_count: int = 0

    # Layer distribution
    short_term_count: int = 0
    mid_term_count: int = 0
    long_term_count: int = 0

    # Performance
    avg_retrieval_time_ms: float = 0.0
    avg_search_time_ms: float = 0.0
    cache_hit_rate: float = 0.0

    # Categories
    by_category: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_stores": self.total_stores,
            "total_retrievals": self.total_retrievals,
            "total_searches": self.total_searches,
            "total_graph_queries": self.total_graph_queries,
            "memories_created": self.memories_created,
            "memories_updated": self.memories_updated,
            "memories_expired": self.memories_expired,
            "current_memory_count": self.current_memory_count,
            "short_term_count": self.short_term_count,
            "mid_term_count": self.mid_term_count,
            "long_term_count": self.long_term_count,
            "avg_retrieval_time_ms": round(self.avg_retrieval_time_ms, 2),
            "avg_search_time_ms": round(self.avg_search_time_ms, 2),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "by_category": self.by_category,
        }


@dataclass
class QualityTrend:
    """Quality gate trend data."""

    metric_name: str = ""
    current_value: float = 0.0
    previous_value: float = 0.0
    change_percent: float = 0.0
    direction: TrendDirection = TrendDirection.STABLE

    # Historical data
    data_points: List[float] = field(default_factory=list)
    timestamps: List[str] = field(default_factory=list)

    # Thresholds
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    is_warning: bool = False
    is_critical: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "metric_name": self.metric_name,
            "current_value": round(self.current_value, 4),
            "previous_value": round(self.previous_value, 4),
            "change_percent": round(self.change_percent, 2),
            "direction": self.direction.value,
            "data_points": [round(d, 4) for d in self.data_points],
            "timestamps": self.timestamps,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "is_warning": self.is_warning,
            "is_critical": self.is_critical,
        }


@dataclass
class CostAnalysis:
    """Cost and token usage analysis."""

    # Time period
    period_start: str = ""
    period_end: str = ""

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0

    # By model
    tokens_by_model: Dict[str, int] = field(default_factory=dict)

    # By category
    tokens_by_category: Dict[str, int] = field(default_factory=dict)

    # Cost estimates (USD)
    estimated_cost: float = 0.0
    cost_by_model: Dict[str, float] = field(default_factory=dict)

    # Efficiency
    tokens_per_task: float = 0.0
    cost_per_task: float = 0.0

    # Comparison to previous
    token_change_percent: float = 0.0
    cost_change_percent: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "tokens_by_model": self.tokens_by_model,
            "tokens_by_category": self.tokens_by_category,
            "estimated_cost": round(self.estimated_cost, 4),
            "cost_by_model": {k: round(v, 4) for k, v in self.cost_by_model.items()},
            "tokens_per_task": round(self.tokens_per_task, 2),
            "cost_per_task": round(self.cost_per_task, 4),
            "token_change_percent": round(self.token_change_percent, 2),
            "cost_change_percent": round(self.cost_change_percent, 2),
        }


@dataclass
class ImprovementSuggestion:
    """An actionable improvement suggestion."""

    suggestion_id: str = field(default_factory=lambda: f"sug-{uuid.uuid4().hex[:8]}")
    priority: SuggestionPriority = SuggestionPriority.MEDIUM

    # Content
    title: str = ""
    description: str = ""
    rationale: str = ""

    # Action
    action_type: str = ""  # "config_change", "code_change", "process_change"
    specific_action: str = ""  # What to do

    # Impact
    expected_benefit: str = ""
    estimated_effort: str = ""  # "trivial", "small", "medium", "large"

    # Source
    source_metric: str = ""
    source_value: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "suggestion_id": self.suggestion_id,
            "priority": self.priority.name,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "action_type": self.action_type,
            "specific_action": self.specific_action,
            "expected_benefit": self.expected_benefit,
            "estimated_effort": self.estimated_effort,
            "source_metric": self.source_metric,
            "source_value": round(self.source_value, 4),
        }


@dataclass
class WeeklyReview:
    """Complete weekly review report."""

    review_id: str = field(default_factory=lambda: f"review-{uuid.uuid4().hex[:8]}")
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Time period
    week_start: str = ""
    week_end: str = ""
    week_number: int = 0

    # Sections
    usage: Optional[UsageSummary] = None
    quality_trends: List[QualityTrend] = field(default_factory=list)
    cost_analysis: Optional[CostAnalysis] = None
    suggestions: List[ImprovementSuggestion] = field(default_factory=list)

    # Summary
    executive_summary: str = ""
    health_score: float = 0.0  # 0-100
    key_highlights: List[str] = field(default_factory=list)
    areas_of_concern: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "review_id": self.review_id,
            "generated_at": self.generated_at,
            "week_start": self.week_start,
            "week_end": self.week_end,
            "week_number": self.week_number,
            "usage": self.usage.to_dict() if self.usage else None,
            "quality_trends": [t.to_dict() for t in self.quality_trends],
            "cost_analysis": self.cost_analysis.to_dict()
            if self.cost_analysis
            else None,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "executive_summary": self.executive_summary,
            "health_score": round(self.health_score, 1),
            "key_highlights": self.key_highlights,
            "areas_of_concern": self.areas_of_concern,
        }

    def format_markdown(self) -> str:
        """Format as markdown report."""
        lines = [
            f"# Weekly Review: Week {self.week_number}",
            f"*Generated: {self.generated_at}*",
            f"*Period: {self.week_start} to {self.week_end}*",
            "",
            f"## Health Score: {self.health_score:.0f}/100",
            "",
            "## Executive Summary",
            self.executive_summary,
            "",
        ]

        if self.key_highlights:
            lines.append("### Key Highlights")
            for h in self.key_highlights:
                lines.append(f"- {h}")
            lines.append("")

        if self.areas_of_concern:
            lines.append("### Areas of Concern")
            for c in self.areas_of_concern:
                lines.append(f"- {c}")
            lines.append("")

        if self.usage:
            lines.extend(
                [
                    "## Usage Summary",
                    f"- Total stores: {self.usage.total_stores:,}",
                    f"- Total retrievals: {self.usage.total_retrievals:,}",
                    f"- Memories created: {self.usage.memories_created:,}",
                    f"- Cache hit rate: {self.usage.cache_hit_rate:.1%}",
                    "",
                ]
            )

        if self.quality_trends:
            lines.append("## Quality Trends")
            for trend in self.quality_trends:
                icon = {"improving": "+", "stable": "=", "declining": "-"}.get(
                    trend.direction.value, ""
                )
                lines.append(
                    f"- {trend.metric_name}: {trend.current_value:.2f} ({icon}{trend.change_percent:+.1f}%)"
                )
            lines.append("")

        if self.cost_analysis:
            lines.extend(
                [
                    "## Cost Analysis",
                    f"- Total tokens: {self.cost_analysis.total_tokens:,}",
                    f"- Estimated cost: ${self.cost_analysis.estimated_cost:.2f}",
                    f"- Cost per task: ${self.cost_analysis.cost_per_task:.4f}",
                    "",
                ]
            )

        if self.suggestions:
            lines.append("## Improvement Suggestions")
            for sug in self.suggestions:
                lines.append(f"### [{sug.priority.name}] {sug.title}")
                lines.append(sug.description)
                lines.append(f"**Action:** {sug.specific_action}")
                lines.append("")

        return "\n".join(lines)
