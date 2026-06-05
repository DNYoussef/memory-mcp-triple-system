"""Improvement Coordinator for IMPROVE-001.

Orchestrates the full improvement pipeline:
Outcomes -> Patterns -> Proposals -> Approval -> Deployment

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.services.improvement.outcome_schema import (
    Outcome,
    OutcomeType,
    Pattern,
    RuleProposal,
    ProposalStatus,
    ApprovalDecision,
)
from src.services.improvement.outcome_measurement import (
    OutcomeMeasurementService,
    OutcomeMeasurementConfig,
)
from src.services.improvement.pattern_detection import (
    PatternDetectionService,
    PatternDetectionConfig,
)
from src.services.improvement.rule_proposal import (
    RuleProposalGenerator,
    RuleProposalConfig,
)
from src.services.improvement.approval_gate import (
    HumanApprovalGate,
    ApprovalGateConfig,
    ApprovalPriority,
)
from src.services.improvement.rule_deployment import (
    RuleDeploymentService,
    RuleDeploymentConfig,
    DeploymentResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ImprovementConfig:
    """Configuration for improvement coordinator."""

    auto_detect_patterns: bool = True
    auto_generate_proposals: bool = True
    min_outcomes_for_detection: int = 20
    pattern_detection_hours: int = 168  # 7 days


@dataclass
class ImprovementCycleResult:
    """Result of running an improvement cycle."""

    cycle_id: str
    started_at: str
    completed_at: str

    # Outcomes analyzed
    outcomes_analyzed: int = 0

    # Patterns detected
    patterns_detected: int = 0
    patterns: List[Pattern] = field(default_factory=list)

    # Proposals generated
    proposals_generated: int = 0
    proposals: List[RuleProposal] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outcomes_analyzed": self.outcomes_analyzed,
            "patterns_detected": self.patterns_detected,
            "patterns": [p.to_dict() for p in self.patterns],
            "proposals_generated": self.proposals_generated,
            "proposals": [p.to_dict() for p in self.proposals],
        }


class ImprovementCoordinator:
    """Coordinates the improvement pipeline.

    Full loop:
    1. Measure outcomes (from CAPTURE-003 and other sources)
    2. Detect patterns in outcomes
    3. Generate rule proposals from patterns
    4. Human approval gate
    5. Deploy approved rules
    """

    def __init__(
        self,
        config: Optional[ImprovementConfig] = None,
        base_path: Optional[str] = None,
    ):
        """Initialize improvement coordinator.

        Args:
            config: Coordinator configuration
            base_path: Base path for file operations
        """
        self.config = config or ImprovementConfig()

        # Initialize services
        self.outcome_service = OutcomeMeasurementService()
        self.pattern_service = PatternDetectionService()
        self.proposal_generator = RuleProposalGenerator()
        self.approval_gate = HumanApprovalGate()
        self.deployment_service = RuleDeploymentService(base_path=base_path)

        # Cycle tracking
        self._cycles: List[ImprovementCycleResult] = []
        self._cycle_count = 0

    def run_improvement_cycle(
        self,
        category: Optional[str] = None,
    ) -> ImprovementCycleResult:
        """Run a full improvement cycle.

        Args:
            category: Optional category to focus on

        Returns:
            Cycle result
        """
        self._cycle_count += 1
        cycle_id = f"cycle-{self._cycle_count}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        started_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"Starting improvement cycle {cycle_id}")

        # 1. Get recent outcomes
        outcomes = self.outcome_service.get_recent_outcomes(
            limit=1000,
            hours=self.config.pattern_detection_hours,
        )

        if category:
            outcomes = [o for o in outcomes if o.category == category]

        logger.info(f"Analyzing {len(outcomes)} outcomes")

        # 2. Detect patterns
        patterns = []
        if (
            len(outcomes) >= self.config.min_outcomes_for_detection
            and self.config.auto_detect_patterns
        ):
            patterns = self.pattern_service.detect_patterns(outcomes, category)
            logger.info(f"Detected {len(patterns)} patterns")

        # 3. Generate proposals
        proposals = []
        if patterns and self.config.auto_generate_proposals:
            proposals = self.proposal_generator.generate_proposals_from_patterns(patterns)
            logger.info(f"Generated {len(proposals)} proposals")

            # 4. Submit to approval gate
            for proposal in proposals:
                self.approval_gate.submit_for_approval(proposal)

        completed_at = datetime.now(timezone.utc).isoformat()

        result = ImprovementCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            outcomes_analyzed=len(outcomes),
            patterns_detected=len(patterns),
            patterns=patterns,
            proposals_generated=len(proposals),
            proposals=proposals,
        )

        self._cycles.append(result)

        return result

    def record_outcome(self, outcome: Outcome) -> str:
        """Record a new outcome.

        Args:
            outcome: Outcome to record

        Returns:
            Outcome ID
        """
        return self.outcome_service.record_outcome(outcome)

    def record_from_confidence_result(
        self,
        classification_result: Dict[str, Any],
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Record outcome from CAPTURE-003 confidence result.

        Args:
            classification_result: Classification result
            session_id: Session ID
            task_id: Task ID

        Returns:
            Outcome ID
        """
        return self.outcome_service.record_from_confidence_result(
            classification_result,
            session_id,
            task_id,
        )

    def record_user_feedback(
        self,
        input_text: str,
        output_text: str,
        feedback_type: str,
        correct_output: Optional[str] = None,
        category: str = "",
    ) -> str:
        """Record user feedback as outcome.

        Args:
            input_text: Original input
            output_text: System output
            feedback_type: "correction", "approval", or "rejection"
            correct_output: Correct output if correction
            category: Category

        Returns:
            Outcome ID
        """
        return self.outcome_service.record_user_feedback(
            input_text=input_text,
            output_text=output_text,
            feedback_type=feedback_type,
            correct_output=correct_output,
            category=category,
        )

    def detect_patterns(
        self,
        category: Optional[str] = None,
        hours: int = 168,
    ) -> List[Pattern]:
        """Detect patterns in recent outcomes.

        Args:
            category: Optional category filter
            hours: Time window in hours

        Returns:
            List of detected patterns
        """
        outcomes = self.outcome_service.get_recent_outcomes(
            limit=1000,
            hours=hours,
        )

        if category:
            outcomes = [o for o in outcomes if o.category == category]

        return self.pattern_service.detect_patterns(outcomes, category)

    def generate_proposals(
        self,
        patterns: Optional[List[Pattern]] = None,
    ) -> List[RuleProposal]:
        """Generate proposals from patterns.

        Args:
            patterns: Patterns to generate proposals from (or detect new)

        Returns:
            List of proposals
        """
        if patterns is None:
            patterns = self.detect_patterns()

        return self.proposal_generator.generate_proposals_from_patterns(patterns)

    def get_pending_approvals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending approval requests.

        Args:
            limit: Maximum results

        Returns:
            List of pending requests
        """
        requests = self.approval_gate.get_pending_requests(limit=limit)
        return [r.to_dict() for r in requests]

    def approve_proposal(
        self,
        proposal_id: str,
        reviewer: str,
        notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Approve a proposal.

        Args:
            proposal_id: Proposal ID
            reviewer: Reviewer identifier
            notes: Approval notes

        Returns:
            Approval result or None
        """
        request_id = f"req-{proposal_id}"
        result = self.approval_gate.approve(request_id, reviewer, notes)
        return result.to_dict() if result else None

    def reject_proposal(
        self,
        proposal_id: str,
        reviewer: str,
        reason: str,
    ) -> Optional[Dict[str, Any]]:
        """Reject a proposal.

        Args:
            proposal_id: Proposal ID
            reviewer: Reviewer identifier
            reason: Rejection reason

        Returns:
            Rejection result or None
        """
        request_id = f"req-{proposal_id}"
        result = self.approval_gate.reject(request_id, reviewer, reason)
        return result.to_dict() if result else None

    def deploy_approved(
        self,
        dry_run: bool = True,
    ) -> List[DeploymentResult]:
        """Deploy all approved proposals.

        Args:
            dry_run: Whether to do dry run

        Returns:
            List of deployment results
        """
        results = []

        approved = self.approval_gate.get_approved_proposals(not_deployed=True)

        for proposal in approved:
            result = self.deployment_service.deploy(proposal, dry_run=dry_run)
            results.append(result)

        return results

    def deploy_proposal(
        self,
        proposal_id: str,
        dry_run: bool = True,
    ) -> Optional[DeploymentResult]:
        """Deploy a specific approved proposal.

        Args:
            proposal_id: Proposal ID
            dry_run: Whether to do dry run

        Returns:
            Deployment result or None
        """
        proposal = self.proposal_generator.get_proposal(proposal_id)

        if not proposal:
            logger.warning(f"Proposal {proposal_id} not found")
            return None

        if proposal.status != ProposalStatus.APPROVED:
            logger.warning(f"Proposal {proposal_id} not approved")
            return None

        return self.deployment_service.deploy(proposal, dry_run=dry_run)

    def rollback_deployment(self, proposal_id: str) -> Dict[str, Any]:
        """Rollback a deployment.

        Args:
            proposal_id: Proposal ID

        Returns:
            Rollback result
        """
        result = self.deployment_service.rollback(proposal_id)
        return result.to_dict()

    def get_metrics(
        self,
        category: Optional[str] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get improvement metrics.

        Args:
            category: Optional category filter
            hours: Time window

        Returns:
            Metrics dictionary
        """
        outcome_metrics = self.outcome_service.calculate_metrics(category, hours)

        return {
            "outcomes": outcome_metrics,
            "patterns": self.pattern_service.get_stats(),
            "proposals": self.proposal_generator.get_stats(),
            "approvals": self.approval_gate.get_stats(),
            "deployments": self.deployment_service.get_stats(),
            "cycles_run": len(self._cycles),
        }

    def get_recent_cycles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent improvement cycles.

        Args:
            limit: Maximum results

        Returns:
            List of cycle results
        """
        return [c.to_dict() for c in self._cycles[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get coordinator statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "outcome_service": self.outcome_service.get_stats(),
            "pattern_service": self.pattern_service.get_stats(),
            "proposal_generator": self.proposal_generator.get_stats(),
            "approval_gate": self.approval_gate.get_stats(),
            "deployment_service": self.deployment_service.get_stats(),
            "cycles_run": len(self._cycles),
        }


# Singleton instance
_coordinator: Optional[ImprovementCoordinator] = None


def get_improvement_coordinator() -> ImprovementCoordinator:
    """Get the global improvement coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = ImprovementCoordinator()
    return _coordinator


def initialize_improvement_coordinator(
    config: Optional[ImprovementConfig] = None,
    base_path: Optional[str] = None,
) -> ImprovementCoordinator:
    """Initialize the global improvement coordinator.

    Args:
        config: Coordinator configuration
        base_path: Base path for file operations

    Returns:
        Initialized coordinator
    """
    global _coordinator
    _coordinator = ImprovementCoordinator(config, base_path)
    return _coordinator
