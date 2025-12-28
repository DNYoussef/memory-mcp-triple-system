"""
Detection Rules - Focused component for error detection patterns.

Extracted from ErrorAttribution to improve cohesion.
Single Responsibility: Pattern matching for error detection.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import re
from typing import Any
from loguru import logger


class DetectionRules:
    """
    Rules for detecting specific error types.

    Single Responsibility: Pattern-based error detection.
    Cohesion: HIGH - all methods are detection rules.
    """

    def is_wrong_store(self, trace: Any) -> bool:
        """
        Detect if wrong store was queried.

        Args:
            trace: QueryTrace instance

        Returns:
            True if wrong store detected
        """
        if not hasattr(trace, "query"):
            return False

        query_lower = trace.query.lower().strip()
        stores_queried = getattr(trace, "stores_queried", [])

        if isinstance(stores_queried, str):
            stores_queried = [stores_queried]

        # "What's my X?" should use KV store
        if re.search(r"whats?(?:'s| is)? my (.*?)\??", query_lower):
            return "kv" not in stores_queried

        # "What about X?" should use vector store
        if re.search(r"what about (.*?)\??", query_lower):
            return "vector" not in stores_queried

        return False

    def is_wrong_mode(self, trace: Any) -> bool:
        """
        Detect if wrong mode was detected.

        Args:
            trace: QueryTrace instance

        Returns:
            True if wrong mode detected
        """
        if not hasattr(trace, "query"):
            return False

        query_lower = trace.query.lower().strip()
        mode_detected = getattr(trace, "mode_detected", None)

        # If query contains "P(" or "probability", should be planning
        if re.search(r"p\(", query_lower):
            return mode_detected != "planning"

        return False

    def is_wrong_lifecycle(self, trace: Any) -> bool:
        """
        Detect if wrong lifecycle filter was used.

        Args:
            trace: QueryTrace instance

        Returns:
            True if wrong lifecycle detected
        """
        if not hasattr(trace, "retrieved_chunks") or not trace.retrieved_chunks:
            return False

        for chunk in trace.retrieved_chunks:
            if isinstance(chunk, dict):
                metadata = chunk.get("metadata", {})
                stage = metadata.get("stage", "active")

                if stage in ["archived", "demoted", "rehydratable"]:
                    if hasattr(trace, "query"):
                        query_lower = trace.query.lower()
                        active_keywords = ["current", "latest", "now", "today", "recent"]
                        if any(kw in query_lower for kw in active_keywords):
                            return True

        return False
