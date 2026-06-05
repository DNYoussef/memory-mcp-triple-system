"""Quality Trends Analyzer for IMPROVE-002.

Analyzes quality gate trends over time.

WHO: weekly-review:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-002)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import statistics

from src.services.weekly_review.review_schema import QualityTrend, TrendDirection

logger = logging.getLogger(__name__)


@dataclass
class QualityMetricConfig:
    """Configuration for a quality metric."""

    name: str = ""
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    higher_is_better: bool = True


# Default quality metrics to track
DEFAULT_METRICS = [
    QualityMetricConfig("success_rate", 0.8, 0.6, True),
    QualityMetricConfig("confidence_avg", 0.65, 0.5, True),
    QualityMetricConfig("escalation_rate", 0.2, 0.3, False),
    QualityMetricConfig("correction_rate", 0.15, 0.25, False),
    QualityMetricConfig("cache_hit_rate", 0.7, 0.5, True),
]


@dataclass
class QualityTrendsConfig:
    """Configuration for quality trends analyzer."""

    metrics: List[QualityMetricConfig] = field(default_factory=lambda: DEFAULT_METRICS)
    trend_period_days: int = 7
    min_data_points: int = 3


class QualityTrendsAnalyzer:
    """Analyzes quality gate trends.

    Tracks and analyzes:
    - Success rates
    - Confidence scores
    - Escalation rates
    - Correction rates
    - Cache performance
    """

    def __init__(self, config: Optional[QualityTrendsConfig] = None):
        """Initialize quality trends analyzer.

        Args:
            config: Analyzer configuration
        """
        self.config = config or QualityTrendsConfig()

        # Data storage (in production, read from Memory MCP)
        self._data_points: Dict[str, List[Dict[str, Any]]] = {}

        for metric in self.config.metrics:
            self._data_points[metric.name] = []

    def record_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a quality metric data point.

        Args:
            metric_name: Name of metric
            value: Metric value
            timestamp: When recorded
        """
        if metric_name not in self._data_points:
            self._data_points[metric_name] = []

        self._data_points[metric_name].append({
            "value": value,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        })

    def analyze_trends(
        self,
        days: Optional[int] = None,
    ) -> List[QualityTrend]:
        """Analyze trends for all metrics.

        Args:
            days: Period to analyze

        Returns:
            List of quality trends
        """
        period_days = days or self.config.trend_period_days
        trends = []

        for metric_config in self.config.metrics:
            trend = self._analyze_metric(metric_config, period_days)
            if trend:
                trends.append(trend)

        return trends

    def _analyze_metric(
        self,
        metric_config: QualityMetricConfig,
        days: int,
    ) -> Optional[QualityTrend]:
        """Analyze trend for a single metric.

        Args:
            metric_config: Metric configuration
            days: Period in days

        Returns:
            Quality trend or None
        """
        data = self._data_points.get(metric_config.name, [])

        if len(data) < self.config.min_data_points:
            return None

        # Filter to period
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        period_data = [
            d for d in data
            if datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")) >= cutoff
        ]

        if len(period_data) < self.config.min_data_points:
            return None

        # Sort by timestamp
        period_data.sort(key=lambda d: d["timestamp"])

        values = [d["value"] for d in period_data]
        timestamps = [d["timestamp"] for d in period_data]

        # Current and previous values
        current = values[-1]

        # Split into halves for comparison
        mid = len(values) // 2
        first_half = values[:mid] if mid > 0 else values[:1]
        second_half = values[mid:] if mid > 0 else values

        previous = statistics.mean(first_half)
        current_avg = statistics.mean(second_half)

        # Calculate change
        if previous != 0:
            change_percent = ((current_avg - previous) / abs(previous)) * 100
        else:
            change_percent = 0.0

        # Determine direction
        if metric_config.higher_is_better:
            if change_percent > 5:
                direction = TrendDirection.IMPROVING
            elif change_percent < -5:
                direction = TrendDirection.DECLINING
            else:
                direction = TrendDirection.STABLE
        else:
            # For metrics where lower is better
            if change_percent < -5:
                direction = TrendDirection.IMPROVING
            elif change_percent > 5:
                direction = TrendDirection.DECLINING
            else:
                direction = TrendDirection.STABLE

        # Check thresholds
        if metric_config.higher_is_better:
            is_warning = current < metric_config.warning_threshold
            is_critical = current < metric_config.critical_threshold
        else:
            is_warning = current > metric_config.warning_threshold
            is_critical = current > metric_config.critical_threshold

        return QualityTrend(
            metric_name=metric_config.name,
            current_value=current,
            previous_value=previous,
            change_percent=change_percent,
            direction=direction,
            data_points=values,
            timestamps=timestamps,
            warning_threshold=metric_config.warning_threshold,
            critical_threshold=metric_config.critical_threshold,
            is_warning=is_warning,
            is_critical=is_critical,
        )

    def get_critical_trends(self) -> List[QualityTrend]:
        """Get trends at critical levels.

        Returns:
            List of critical trends
        """
        trends = self.analyze_trends()
        return [t for t in trends if t.is_critical]

    def get_declining_trends(self) -> List[QualityTrend]:
        """Get declining trends.

        Returns:
            List of declining trends
        """
        trends = self.analyze_trends()
        return [t for t in trends if t.direction == TrendDirection.DECLINING]

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            "metrics_tracked": len(self._data_points),
            "data_points_per_metric": {
                k: len(v) for k, v in self._data_points.items()
            },
        }

    def clear(self) -> None:
        """Clear all data points."""
        for metric in self._data_points:
            self._data_points[metric] = []
