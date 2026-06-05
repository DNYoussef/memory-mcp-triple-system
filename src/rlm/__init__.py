"""
RLM (Recursive Language Model) Module for Memory MCP.

RLM-001: Foundation for self-referential code analysis.
Allows the AI Exoskeleton to use telemetry to detect issues
and examine its own code in a recursive, self-aware manner.

Based on: https://arxiv.org/abs/2512.24601
GitHub: https://github.com/alexzhang13/rlm

Key Components:
- RLMEnvironment: Base class for recursive execution environments
- CostTracker: Safety limits for recursion depth and API costs
- RLMLogger: Trajectory logging for analysis (RLM-004)
- RLMMemoryEnvironment: Memory MCP adapter (RLM-005)
- RLMSearchTools: Search tools for RLM operations (RLM-006)
- RecursiveQueryResult: Recursive query interface (RLM-007)
- RLMCodebaseEnvironment: AI Exoskeleton project indexer (RLM-009)

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from .rlm_environment import (
    RLMEnvironment,
    RLMConfig,
    RLMResult,
    ExecutionContext,
)
from .cost_tracker import (
    CostTracker,
    CostConfig,
    CostRecord,
    CostAlert,
    RecursionLimitError,
    CostLimitError,
)
from .logger import (
    RLMLogger,
    TrajectoryEvent,
    TrajectoryEventType,
    TrajectoryStats,
)
from .rlm_memory_env import (
    RLMMemoryEnvironment,
    MemoryChunk,
    RecursiveQueryResult,
)
from .rlm_codebase_env import (
    RLMCodebaseEnvironment,
    CodeFile,
    AI_EXOSKELETON_PROJECTS,
)
from .rlm_nexus_adapter import RLMNexusAdapter

__all__ = [
    # Environment (RLM-002)
    "RLMEnvironment",
    "RLMConfig",
    "RLMResult",
    "ExecutionContext",
    # Cost Tracking (RLM-003)
    "CostTracker",
    "CostConfig",
    "CostRecord",
    "CostAlert",
    "RecursionLimitError",
    "CostLimitError",
    # Trajectory Logging (RLM-004)
    "RLMLogger",
    "TrajectoryEvent",
    "TrajectoryEventType",
    "TrajectoryStats",
    # Memory Environment (RLM-005)
    "RLMMemoryEnvironment",
    "MemoryChunk",
    # Recursive Query (RLM-007)
    "RecursiveQueryResult",
    # Codebase Environment (RLM-009)
    "RLMCodebaseEnvironment",
    "CodeFile",
    "AI_EXOSKELETON_PROJECTS",
    # Nexus Adapter (RLM-008)
    "RLMNexusAdapter",
]

# RLM-001: Version info
__version__ = "0.3.0"
__rlm_paper__ = "https://arxiv.org/abs/2512.24601"
