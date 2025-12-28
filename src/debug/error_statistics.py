"""
Error Statistics Service - Focused component for error statistics.

Extracted from ErrorAttribution to improve cohesion.
Single Responsibility: Aggregate and report error statistics.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger


class ErrorStatisticsService:
    """
    Aggregates error statistics from database.

    Single Responsibility: Statistics collection and reporting.
    Cohesion: HIGH - all methods relate to statistics.
    """

    def __init__(self, db: Optional[Any] = None):
        """
        Initialize statistics service.

        Args:
            db: Database connection
        """
        self.db = db

    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Aggregate error statistics for dashboard.

        Args:
            days: Number of days to aggregate

        Returns:
            Statistics dictionary
        """
        if not self.db:
            logger.warning("Database not available for statistics")
            return self._empty_stats()

        try:
            return self._query_statistics(days)
        except Exception as e:
            logger.error(f"Failed to aggregate statistics: {e}")
            return self._empty_stats()

    def _query_statistics(self, days: int) -> Dict[str, Any]:
        """Query statistics from database."""
        import sqlite3

        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()

        cursor = self.db.cursor()

        # Total queries
        cursor.execute(
            "SELECT COUNT(*) FROM query_traces WHERE timestamp >= ?",
            (cutoff_str,)
        )
        total_queries = cursor.fetchone()[0]

        # Failed queries
        cursor.execute(
            "SELECT COUNT(*) FROM query_traces WHERE timestamp >= ? AND error IS NOT NULL",
            (cutoff_str,)
        )
        failed_queries = cursor.fetchone()[0]

        # Error type breakdown
        cursor.execute(
            "SELECT error_type, COUNT(*) FROM query_traces "
            "WHERE timestamp >= ? AND error_type IS NOT NULL GROUP BY error_type",
            (cutoff_str,)
        )
        error_breakdown = dict(cursor.fetchall())

        return {
            "total_queries": total_queries,
            "failed_queries": failed_queries,
            "failure_breakdown": {
                "context_bugs": error_breakdown.get("context_bug", 0),
                "model_bugs": error_breakdown.get("model_bug", 0),
                "system_errors": error_breakdown.get("system_error", 0)
            },
            "context_bug_breakdown": {
                "wrong_store_queried": 0,
                "wrong_mode_detected": 0,
                "wrong_lifecycle_filter": 0,
                "retrieval_ranking_error": 0
            },
            "days": days
        }

    def _empty_stats(self) -> Dict[str, Any]:
        """Return empty statistics structure."""
        return {
            "total_queries": 0,
            "failed_queries": 0,
            "failure_breakdown": {
                "context_bugs": 0,
                "model_bugs": 0,
                "system_errors": 0
            },
            "context_bug_breakdown": {
                "wrong_store_queried": 0,
                "wrong_mode_detected": 0,
                "wrong_lifecycle_filter": 0,
                "retrieval_ranking_error": 0
            },
            "days": 0
        }
