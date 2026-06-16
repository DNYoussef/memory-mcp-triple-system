"""Cost/Token Analyzer for IMPROVE-002.

Analyzes token usage and cost estimates.

WHO: weekly-review:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-002)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from src.services.weekly_review.review_schema import CostAnalysis

logger = logging.getLogger(__name__)


# Token pricing (USD per 1M tokens) - 2026 estimates
MODEL_PRICING = {
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-opus-4.5": {"input": 15.0, "output": 75.0},
    "gemini-pro": {"input": 1.25, "output": 5.0},
    "gemini-flash": {"input": 0.075, "output": 0.30},
    "codex": {"input": 2.0, "output": 8.0},
    "default": {"input": 3.0, "output": 15.0},
}


@dataclass
class CostAnalyzerConfig:
    """Configuration for cost analyzer."""

    default_period_days: int = 7
    cost_warning_threshold: float = 10.0    # USD per week
    token_warning_threshold: int = 1000000   # 1M tokens


class CostTokenAnalyzer:
    """Analyzes token usage and cost.

    Tracks and analyzes:
    - Token consumption by model
    - Token consumption by category
    - Cost estimates
    - Efficiency metrics
    """

    def __init__(self, config: Optional[CostAnalyzerConfig] = None):
        """Initialize cost analyzer.

        Args:
            config: Analyzer configuration
        """
        self.config = config or CostAnalyzerConfig()

        # Usage tracking
        self._usage_records: List[Dict[str, Any]] = []
        self._task_count = 0

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "default",
        category: str = "",
        task_id: Optional[str] = None,
    ) -> None:
        """Record token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used
            category: Usage category
            task_id: Associated task ID
        """
        record = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model,
            "category": category,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._usage_records.append(record)

        if task_id:
            self._task_count += 1

    def analyze(
        self,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostAnalysis:
        """Analyze token usage and cost.

        Args:
            days: Period in days
            start_date: Period start
            end_date: Period end

        Returns:
            Cost analysis
        """
        # Determine period
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        if start_date is None:
            period_days = days or self.config.default_period_days
            start_date = end_date - timedelta(days=period_days)

        # Filter records
        period_records = self._filter_records(start_date, end_date)

        # Aggregate tokens
        total_input = 0
        total_output = 0
        by_model: Dict[str, int] = defaultdict(int)
        by_category: Dict[str, int] = defaultdict(int)
        cost_by_model: Dict[str, float] = defaultdict(float)

        for record in period_records:
            input_tokens = record["input_tokens"]
            output_tokens = record["output_tokens"]
            total = input_tokens + output_tokens

            total_input += input_tokens
            total_output += output_tokens

            model = record["model"]
            by_model[model] += total

            category = record["category"]
            if category:
                by_category[category] += total

            # Calculate cost
            pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            cost_by_model[model] += input_cost + output_cost

        total_tokens = total_input + total_output
        total_cost = sum(cost_by_model.values())

        # Calculate efficiency
        task_count = len(set(r["task_id"] for r in period_records if r["task_id"]))
        tokens_per_task = total_tokens / task_count if task_count > 0 else 0.0
        cost_per_task = total_cost / task_count if task_count > 0 else 0.0

        # Get previous period for comparison
        prev_start = start_date - (end_date - start_date)
        prev_records = self._filter_records(prev_start, start_date)
        prev_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in prev_records)
        prev_cost = self._calculate_cost(prev_records)

        token_change = ((total_tokens - prev_tokens) / prev_tokens * 100) if prev_tokens > 0 else 0.0
        cost_change = ((total_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0.0

        return CostAnalysis(
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_tokens,
            tokens_by_model=dict(by_model),
            tokens_by_category=dict(by_category),
            estimated_cost=total_cost,
            cost_by_model=dict(cost_by_model),
            tokens_per_task=tokens_per_task,
            cost_per_task=cost_per_task,
            token_change_percent=token_change,
            cost_change_percent=cost_change,
        )

    def get_top_consumers(
        self,
        days: int = 7,
        top_n: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get top token consumers.

        Args:
            days: Period in days
            top_n: Number of top consumers

        Returns:
            Top consumers by model and category
        """
        analysis = self.analyze(days=days)

        by_model = sorted(
            analysis.tokens_by_model.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

        by_category = sorted(
            analysis.tokens_by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

        return {
            "by_model": [{"model": k, "tokens": v} for k, v in by_model],
            "by_category": [{"category": k, "tokens": v} for k, v in by_category],
        }

    def _filter_records(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Filter records to date range."""
        filtered = []

        for record in self._usage_records:
            rec_time = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            if start_date <= rec_time <= end_date:
                filtered.append(record)

        return filtered

    def _calculate_cost(self, records: List[Dict[str, Any]]) -> float:
        """Calculate cost for records."""
        total = 0.0

        for record in records:
            model = record["model"]
            pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
            input_cost = (record["input_tokens"] / 1_000_000) * pricing["input"]
            output_cost = (record["output_tokens"] / 1_000_000) * pricing["output"]
            total += input_cost + output_cost

        return total

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            "records_tracked": len(self._usage_records),
            "task_count": self._task_count,
        }

    def clear(self) -> None:
        """Clear all usage records."""
        self._usage_records.clear()
        self._task_count = 0
