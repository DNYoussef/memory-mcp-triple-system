"""Human Approval Gate for IMPROVE-001.

Manages human review and approval of rule proposals.

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.services.improvement.outcome_schema import (
    RuleProposal,
    RuleChange,
    ProposalStatus,
    ApprovalDecision,
)

logger = logging.getLogger(__name__)


class ApprovalPriority(Enum):
    """Priority levels for approval queue."""

    URGENT = 1        # High impact, needs immediate attention
    HIGH = 2          # Important changes
    NORMAL = 3        # Standard proposals
    LOW = 4           # Minor improvements


@dataclass
class ApprovalRequest:
    """A request for human approval."""

    request_id: str
    proposal: RuleProposal
    priority: ApprovalPriority = ApprovalPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Review state
    assigned_to: Optional[str] = None
    reviewed_at: Optional[str] = None
    decision: Optional[ApprovalDecision] = None
    notes: str = ""

    # Modifications (if decision is MODIFY)
    modified_changes: Optional[List[RuleChange]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "proposal": self.proposal.to_dict(),
            "priority": self.priority.value,
            "created_at": self.created_at,
            "assigned_to": self.assigned_to,
            "reviewed_at": self.reviewed_at,
            "decision": self.decision.value if self.decision else None,
            "notes": self.notes,
            "modified_changes": [c.to_dict() for c in self.modified_changes] if self.modified_changes else None,
        }


@dataclass
class ApprovalGateConfig:
    """Configuration for human approval gate."""

    auto_approve_low_risk: bool = False
    require_approval_for_high_risk: bool = True
    approval_timeout_hours: int = 72
    max_pending_requests: int = 100


class HumanApprovalGate:
    """Gate for human approval of rule proposals.

    Manages the approval workflow:
    1. Queue proposals for review
    2. Prioritize by risk/impact
    3. Track reviewer assignments
    4. Record decisions and modifications
    """

    def __init__(self, config: Optional[ApprovalGateConfig] = None):
        """Initialize approval gate.

        Args:
            config: Gate configuration
        """
        self.config = config or ApprovalGateConfig()

        # Pending requests
        self._pending: Dict[str, ApprovalRequest] = {}
        self._completed: Dict[str, ApprovalRequest] = {}

        # Statistics
        self._stats = {
            "total_submitted": 0,
            "approved": 0,
            "rejected": 0,
            "modified": 0,
            "deferred": 0,
        }

    def submit_for_approval(
        self,
        proposal: RuleProposal,
        priority: Optional[ApprovalPriority] = None,
    ) -> ApprovalRequest:
        """Submit a proposal for human approval.

        Args:
            proposal: Proposal to submit
            priority: Optional priority override

        Returns:
            Approval request
        """
        # Determine priority
        if priority is None:
            priority = self._calculate_priority(proposal)

        # Check for auto-approval
        if self._can_auto_approve(proposal, priority):
            logger.info(f"Auto-approving low-risk proposal: {proposal.proposal_id}")
            proposal.status = ProposalStatus.APPROVED
            proposal.decision = ApprovalDecision.APPROVE
            proposal.reviewed_at = datetime.now(timezone.utc).isoformat()
            proposal.reviewer = "auto"

            request = ApprovalRequest(
                request_id=f"req-{proposal.proposal_id}",
                proposal=proposal,
                priority=priority,
                decision=ApprovalDecision.APPROVE,
                notes="Auto-approved: low risk",
            )
            self._completed[request.request_id] = request
            self._stats["approved"] += 1
            return request

        # Create approval request
        request = ApprovalRequest(
            request_id=f"req-{proposal.proposal_id}",
            proposal=proposal,
            priority=priority,
        )

        self._pending[request.request_id] = request
        self._stats["total_submitted"] += 1

        logger.info(f"Submitted proposal {proposal.proposal_id} for approval (priority: {priority.name})")

        return request

    def get_pending_requests(
        self,
        limit: int = 50,
        priority_filter: Optional[ApprovalPriority] = None,
    ) -> List[ApprovalRequest]:
        """Get pending approval requests.

        Args:
            limit: Maximum results
            priority_filter: Optional priority filter

        Returns:
            List of pending requests
        """
        requests = list(self._pending.values())

        if priority_filter:
            requests = [r for r in requests if r.priority == priority_filter]

        # Sort by priority then creation time
        requests.sort(key=lambda r: (r.priority.value, r.created_at))

        return requests[:limit]

    def get_next_for_review(self) -> Optional[ApprovalRequest]:
        """Get next request for review (highest priority).

        Returns:
            Next request or None
        """
        pending = self.get_pending_requests(limit=1)
        return pending[0] if pending else None

    def assign_reviewer(
        self,
        request_id: str,
        reviewer: str,
    ) -> Optional[ApprovalRequest]:
        """Assign a reviewer to a request.

        Args:
            request_id: Request ID
            reviewer: Reviewer identifier

        Returns:
            Updated request or None
        """
        request = self._pending.get(request_id)
        if not request:
            return None

        request.assigned_to = reviewer
        logger.info(f"Assigned {request_id} to reviewer {reviewer}")

        return request

    def record_decision(
        self,
        request_id: str,
        decision: ApprovalDecision,
        reviewer: str,
        notes: str = "",
        modified_changes: Optional[List[RuleChange]] = None,
    ) -> Optional[ApprovalRequest]:
        """Record approval decision.

        Args:
            request_id: Request ID
            decision: Approval decision
            reviewer: Reviewer identifier
            notes: Review notes
            modified_changes: Modified changes if decision is MODIFY

        Returns:
            Updated request or None
        """
        request = self._pending.get(request_id)
        if not request:
            logger.warning(f"Request {request_id} not found")
            return None

        # Update request
        request.reviewed_at = datetime.now(timezone.utc).isoformat()
        request.decision = decision
        request.assigned_to = reviewer
        request.notes = notes

        if modified_changes:
            request.modified_changes = modified_changes

        # Update proposal
        proposal = request.proposal
        proposal.reviewed_at = request.reviewed_at
        proposal.reviewer = reviewer
        proposal.decision = decision
        proposal.review_notes = notes

        if decision == ApprovalDecision.APPROVE:
            proposal.status = ProposalStatus.APPROVED
            self._stats["approved"] += 1
        elif decision == ApprovalDecision.REJECT:
            proposal.status = ProposalStatus.REJECTED
            self._stats["rejected"] += 1
        elif decision == ApprovalDecision.MODIFY:
            if modified_changes:
                proposal.changes = modified_changes
            proposal.status = ProposalStatus.APPROVED
            self._stats["modified"] += 1
        elif decision == ApprovalDecision.DEFER:
            self._stats["deferred"] += 1
            # Keep in pending queue
            return request

        # Move to completed
        del self._pending[request_id]
        self._completed[request_id] = request

        logger.info(f"Recorded decision {decision.value} for {request_id}")

        return request

    def approve(
        self,
        request_id: str,
        reviewer: str,
        notes: str = "",
    ) -> Optional[ApprovalRequest]:
        """Approve a request.

        Args:
            request_id: Request ID
            reviewer: Reviewer identifier
            notes: Approval notes

        Returns:
            Updated request or None
        """
        return self.record_decision(
            request_id,
            ApprovalDecision.APPROVE,
            reviewer,
            notes,
        )

    def reject(
        self,
        request_id: str,
        reviewer: str,
        reason: str,
    ) -> Optional[ApprovalRequest]:
        """Reject a request.

        Args:
            request_id: Request ID
            reviewer: Reviewer identifier
            reason: Rejection reason

        Returns:
            Updated request or None
        """
        return self.record_decision(
            request_id,
            ApprovalDecision.REJECT,
            reviewer,
            reason,
        )

    def modify_and_approve(
        self,
        request_id: str,
        reviewer: str,
        modified_changes: List[RuleChange],
        notes: str = "",
    ) -> Optional[ApprovalRequest]:
        """Modify proposal and approve.

        Args:
            request_id: Request ID
            reviewer: Reviewer identifier
            modified_changes: Modified changes
            notes: Modification notes

        Returns:
            Updated request or None
        """
        return self.record_decision(
            request_id,
            ApprovalDecision.MODIFY,
            reviewer,
            notes,
            modified_changes,
        )

    def get_approved_proposals(
        self,
        limit: int = 50,
        not_deployed: bool = True,
    ) -> List[RuleProposal]:
        """Get approved proposals ready for deployment.

        Args:
            limit: Maximum results
            not_deployed: Only return not-yet-deployed proposals

        Returns:
            List of approved proposals
        """
        approved = []

        for request in self._completed.values():
            proposal = request.proposal
            if proposal.status == ProposalStatus.APPROVED:
                if not_deployed and proposal.deployed_at:
                    continue
                approved.append(proposal)

        # Sort by review time
        approved.sort(key=lambda p: p.reviewed_at or "", reverse=True)

        return approved[:limit]

    def format_for_review(self, request: ApprovalRequest) -> str:
        """Format request for human review.

        Args:
            request: Request to format

        Returns:
            Formatted string for review
        """
        proposal = request.proposal

        lines = [
            "=" * 60,
            f"APPROVAL REQUEST: {request.request_id}",
            f"Priority: {request.priority.name}",
            f"Submitted: {request.created_at}",
            "=" * 60,
            "",
            f"PROPOSAL: {proposal.title}",
            f"Pattern: {proposal.pattern_id}",
            f"Risk Level: {proposal.risk_level.upper()}",
            "",
            "DESCRIPTION:",
            proposal.description,
            "",
            "IMPACT ASSESSMENT:",
            proposal.impact_assessment,
            "",
            "PROPOSED CHANGES:",
        ]

        for i, change in enumerate(proposal.changes, 1):
            lines.append(f"\n  [{i}] {change.rule_path}")
            lines.append(f"      Section: {change.rule_section}")
            lines.append(f"      Type: {change.change_type}")
            lines.append(f"      Rationale: {change.rationale}")

        lines.extend([
            "",
            "EXPECTED IMPROVEMENT:",
        ])
        for metric, value in proposal.expected_improvement.items():
            lines.append(f"  - {metric}: {value}")

        lines.extend([
            "",
            "=" * 60,
            "OPTIONS: [A]pprove  [R]eject  [M]odify  [D]efer",
            "=" * 60,
        ])

        return "\n".join(lines)

    def _calculate_priority(self, proposal: RuleProposal) -> ApprovalPriority:
        """Calculate priority from proposal."""
        if proposal.risk_level == "high":
            return ApprovalPriority.URGENT

        if proposal.pattern_confidence > 0.85:
            return ApprovalPriority.HIGH

        expected = proposal.expected_improvement.get("expected_reduction", 0)
        if expected > 0.5:
            return ApprovalPriority.HIGH

        return ApprovalPriority.NORMAL

    def _can_auto_approve(
        self,
        proposal: RuleProposal,
        priority: ApprovalPriority,
    ) -> bool:
        """Check if proposal can be auto-approved."""
        if not self.config.auto_approve_low_risk:
            return False

        if self.config.require_approval_for_high_risk and proposal.risk_level == "high":
            return False

        if priority in (ApprovalPriority.URGENT, ApprovalPriority.HIGH):
            return False

        return proposal.risk_level == "low"

    def get_stats(self) -> Dict[str, Any]:
        """Get gate statistics."""
        return {
            "total_submitted": self._stats["total_submitted"],
            "pending": len(self._pending),
            "approved": self._stats["approved"],
            "rejected": self._stats["rejected"],
            "modified": self._stats["modified"],
            "deferred": self._stats["deferred"],
            "approval_rate": round(
                self._stats["approved"] / max(1, self._stats["total_submitted"] - len(self._pending)),
                4,
            ),
        }
