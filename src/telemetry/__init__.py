"""
Telemetry module for Memory MCP.

ORG-001: Namespace support for AI Exoskeleton telemetry types.
ORG-006: Telemetry packet schema with WHO/WHEN/PROJECT/WHY tagging.
"""

from .namespace_router import (
    NamespaceRouter,
    TelemetryNamespace,
    parse_namespace_key,
    build_namespace_key,
    NAMESPACE_PATTERNS,
)
from .packet_schema import (
    TelemetryPacket,
    TelemetryPacketBuilder,
    ActionType,
    TelemetryStatus,
    create_packet,
    parse_packet,
)

__all__ = [
    # Namespace router (ORG-001)
    "NamespaceRouter",
    "TelemetryNamespace",
    "parse_namespace_key",
    "build_namespace_key",
    "NAMESPACE_PATTERNS",
    # Packet schema (ORG-006)
    "TelemetryPacket",
    "TelemetryPacketBuilder",
    "ActionType",
    "TelemetryStatus",
    "create_packet",
    "parse_packet",
]
