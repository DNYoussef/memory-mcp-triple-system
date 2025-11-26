"""
Helper script to find best SPEK agents for Memory MCP tasks.
Uses agent_registry.py from SPEK Platform.
"""

import os
import sys

# Use environment variable or default to relative path
SPEK_PATH = os.environ.get('SPEK_PATH', os.path.expanduser('~/Desktop/spek-v2-rebuild'))
sys.path.insert(0, SPEK_PATH)

from src.coordination.agent_registry import find_drones_for_task, get_drone_description

# Week 1 Tasks (DEPRECATED - v5.0 uses ChromaDB and NetworkX, no Docker)
# This file is kept for reference only. System now uses:
# - ChromaDB (embedded) instead of Qdrant
# - NetworkX (in-memory) instead of Neo4j
tasks = {
    "docker_devops": "Setup Docker Compose with ChromaDB NetworkX Redis containers CI/CD pipeline deploy",
    "backend_chromadb": "Implement backend API for ChromaDB vector database MCP server endpoints database",
    "file_watcher": "Write code for Obsidian file watcher implement embedding pipeline vector indexing",
    "testing": "Write pytest tests for file watcher test embedding pipeline create test fixtures"
}

print("=== WEEK 1 AGENT RECOMMENDATIONS ===\n")

for task_name, task_desc in tasks.items():
    print(f"Task: {task_name}")
    print(f"Description: {task_desc}")
    drones = find_drones_for_task(task_desc, 'loop2')
    print(f"Recommended Drones (top 3):")
    for drone in drones[:3]:
        print(f"  - {drone}")
    print()
