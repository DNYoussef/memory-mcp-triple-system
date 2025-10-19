"""
Helper script to find best SPEK agents for Memory MCP tasks.
Uses agent_registry.py from SPEK Platform.
"""

import sys
sys.path.insert(0, 'C:/Users/17175/Desktop/spek-v2-rebuild')

from src.coordination.agent_registry import find_drones_for_task, get_drone_description

# Week 1 Tasks
tasks = {
    "docker_devops": "Setup Docker Compose with Qdrant Neo4j Redis containers CI/CD pipeline deploy",
    "backend_qdrant": "Implement backend API for Qdrant vector database MCP server endpoints database",
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
