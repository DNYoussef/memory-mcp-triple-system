"""Context builder -- assembles injection context from multiple sources.

Priority ordering:
  1. Recent session summary (highest)
  2. Recent observations for current project
  3. Historical session list
  4. Beads active tasks (if available)

Token-aware truncation via TokenTracker.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from ..stores.kv_store import KVStore
from .token_calculator import TokenTracker


class ContextBuilder:
    """Assembles context injection blocks from memory sources."""

    def __init__(self, kv_store: KVStore):
        self.kv_store = kv_store

    def build(
        self,
        project: str,
        mode: str = "execution",
        include_beads: bool = False,
        beads_tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build full context injection block.

        Args:
            project: Current project name
            mode: Token budget mode (execution/planning/brainstorming)
            include_beads: Whether to include Beads task context
            beads_tasks: Pre-fetched Beads tasks (avoids re-querying)

        Returns:
            Formatted context block string, empty if nothing to inject
        """
        tracker = TokenTracker(mode=mode)
        sections = []

        # Section 1: Last session summary
        section = self._build_session_summary(tracker, project)
        if section:
            sections.append(section)

        # Section 2: Recent observations
        section = self._build_observations(tracker, project)
        if section:
            sections.append(section)

        # Section 3: Prior sessions
        section = self._build_prior_sessions(tracker, project)
        if section:
            sections.append(section)

        # Section 4: Beads tasks
        if include_beads and beads_tasks:
            section = self._build_beads_context(tracker, beads_tasks)
            if section:
                sections.append(section)

        if not sections:
            return ""

        header = f"# Memory Context [{project}]"
        footer = (
            f"\n---\n_Tokens: {tracker.used}/{tracker.budget} "
            f"({tracker.mode} mode)_"
        )
        return header + "\n\n" + "\n\n".join(sections) + footer

    def _build_session_summary(
        self, tracker: TokenTracker, project: str
    ) -> str:
        """Build last session summary section."""
        last = self.kv_store.get_last_session(project=project)
        if not last or not last.get("summary"):
            return ""

        summary = last["summary"]
        if tracker.try_add("last_session", summary):
            return f"## Previous Session\n{summary}"
        return ""

    def _build_observations(
        self, tracker: TokenTracker, project: str
    ) -> str:
        """Build recent observations section."""
        obs_list = self.kv_store.get_observations(project=project, limit=15)
        if not obs_list:
            return ""

        lines = []
        for obs in obs_list:
            ts = obs.get("created_at", "")[:16]
            tool = obs.get("tool_name", "")
            content = obs.get("content", "")[:100].replace("\n", " ")
            lines.append(f"  [{ts}] {tool}: {content}")

        text = "\n".join(lines)
        truncated = tracker.add_truncated("recent_observations", text)
        if truncated:
            return f"## Recent Activity ({len(obs_list)} observations)\n{truncated}"
        return ""

    def _build_prior_sessions(
        self, tracker: TokenTracker, project: str
    ) -> str:
        """Build prior sessions list section."""
        sessions = self.kv_store.get_recent_sessions(project=project, limit=3)
        if len(sessions) <= 1:
            return ""

        lines = []
        for s in sessions[1:]:
            started = s.get("started_at", "")[:16]
            tools = s.get("tool_count", 0)
            summ = s.get("summary", "")[:80].replace("\n", " ")
            lines.append(f"  [{started}] {tools} tools - {summ}")

        text = "\n".join(lines)
        if tracker.try_add("prior_sessions", text):
            return f"## Prior Sessions\n{text}"
        return ""

    def _build_beads_context(
        self, tracker: TokenTracker, tasks: List[Dict[str, Any]]
    ) -> str:
        """Build Beads active tasks section."""
        if not tasks:
            return ""

        lines = []
        for task in tasks[:3]:  # Top 3 only
            title = task.get("title", task.get("subject", ""))[:80]
            status = task.get("status", "")
            priority = task.get("priority", "")
            lines.append(f"  [{status}] P{priority}: {title}")

        text = "\n".join(lines)
        if tracker.try_add("beads_tasks", text):
            return f"## Active Tasks (Beads)\n{text}"
        return ""

    def get_token_summary(self) -> Dict[str, Any]:
        """Return last build's token usage (for economics tracking)."""
        # This would be set during build() -- for now return empty
        return {}
