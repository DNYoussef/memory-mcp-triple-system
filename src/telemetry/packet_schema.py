"""
Telemetry Packet Schema - Structured telemetry data format.

ORG-006: Implement telemetry packet schema.

Required Fields (6 minimum metrics):
1. WHO: Agent identifier
2. WHEN: ISO8601 timestamp
3. PROJECT: Project identifier
4. WHY: Action type (implementation, bugfix, refactor, etc.)
5. DURATION: Execution duration in milliseconds
6. STATUS: Success/failure/partial

Extended Fields:
- TOKENS: Token usage
- ERRORS: Error count
- CONFIDENCE: Confidence score
- CUSTOM: Custom metadata dict

Purpose:
- Standardize telemetry data across all agents
- Enable dashboard pipeline node integration
- Support real-time monitoring and analysis

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from loguru import logger
import json


class ActionType(Enum):
    """Standard action types for WHY field."""
    IMPLEMENTATION = "implementation"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    RESEARCH = "research"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"


class TelemetryStatus(Enum):
    """Status values for telemetry packets."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    PENDING = "pending"
    CANCELLED = "cancelled"


@dataclass
class TelemetryPacket:
    """
    Standardized telemetry packet with 6 minimum metrics.

    Required (6 metrics):
    - who: Agent identifier
    - when: ISO8601 timestamp
    - project: Project identifier
    - why: Action type
    - duration_ms: Execution duration
    - status: Execution status

    Optional (extended metrics):
    - tokens: Token usage
    - errors: Error count
    - confidence: Confidence score
    - custom: Custom metadata
    """

    # Required fields (6 minimum metrics)
    who: str  # Agent identifier (e.g., "coder:bug-fixer:1.0.0")
    when: str  # ISO8601 timestamp
    project: str  # Project identifier
    why: ActionType  # Action type
    duration_ms: int  # Duration in milliseconds
    status: TelemetryStatus  # Execution status

    # Optional extended fields
    tokens: int = 0  # Token usage
    errors: int = 0  # Error count
    confidence: float = 1.0  # Confidence score (0-1)
    custom: Dict[str, Any] = field(default_factory=dict)  # Custom metadata

    # Internal tracking
    packet_id: str = field(default_factory=lambda: "")
    version: str = "1.0.0"

    def __post_init__(self):
        """Generate packet ID if not provided."""
        if not self.packet_id:
            import hashlib
            hash_input = f"{self.who}:{self.when}:{self.project}"
            self.packet_id = f"TEL-{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            # Required 6 metrics
            "WHO": self.who,
            "WHEN": self.when,
            "PROJECT": self.project,
            "WHY": self.why.value,
            "DURATION_MS": self.duration_ms,
            "STATUS": self.status.value,
            # Extended metrics
            "TOKENS": self.tokens,
            "ERRORS": self.errors,
            "CONFIDENCE": self.confidence,
            "CUSTOM": self.custom
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    def validate(self) -> List[str]:
        """
        Validate packet has all required fields.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not self.who or not self.who.strip():
            errors.append("WHO field is required")
        if not self.when or not self.when.strip():
            errors.append("WHEN field is required")
        if not self.project or not self.project.strip():
            errors.append("PROJECT field is required")
        if not isinstance(self.why, ActionType):
            errors.append("WHY must be a valid ActionType")
        if self.duration_ms < 0:
            errors.append("DURATION_MS must be non-negative")
        if not isinstance(self.status, TelemetryStatus):
            errors.append("STATUS must be a valid TelemetryStatus")

        return errors


class TelemetryPacketBuilder:
    """
    Builder for creating telemetry packets.

    Provides fluent interface for constructing packets
    with validation and sensible defaults.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self):
        """Initialize builder with defaults."""
        self._who: str = ""
        self._when: str = datetime.utcnow().isoformat()
        self._project: str = ""
        self._why: ActionType = ActionType.IMPLEMENTATION
        self._duration_ms: int = 0
        self._status: TelemetryStatus = TelemetryStatus.PENDING
        self._tokens: int = 0
        self._errors: int = 0
        self._confidence: float = 1.0
        self._custom: Dict[str, Any] = {}

    def who(self, agent_id: str) -> "TelemetryPacketBuilder":
        """Set agent identifier."""
        self._who = agent_id
        return self

    def when(self, timestamp: Optional[str] = None) -> "TelemetryPacketBuilder":
        """Set timestamp (defaults to now)."""
        self._when = timestamp or datetime.utcnow().isoformat()
        return self

    def project(self, project_id: str) -> "TelemetryPacketBuilder":
        """Set project identifier."""
        self._project = project_id
        return self

    def why(self, action_type: ActionType) -> "TelemetryPacketBuilder":
        """Set action type."""
        self._why = action_type
        return self

    def duration(self, duration_ms: int) -> "TelemetryPacketBuilder":
        """Set duration in milliseconds."""
        self._duration_ms = max(0, duration_ms)
        return self

    def status(self, status: TelemetryStatus) -> "TelemetryPacketBuilder":
        """Set execution status."""
        self._status = status
        return self

    def tokens(self, count: int) -> "TelemetryPacketBuilder":
        """Set token usage."""
        self._tokens = max(0, count)
        return self

    def errors(self, count: int) -> "TelemetryPacketBuilder":
        """Set error count."""
        self._errors = max(0, count)
        return self

    def confidence(self, score: float) -> "TelemetryPacketBuilder":
        """Set confidence score (0-1)."""
        self._confidence = max(0.0, min(1.0, score))
        return self

    def custom(self, metadata: Dict[str, Any]) -> "TelemetryPacketBuilder":
        """Set custom metadata."""
        self._custom = metadata
        return self

    def build(self) -> TelemetryPacket:
        """
        Build the telemetry packet.

        Returns:
            Constructed TelemetryPacket

        Raises:
            ValueError if validation fails

        NASA Rule 10: 25 LOC (<=60)
        """
        packet = TelemetryPacket(
            who=self._who,
            when=self._when,
            project=self._project,
            why=self._why,
            duration_ms=self._duration_ms,
            status=self._status,
            tokens=self._tokens,
            errors=self._errors,
            confidence=self._confidence,
            custom=self._custom
        )

        # Validate
        errors = packet.validate()
        if errors:
            raise ValueError(f"Invalid packet: {'; '.join(errors)}")

        logger.debug(f"Built telemetry packet: {packet.packet_id}")
        return packet


def create_packet(
    who: str,
    project: str,
    why: ActionType,
    duration_ms: int,
    status: TelemetryStatus,
    **kwargs
) -> TelemetryPacket:
    """
    Convenience function to create a telemetry packet.

    Args:
        who: Agent identifier
        project: Project identifier
        why: Action type
        duration_ms: Duration in milliseconds
        status: Execution status
        **kwargs: Optional extended fields

    Returns:
        TelemetryPacket

    NASA Rule 10: 25 LOC (<=60)
    """
    return TelemetryPacket(
        who=who,
        when=datetime.utcnow().isoformat(),
        project=project,
        why=why,
        duration_ms=duration_ms,
        status=status,
        tokens=kwargs.get("tokens", 0),
        errors=kwargs.get("errors", 0),
        confidence=kwargs.get("confidence", 1.0),
        custom=kwargs.get("custom", {})
    )


def parse_packet(data: Dict[str, Any]) -> Optional[TelemetryPacket]:
    """
    Parse a telemetry packet from dictionary.

    Args:
        data: Dictionary with packet fields

    Returns:
        TelemetryPacket or None if invalid

    NASA Rule 10: 35 LOC (<=60)
    """
    try:
        # Map WHY to ActionType
        why_str = data.get("WHY", data.get("why", "implementation"))
        try:
            why = ActionType(why_str)
        except ValueError:
            why = ActionType.IMPLEMENTATION

        # Map STATUS to TelemetryStatus
        status_str = data.get("STATUS", data.get("status", "pending"))
        try:
            status = TelemetryStatus(status_str)
        except ValueError:
            status = TelemetryStatus.PENDING

        packet = TelemetryPacket(
            who=data.get("WHO", data.get("who", "")),
            when=data.get("WHEN", data.get("when", datetime.utcnow().isoformat())),
            project=data.get("PROJECT", data.get("project", "")),
            why=why,
            duration_ms=data.get("DURATION_MS", data.get("duration_ms", 0)),
            status=status,
            tokens=data.get("TOKENS", data.get("tokens", 0)),
            errors=data.get("ERRORS", data.get("errors", 0)),
            confidence=data.get("CONFIDENCE", data.get("confidence", 1.0)),
            custom=data.get("CUSTOM", data.get("custom", {})),
            packet_id=data.get("packet_id", "")
        )

        return packet

    except Exception as e:
        logger.error(f"Failed to parse packet: {e}")
        return None
