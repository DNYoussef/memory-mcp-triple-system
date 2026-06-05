"""Outcome Schema for IMPROVE-001.

Defines data structures for outcomes, patterns, and rule proposals.

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid


class OutcomeType(Enum):
    """Types of outcomes to track."""

    SUCCESS = "success"           # Task completed successfully
    FAILURE = "failure"           # Task failed
    PARTIAL = "partial"           # Partially completed
    ESCALATED = "escalated"       # Escalated to human
    TIMEOUT = "timeout"           # Timed out
    CORRECTION = "correction"     # User corrected output
    APPROVAL = "approval"         # User approved output
    REJECTION = "rejection"       # User rejected output


class OutcomeSource(Enum):
    """Source of outcome data."""

    CONFIDENCE_SCORING = "confidence_scoring"   # CAPTURE-003
    USER_FEEDBACK = "user_feedback"             # Direct user input
    QUALITY_GATE = "quality_gate"               # Quality gate results
    ESCALATION = "escalation"                   # Escalation resolution
    AGENT_EXECUTION = "agent_execution"         # Agent task results
    PIPELINE = "pipeline"                       # Pipeline outcomes


class ProposalStatus(Enum):
    """Status of a rule proposal."""

    PENDING = "pending"           # Awaiting review
    APPROVED = "approved"         # Approved by human
    REJECTED = "rejected"         # Rejected by human
    DEPLOYED = "deployed"         # Successfully deployed
    ROLLED_BACK = "rolled_back"   # Deployment rolled back


class ApprovalDecision(Enum):
    """Human approval decision."""

    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"
    MODIFY = "modify"


@dataclass
class Outcome:
    """An observed outcome to track for improvement."""

    outcome_id: str = field(default_factory=lambda: f"outcome-{uuid.uuid4().hex[:8]}")
    outcome_type: OutcomeType = OutcomeType.SUCCESS
    source: OutcomeSource = OutcomeSource.AGENT_EXECUTION

    # Context
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_type: Optional[str] = None

    # Outcome data
    input_text: str = ""
    output_text: str = ""
    expected_output: Optional[str] = None

    # Metrics
    confidence_score: float = 0.0
    execution_time_ms: int = 0
    token_count: int = 0

    # Classification
    category: str = ""          # e.g., "mode_detection", "entity_extraction"
    subcategory: str = ""       # e.g., "execution", "planning"

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "outcome_id": self.outcome_id,
            "outcome_type": self.outcome_type.value,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "expected_output": self.expected_output,
            "confidence_score": round(self.confidence_score, 4),
            "execution_time_ms": self.execution_time_ms,
            "token_count": self.token_count,
            "category": self.category,
            "subcategory": self.subcategory,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Outcome":
        """Deserialize from dictionary."""
        return cls(
            outcome_id=data.get("outcome_id", f"outcome-{uuid.uuid4().hex[:8]}"),
            outcome_type=OutcomeType(data.get("outcome_type", "success")),
            source=OutcomeSource(data.get("source", "agent_execution")),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            session_id=data.get("session_id"),
            task_id=data.get("task_id"),
            agent_type=data.get("agent_type"),
            input_text=data.get("input_text", ""),
            output_text=data.get("output_text", ""),
            expected_output=data.get("expected_output"),
            confidence_score=data.get("confidence_score", 0.0),
            execution_time_ms=data.get("execution_time_ms", 0),
            token_count=data.get("token_count", 0),
            category=data.get("category", ""),
            subcategory=data.get("subcategory", ""),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )


@dataclass
class Pattern:
    """A detected pattern from outcomes."""

    pattern_id: str = field(default_factory=lambda: f"pattern-{uuid.uuid4().hex[:8]}")
    pattern_type: str = ""           # e.g., "failure_cluster", "correction_trend"

    # Detection info
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 0.0
    sample_size: int = 0

    # Pattern details
    description: str = ""
    affected_category: str = ""      # e.g., "mode_detection"
    affected_subcategory: str = ""   # e.g., "planning"

    # Statistics
    frequency: float = 0.0           # How often pattern occurs
    impact: float = 0.0              # Severity/importance (0-1)
    trend: str = "stable"            # "increasing", "stable", "decreasing"

    # Supporting evidence
    outcome_ids: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "detected_at": self.detected_at,
            "confidence": round(self.confidence, 4),
            "sample_size": self.sample_size,
            "description": self.description,
            "affected_category": self.affected_category,
            "affected_subcategory": self.affected_subcategory,
            "frequency": round(self.frequency, 4),
            "impact": round(self.impact, 4),
            "trend": self.trend,
            "outcome_ids": self.outcome_ids,
            "evidence": self.evidence,
        }


@dataclass
class RuleChange:
    """A specific change to a rule."""

    rule_path: str = ""              # Path to rule file
    rule_section: str = ""           # Section within file
    current_value: str = ""          # Current rule text
    proposed_value: str = ""         # Proposed new text
    change_type: str = "modify"      # "add", "modify", "remove"
    rationale: str = ""              # Why this change

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "rule_path": self.rule_path,
            "rule_section": self.rule_section,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "change_type": self.change_type,
            "rationale": self.rationale,
        }


@dataclass
class RuleProposal:
    """A proposal to update rules based on patterns."""

    proposal_id: str = field(default_factory=lambda: f"proposal-{uuid.uuid4().hex[:8]}")
    status: ProposalStatus = ProposalStatus.PENDING

    # Timing
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewed_at: Optional[str] = None
    deployed_at: Optional[str] = None

    # Source
    pattern_id: str = ""             # Pattern that triggered this
    pattern_confidence: float = 0.0

    # Proposal details
    title: str = ""
    description: str = ""
    impact_assessment: str = ""
    risk_level: str = "low"          # "low", "medium", "high"

    # Changes
    changes: List[RuleChange] = field(default_factory=list)

    # Expected improvement
    expected_improvement: Dict[str, float] = field(default_factory=dict)

    # Review
    reviewer: Optional[str] = None
    decision: Optional[ApprovalDecision] = None
    review_notes: str = ""

    # Rollback info
    rollback_changes: List[RuleChange] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "deployed_at": self.deployed_at,
            "pattern_id": self.pattern_id,
            "pattern_confidence": round(self.pattern_confidence, 4),
            "title": self.title,
            "description": self.description,
            "impact_assessment": self.impact_assessment,
            "risk_level": self.risk_level,
            "changes": [c.to_dict() for c in self.changes],
            "expected_improvement": self.expected_improvement,
            "reviewer": self.reviewer,
            "decision": self.decision.value if self.decision else None,
            "review_notes": self.review_notes,
            "rollback_changes": [c.to_dict() for c in self.rollback_changes],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleProposal":
        """Deserialize from dictionary."""
        changes = [
            RuleChange(**c) if isinstance(c, dict) else c
            for c in data.get("changes", [])
        ]
        rollback_changes = [
            RuleChange(**c) if isinstance(c, dict) else c
            for c in data.get("rollback_changes", [])
        ]

        return cls(
            proposal_id=data.get("proposal_id", f"proposal-{uuid.uuid4().hex[:8]}"),
            status=ProposalStatus(data.get("status", "pending")),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            reviewed_at=data.get("reviewed_at"),
            deployed_at=data.get("deployed_at"),
            pattern_id=data.get("pattern_id", ""),
            pattern_confidence=data.get("pattern_confidence", 0.0),
            title=data.get("title", ""),
            description=data.get("description", ""),
            impact_assessment=data.get("impact_assessment", ""),
            risk_level=data.get("risk_level", "low"),
            changes=changes,
            expected_improvement=data.get("expected_improvement", {}),
            reviewer=data.get("reviewer"),
            decision=ApprovalDecision(data["decision"]) if data.get("decision") else None,
            review_notes=data.get("review_notes", ""),
            rollback_changes=rollback_changes,
        )
