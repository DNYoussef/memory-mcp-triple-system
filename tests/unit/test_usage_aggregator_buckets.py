"""Regression tests for daily-bucket labeling (MECE H6).

H6: get_daily_breakdown builds rolling 24h windows ending at `now`
(day_end = now - i days, day_start = day_end - 1 day) but labeled each bucket
with day_start. So the most recent bucket (i=0, the window ending at now) was
labeled YESTERDAY - every bucket was one day early. The fix labels by day_end;
the windows and counts are unchanged.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.services.weekly_review.usage_aggregator import UsageAggregator

NOW = datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)


class _FixedNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def _agg_with_ops(*offsets):
    agg = UsageAggregator()
    for off in offsets:
        agg._operations.append({
            "type": "store",
            "category": "",
            "duration_ms": 0.0,
            "timestamp": (NOW - off).isoformat(),
            "metadata": {},
        })
    return agg


class TestDailyBucketLabel:
    def test_recent_op_labeled_today_not_yesterday(self):
        """An op an hour ago belongs to 'today' (NOW's date), not yesterday."""
        agg = _agg_with_ops(timedelta(hours=1))
        with patch("src.services.weekly_review.usage_aggregator.datetime", _FixedNow):
            breakdown = agg.get_daily_breakdown(days=7)

        by_date = {d["date"]: d for d in breakdown}
        assert "2024-06-15" in by_date, "most recent bucket must be labeled today"
        assert by_date["2024-06-15"]["total"] == 1
        # The op must not be attributed to yesterday.
        assert by_date.get("2024-06-14", {"total": 0})["total"] == 0

    def test_counts_preserved_labels_shift_only(self):
        """Every op in range is still counted exactly once (the fix only relabels)."""
        agg = _agg_with_ops(
            timedelta(hours=1),    # today
            timedelta(hours=25),   # ~1 day ago
            timedelta(hours=49),   # ~2 days ago
        )
        with patch("src.services.weekly_review.usage_aggregator.datetime", _FixedNow):
            breakdown = agg.get_daily_breakdown(days=7)

        assert sum(d["total"] for d in breakdown) == 3
        assert len(breakdown) == 7
        # Buckets are labeled by their day_end date, ending today.
        assert breakdown[-1]["date"] == "2024-06-15"
        assert breakdown[0]["date"] == "2024-06-09"
