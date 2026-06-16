"""Regression tests for DriftDetector.get_candidates_for_cleanup (MECE E11).

E11 ("DriftSeverity.NONE ValueError"): get_candidates_for_cleanup built a local
severity_order list that omitted DriftSeverity.NONE, then called
severity_order.index(signal.severity). _score_to_severity returns NONE for any
drift_score below the LOW threshold, and detect_confidence_drift emits such a
signal whenever confidence is just below the threshold - so a NONE-severity
signal reaches report.signals and .index(NONE) raised ValueError. Passing
min_severity=DriftSeverity.NONE raised the same way.

The fix includes NONE as the lowest rung of severity_order, so .index() is total
over the enum: NONE signals rank lowest (included only when min_severity=NONE).
"""

from datetime import datetime

from src.memory.drift_detector import (
    DriftDetector,
    DriftReport,
    DriftSignal,
    DriftSeverity,
)


def _signal(chunk_id, severity, drift_type="confidence"):
    return DriftSignal(
        chunk_id=chunk_id,
        drift_score=0.1,
        severity=severity,
        drift_type=drift_type,
        detected_at=datetime(2024, 1, 1),
        context={},
    )


def _report(signals):
    return DriftReport(
        run_id="r",
        started_at=datetime(2024, 1, 1),
        completed_at=datetime(2024, 1, 1),
        chunks_analyzed=len(signals),
        signals_detected=len(signals),
        by_severity={},
        by_type={},
        signals=signals,
    )


class TestGetCandidatesForCleanupNoneSeverity:
    def test_none_severity_signal_does_not_raise(self):
        """A NONE-severity signal in the report must not raise; at the default
        min_severity (MEDIUM) it is excluded, while a real MEDIUM signal in the
        same report is still returned."""
        detector = DriftDetector()
        report = _report(
            [
                _signal("none_chunk", DriftSeverity.NONE),
                _signal("medium_chunk", DriftSeverity.MEDIUM),
            ]
        )

        candidates = detector.get_candidates_for_cleanup(report)

        assert "none_chunk" not in candidates
        assert "medium_chunk" in candidates

    def test_min_severity_none_includes_everything(self):
        """min_severity=NONE must not raise and includes the lowest rung."""
        detector = DriftDetector()
        report = _report(
            [
                _signal("none_chunk", DriftSeverity.NONE),
                _signal("high_chunk", DriftSeverity.HIGH),
            ]
        )

        candidates = detector.get_candidates_for_cleanup(
            report, min_severity=DriftSeverity.NONE
        )

        assert "none_chunk" in candidates
        assert "high_chunk" in candidates

    def test_real_confidence_drift_none_signal_flows_through(self):
        """End-to-end: detect_confidence_drift emits a NONE-severity signal when
        confidence is just below the threshold, and get_candidates_for_cleanup
        over a report containing it must not raise."""
        detector = DriftDetector()  # confidence_threshold=0.4
        signal = detector.detect_confidence_drift("c1", current_confidence=0.38)

        assert signal is not None
        assert signal.severity == DriftSeverity.NONE

        report = _report([signal])
        # Must not raise regardless of the requested floor.
        assert detector.get_candidates_for_cleanup(report) == []
        assert detector.get_candidates_for_cleanup(
            report, min_severity=DriftSeverity.NONE
        ) == ["c1"]
