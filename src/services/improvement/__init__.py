"""IMPROVE-001: Rule Update Automation from Outcomes.

Connects outcomes to rule updates automatically (Level 8: IMPROVE).
Loop: Outcome measurement -> Pattern detection -> Rule proposal -> Human approval -> Rule deployment

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

from src.services.improvement.outcome_schema import (
    Outcome,
    OutcomeType,
    OutcomeSource,
    RuleProposal,
    ProposalStatus,
    ApprovalDecision,
)
from src.services.improvement.outcome_measurement import OutcomeMeasurementService
from src.services.improvement.pattern_detection import PatternDetectionService
from src.services.improvement.rule_proposal import RuleProposalGenerator
from src.services.improvement.approval_gate import HumanApprovalGate
from src.services.improvement.rule_deployment import RuleDeploymentService
from src.services.improvement.improvement_coordinator import ImprovementCoordinator

__all__ = [
    "Outcome",
    "OutcomeType",
    "OutcomeSource",
    "RuleProposal",
    "ProposalStatus",
    "ApprovalDecision",
    "OutcomeMeasurementService",
    "PatternDetectionService",
    "RuleProposalGenerator",
    "HumanApprovalGate",
    "RuleDeploymentService",
    "ImprovementCoordinator",
]
