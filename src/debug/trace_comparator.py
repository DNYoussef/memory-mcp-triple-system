"""
Trace Comparator - Focused component for comparing query traces.

Extracted from QueryReplay to improve cohesion.
Single Responsibility: Compare two traces and identify differences.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, List
from loguru import logger

from .query_trace import QueryTrace


class TraceComparator:
    """
    Compares query traces and identifies differences.

    Single Responsibility: Trace comparison logic.
    Cohesion: HIGH - all methods relate to trace comparison.
    """

    def compare(
        self,
        original: QueryTrace,
        replay: QueryTrace
    ) -> Dict[str, Any]:
        """
        Compare two traces and identify differences.

        Args:
            original: Original query trace
            replay: Replayed query trace

        Returns:
            Dictionary of differences
        """
        diff: Dict[str, Any] = {}

        # Compare mode detection
        if original.mode_detected != replay.mode_detected:
            diff["mode_detected"] = {
                "original": original.mode_detected,
                "replay": replay.mode_detected
            }

        # Compare stores queried
        if original.stores_queried != replay.stores_queried:
            diff["stores_queried"] = {
                "original": original.stores_queried,
                "replay": replay.stores_queried
            }

        # Compare output
        if original.output != replay.output:
            diff["output"] = {
                "original": original.output,
                "replay": replay.output
            }

        # Compare latency (significant difference > 20%)
        if self._latency_differs_significantly(original, replay):
            diff["latency_ms"] = {
                "original": original.total_latency_ms,
                "replay": replay.total_latency_ms
            }

        # Compare chunk counts
        orig_chunks = len(original.retrieved_chunks)
        replay_chunks = len(replay.retrieved_chunks)
        if orig_chunks != replay_chunks:
            diff["chunk_count"] = {
                "original": orig_chunks,
                "replay": replay_chunks
            }

        return diff

    def _latency_differs_significantly(
        self,
        original: QueryTrace,
        replay: QueryTrace,
        threshold: float = 0.2
    ) -> bool:
        """Check if latency difference exceeds threshold."""
        if original.total_latency_ms == 0:
            return replay.total_latency_ms > 0

        diff_ratio = abs(
            original.total_latency_ms - replay.total_latency_ms
        ) / original.total_latency_ms

        return diff_ratio > threshold

    def summarize(self, diff: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of differences.

        Args:
            diff: Difference dictionary from compare()

        Returns:
            Summary string
        """
        if not diff:
            return "No differences found - traces are identical."

        lines = ["Trace Comparison Summary:"]

        if "mode_detected" in diff:
            lines.append(
                f"  Mode: {diff['mode_detected']['original']} -> "
                f"{diff['mode_detected']['replay']}"
            )

        if "stores_queried" in diff:
            lines.append(
                f"  Stores: {diff['stores_queried']['original']} -> "
                f"{diff['stores_queried']['replay']}"
            )

        if "chunk_count" in diff:
            lines.append(
                f"  Chunks: {diff['chunk_count']['original']} -> "
                f"{diff['chunk_count']['replay']}"
            )

        if "latency_ms" in diff:
            lines.append(
                f"  Latency: {diff['latency_ms']['original']}ms -> "
                f"{diff['latency_ms']['replay']}ms"
            )

        if "output" in diff:
            lines.append("  Output: Different (see details)")

        return "\n".join(lines)
