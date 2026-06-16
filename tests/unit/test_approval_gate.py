"""Regression tests for approval-gate accounting (MECE H9)."""

from src.services.improvement.approval_gate import (
    ApprovalGateConfig,
    HumanApprovalGate,
)
from src.services.improvement.outcome_schema import RuleProposal


def _proposal(proposal_id, risk_level="low"):
    return RuleProposal(
        proposal_id=proposal_id,
        pattern_confidence=0.25,
        title=f"Proposal {proposal_id}",
        description="Test proposal",
        impact_assessment="Low impact",
        risk_level=risk_level,
    )


class TestApprovalGateStats:
    def test_auto_approval_counts_as_submitted_and_rate_stays_bounded(self):
        gate = HumanApprovalGate(ApprovalGateConfig(auto_approve_low_risk=True))

        gate.submit_for_approval(_proposal("auto-1"))

        stats = gate.get_stats()
        assert stats["total_submitted"] == 1
        assert stats["approved"] == 1
        assert stats["pending"] == 0
        assert stats["approval_rate"] == 1.0

    def test_approval_rate_includes_auto_and_manual_completed_requests(self):
        gate = HumanApprovalGate(ApprovalGateConfig(auto_approve_low_risk=True))

        gate.submit_for_approval(_proposal("auto-1"))
        manual = gate.submit_for_approval(_proposal("manual-1", risk_level="medium"))

        assert gate.get_stats()["approval_rate"] == 1.0

        gate.reject(manual.request_id, reviewer="reviewer", reason="No")

        stats = gate.get_stats()
        assert stats["total_submitted"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["pending"] == 0
        assert stats["approval_rate"] == 0.5
