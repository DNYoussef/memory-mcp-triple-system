#!/usr/bin/env python3
"""Query BB beads using direct bd.exe list command."""

import subprocess
import json
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BEADS_CLI = r"C:\Users\17175\AppData\Local\beads\bd.exe"
BEADS_DIR = r"D:\2026-AI-EXOSKELETON"


def run_beads_list():
    """Run bd list --json --limit 0 to get all tasks."""
    result = subprocess.run(
        [BEADS_CLI, "list", "--json", "--limit", "0"],
        cwd=BEADS_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return []


def show_task(task_id):
    """Get detailed task info."""
    result = subprocess.run(
        [BEADS_CLI, "show", task_id],
        cwd=BEADS_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # Clean up unicode characters that may cause issues
    output = result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    # Replace problematic unicode chars
    output = output.replace('\u25cb', 'o').replace('\u25cf', '*')
    return output


def main():
    print("Loading all beads tasks...")
    all_tasks = run_beads_list()
    print(f"Total tasks: {len(all_tasks)}")

    # Filter for BB- tasks
    bb_tasks = [t for t in all_tasks if "BB-" in t.get("title", "")]
    print(f"Found {len(bb_tasks)} BB tasks:\n")

    for task in bb_tasks:
        task_id = task.get("id", "unknown")
        title = task.get("title", "no title")
        print(f"  {task_id}: {title}")

    print("\n" + "=" * 70)
    print("DETAILED VIEW OF BB TASKS")
    print("=" * 70)

    for task in bb_tasks:
        task_id = task.get("id")
        if task_id:
            print(f"\n### {task_id}")
            detail = show_task(task_id)
            print(detail)
            print("-" * 70)


if __name__ == "__main__":
    main()
