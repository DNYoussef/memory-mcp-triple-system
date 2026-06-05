#!/usr/bin/env python3
"""Test script for BeadsBridge dependency tree methods."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.beads_bridge import BeadsBridge


async def main():
    """Test the new BeadsBridge dependency methods."""
    # Initialize bridge with full path to bd.exe
    bd_path = r"C:\Users\17175\AppData\Local\beads\bd.exe"
    bridge = BeadsBridge(beads_binary=bd_path)

    print("=" * 60)
    print("BEADS BRIDGE DEPENDENCY TREE TEST")
    print("=" * 60)

    # 1. Test get_ready_tasks
    print("\n[1] READY TASKS (no blockers):")
    print("-" * 40)
    ready = await bridge.get_ready_tasks(limit=5)
    for task in ready:
        hrs = task.estimated_minutes / 60 if hasattr(task, 'estimated_minutes') else 0
        print(f"  {task.id}: {task.title[:50]}... ({hrs:.1f}h)")
    print(f"  ... showing 5 of {len(ready)} ready tasks")

    # 2. Test get_blocked_tasks
    print("\n[2] BLOCKED TASKS (have dependencies):")
    print("-" * 40)
    blocked = await bridge.get_blocked_tasks(limit=5)
    for task in blocked:
        blockers = ", ".join(task.blocked_by[:2])
        if len(task.blocked_by) > 2:
            blockers += f" +{len(task.blocked_by) - 2} more"
        print(f"  {task.id}: {task.title[:40]}...")
        print(f"    blocked by: {blockers}")
    print(f"  ... showing 5 of {len(blocked)} blocked tasks")

    # 3. Test get_dependency_tree for a specific task
    test_task_id = "life-os-dashboard-0l8"  # MOO-002
    print(f"\n[3] DEPENDENCY TREE for {test_task_id}:")
    print("-" * 40)
    tree = await bridge.get_dependency_tree(test_task_id)
    ascii_tree = bridge.format_tree_ascii(tree)
    print(ascii_tree)

    # 4. Test get_full_graph (summary only)
    print("\n[4] FULL GRAPH (connected components):")
    print("-" * 40)
    graphs = await bridge.get_full_graph()
    print(f"  Found {len(graphs)} connected components:")
    for i, graph in enumerate(graphs[:5]):
        root_title = graph.root.get("title", "Unknown")[:40]
        print(f"    {i+1}. {root_title}... ({len(graph.issues)} issues)")
    if len(graphs) > 5:
        print(f"    ... and {len(graphs) - 5} more components")

    # 5. Summary stats
    print("\n[5] SUMMARY:")
    print("-" * 40)
    print(f"  Ready tasks:   {len(ready)}")
    print(f"  Blocked tasks: {len(blocked)}")
    print(f"  Components:    {len(graphs)}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    # Change working directory to the AI Exoskeleton project
    import os
    os.chdir(r"D:\2026-AI-EXOSKELETON")

    asyncio.run(main())
