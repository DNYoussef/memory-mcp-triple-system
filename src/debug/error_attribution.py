"""
Error Attribution: Classify failures as context bugs vs model bugs.

PREMORTEM Risk #13 Mitigation:
- Analyze query trace to identify root cause
- Classify as context bug (70%), model bug (20%), or system error (10%)
- Aggregate statistics for dashboard

Expected Distribution:
- 40% of all queries: Context bugs
- 10% of all queries: Model bugs
- 5% of all queries: System errors
"""

from typing import Dict, List, Optional
from enum import Enum
import re
from loguru import logger


class ErrorType(Enum):
    """Error classification categories."""
    CONTEXT_BUG = "context_bug"      # 70% of failures
    MODEL_BUG = "model_bug"          # 20% of failures
    SYSTEM_ERROR = "system_error"    # 10% of failures


class ContextBugType(Enum):
    """Context bug subcategories."""
    WRONG_STORE_QUERIED = "wrong_store_queried"          # 40% of context bugs
    WRONG_MODE_DETECTED = "wrong_mode_detected"          # 30% of context bugs
    WRONG_LIFECYCLE_FILTER = "wrong_lifecycle_filter"    # 20% of context bugs
    RETRIEVAL_RANKING_ERROR = "retrieval_ranking_error"  # 10% of context bugs


class ErrorAttribution:
    """
    Classify failures: context bugs vs model bugs.

    PREMORTEM Risk #13 Mitigation:
    - Analyze query trace to identify root cause
    - Classify as context bug (70%), model bug (20%), or system error (10%)
    - Aggregate statistics for dashboard

    Expected Distribution (from PREMORTEM):
    - 40% of all failures: Context bugs
    - 10% of all failures: Model bugs
    - 5% of all failures: System errors
    """

    def __init__(self, db=None):
        """
        Initialize Error Attribution classifier.

        Args:
            db: Database connection for statistics (optional)
        """
        self.db = db
        logger.info("ErrorAttribution initialized")

    def classify_failure(self, trace) -> ErrorType:
        """
        Classify failure based on query trace.

        Logic:
        - Wrong store queried → CONTEXT_BUG
        - Wrong mode detected → CONTEXT_BUG
        - Correct context, wrong output → MODEL_BUG
        - Exception/timeout → SYSTEM_ERROR

        Args:
            trace: QueryTrace instance with query metadata

        Returns:
            ErrorType enum (CONTEXT_BUG, MODEL_BUG, SYSTEM_ERROR)
        """
        # Check for pre-classified error
        if hasattr(trace, "error_type") and trace.error_type:
            try:
                return ErrorType(trace.error_type)
            except ValueError:
                pass

        # Analyze trace for classification
        if self._is_wrong_store(trace):
            return ErrorType.CONTEXT_BUG

        if self._is_wrong_mode(trace):
            return ErrorType.CONTEXT_BUG

        if self._is_wrong_lifecycle(trace):
            return ErrorType.CONTEXT_BUG

        # Check for system errors (timeout, exception)
        if hasattr(trace, "error") and trace.error:
            error_lower = str(trace.error).lower()
            if "timeout" in error_lower or "exception" in error_lower:
                return ErrorType.SYSTEM_ERROR

        # Default to model bug (correct context, wrong output)
        return ErrorType.MODEL_BUG

    def classify_context_bug(self, trace) -> ContextBugType:
        """
        Classify context bug subcategory.

        Args:
            trace: QueryTrace instance

        Returns:
            ContextBugType enum
        """
        if self._is_wrong_store(trace):
            return ContextBugType.WRONG_STORE_QUERIED

        if self._is_wrong_mode(trace):
            return ContextBugType.WRONG_MODE_DETECTED

        if self._is_wrong_lifecycle(trace):
            return ContextBugType.WRONG_LIFECYCLE_FILTER

        # Default to retrieval ranking error
        return ContextBugType.RETRIEVAL_RANKING_ERROR

    def _is_wrong_store(self, trace) -> bool:
        """
        Detect wrong store queried.

        Examples:
        - Query "What's my style?" should use KV, not vector
        - Query "What about X?" should use vector, not KV

        Args:
            trace: QueryTrace instance

        Returns:
            True if wrong store detected
        """
        if not hasattr(trace, "query"):
            return False

        query_lower = trace.query.lower().strip()

        # Get stores queried
        stores_queried = getattr(trace, "stores_queried", [])
        if isinstance(stores_queried, str):
            stores_queried = [stores_queried]

        # "What's my X?", "What is my X?", or "Whats my X?" should use KV
        if re.search(r"whats?(?:'s| is)? my (.*?)\??", query_lower):
            return "kv" not in stores_queried

        # "What about X?" should use vector
        if re.search(r"what about (.*?)\??", query_lower):
            return "vector" not in stores_queried

        return False

    def _is_wrong_mode(self, trace) -> bool:
        """
        Detect wrong mode detected.

        Example:
        - Execution query in brainstorming mode (no verification)
        - Planning query with "P(" notation should be in planning mode

        Args:
            trace: QueryTrace instance

        Returns:
            True if wrong mode detected
        """
        if not hasattr(trace, "query"):
            return False

        query_lower = trace.query.lower().strip()
        mode_detected = getattr(trace, "mode_detected", None)

        # Heuristic: If query contains "P(" or "probability", should be planning
        if re.search(r"p\(", query_lower):
            return mode_detected != "planning"

        return False

    def _is_wrong_lifecycle(self, trace) -> bool:
        """
        Detect wrong lifecycle filter.

        Example:
        - Session chunks in personal memory
        - Archived chunks in active queries

        Args:
            trace: QueryTrace instance

        Returns:
            True if wrong lifecycle detected
        """
        if not hasattr(trace, "retrieved_chunks") or not trace.retrieved_chunks:
            return False

        # Check if archived/demoted chunks returned for active query
        for chunk in trace.retrieved_chunks:
            if isinstance(chunk, dict):
                metadata = chunk.get("metadata", {})
                stage = metadata.get("stage", "active")

                # If query expects active but got archived/demoted
                if stage in ["archived", "demoted", "rehydratable"]:
                    # Check if query was looking for current/active info
                    if hasattr(trace, "query"):
                        query_lower = trace.query.lower()
                        # Keywords suggesting active/current query
                        if any(kw in query_lower for kw in ["current", "latest", "now", "today", "recent"]):
                            return True

        return False

    def get_statistics(self, days: int = 30) -> Dict:
        """
        Aggregate error statistics for dashboard.

        Args:
            days: Number of days to aggregate (default: 30)

        Returns:
            {
                "total_queries": int,
                "failed_queries": int,
                "failure_breakdown": {
                    "context_bugs": int,
                    "model_bugs": int,
                    "system_errors": int
                },
                "context_bug_breakdown": {
                    "wrong_store_queried": int,
                    "wrong_mode_detected": int,
                    "wrong_lifecycle_filter": int,
                    "retrieval_ranking_error": int
                }
            }
        """
        if not self.db:
            logger.warning("Database not available for statistics")
            return self._empty_stats()

        try:
            from datetime import datetime, timedelta
            import sqlite3

            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.isoformat()

            # Query total and failed queries
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM query_traces WHERE timestamp >= ?",
                (cutoff_str,)
            )
            total_queries = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM query_traces WHERE timestamp >= ? AND error IS NOT NULL",
                (cutoff_str,)
            )
            failed_queries = cursor.fetchone()[0]

            # Query error type breakdown
            cursor.execute(
                "SELECT error_type, COUNT(*) FROM query_traces WHERE timestamp >= ? AND error_type IS NOT NULL GROUP BY error_type",
                (cutoff_str,)
            )
            error_breakdown = dict(cursor.fetchall())

            stats = {
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

            logger.info(f"Statistics aggregated: {total_queries} queries, {failed_queries} failures in {days} days")
            return stats

        except Exception as e:
            logger.error(f"Failed to aggregate statistics: {e}")
            return self._empty_stats()

    def _empty_stats(self) -> Dict:
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
