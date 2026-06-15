"""Regression tests for QualityGateAggregator weighted_min (MECE H3).

H3 ("weighted_min discards weighting"): the weighted_min branch computed
weighted_scores = [s.score * w], found the index of the minimum weighted score,
then returned scores[min_idx].score - the RAW (unweighted) score of that check.
The weighting was used only to pick which check, never to shape the output, so
gate_weights had no effect on overall_score.

The fix returns the weighted minimum itself (clamped to [0, 1], since a weight
> 1 can push a weighted score past 1.0), so the weights actually drive the
conservative aggregate.
"""

from src.services.confidence.quality_gate import (
    QualityGateAggregator,
    QualityGateConfig,
    GateType,
)


def _gate(weights, method="weighted_min"):
    return QualityGateAggregator(
        QualityGateConfig(
            aggregation_method=method,
            gate_weights=weights,
            pass_threshold=0.6,
            warn_threshold=0.5,
            min_checks=1,
        )
    )


class TestWeightedMinAggregation:
    def test_weights_shape_the_output(self):
        """With non-uniform weights, overall_score is the weighted minimum, not
        the raw score of the min-weighted check. checks a(0.8)*0.5=0.40 and
        b(0.6)*1.0=0.60 -> min weighted 0.40 (check a). Old code returned a's
        RAW score 0.80; the fix returns 0.40."""
        gate = _gate({"a": 0.5, "b": 1.0})
        gate.add_confidence_score(GateType.CUSTOM, "a", 0.8)
        gate.add_confidence_score(GateType.CUSTOM, "b", 0.6)

        result = gate.evaluate()

        assert result.overall_score == 0.4
        assert result.overall_score != 0.8  # the discarded-weighting bug value

    def test_uniform_weights_match_plain_minimum(self):
        """With all weights 1.0, weighted_min reduces to the plain minimum raw
        score - the common path is preserved (no regression)."""
        gate = _gate({"a": 1.0, "b": 1.0})
        gate.add_confidence_score(GateType.CUSTOM, "a", 0.8)
        gate.add_confidence_score(GateType.CUSTOM, "b", 0.6)

        result = gate.evaluate()

        assert result.overall_score == 0.6

    def test_weighted_min_clamped_to_unit_interval(self):
        """A weight > 1 can push every weighted score past 1.0; the aggregate
        must stay in [0, 1]. Both checks score 1.0 with weights 1.2 and 1.5 ->
        min weighted 1.2 -> clamped to 1.0."""
        gate = _gate({"a": 1.2, "b": 1.5})
        gate.add_confidence_score(GateType.CUSTOM, "a", 1.0)
        gate.add_confidence_score(GateType.CUSTOM, "b", 1.0)

        result = gate.evaluate()

        assert result.overall_score == 1.0
