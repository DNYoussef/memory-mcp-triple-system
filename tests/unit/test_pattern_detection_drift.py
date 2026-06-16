"""Regression tests for category-drift detection (MECE H5).

H5: _detect_category_drift compared the success rate of each category across the
first vs second half of the window, but iterated the UNION of categories and
substituted 0.5 for whichever half a category was missing from
(first_rates.get(cat, 0.5)). A category present in only one half therefore got a
fabricated drift of rate-0.5 >= 0.15 and produced a false CATEGORY_DRIFT pattern
(-> false rule proposals) from data that simply did not exist in the other half.

Fix: only compare categories present in BOTH halves; a missing baseline yields
no drift.
"""

from src.services.improvement.pattern_detection import (
    PatternDetectionService,
    PatternDetectionConfig,
    PatternType,
)
from src.services.improvement.outcome_schema import Outcome, OutcomeType


def _outcome(category, success, ts):
    return Outcome(
        category=category,
        outcome_type=OutcomeType.SUCCESS if success else OutcomeType.FAILURE,
        timestamp=ts,
    )


def _svc():
    return PatternDetectionService(PatternDetectionConfig(min_sample_size=2))


class TestCategoryDriftBaseline:
    def test_category_in_one_half_only_is_not_drift(self):
        """'A' only in the first half, 'B' only in the second half: neither has a
        comparable baseline, so no CATEGORY_DRIFT may be fabricated."""
        outcomes = [
            _outcome("A", True, "2024-01-01T00:00:01"),
            _outcome("A", True, "2024-01-01T00:00:02"),
            _outcome("B", True, "2024-01-01T00:00:03"),
            _outcome("B", False, "2024-01-01T00:00:04"),
        ]
        patterns = _svc()._detect_category_drift(outcomes)
        drift_cats = {
            p.affected_category
            for p in patterns
            if p.pattern_type == PatternType.CATEGORY_DRIFT
        }
        assert (
            drift_cats == set()
        ), f"fabricated drift from missing baseline: {drift_cats}"

    def test_real_drift_in_both_halves_is_detected(self):
        """'A' present in both halves with a real rate change (1.0 -> 0.0) is
        still reported - the fix only suppresses missing-baseline fabrication."""
        outcomes = [
            _outcome("A", True, "2024-01-01T00:00:01"),
            _outcome("A", True, "2024-01-01T00:00:02"),
            _outcome("A", False, "2024-01-01T00:00:03"),
            _outcome("A", False, "2024-01-01T00:00:04"),
        ]
        patterns = _svc()._detect_category_drift(outcomes)
        drift = [
            p
            for p in patterns
            if p.pattern_type == PatternType.CATEGORY_DRIFT
            and p.affected_category == "A"
        ]
        assert len(drift) == 1
        assert drift[0].evidence["first_rate"] == 1.0
        assert drift[0].evidence["second_rate"] == 0.0
