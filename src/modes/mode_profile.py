"""
Mode profiles for context-aware retrieval.

Insight #5: Mode awareness > prompt cleverness.
Different modes need different retrieval strategies.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModeProfile:
    """
    Mode-specific configuration profile.

    Defines retrieval behavior for different interaction modes:
    - Execution: High precision, minimal context
    - Planning: Balanced precision/recall
    - Brainstorming: High recall, exploratory

    NASA Rule 10 Compliant: Dataclass (no methods >60 LOC)
    """

    name: str
    """Mode name: execution, planning, or brainstorming"""

    core_size: int
    """Number of core results (curated, high-confidence)"""

    extended_size: int
    """Number of extended results (broader recall)"""

    verification_enabled: bool
    """Enable ground truth verification"""

    constraints_enabled: bool
    """Enable error constraints"""

    latency_budget_ms: int
    """Maximum latency in milliseconds"""

    token_budget: int
    """Maximum tokens for context"""

    randomness: float
    """Random injection rate (0.0-1.0)"""

    def __post_init__(self) -> None:
        """Validate profile configuration."""
        if self.core_size < 0:
            raise ValueError(f"core_size must be ≥0, got {self.core_size}")

        if self.extended_size < 0:
            raise ValueError(f"extended_size must be ≥0, got {self.extended_size}")

        if self.latency_budget_ms <= 0:
            raise ValueError(f"latency_budget_ms must be >0, got {self.latency_budget_ms}")

        if self.token_budget <= 0:
            raise ValueError(f"token_budget must be >0, got {self.token_budget}")

        if not 0.0 <= self.randomness <= 1.0:
            raise ValueError(f"randomness must be in [0.0, 1.0], got {self.randomness}")

    @property
    def total_size(self) -> int:
        """Total results (core + extended)."""
        return self.core_size + self.extended_size


# Predefined Mode Profiles

EXECUTION = ModeProfile(
    name="execution",
    core_size=5,
    extended_size=0,           # Precision only (no extended)
    verification_enabled=True,  # Verify against ground truth
    constraints_enabled=True,   # Strict error handling
    latency_budget_ms=500,     # Fast response
    token_budget=5000,         # Minimal context
    randomness=0.0             # No randomness
)
"""
Execution mode: High precision, minimal context.

Use for: "What is X?", "How do I X?", imperative queries.
Focus: Correct answers quickly.
"""

PLANNING = ModeProfile(
    name="planning",
    core_size=5,
    extended_size=15,         # 5 + 15 = 20 total
    verification_enabled=True,
    constraints_enabled=True,
    latency_budget_ms=1000,   # Medium response
    token_budget=10000,       # Balanced context
    randomness=0.05           # 5% random injection
)
"""
Planning mode: Balanced precision/recall.

Use for: "What should I X?", "How can I X?", conditional queries.
Focus: Explore options, compare alternatives.
"""

BRAINSTORMING = ModeProfile(
    name="brainstorming",
    core_size=5,
    extended_size=25,          # 5 + 25 = 30 total
    verification_enabled=False,  # No verification (allow creative errors)
    constraints_enabled=False,   # No constraints
    latency_budget_ms=2000,    # Slower response OK
    token_budget=20000,        # Large context
    randomness=0.10            # 10% random injection
)
"""
Brainstorming mode: High recall, exploratory.

Use for: "What if X?", "Could we X?", creative queries.
Focus: Maximum coverage, creative connections.
"""

# Profile registry
PROFILES: Dict[str, ModeProfile] = {
    "execution": EXECUTION,
    "planning": PLANNING,
    "brainstorming": BRAINSTORMING
}


def get_profile(name: str) -> ModeProfile:
    """
    Get mode profile by name.

    Args:
        name: Mode name (execution, planning, brainstorming)

    Returns:
        ModeProfile instance

    Raises:
        ValueError: If mode name not found
    """
    if name not in PROFILES:
        raise ValueError(
            f"Unknown mode: {name}. "
            f"Valid modes: {', '.join(PROFILES.keys())}"
        )

    return PROFILES[name]
