"""MCP Tools for Beads Task System Integration (MCP-005).

Provides MCP tool interfaces for interacting with the Beads CLI.

WHO: beads-mcp:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (MCP-005)
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Default Beads CLI path
DEFAULT_BEADS_CLI = r"C:\Users\17175\AppData\Local\beads\bd.exe"
DEFAULT_BEADS_DIR = r"D:\2026-AI-EXOSKELETON"


class BeadsTools:
    """MCP tool implementations for Beads task system integration."""

    def __init__(
        self,
        beads_cli_path: Optional[str] = None,
        beads_dir: Optional[str] = None,
        graph_service: Optional[Any] = None,
    ):
        """Initialize Beads tools.

        Args:
            beads_cli_path: Path to bd.exe CLI
            beads_dir: Working directory for beads operations
        """
        self.beads_cli = beads_cli_path or DEFAULT_BEADS_CLI
        self.beads_dir = beads_dir or DEFAULT_BEADS_DIR
        self.graph_service = graph_service

    def _run_beads_command(
        self,
        args: List[str],
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Run a beads CLI command.

        Args:
            args: Command arguments (without bd.exe)
            timeout: Command timeout in seconds

        Returns:
            Command result with stdout, stderr, success
        """
        try:
            cmd = [self.beads_cli] + args
            result = subprocess.run(
                cmd,
                cwd=self.beads_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "returncode": -1,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Beads CLI not found at {self.beads_cli}",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }

    # Task Listing Tools

    async def beads_list(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        label: Optional[str] = None,
        limit: int = 20,
        use_json: bool = False,
    ) -> Dict[str, Any]:
        """List beads tasks with optional filters.

        Args:
            status: Filter by status (open, closed, all)
            priority: Filter by priority (P0, P1, P2, P3)
            assignee: Filter by assignee
            label: Filter by label
            limit: Maximum tasks to return (0 for all)
            use_json: Return JSON format instead of text

        Returns:
            List of tasks or formatted text
        """
        args = ["list"]

        if status:
            args.extend(["--status", status])
        if priority:
            args.extend(["--priority", priority])
        if assignee:
            args.extend(["--assignee", assignee])
        if label:
            args.extend(["--label", label])
        if limit > 0:
            args.extend(["--limit", str(limit)])
        if use_json:
            args.append("--json")

        result = self._run_beads_command(args)

        if not result["success"]:
            return {
                "success": False,
                "error": result["stderr"],
                "tasks": [],
            }

        if use_json and result["stdout"]:
            try:
                tasks = json.loads(result["stdout"])
                return {
                    "success": True,
                    "tasks": tasks,
                    "count": len(tasks),
                }
            except json.JSONDecodeError:
                pass

        # Parse text output
        tasks = self._parse_list_output(result["stdout"])
        return {
            "success": True,
            "tasks": tasks,
            "count": len(tasks),
            "raw_output": result["stdout"],
        }

    async def beads_ready(
        self,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Get tasks that are ready to work on (not blocked by dependencies).

        Args:
            limit: Maximum tasks to return (0 for all)

        Returns:
            List of ready tasks
        """
        args = ["list", "--ready"]
        if limit > 0:
            args.extend(["--limit", str(limit)])

        result = self._run_beads_command(args)

        if not result["success"]:
            return {
                "success": False,
                "error": result["stderr"],
                "tasks": [],
            }

        tasks = self._parse_list_output(result["stdout"])
        return {
            "success": True,
            "tasks": tasks,
            "count": len(tasks),
            "raw_output": result["stdout"],
        }

    async def beads_show(
        self,
        task_id: str,
    ) -> Dict[str, Any]:
        """Show detailed information about a specific task.

        Args:
            task_id: The beads task ID

        Returns:
            Task details
        """
        result = self._run_beads_command(["show", task_id])

        if not result["success"]:
            return {
                "success": False,
                "error": result["stderr"],
                "task": None,
            }

        # Parse task details
        task = self._parse_show_output(result["stdout"], task_id)
        return {
            "success": True,
            "task": task,
            "raw_output": result["stdout"],
        }

    # Task Creation/Modification Tools

    async def beads_create(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "P2",
        task_type: str = "task",
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
        depends_on: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new beads task.

        Args:
            title: Task title
            description: Task description
            priority: Priority level (P0, P1, P2, P3)
            task_type: Task type (task, bug, feature, etc.)
            assignee: Assignee name
            labels: List of labels
            depends_on: List of task IDs this depends on

        Returns:
            Created task info
        """
        args = ["create", title]

        if description:
            args.extend(["--description", description])
        if priority:
            args.extend(["--priority", priority])
        if task_type:
            args.extend(["--type", task_type])
        if assignee:
            args.extend(["--assignee", assignee])
        if labels:
            for label in labels:
                args.extend(["--label", label])
        if depends_on:
            for dep in depends_on:
                args.extend(["--depends", dep])

        result = self._run_beads_command(args)

        if not result["success"]:
            return {
                "success": False,
                "error": result["stderr"],
                "task_id": None,
            }

        # Extract task ID from output
        task_id = self._extract_task_id(result["stdout"])
        return {
            "success": True,
            "task_id": task_id,
            "message": result["stdout"].strip(),
        }

    async def beads_close(
        self,
        task_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Close a beads task with a reason.

        Args:
            task_id: The beads task ID to close
            reason: Reason for closing

        Returns:
            Close result
        """
        result = self._run_beads_command(["close", task_id, "--reason", reason])

        if not result["success"]:
            return {
                "success": False,
                "error": result["stderr"],
            }

        return {
            "success": True,
            "task_id": task_id,
            "message": result["stdout"].strip(),
        }

    # Search and Query Tools

    async def beads_search(
        self,
        query: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Search beads tasks by text query.

        Args:
            query: Search query string
            limit: Maximum results

        Returns:
            Matching tasks
        """
        args = ["q", query]
        if limit > 0:
            args.extend(["--limit", str(limit)])

        result = self._run_beads_command(args)

        if not result["success"]:
            return {
                "success": False,
                "error": result["stderr"],
                "tasks": [],
            }

        tasks = self._parse_list_output(result["stdout"])
        return {
            "success": True,
            "tasks": tasks,
            "count": len(tasks),
            "query": query,
            "raw_output": result["stdout"],
        }

    async def beads_stats(self) -> Dict[str, Any]:
        """Get beads task statistics.

        Returns:
            Task counts by status, priority, etc.
        """
        result = self._run_beads_command(["stats"])

        if not result["success"]:
            return {
                "success": False,
                "error": result["stderr"],
                "stats": {},
            }

        stats = self._parse_stats_output(result["stdout"])
        return {
            "success": True,
            "stats": stats,
            "raw_output": result["stdout"],
        }

    # Memory Integration Tools

    async def beads_link_memory(
        self,
        task_id: str,
        memory_key: str,
        relationship: str = "related_to",
    ) -> Dict[str, Any]:
        """Link a memory entity to a beads task.

        This creates a cross-reference between Memory MCP and Beads.

        Args:
            task_id: Beads task ID
            memory_key: Memory MCP key/entity ID
            relationship: Type of relationship

        Returns:
            Link result
        """
        if self.graph_service is None:
            return {
                "success": False,
                "error": "Memory graph service is not configured; no graph link was created",
            }

        link_data = {
            "task_id": task_id,
            "memory_key": memory_key,
            "relationship": relationship,
            "created_at": self._get_timestamp(),
        }

        task_node = f"beads:{task_id}"
        memory_node = f"memory:{memory_key}"
        if hasattr(self.graph_service, "add_entity_node"):
            self.graph_service.add_entity_node(task_node, "beads_task", {"task_id": task_id})
            self.graph_service.add_entity_node(memory_node, "memory_entity", {"memory_key": memory_key})

        linked = self.graph_service.add_relationship(
            task_node,
            relationship,
            memory_node,
            link_data,
        )
        if not linked:
            return {
                "success": False,
                "error": "Memory graph service rejected the graph link",
            }

        return {
            "success": True,
            "link": link_data,
            "graph_edge": {"source": task_node, "target": memory_node, "type": relationship},
            "message": f"Linked memory {memory_key} to task {task_id}",
        }

    # Helper Methods

    def _parse_list_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse list command output into structured data.

        Args:
            output: Raw command output

        Returns:
            List of task dictionaries
        """
        tasks = []
        lines = output.strip().split("\n")

        for line in lines:
            if not line.strip():
                continue
            if line.startswith("Showing"):
                continue

            # Parse task line
            # Format: status task_id [priority] [type] [labels] - title
            task = self._parse_task_line(line)
            if task:
                tasks.append(task)

        return tasks

    def _parse_task_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single task line.

        Args:
            line: Task line from list output

        Returns:
            Task dictionary or None
        """
        # Regex to match task line format
        # Example: ○ life-os-dashboard-3yi [● P0] [task] [labels] - Title
        pattern = r"^[○●✓] (\S+)\s+\[(● \w+)\]\s+\[(\w+)\](?:\s+\[([^\]]+)\])?\s*-\s*(.+)$"
        match = re.match(pattern, line)

        if match:
            task_id = match.group(1)
            priority = match.group(2).replace("● ", "")
            task_type = match.group(3)
            labels_str = match.group(4)
            title = match.group(5)

            labels = []
            if labels_str:
                labels = [l.strip() for l in labels_str.split(",") if l.strip()]

            return {
                "task_id": task_id,
                "priority": priority,
                "type": task_type,
                "labels": labels,
                "title": title,
            }

        return None

    def _parse_show_output(
        self,
        output: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """Parse show command output.

        Args:
            output: Raw command output
            task_id: Task ID for context

        Returns:
            Task details dictionary
        """
        task = {
            "task_id": task_id,
            "title": "",
            "description": "",
            "status": "",
            "priority": "",
            "type": "",
            "labels": [],
            "depends_on": [],
            "assignee": "",
        }

        lines = output.strip().split("\n")
        in_description = False
        description_lines = []

        for line in lines:
            if "DESCRIPTION" in line:
                in_description = True
                continue
            elif "LABELS:" in line:
                in_description = False
                labels = line.replace("LABELS:", "").strip()
                task["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
            elif "DEPENDS ON" in line:
                in_description = False
            elif line.startswith("Owner:"):
                parts = line.split("·")
                for part in parts:
                    if "Assignee:" in part:
                        task["assignee"] = part.replace("Assignee:", "").strip()
            elif line.startswith("→"):
                # Dependency line
                dep_match = re.search(r"(\S+):", line)
                if dep_match:
                    task["depends_on"].append(dep_match.group(1))
            elif in_description:
                description_lines.append(line)
            elif "·" in line and task_id in line:
                # Title line
                title_match = re.search(rf"{task_id}\s*·\s*(.+?)\s*\[", line)
                if title_match:
                    task["title"] = title_match.group(1).strip()
                # Status and priority
                if "[OPEN]" in line or "[CLOSED]" in line:
                    task["status"] = "OPEN" if "[OPEN]" in line else "CLOSED"
                prio_match = re.search(r"\[● (\w+)\s*·", line)
                if prio_match:
                    task["priority"] = prio_match.group(1)

        task["description"] = "\n".join(description_lines).strip()
        return task

    def _parse_stats_output(self, output: str) -> Dict[str, Any]:
        """Parse stats command output.

        Args:
            output: Raw command output

        Returns:
            Stats dictionary
        """
        stats = {
            "total": 0,
            "by_status": {},
            "by_priority": {},
        }

        for line in output.strip().split("\n"):
            # Parse various stat lines
            if "total" in line.lower():
                match = re.search(r"(\d+)", line)
                if match:
                    stats["total"] = int(match.group(1))
            elif "open" in line.lower():
                match = re.search(r"(\d+)", line)
                if match:
                    stats["by_status"]["open"] = int(match.group(1))
            elif "closed" in line.lower():
                match = re.search(r"(\d+)", line)
                if match:
                    stats["by_status"]["closed"] = int(match.group(1))
            elif re.search(r"P\d", line):
                match = re.search(r"(P\d)[:\s]+(\d+)", line)
                if match:
                    stats["by_priority"][match.group(1)] = int(match.group(2))

        return stats

    def _extract_task_id(self, output: str) -> Optional[str]:
        """Extract task ID from create command output.

        Args:
            output: Command output

        Returns:
            Task ID or None
        """
        # Look for task ID pattern
        match = re.search(r"(life-os-dashboard-\w+)", output)
        if match:
            return match.group(1)

        # Try other patterns
        match = re.search(r"Created\s+(\S+)", output)
        if match:
            return match.group(1)

        return None

    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# Tool definitions for MCP registration
BEADS_TOOL_DEFINITIONS = [
    {
        "name": "beads_list",
        "description": "List beads tasks with optional filters (status, priority, assignee, label)",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "closed", "all"]},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                "assignee": {"type": "string"},
                "label": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "beads_ready",
        "description": "Get tasks that are ready to work on (not blocked by dependencies)",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "beads_show",
        "description": "Show detailed information about a specific beads task",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Beads task ID"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "beads_create",
        "description": "Create a new beads task",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"], "default": "P2"},
                "task_type": {"type": "string", "default": "task"},
                "assignee": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title"],
        },
    },
    {
        "name": "beads_close",
        "description": "Close a beads task with a reason",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to close"},
                "reason": {"type": "string", "description": "Reason for closing"},
            },
            "required": ["task_id", "reason"],
        },
    },
    {
        "name": "beads_search",
        "description": "Search beads tasks by text query",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "beads_stats",
        "description": "Get beads task statistics (counts by status, priority)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "beads_link_memory",
        "description": "Link a Memory MCP entity to a beads task",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Beads task ID"},
                "memory_key": {"type": "string", "description": "Memory MCP key/entity ID"},
                "relationship": {"type": "string", "default": "related_to"},
            },
            "required": ["task_id", "memory_key"],
        },
    },
]


# Singleton instance
_beads_tools: Optional[BeadsTools] = None


def get_beads_tools() -> BeadsTools:
    """Get the global BeadsTools instance."""
    global _beads_tools
    if _beads_tools is None:
        _beads_tools = BeadsTools()
    return _beads_tools


def initialize_beads_tools(
    beads_cli_path: Optional[str] = None,
    beads_dir: Optional[str] = None,
    graph_service: Optional[Any] = None,
) -> BeadsTools:
    """Initialize the global BeadsTools instance.

    Args:
        beads_cli_path: Path to bd.exe CLI
        beads_dir: Working directory for beads

    Returns:
        Initialized BeadsTools
    """
    global _beads_tools
    _beads_tools = BeadsTools(beads_cli_path, beads_dir, graph_service=graph_service)
    return _beads_tools
