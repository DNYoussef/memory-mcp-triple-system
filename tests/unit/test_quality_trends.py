"""Regression tests for quality-trend statistic consistency (MECE H7)."""

from datetime import datetime, timedelta, timezone

from src.services.weekly_review.quality_trends import (
    QualityMetricConfig,
    QualityTrendsAnalyzer,
    QualityTrendsConfig,
)


def _analyzer(metric):
    return QualityTrendsAnalyzer(
        QualityTrendsConfig(metrics=[metric], trend_period_days=7, min_data_points=4)
    )


def _record_values(analyzer, metric_name, values):
    now = datetime.now(timezone.utc)
    for index, value in enumerate(values):
        analyzer.record_metric(
            metric_name,
            value,
            timestamp=now - timedelta(hours=len(values) - index),
        )


class TestQualityTrendStatisticConsistency:
    def test_current_value_is_current_period_average_not_last_sample(self):
        """The reported current value must match the statistic used for trend math."""
        metric = QualityMetricConfig(
            "confidence_avg",
            warning_threshold=0.85,
            critical_threshold=0.75,
            higher_is_better=True,
        )
        analyzer = _analyzer(metric)
        _record_values(analyzer, "confidence_avg", [0.90, 0.90, 0.70, 0.95])

        trend = analyzer.analyze_trends(days=7)[0]

        assert trend.previous_value == 0.90
        assert trend.current_value == 0.825
        assert trend.change_percent < 0
        assert trend.is_warning is True
        assert trend.is_critical is False

    def test_lower_is_better_thresholds_use_current_period_average(self):
        """A good last sample must not hide a bad current-period average."""
        metric = QualityMetricConfig(
            "escalation_rate",
            warning_threshold=0.20,
            critical_threshold=0.30,
            higher_is_better=False,
        )
        analyzer = _analyzer(metric)
        _record_values(analyzer, "escalation_rate", [0.10, 0.10, 0.40, 0.05])

        trend = analyzer.analyze_trends(days=7)[0]

        assert trend.previous_value == 0.10
        assert trend.current_value == 0.225
        assert trend.change_percent > 0
        assert trend.is_warning is True
        assert trend.is_critical is False
