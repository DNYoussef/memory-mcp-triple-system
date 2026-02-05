"""Observation type system for auto-captured tool usage.

Structured typing for observations captured by PostToolUse hooks.
6 observation types, 7 concept categories, WHO/WHEN/PROJECT/WHY tagging.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ObservationType(str, Enum):
    """What kind of thing happened."""
    TOOL_USE = "tool_use"
    CODE_CHANGE = "code_change"
    ERROR = "error"
    DECISION = "decision"
    DISCOVERY = "discovery"
    CONVERSATION = "conversation"


class ConceptCategory(str, Enum):
    """What domain does this observation belong to."""
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    DEBUGGING = "debugging"
    TESTING = "testing"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    PLANNING = "planning"


# Map tool names to observation types for auto-classification
TOOL_TYPE_MAP: Dict[str, ObservationType] = {
    "Write": ObservationType.CODE_CHANGE,
    "Edit": ObservationType.CODE_CHANGE,
    "NotebookEdit": ObservationType.CODE_CHANGE,
    "Bash": ObservationType.TOOL_USE,
    "Read": ObservationType.TOOL_USE,
    "Glob": ObservationType.TOOL_USE,
    "Grep": ObservationType.TOOL_USE,
    "Task": ObservationType.TOOL_USE,
    "Skill": ObservationType.TOOL_USE,
    "WebFetch": ObservationType.DISCOVERY,
    "WebSearch": ObservationType.DISCOVERY,
}


def classify_tool(tool_name: str, is_error: bool = False) -> ObservationType:
    """Classify a tool invocation into an observation type.

    Args:
        tool_name: Name of the tool that was invoked
        is_error: Whether the tool invocation resulted in an error

    Returns:
        ObservationType for this tool invocation
    """
    if is_error:
        return ObservationType.ERROR
    return TOOL_TYPE_MAP.get(tool_name, ObservationType.TOOL_USE)


@dataclass
class Observation:
    """A single captured observation from a tool invocation.

    This is the core data unit for auto-capture. Every PostToolUse hook
    creates one of these.
    """
    # Identity
    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""

    # Classification
    obs_type: ObservationType = ObservationType.TOOL_USE
    concept: ConceptCategory = ConceptCategory.IMPLEMENTATION

    # Content
    tool_name: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # WHO/WHEN/PROJECT/WHY tagging (required by memory-mcp protocol)
    who: str = "auto-capture:1.0.0"
    when: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    project: str = ""
    why: str = "observation"

    # Graph integration
    entities: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for KVStore storage."""
        return {
            "observation_id": self.observation_id,
            "session_id": self.session_id,
            "obs_type": self.obs_type.value,
            "concept": self.concept.value,
            "tool_name": self.tool_name,
            "content": self.content,
            "metadata": self.metadata,
            "who": self.who,
            "when": self.when,
            "project": self.project,
            "why": self.why,
            "entities": self.entities,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Observation":
        """Deserialize from dict."""
        return cls(
            observation_id=data.get("observation_id", str(uuid.uuid4())),
            session_id=data.get("session_id", ""),
            obs_type=ObservationType(data.get("obs_type", "tool_use")),
            concept=ConceptCategory(data.get("concept", "implementation")),
            tool_name=data.get("tool_name", ""),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            who=data.get("who", "auto-capture:1.0.0"),
            when=data.get("when", ""),
            project=data.get("project", ""),
            why=data.get("why", "observation"),
            entities=data.get("entities", []),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data else datetime.utcnow(),
        )

    def compact_summary(self) -> str:
        """Return a compact ~50 token summary for progressive disclosure."""
        ts = self.created_at.strftime("%H:%M")
        prefix = self.content[:80].replace("\n", " ")
        return f"[{ts}] {self.obs_type.value}: {self.tool_name} - {prefix}"


@dataclass
class Session:
    """A Claude Code session as a first-class entity.

    Created on SessionStart, updated on PostToolUse, finalized on Stop.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    tool_count: int = 0
    project: str = ""
    branch: str = ""
    working_dir: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for KVStore storage."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "tool_count": self.tool_count,
            "project": self.project,
            "branch": self.branch,
            "working_dir": self.working_dir,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Deserialize from dict."""
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            started_at=datetime.fromisoformat(data["started_at"])
            if "started_at" in data else datetime.utcnow(),
            ended_at=datetime.fromisoformat(data["ended_at"])
            if data.get("ended_at") else None,
            tool_count=data.get("tool_count", 0),
            project=data.get("project", ""),
            branch=data.get("branch", ""),
            working_dir=data.get("working_dir", ""),
            summary=data.get("summary", ""),
        )

    @property
    def is_active(self) -> bool:
        """Whether this session is still running."""
        return self.ended_at is None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Duration in seconds, or None if still active."""
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


@dataclass
class SessionSummary:
    """Structured session summary generated at Stop."""
    session_id: str = ""
    request: str = ""
    investigated: List[str] = field(default_factory=list)
    learned: List[str] = field(default_factory=list)
    completed: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    observation_count: int = 0
    duration_seconds: float = 0.0

    def to_text(self) -> str:
        """Format as readable text block for context injection."""
        lines = []
        if self.request:
            lines.append(f"Request: {self.request}")
        if self.investigated:
            lines.append("Investigated: " + "; ".join(self.investigated))
        if self.learned:
            lines.append("Learned: " + "; ".join(self.learned))
        if self.completed:
            lines.append("Completed: " + "; ".join(self.completed))
        if self.next_steps:
            lines.append("Next steps: " + "; ".join(self.next_steps))
        lines.append(
            f"({self.observation_count} observations, "
            f"{self.duration_seconds:.0f}s)"
        )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "session_id": self.session_id,
            "request": self.request,
            "investigated": self.investigated,
            "learned": self.learned,
            "completed": self.completed,
            "next_steps": self.next_steps,
            "observation_count": self.observation_count,
            "duration_seconds": self.duration_seconds,
        }
