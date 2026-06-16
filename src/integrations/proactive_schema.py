"""Proactive Context Injection Schema.

Defines triggers and context injection rules for RETRIEVE-001.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class TriggerType(str, Enum):
    """Types of proactive triggers."""

    FILE_OPEN = "file-open"
    GIT_CHECKOUT = "git-checkout"
    TIME_OF_DAY = "time-of-day"
    ACTIVITY_PATTERN = "activity-pattern"
    PROJECT_SWITCH = "project-switch"
    BEADS_TASK_READY = "beads-task-ready"


class ContextPriority(str, Enum):
    """Priority levels for injected context."""

    CRITICAL = "critical"  # Must be injected immediately
    HIGH = "high"  # Inject at next opportunity
    MEDIUM = "medium"  # Inject if space available
    LOW = "low"  # Inject only if idle
    BACKGROUND = "background"  # Pre-fetch for potential future use


@dataclass
class TriggerEvent:
    """A detected trigger event."""

    trigger_type: TriggerType
    detected_at: datetime
    source_data: Dict[str, Any]  # Trigger-specific data
    context_query: str  # Query to retrieve context
    priority: ContextPriority = ContextPriority.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file_open(
        cls, file_path: str, project: Optional[str] = None
    ) -> "TriggerEvent":
        """Create trigger from file open event."""
        return cls(
            trigger_type=TriggerType.FILE_OPEN,
            detected_at=datetime.utcnow(),
            source_data={"file_path": file_path, "project": project},
            context_query=f"file:{file_path}",
            priority=ContextPriority.HIGH,
        )

    @classmethod
    def from_git_checkout(cls, branch: str, project: str) -> "TriggerEvent":
        """Create trigger from git checkout event."""
        return cls(
            trigger_type=TriggerType.GIT_CHECKOUT,
            detected_at=datetime.utcnow(),
            source_data={"branch": branch, "project": project},
            context_query=f"branch:{branch} project:{project}",
            priority=ContextPriority.HIGH,
        )

    @classmethod
    def from_time_of_day(cls, hour: int, day_of_week: int) -> "TriggerEvent":
        """Create trigger from time-of-day pattern."""
        return cls(
            trigger_type=TriggerType.TIME_OF_DAY,
            detected_at=datetime.utcnow(),
            source_data={"hour": hour, "day_of_week": day_of_week},
            context_query=f"scheduled hour:{hour} day:{day_of_week}",
            priority=ContextPriority.MEDIUM,
        )

    @classmethod
    def from_activity_pattern(cls, pattern: str, confidence: float) -> "TriggerEvent":
        """Create trigger from detected activity pattern."""
        return cls(
            trigger_type=TriggerType.ACTIVITY_PATTERN,
            detected_at=datetime.utcnow(),
            source_data={"pattern": pattern, "confidence": confidence},
            context_query=f"pattern:{pattern}",
            priority=ContextPriority.MEDIUM
            if confidence > 0.7
            else ContextPriority.LOW,
        )


@dataclass
class InjectedContext:
    """Context that was proactively injected."""

    trigger_event: TriggerEvent
    injected_at: datetime
    chunks: List[Dict[str, Any]]  # Retrieved memory chunks
    relevance_score: float
    token_count: int
    source_ontologies: List[str]  # Which ontologies contributed
    was_used: bool = False  # Did user actually use this context?
    user_feedback: Optional[str] = None  # User feedback on helpfulness

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_type": self.trigger_event.trigger_type.value,
            "triggered_at": self.trigger_event.detected_at.isoformat(),
            "injected_at": self.injected_at.isoformat(),
            "chunk_count": len(self.chunks),
            "relevance_score": self.relevance_score,
            "token_count": self.token_count,
            "source_ontologies": self.source_ontologies,
            "was_used": self.was_used,
            "user_feedback": self.user_feedback,
        }


@dataclass
class InjectionRule:
    """Rule for when and how to inject context."""

    rule_id: str
    trigger_types: List[TriggerType]
    enabled: bool = True
    min_relevance: float = 0.5  # Minimum relevance to inject
    max_tokens: int = 2000  # Max tokens to inject
    cooldown_seconds: int = 300  # Min time between injections
    require_ontologies: Optional[
        List[str]
    ] = None  # Only inject if these ontologies have results
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InjectionStats:
    """Statistics for proactive injections."""

    total_triggers: int = 0
    total_injections: int = 0
    by_trigger_type: Dict[str, int] = field(default_factory=dict)
    by_priority: Dict[str, int] = field(default_factory=dict)
    average_relevance: float = 0.0
    total_tokens_injected: int = 0
    used_count: int = 0  # How many were actually used
    unused_count: int = 0  # How many were ignored

    def injection_rate(self) -> float:
        """Calculate injection rate (triggers -> injections)."""
        if self.total_triggers == 0:
            return 0.0
        return self.total_injections / self.total_triggers

    def usage_rate(self) -> float:
        """Calculate usage rate (injections -> used)."""
        if self.total_injections == 0:
            return 0.0
        return self.used_count / self.total_injections

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_triggers": self.total_triggers,
            "total_injections": self.total_injections,
            "by_trigger_type": self.by_trigger_type,
            "by_priority": self.by_priority,
            "average_relevance": self.average_relevance,
            "total_tokens_injected": self.total_tokens_injected,
            "used_count": self.used_count,
            "unused_count": self.unused_count,
            "injection_rate": self.injection_rate(),
            "usage_rate": self.usage_rate(),
        }


# Default injection rules
DEFAULT_RULES = [
    InjectionRule(
        rule_id="file-open-high-priority",
        trigger_types=[TriggerType.FILE_OPEN],
        min_relevance=0.6,
        max_tokens=1500,
        cooldown_seconds=180,
    ),
    InjectionRule(
        rule_id="git-checkout-branch-context",
        trigger_types=[TriggerType.GIT_CHECKOUT],
        min_relevance=0.5,
        max_tokens=2000,
        cooldown_seconds=300,
        require_ontologies=["projects", "beads"],
    ),
    InjectionRule(
        rule_id="time-scheduled-reminders",
        trigger_types=[TriggerType.TIME_OF_DAY],
        min_relevance=0.4,
        max_tokens=1000,
        cooldown_seconds=3600,  # Once per hour max
    ),
    InjectionRule(
        rule_id="activity-pattern-anticipation",
        trigger_types=[TriggerType.ACTIVITY_PATTERN],
        min_relevance=0.7,
        max_tokens=1500,
        cooldown_seconds=600,
    ),
]
