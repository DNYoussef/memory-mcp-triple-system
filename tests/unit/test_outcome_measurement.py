"""Regression tests for outcome recall filtering (MECE H10)."""

from datetime import datetime, timedelta, timezone

from src.services.improvement.outcome_measurement import OutcomeMeasurementService
from src.services.improvement.outcome_schema import (
    Outcome,
    OutcomeSource,
    OutcomeType,
)


NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def _outcome(
    outcome_id, *, timestamp, category="search", outcome_type=OutcomeType.SUCCESS
):
    return Outcome(
        outcome_id=outcome_id,
        outcome_type=outcome_type,
        source=OutcomeSource.AGENT_EXECUTION,
        timestamp=timestamp.isoformat(),
        category=category,
    )


def _service_with_sparse_recent_matches(total=10, recent_count=2):
    service = OutcomeMeasurementService()
    stale_time = NOW - timedelta(days=10)
    recent_time = NOW - timedelta(hours=1)

    for index in range(recent_count):
        service.record_outcome(_outcome(f"recent-{index}", timestamp=recent_time))

    for index in range(total - recent_count):
        service.record_outcome(_outcome(f"stale-{index}", timestamp=stale_time))

    return service


class TestOutcomeRecallFilterBeforeLimit:
    def test_category_query_filters_since_before_applying_limit(self):
        service = _service_with_sparse_recent_matches()

        outcomes = service.get_outcomes_by_category(
            "search",
            limit=2,
            since=NOW - timedelta(days=1),
        )

        assert [o.outcome_id for o in outcomes] == ["recent-1", "recent-0"]

    def test_type_query_filters_since_before_applying_limit(self):
        service = _service_with_sparse_recent_matches()

        outcomes = service.get_outcomes_by_type(
            OutcomeType.SUCCESS,
            limit=2,
            since=NOW - timedelta(days=1),
        )

        assert [o.outcome_id for o in outcomes] == ["recent-1", "recent-0"]
