"""Session summarizer -- generates structured summaries from observations.

Template-based, no LLM call. Takes a session's observations and produces
a SessionSummary with: request, investigated, learned, completed, next_steps.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from ..models.observation_types import (
    ObservationType,
    SessionSummary,
)
from ..stores.kv_store import KVStore


class SessionSummarizer:
    """Generates structured session summaries from captured observations."""

    def __init__(self, kv_store: KVStore):
        self.kv_store = kv_store

    def summarize(self, session_id: str) -> SessionSummary:
        """Generate a summary for a completed session.

        Args:
            session_id: Session to summarize

        Returns:
            Structured SessionSummary
        """
        # Get session metadata
        session = self.kv_store.get_session(session_id)
        observations = self.kv_store.get_observations(
            session_id=session_id, limit=500
        )

        summary = SessionSummary(session_id=session_id)
        summary.observation_count = len(observations)

        if session:
            started = session.get("started_at", "")
            ended = session.get("ended_at", "")
            if started and ended:
                from datetime import datetime
                try:
                    t0 = datetime.fromisoformat(started)
                    t1 = datetime.fromisoformat(ended)
                    summary.duration_seconds = (t1 - t0).total_seconds()
                except (ValueError, TypeError):
                    pass

        # Classify observations into summary sections
        summary.investigated = self._extract_investigated(observations)
        summary.learned = self._extract_learned(observations)
        summary.completed = self._extract_completed(observations)
        summary.request = self._infer_request(observations)
        summary.next_steps = self._infer_next_steps(observations)

        return summary

    def _extract_investigated(
        self, observations: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract what was investigated (files read, searches done)."""
        items = []
        seen = set()
        for obs in observations:
            tool = obs.get("tool_name", "")
            content = obs.get("content", "")
            if tool in ("Read", "Grep", "Glob", "WebSearch", "WebFetch"):
                # Extract the path or query from content
                key = content[:120]
                if key not in seen:
                    seen.add(key)
                    items.append(key)
        return items[:10]

    def _extract_learned(
        self, observations: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract discoveries and errors (things we learned)."""
        items = []
        for obs in observations:
            obs_type = obs.get("obs_type", "")
            if obs_type in ("error", "discovery"):
                content = obs.get("content", "")[:150]
                items.append(content)
        return items[:5]

    def _extract_completed(
        self, observations: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract what was completed (writes, edits, commands)."""
        items = []
        seen = set()
        for obs in observations:
            obs_type = obs.get("obs_type", "")
            tool = obs.get("tool_name", "")
            content = obs.get("content", "")
            if obs_type == "code_change" or tool in ("Write", "Edit", "Bash"):
                key = content[:120]
                if key not in seen:
                    seen.add(key)
                    items.append(key)
        return items[:10]

    def _infer_request(
        self, observations: List[Dict[str, Any]]
    ) -> str:
        """Infer what was requested from the first few observations."""
        if not observations:
            return ""
        # The earliest observations often relate to the user's request
        # Look at conversation-type or the first tool use
        for obs in reversed(observations):  # oldest first
            if obs.get("obs_type") == "conversation":
                return obs.get("content", "")[:200]
        # Fallback: first observation content
        if observations:
            first = observations[-1]  # oldest (list is DESC)
            return f"{first.get('tool_name', '')}: {first.get('content', '')[:150]}"
        return ""

    def _infer_next_steps(
        self, observations: List[Dict[str, Any]]
    ) -> List[str]:
        """Infer next steps from the last few observations.

        Heuristic: if last observations are errors or investigations
        without corresponding completions, those are likely unfinished work.
        """
        if len(observations) < 2:
            return []

        # Recent observations (newest first -- already sorted DESC)
        recent = observations[:5]
        steps = []

        for obs in recent:
            obs_type = obs.get("obs_type", "")
            content = obs.get("content", "")[:120]
            if obs_type == "error":
                steps.append(f"Fix: {content}")
            elif obs_type in ("tool_use", "discovery"):
                # If it's a read/search, the user might still be investigating
                tool = obs.get("tool_name", "")
                if tool in ("Read", "Grep", "Glob"):
                    steps.append(f"Continue investigating: {content}")

        return steps[:3]

    def store_summary(self, summary: SessionSummary) -> bool:
        """Store the summary in the session record and as a KV entry."""
        text = summary.to_text()

        # Update session record
        self.kv_store.end_session(
            session_id=summary.session_id,
            summary=text,
            tool_count=summary.observation_count,
        )

        # Also store as standalone KV for quick retrieval
        self.kv_store.set(
            f"session:summary:{summary.session_id}",
            text,
            ttl=30 * 86400,  # 30 day TTL
        )

        return True
