"""
WoundHealer Package.

GS-016/GS-017: Telemetry-driven auto-repair system with RLM integration.

Components:
- RLMClient: Pattern matching via Memory MCP queries
- WoundHealer: Core auto-repair with confidence gating
"""

from .rlm_client import (
    RLMClient,
    Finding,
    Fix,
    PatternMatch,
)

from .woundhealer_core import (
    WoundHealer,
    GuardEvent,
    FixPlan,
    RepairResult,
    RepairStatus,
    RepairConfidence,
)

__all__ = [
    # RLM Client (GS-017)
    "RLMClient",
    "Finding",
    "Fix",
    "PatternMatch",
    # WoundHealer Core (GS-016)
    "WoundHealer",
    "GuardEvent",
    "FixPlan",
    "RepairResult",
    "RepairStatus",
    "RepairConfidence",
]
