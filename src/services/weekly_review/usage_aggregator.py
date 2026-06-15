"""Usage Aggregator for IMPROVE-002.

Aggregates Memory MCP usage statistics.

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

from src.services.weekly_review.review_schema import UsageSummary

logger = logging.getLogger(__name__)


@dataclass
class UsageAggregatorConfig:
    """Configuration for usage aggregator."""

    default_period_days: int = 7


class UsageAggregator:
    """Aggregates Memory MCP usage statistics.

    Collects and summarizes:
    - Store/retrieve/search operations
    - Memory creation/update/expiration
    - Layer distribution
    - Performance metrics
    """

    def __init__(self, config: Optional[UsageAggregatorConfig] = None):
        """Initialize usage aggregator.

        Args:
            config: Aggregator configuration
        """
        self.config = config or UsageAggregatorConfig()

        # In-memory tracking (in production, read from Memory MCP)
        self._operations: List[Dict[str, Any]] = []
        self._stats = {
            "total_stores": 0,
            "total_retrievals": 0,
            "total_searches": 0,
            "total_graph_queries": 0,
            "memories_created": 0,
            "memories_updated": 0,
        }

    def record_operation(
        self,
        operation_type: str,
        category: str = "",
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a Memory MCP operation.

        Args:
            operation_type: Type of operation (store, retrieve, search, graph_query)
            category: Category of memory
            duration_ms: Operation duration
            metadata: Additional metadata
        """
        operation = {
            "type": operation_type,
            "category": category,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        self._operations.append(operation)

        # Update stats
        if operation_type == "store":
            self._stats["total_stores"] += 1
            self._stats["memories_created"] += 1
        elif operation_type == "retrieve":
            self._stats["total_retrievals"] += 1
        elif operation_type == "search":
            self._stats["total_searches"] += 1
        elif operation_type == "graph_query":
            self._stats["total_graph_queries"] += 1
        elif operation_type == "update":
            self._stats["total_stores"] += 1
            self._stats["memories_updated"] += 1

    def aggregate(
        self,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> UsageSummary:
        """Aggregate usage statistics for a period.

        Args:
            days: Number of days to aggregate (default 7)
            start_date: Period start date
            end_date: Period end date

        Returns:
            Usage summary
        """
        # Determine period
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        if start_date is None:
            period_days = days or self.config.default_period_days
            start_date = end_date - timedelta(days=period_days)

        # Filter operations to period
        period_ops = self._filter_operations(start_date, end_date)

        # Calculate statistics
        stores = [o for o in period_ops if o["type"] in ("store", "update")]
        retrieves = [o for o in period_ops if o["type"] == "retrieve"]
        searches = [o for o in period_ops if o["type"] == "search"]
        graph_queries = [o for o in period_ops if o["type"] == "graph_query"]

        # Calculate averages
        retrieve_times = [o["duration_ms"] for o in retrieves if o["duration_ms"] > 0]
        search_times = [o["duration_ms"] for o in searches if o["duration_ms"] > 0]

        avg_retrieval = sum(retrieve_times) / len(retrieve_times) if retrieve_times else 0.0
        avg_search = sum(search_times) / len(search_times) if search_times else 0.0

        # Category distribution
        by_category: Dict[str, int] = defaultdict(int)
        for op in period_ops:
            if op["category"]:
                by_category[op["category"]] += 1

        # Create summary
        summary = UsageSummary(
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            total_stores=len(stores),
            total_retrievals=len(retrieves),
            total_searches=len(searches),
            total_graph_queries=len(graph_queries),
            memories_created=len([o for o in stores if o["type"] == "store"]),
            memories_updated=len([o for o in stores if o["type"] == "update"]),
            avg_retrieval_time_ms=avg_retrieval,
            avg_search_time_ms=avg_search,
            by_category=dict(by_category),
        )

        return summary

    def get_daily_breakdown(
        self,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Get day-by-day breakdown.

        Args:
            days: Number of days

        Returns:
            List of daily summaries
        """
        daily = []
        now = datetime.now(timezone.utc)

        for i in range(days):
            day_end = now - timedelta(days=i)
            day_start = day_end - timedelta(days=1)

            ops = self._filter_operations(day_start, day_end)

            daily.append({
                # Label by the day the window ends on (i=0 ends at now = today).
                # day_start labeled every bucket one day early (H6).
                "date": day_end.strftime("%Y-%m-%d"),
                "stores": len([o for o in ops if o["type"] in ("store", "update")]),
                "retrievals": len([o for o in ops if o["type"] == "retrieve"]),
                "searches": len([o for o in ops if o["type"] == "search"]),
                "total": len(ops),
            })

        return list(reversed(daily))

    def _filter_operations(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Filter operations to date range."""
        filtered = []

        for op in self._operations:
            op_time = datetime.fromisoformat(op["timestamp"].replace("Z", "+00:00"))
            if start_date <= op_time <= end_date:
                filtered.append(op)

        return filtered

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics."""
        return {
            **self._stats,
            "operations_tracked": len(self._operations),
        }

    def clear(self) -> None:
        """Clear all tracked operations."""
        self._operations.clear()
