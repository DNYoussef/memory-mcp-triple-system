"""
Bead Completion Logger - Automated Memory MCP entries for completed beads.

Implements session improvement recommendations from 2026-01-24 reflection.
Creates structured Memory MCP entries with WHO/WHEN/PROJECT/WHY tagging.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import os
import subprocess

from src.integrations.beads_bridge import resolve_beads_binary
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger


# Bead label to WHY tag mapping
LABEL_TO_WHY: Dict[str, str] = {
    "bug": "bugfix",
    "bugfix": "bugfix",
    "fix": "bugfix",
    "feature": "feature",
    "enhancement": "feature",
    "refactor": "refactor",
    "refactoring": "refactor",
    "security": "security",
    "test": "testing",
    "testing": "testing",
    "docs": "documentation",
    "documentation": "documentation",
    "perf": "performance",
    "performance": "performance",
}


def infer_why_from_bead(labels: List[str], title: str) -> str:
    """
    Infer WHY tag from bead labels and title.

    Args:
        labels: List of bead labels
        title: Bead title

    Returns:
        WHY tag (bugfix, feature, refactor, etc.)

    NASA Rule 10: 20 LOC
    """
    # Check labels first
    for label in labels:
        label_lower = label.lower()
        if label_lower in LABEL_TO_WHY:
            return LABEL_TO_WHY[label_lower]

    # Infer from title keywords
    title_lower = title.lower()
    if any(w in title_lower for w in ["fix", "bug", "error", "issue"]):
        return "bugfix"
    if any(w in title_lower for w in ["add", "implement", "create", "new"]):
        return "feature"
    if any(w in title_lower for w in ["refactor", "clean", "improve"]):
        return "refactor"
    if any(w in title_lower for w in ["test", "spec"]):
        return "testing"
    if any(w in title_lower for w in ["doc", "readme"]):
        return "documentation"

    return "implementation"  # Default


def log_bead_completion(
    bead_id: str,
    project: str,
    files_changed: List[str],
    pattern: str,
    labels: Optional[List[str]] = None,
    title: Optional[str] = None,
    tests_added: Optional[List[str]] = None,
    confidence: str = "HIGH",
    agent_name: str = "claude:opus-4.5",
    kv_store: Optional[Any] = None,
    ttl_days: int = 180,
) -> Dict[str, Any]:
    """
    Log bead completion to Memory MCP.

    Creates structured entry with WHO/WHEN/PROJECT/WHY tags.

    Args:
        bead_id: Bead identifier (e.g., "life-os-dashboard-wvx8")
        project: Project name (e.g., "memory-mcp-triple-system")
        files_changed: List of modified file paths
        pattern: One-line description of fix approach
        labels: Bead labels (optional, for WHY inference)
        title: Bead title (optional, for WHY inference)
        tests_added: List of test files added (optional)
        confidence: HIGH, MEDIUM, or LOW
        agent_name: Agent identifier for WHO tag
        kv_store: KVStore instance (will create if None)
        ttl_days: Time-to-live in days

    Returns:
        Entry dict that was stored

    NASA Rule 10: 55 LOC
    """
    # Build entry
    entry = {
        # MANDATORY TAGS
        "WHO": agent_name,
        "WHEN": datetime.now(timezone.utc).isoformat(),
        "PROJECT": project,
        "WHY": infer_why_from_bead(labels or [], title or ""),
        # BEAD REFERENCE
        "bead_id": bead_id,
        "bead_title": title or "",
        # FIX DETAILS
        "pattern": pattern,
        "files_changed": files_changed,
        "tests_added": tests_added or [],
        "confidence": confidence,
    }

    # Store to Memory MCP
    key = f"fixes:codex:{bead_id}"

    if kv_store is None:
        try:
            from ..stores.kv_store import KVStore

            kv_db_path = Path.home() / ".claude" / "memory-mcp-data" / "agent_kv.db"
            kv_store = KVStore(str(kv_db_path))
            should_close = True
        except Exception as e:
            logger.error(f"Failed to connect to KVStore: {e}")
            return entry
    else:
        should_close = False

    try:
        # Convert days to seconds for KVStore TTL
        ttl_seconds = ttl_days * 24 * 60 * 60
        kv_store.set(key=key, value=json.dumps(entry), ttl=ttl_seconds)
        logger.info(f"Logged bead completion: {key}")
    except Exception as e:
        logger.error(f"Failed to log bead completion: {e}")
    finally:
        if should_close:
            kv_store.close()

    return entry


def verify_bead_unblocked(
    bead_id: str, beads_cli: Optional[str] = None, working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify bead has no open blockers before claiming.

    Args:
        bead_id: Bead identifier
        beads_cli: Path to beads CLI (default: MEMORY_MCP_BEADS_CLI env or "bd")
        working_dir: Working directory (default: MEMORY_MCP_BEADS_DIR env or cwd)

    Returns:
        {
            "unblocked": bool,
            "blockers": [list of open blockers],
            "bead_status": str
        }

    NASA Rule 10: 45 LOC
    """
    beads_cli = beads_cli or resolve_beads_binary()
    working_dir = working_dir or os.getenv("MEMORY_MCP_BEADS_DIR") or os.getcwd()

    result = {"unblocked": True, "blockers": [], "bead_status": "unknown"}

    try:
        # Get bead details without interpolating bead_id into a shell string.
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "& { Set-Location -LiteralPath $args[0]; & $args[1] show $args[2] }",
            working_dir,
            beads_cli,
            bead_id,
        ]
        output = subprocess.run(
            cmd, shell=False, capture_output=True, text=True, timeout=30
        )

        if output.returncode != 0:
            logger.error(f"Failed to get bead details: {output.stderr}")
            result["unblocked"] = False
            return result

        # Parse output for blockers
        lines = output.stdout.split("\n")
        in_depends = False

        for line in lines:
            if "DEPENDS ON" in line:
                in_depends = True
                continue
            if "BLOCKS" in line:
                in_depends = False
                continue

            if in_depends and line.strip().startswith("->"):
                # Check if blocker is open (no checkmark)
                if not line.strip().startswith("-> "):
                    # Has checkmark, blocker is closed
                    continue
                # Extract blocker ID and status
                blocker_line = line.strip()
                if "" not in blocker_line:  # No checkmark = still open
                    result["blockers"].append(blocker_line)
                    result["unblocked"] = False

        blockers_count = len(result["blockers"])
        status_msg = (
            "unblocked"
            if result["unblocked"]
            else f"blocked by {blockers_count} issues"
        )
        logger.info(f"Bead {bead_id}: {status_msg}")

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout checking bead {bead_id}")
        result["unblocked"] = False
    except Exception as e:
        logger.error(f"Error checking bead {bead_id}: {e}")
        result["unblocked"] = False

    return result


def get_parallel_test_command(
    test_files: List[str], project_root: str, workers: str = "auto"
) -> str:
    """
    Generate parallel pytest command for faster test execution.

    Args:
        test_files: List of test file paths
        project_root: Project root directory
        workers: Number of workers ("auto" or integer)

    Returns:
        pytest command string

    NASA Rule 10: 15 LOC
    """
    if not test_files:
        return f"cd {project_root} && python -m pytest tests/ -n {workers}"

    test_paths = " ".join(test_files)
    return (
        f"cd {project_root} && python -m pytest {test_paths} -n {workers} -v --tb=short"
    )
