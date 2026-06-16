"""
Namespace Router - Structured key namespacing for Memory MCP telemetry.

ORG-001: Add namespace support for telemetry types.
ORG-007: Add quarantine namespace for apoptosis/failure containment.

Supported namespaces:
- agents:{category}:{type}:{project}:{timestamp}
- expertise:{domain}:{topic}
- findings:{agent}:{severity}:{id}
- fixes:{agent}:{finding-id}
- optimization:{type}:{target}
- quality:{metric}:{project}
- tasks:{project}:{id}
- pipelines:{name}:{stage}
- quarantine:{component}:{reason}:{id}  (ORG-007)

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger


class TelemetryNamespace(Enum):
    """Supported telemetry namespace types."""
    AGENTS = "agents"
    EXPERTISE = "expertise"
    FINDINGS = "findings"
    FIXES = "fixes"
    OPTIMIZATION = "optimization"
    QUALITY = "quality"
    TASKS = "tasks"
    PIPELINES = "pipelines"
    # ORG-007: Add quarantine namespace for apoptosis/failure containment
    QUARANTINE = "quarantine"


# Namespace patterns with required segments
NAMESPACE_PATTERNS: Dict[TelemetryNamespace, Tuple[str, ...]] = {
    TelemetryNamespace.AGENTS: ("category", "type", "project", "timestamp"),
    TelemetryNamespace.EXPERTISE: ("domain", "topic"),
    TelemetryNamespace.FINDINGS: ("agent", "severity", "id"),
    TelemetryNamespace.FIXES: ("agent", "finding_id"),
    TelemetryNamespace.OPTIMIZATION: ("type", "target"),
    TelemetryNamespace.QUALITY: ("metric", "project"),
    TelemetryNamespace.TASKS: ("project", "id"),
    TelemetryNamespace.PIPELINES: ("name", "stage"),
    # ORG-007: Quarantine namespace for failure containment (Apoptosis organ)
    TelemetryNamespace.QUARANTINE: ("component", "reason", "id"),
}

# Valid severity levels for findings
SEVERITY_LEVELS = ("critical", "high", "medium", "low", "info")

# Valid agent categories
AGENT_CATEGORIES = (
    "coder", "researcher", "tester", "reviewer", "deployer",
    "documenter", "security", "performance", "quality", "meta"
)


@dataclass
class ParsedNamespace:
    """Parsed namespace key with segments."""
    namespace: TelemetryNamespace
    segments: Dict[str, str]
    raw_key: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "namespace": self.namespace.value,
            "segments": self.segments,
            "raw_key": self.raw_key
        }


def parse_namespace_key(key: str) -> Optional[ParsedNamespace]:
    """
    Parse a namespace key into its components.

    Args:
        key: Namespace key (e.g., "agents:coder:bug-fixer:trader-ai:2026-01-20T12:00:00")

    Returns:
        ParsedNamespace or None if invalid

    NASA Rule 10: 35 LOC (<=60)
    """
    if not key or ":" not in key:
        return None

    parts = key.split(":")
    if len(parts) < 2:
        return None

    # Get namespace type
    try:
        namespace = TelemetryNamespace(parts[0])
    except ValueError:
        logger.warning(f"Unknown namespace: {parts[0]}")
        return None

    # Get expected segments
    expected_segments = NAMESPACE_PATTERNS.get(namespace)
    if not expected_segments:
        return None

    # Parse segments
    segments_values = parts[1:]

    # Allow partial matches (fewer segments than expected)
    segments = {}
    for i, segment_name in enumerate(expected_segments):
        if i < len(segments_values):
            value = segments_values[i]
            if value:
                segments[segment_name] = value

    return ParsedNamespace(
        namespace=namespace,
        segments=segments,
        raw_key=key
    )


def build_namespace_key(
    namespace: TelemetryNamespace,
    **kwargs
) -> str:
    """
    Build a namespace key from components.

    Args:
        namespace: Namespace type
        **kwargs: Segment values

    Returns:
        Formatted namespace key

    NASA Rule 10: 30 LOC (<=60)
    """
    expected_segments = NAMESPACE_PATTERNS.get(namespace)
    if not expected_segments:
        raise ValueError(f"Unknown namespace: {namespace}")

    parts = [namespace.value]

    last_provided = -1
    for index, segment_name in enumerate(expected_segments):
        if kwargs.get(segment_name) is not None:
            last_provided = index

    for index, segment_name in enumerate(expected_segments):
        if index > last_provided:
            break
        value = kwargs.get(segment_name)
        if value is None:
            # Use placeholder for missing optional segments
            parts.append("")
            continue
        parts.append(str(value))

    return ":".join(parts)


class NamespaceRouter:
    """
    Routes telemetry data to appropriate KV store keys.

    Provides namespace-aware storage and retrieval for Memory MCP.
    """

    def __init__(self, kv_store: Any):
        """
        Initialize namespace router.

        Args:
            kv_store: KVStore instance for persistence

        NASA Rule 10: 8 LOC (<=60)
        """
        self.kv_store = kv_store
        logger.info("NamespaceRouter initialized")

    def store(
        self,
        namespace: TelemetryNamespace,
        data: Dict[str, Any],
        **key_segments
    ) -> bool:
        """
        Store data under namespaced key.

        Args:
            namespace: Namespace type
            data: Data to store
            **key_segments: Key segment values

        Returns:
            True if stored successfully

        NASA Rule 10: 25 LOC (<=60)
        """
        try:
            # Build key
            key = build_namespace_key(namespace, **key_segments)

            # Add metadata
            data["_namespace"] = namespace.value
            data["_stored_at"] = datetime.utcnow().isoformat()
            data["_key_segments"] = key_segments

            # Store in KV
            import json
            success = self.kv_store.set(key, json.dumps(data))

            if success:
                logger.debug(f"Stored telemetry: {key}")

            return success

        except Exception as e:
            logger.error(f"Failed to store telemetry: {e}")
            return False

    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data by namespace key.

        Args:
            key: Full namespace key

        Returns:
            Data dict or None

        NASA Rule 10: 18 LOC (<=60)
        """
        try:
            value = self.kv_store.get(key)
            if value is None:
                return None

            import json
            return json.loads(value)

        except Exception as e:
            logger.error(f"Failed to retrieve telemetry: {e}")
            return None

    def list_by_namespace(
        self,
        namespace: TelemetryNamespace,
        prefix_filter: str = ""
    ) -> List[str]:
        """
        List all keys in a namespace.

        Args:
            namespace: Namespace type
            prefix_filter: Additional prefix filter within namespace

        Returns:
            List of matching keys

        NASA Rule 10: 15 LOC (<=60)
        """
        full_prefix = namespace.value
        if prefix_filter:
            full_prefix = f"{full_prefix}:{prefix_filter}"

        return self.kv_store.list_keys(full_prefix)

    def store_agent_result(
        self,
        category: str,
        agent_type: str,
        project: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Store agent execution result.

        Convenience method for agents namespace.

        NASA Rule 10: 15 LOC (<=60)
        """
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        return self.store(
            TelemetryNamespace.AGENTS,
            result,
            category=category,
            type=agent_type,
            project=project,
            timestamp=timestamp
        )

    def store_finding(
        self,
        agent: str,
        severity: str,
        finding_id: str,
        finding_data: Dict[str, Any]
    ) -> bool:
        """
        Store a finding/issue.

        Convenience method for findings namespace.

        NASA Rule 10: 18 LOC (<=60)
        """
        if severity not in SEVERITY_LEVELS:
            logger.warning(f"Invalid severity: {severity}, using 'medium'")
            severity = "medium"

        return self.store(
            TelemetryNamespace.FINDINGS,
            finding_data,
            agent=agent,
            severity=severity,
            id=finding_id
        )

    def store_fix(
        self,
        agent: str,
        finding_id: str,
        fix_data: Dict[str, Any]
    ) -> bool:
        """
        Store a fix for a finding.

        Convenience method for fixes namespace.

        NASA Rule 10: 12 LOC (<=60)
        """
        return self.store(
            TelemetryNamespace.FIXES,
            fix_data,
            agent=agent,
            finding_id=finding_id
        )

    def store_expertise(
        self,
        domain: str,
        topic: str,
        expertise_data: Dict[str, Any]
    ) -> bool:
        """
        Store domain expertise.

        Convenience method for expertise namespace.

        NASA Rule 10: 12 LOC (<=60)
        """
        return self.store(
            TelemetryNamespace.EXPERTISE,
            expertise_data,
            domain=domain,
            topic=topic
        )

    def get_namespace_stats(self) -> Dict[str, int]:
        """
        Get count of entries per namespace.

        Returns:
            Dict mapping namespace to count

        NASA Rule 10: 15 LOC (<=60)
        """
        stats = {}
        for ns in TelemetryNamespace:
            keys = self.list_by_namespace(ns)
            stats[ns.value] = len(keys)
        return stats
