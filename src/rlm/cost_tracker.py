"""
RLM Cost Tracker - Safety limits for recursive operations.

RLM-003: Implements cost tracking and recursion depth limits.
Prevents runaway costs and infinite recursion loops.

Key Safety Features:
1. Recursion depth limit (default 10)
2. Cost ceiling per session (default $1.00)
3. Circuit breaker for 3x cost spikes
4. Token budget tracking

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from loguru import logger


class CostAlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    CIRCUIT_BREAK = "circuit_break"


@dataclass
class CostConfig:
    """Configuration for cost tracking.

    Attributes:
        max_recursion_depth: Maximum allowed depth (default 10)
        cost_limit_usd: Maximum cost per session (default 1.00)
        spike_threshold: Circuit breaker threshold (default 3.0x)
        token_budget: Maximum tokens per session (default 100000)
        warning_threshold: Warning at this % of limit (default 0.8)
    """
    max_recursion_depth: int = 10
    cost_limit_usd: float = 1.0
    spike_threshold: float = 3.0
    token_budget: int = 100000
    warning_threshold: float = 0.8


@dataclass
class CostRecord:
    """Record of a single cost event.

    Attributes:
        operation: Operation type
        tokens: Tokens consumed
        cost_usd: Estimated cost in USD
        depth: Recursion depth at time of operation
        timestamp: When operation occurred
    """
    operation: str
    tokens: int
    cost_usd: float
    depth: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class CostAlert:
    """Cost alert notification.

    Attributes:
        level: Alert severity
        message: Alert description
        current_cost: Current accumulated cost
        limit: Configured limit
        triggered_at: When alert was triggered
    """
    level: CostAlertLevel
    message: str
    current_cost: float
    limit: float
    triggered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RecursionLimitError(Exception):
    """Raised when recursion depth limit is exceeded."""
    def __init__(self, depth: int, max_depth: int):
        self.depth = depth
        self.max_depth = max_depth
        super().__init__(f"Recursion depth {depth} exceeds limit {max_depth}")


class CostLimitError(Exception):
    """Raised when cost limit is exceeded."""
    def __init__(self, cost: float, limit: float):
        self.cost = cost
        self.limit = limit
        super().__init__(f"Cost ${cost:.4f} exceeds limit ${limit:.2f}")


# Token cost estimates (per 1K tokens)
TOKEN_COSTS = {
    "claude-3-opus": 0.015,
    "claude-3-sonnet": 0.003,
    "claude-3-haiku": 0.00025,
    "gpt-4": 0.03,
    "gpt-4-turbo": 0.01,
    "gemini-pro": 0.00125,
    "default": 0.003,
}


class CostTracker:
    """
    RLM-003: Cost tracking and safety limits for RLM operations.

    Provides:
    - Recursion depth tracking and limits
    - Cost accumulation and limits
    - Circuit breaker for cost spikes
    - Alert generation

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self, config: Optional[CostConfig] = None):
        """
        Initialize cost tracker.

        Args:
            config: Cost configuration

        NASA Rule 10: 15 LOC (<=60)
        """
        self.config = config or CostConfig()
        self._records: List[CostRecord] = []
        self._alerts: List[CostAlert] = []
        self._total_cost = 0.0
        self._total_tokens = 0
        self._current_depth = 0
        self._max_depth_reached = 0
        self._circuit_open = False
        self._baseline_cost_rate = 0.0

        logger.info(f"CostTracker initialized: limit=${self.config.cost_limit_usd}")

    def check_recursion(self, depth: int) -> None:
        """
        Check if recursion depth is within limits.

        Args:
            depth: Current recursion depth

        Raises:
            RecursionLimitError: If depth exceeds limit

        NASA Rule 10: 15 LOC (<=60)
        """
        self._current_depth = depth
        self._max_depth_reached = max(self._max_depth_reached, depth)

        if depth > self.config.max_recursion_depth:
            self._add_alert(
                CostAlertLevel.CRITICAL,
                f"Recursion depth {depth} exceeds limit {self.config.max_recursion_depth}"
            )
            raise RecursionLimitError(depth, self.config.max_recursion_depth)

        if depth > self.config.max_recursion_depth * 0.8:
            self._add_alert(
                CostAlertLevel.WARNING,
                f"Approaching recursion limit: {depth}/{self.config.max_recursion_depth}"
            )

    def record_cost(
        self,
        operation: str,
        tokens: int,
        model: str = "default"
    ) -> CostRecord:
        """
        Record a cost event.

        Args:
            operation: Operation description
            tokens: Tokens consumed
            model: Model used for cost calculation

        Returns:
            CostRecord for the operation

        Raises:
            CostLimitError: If cost limit exceeded

        NASA Rule 10: 35 LOC (<=60)
        """
        # Check circuit breaker
        if self._circuit_open:
            raise CostLimitError(self._total_cost, self.config.cost_limit_usd)

        # Calculate cost
        rate = TOKEN_COSTS.get(model, TOKEN_COSTS["default"])
        cost_usd = (tokens / 1000) * rate

        # Check for cost spike
        if self._baseline_cost_rate > 0:
            current_rate = cost_usd / max(1, tokens / 1000)
            if current_rate > self._baseline_cost_rate * self.config.spike_threshold:
                self._circuit_open = True
                self._add_alert(
                    CostAlertLevel.CIRCUIT_BREAK,
                    f"Cost spike detected: {current_rate:.4f} vs baseline {self._baseline_cost_rate:.4f}"
                )
                raise CostLimitError(self._total_cost + cost_usd, self.config.cost_limit_usd)

        # Update totals
        self._total_cost += cost_usd
        self._total_tokens += tokens

        # Update baseline
        if len(self._records) < 5:
            self._baseline_cost_rate = self._total_cost / max(1, self._total_tokens / 1000)

        # Record
        record = CostRecord(
            operation=operation,
            tokens=tokens,
            cost_usd=cost_usd,
            depth=self._current_depth
        )
        self._records.append(record)

        # Check limits
        self._check_limits()

        return record

    def _check_limits(self) -> None:
        """
        Check cost and token limits.

        NASA Rule 10: 25 LOC (<=60)
        """
        # Cost limit
        if self._total_cost >= self.config.cost_limit_usd:
            self._add_alert(
                CostAlertLevel.CRITICAL,
                f"Cost limit exceeded: ${self._total_cost:.4f} >= ${self.config.cost_limit_usd}"
            )
            raise CostLimitError(self._total_cost, self.config.cost_limit_usd)

        # Warning threshold
        if self._total_cost >= self.config.cost_limit_usd * self.config.warning_threshold:
            self._add_alert(
                CostAlertLevel.WARNING,
                f"Approaching cost limit: ${self._total_cost:.4f} of ${self.config.cost_limit_usd}"
            )

        # Token budget
        if self._total_tokens >= self.config.token_budget:
            self._add_alert(
                CostAlertLevel.CRITICAL,
                f"Token budget exceeded: {self._total_tokens} >= {self.config.token_budget}"
            )
            raise CostLimitError(self._total_cost, self.config.cost_limit_usd)

    def _add_alert(self, level: CostAlertLevel, message: str) -> None:
        """Add an alert."""
        alert = CostAlert(
            level=level,
            message=message,
            current_cost=self._total_cost,
            limit=self.config.cost_limit_usd
        )
        self._alerts.append(alert)
        logger.log(level.value.upper(), message)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cost tracking statistics.

        NASA Rule 10: 20 LOC (<=60)
        """
        return {
            "total_cost_usd": self._total_cost,
            "total_tokens": self._total_tokens,
            "operations_count": len(self._records),
            "max_depth_reached": self._max_depth_reached,
            "circuit_open": self._circuit_open,
            "alerts_count": len(self._alerts),
            "limits": {
                "cost_limit_usd": self.config.cost_limit_usd,
                "max_recursion_depth": self.config.max_recursion_depth,
                "token_budget": self.config.token_budget
            },
            "usage_percent": {
                "cost": (self._total_cost / self.config.cost_limit_usd) * 100,
                "tokens": (self._total_tokens / self.config.token_budget) * 100,
                "depth": (self._max_depth_reached / self.config.max_recursion_depth) * 100
            }
        }

    def get_alerts(self, level: Optional[CostAlertLevel] = None) -> List[CostAlert]:
        """Get alerts, optionally filtered by level."""
        if level is None:
            return self._alerts.copy()
        return [a for a in self._alerts if a.level == level]

    def reset(self) -> None:
        """Reset tracker state for new session."""
        self._records = []
        self._alerts = []
        self._total_cost = 0.0
        self._total_tokens = 0
        self._current_depth = 0
        self._max_depth_reached = 0
        self._circuit_open = False
        self._baseline_cost_rate = 0.0
        logger.info("CostTracker reset")
