#!/usr/bin/env python3
"""SessionStart hook handler -- injects prior context at session start.

Called by Claude Code's SessionStart lifecycle event.
Reads stdin for hook payload, queries memory for relevant prior context,
outputs structured context block via stdout (hookSpecificOutput).

Usage (from settings.local.json):
    "hooks": {
        "SessionStart": [{
            "type": "command",
            "command": "python D:/Projects/memory-mcp-triple-system/src/hooks/session_start_handler.py"
        }]
    }

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.stores.kv_store import KVStore
from src.models.observation_types import Session
from src.services.token_calculator import TokenTracker


# Default paths
DEFAULT_DB = os.path.join(
    str(Path.home()), ".claude", "memory-mcp-data", "agent_kv.db"
)


def get_project_info() -> dict:
    """Extract project info from environment/cwd."""
    cwd = os.getcwd()
    project = os.path.basename(cwd)
    branch = ""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
    except Exception:
        pass
    return {"project": project, "branch": branch, "cwd": cwd}


def _get_beads_ready_tasks(limit: int = 3) -> str:
    """Query Beads for ready tasks. Returns formatted text or empty string."""
    bd_exe = os.path.join(
        str(Path.home()), "AppData", "Local", "beads", "bd.exe"
    )
    if not os.path.exists(bd_exe):
        return ""
    try:
        import subprocess
        result = subprocess.run(
            [bd_exe, "ls", "--ready", "--limit", str(limit)],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def build_context_block(store: KVStore, project: str, mode: str = "execution") -> str:
    """Build the context injection block from prior sessions and observations.

    Returns formatted text to inject via hookSpecificOutput.
    """
    tracker = TokenTracker(mode=mode)
    sections = []

    # Section 1: Last session summary (highest priority)
    last_session = store.get_last_session(project=project)
    if last_session and last_session.get("summary"):
        summary = last_session["summary"]
        if tracker.try_add("last_session", summary):
            sections.append(
                f"## Previous Session\n{summary}"
            )

    # Section 2: Recent observations for this project
    recent_obs = store.get_observations(project=project, limit=15)
    if recent_obs:
        obs_lines = []
        for obs in recent_obs:
            ts = obs.get("created_at", "")[:16]
            tool = obs.get("tool_name", "")
            content = obs.get("content", "")[:100].replace("\n", " ")
            obs_lines.append(f"  [{ts}] {tool}: {content}")

        obs_text = "\n".join(obs_lines)
        truncated = tracker.add_truncated("recent_observations", obs_text)
        if truncated:
            sections.append(
                f"## Recent Activity ({len(recent_obs)} observations)\n{truncated}"
            )

    # Section 3: Recent sessions list (for broader context)
    recent_sessions = store.get_recent_sessions(project=project, limit=3)
    if len(recent_sessions) > 1:
        sess_lines = []
        for s in recent_sessions[1:]:  # Skip the first (already shown as summary)
            started = s.get("started_at", "")[:16]
            tools = s.get("tool_count", 0)
            summ = s.get("summary", "")[:80].replace("\n", " ")
            sess_lines.append(f"  [{started}] {tools} tools - {summ}")

        sess_text = "\n".join(sess_lines)
        if tracker.try_add("prior_sessions", sess_text):
            sections.append(
                f"## Prior Sessions\n{sess_text}"
            )

    # Section 4: Beads ready tasks (if bd.exe available)
    beads_text = _get_beads_ready_tasks(limit=3)
    if beads_text and tracker.try_add("beads_tasks", beads_text):
        sections.append(f"## Ready Tasks (Beads)\n{beads_text}")

    if not sections:
        return ""

    header = f"# Memory Context [{project}]"
    footer = (
        f"\n---\n_Tokens: {tracker.used}/{tracker.budget} "
        f"({tracker.mode} mode)_"
    )
    return header + "\n\n" + "\n\n".join(sections) + footer


def main():
    """Main entry point for SessionStart hook."""
    # Read hook payload from stdin
    payload = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        pass

    # Get project info
    info = get_project_info()
    project = info["project"]

    # Open KVStore
    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        # No database yet -- nothing to inject
        return

    store = KVStore(db_path)

    try:
        # Create new session record
        session = Session(
            project=project,
            branch=info["branch"],
            working_dir=info["cwd"],
        )
        store.create_session(session.to_dict())

        # Store session ID in env file for PostToolUse/Stop to pick up
        session_file = os.path.join(
            str(Path.home()), ".claude", "memory-mcp-data", "current_session.json"
        )
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        with open(session_file, "w") as f:
            json.dump({
                "session_id": session.session_id,
                "project": project,
                "branch": info["branch"],
                "cwd": info["cwd"],
            }, f)

        # Build and output context injection
        context = build_context_block(store, project)
        if context:
            # hookSpecificOutput: Claude Code reads stdout from hook scripts
            print(context)

            # Token economics: track injection cost
            est_tokens = len(context) // 4
            store.set(
                f"economics:injection:{session.session_id}",
                json.dumps({
                    "session_id": session.session_id,
                    "project": project,
                    "injected_tokens": est_tokens,
                    "injected_chars": len(context),
                    "timestamp": session.started_at,
                }),
            )

    finally:
        store.close()


if __name__ == "__main__":
    main()
