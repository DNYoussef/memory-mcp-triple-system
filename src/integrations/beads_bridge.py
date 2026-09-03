"""Async Beads CLI bridge with TTL caching and dependency tree support."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BeadsCLIError(RuntimeError):
    """Raised when the Beads CLI cannot return a valid response."""


def resolve_beads_binary(explicit: Optional[str] = None) -> str:
    """Resolve the bd binary with one precedence across every surface.

    explicit arg, then MEMORY_MCP_BEADS_CLI, then BEADS_BINARY (back-compat),
    then "bd" on PATH. Keeps a single source of truth so configuring one env
    var reaches the main MCP BeadsBridge, the MCP tools, and the completion
    logger alike.
    """
    return (
        explicit
        or os.getenv("MEMORY_MCP_BEADS_CLI")
        or os.getenv("BEADS_BINARY")
        or "bd"
    )


@dataclass(frozen=True)
class DependencyNode:
    """Represents a node in the dependency tree with depth info."""

    id: str
    title: str
    status: str
    depth: int
    parent_id: Optional[str] = None
    estimated_minutes: int = 0
    labels: Tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DependencyNode":
        return cls(
            id=str(data.get("id", "")),
            title=data.get("title", ""),
            status=data.get("status", "open"),
            depth=int(data.get("depth", 0)),
            parent_id=data.get("parent_id"),
            estimated_minutes=int(data.get("estimated_minutes", 0)),
            labels=tuple(data.get("labels", [])),
        )


@dataclass(frozen=True)
class BlockedTask:
    """Represents a blocked task with blocking dependencies."""

    id: str
    title: str
    status: str
    blocked_by: Tuple[str, ...]
    blocked_by_count: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlockedTask":
        return cls(
            id=str(data.get("id", "")),
            title=data.get("title", ""),
            status=data.get("status", "open"),
            blocked_by=tuple(data.get("blocked_by", [])),
            blocked_by_count=int(data.get("blocked_by_count", 0)),
        )


@dataclass
class DependencyGraph:
    """Represents a connected component in the dependency graph."""

    root: Dict[str, Any]
    issues: List[Dict[str, Any]]
    layers: Dict[int, List[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DependencyGraph":
        graph = cls(
            root=data.get("Root", {}),
            issues=data.get("Issues", []),
        )
        # Build layer mapping from issues
        for issue in graph.issues:
            # Infer layer from dependency chain depth
            deps = issue.get("dependencies", [])
            layer = len(deps)
            if layer not in graph.layers:
                graph.layers[layer] = []
            graph.layers[layer].append(issue.get("id", ""))
        return graph


@dataclass(frozen=True)
class BeadDependency:
    """Represents a Beads dependency record."""

    id: str
    status: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeadDependency":
        return cls(id=str(data.get("id", "")), status=data.get("status"))


@dataclass(frozen=True)
class BeadComment:
    """Represents a Beads comment record."""

    author: Optional[str]
    body: str
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeadComment":
        created = _parse_datetime(data.get("created_at"))
        return cls(
            author=data.get("author"),
            body=data.get("body", ""),
            created_at=created,
        )


@dataclass(frozen=True)
class BeadTask:
    """Represents a Beads task."""

    id: str
    title: str
    status: str
    priority: int
    issue_type: str
    # Nullable fields default to None (constructed by keyword in from_dict);
    # required fields lead so the dataclass ordering stays valid.
    description: Optional[str] = None
    assignee: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    estimated_minutes: int = 0
    dependency_count: int = 0
    dependent_count: int = 0
    dependencies: List[BeadDependency] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    comments: List[BeadComment] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeadTask":
        return cls(
            id=str(data.get("id", "")),
            title=data.get("title", ""),
            description=data.get("description"),
            status=data.get("status", "open"),
            priority=int(data.get("priority", 2)),
            issue_type=data.get("issue_type", "task"),
            assignee=data.get("assignee"),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            estimated_minutes=int(data.get("estimated_minutes", 0)),
            dependency_count=int(data.get("dependency_count", 0)),
            dependent_count=int(data.get("dependent_count", 0)),
            dependencies=[
                BeadDependency.from_dict(dep) for dep in data.get("dependencies", [])
            ],
            labels=list(data.get("labels", [])),
            comments=[
                BeadComment.from_dict(comment) for comment in data.get("comments", [])
            ],
        )

    @classmethod
    def empty(cls, task_id: str) -> "BeadTask":
        return cls(
            id=task_id,
            title="",
            description=None,
            status="unknown",
            priority=0,
            issue_type="task",
            assignee=None,
            created_at=None,
            updated_at=None,
            estimated_minutes=0,
            dependency_count=0,
            dependent_count=0,
        )


class BeadsBridge:
    """Async wrapper around the Beads CLI (bd)."""

    def __init__(self, beads_binary: str = "bd", cache_ttl: int = 60) -> None:
        self._binary = beads_binary
        self._cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, Any]] = {}

    async def get_ready_tasks(
        self,
        limit: int = 10,
        brief: bool = True,
        fields: Optional[List[str]] = None,
    ) -> List[BeadTask]:
        """Get unblocked tasks ready for work."""
        cmd = [self._binary, "ready", "--json"]
        # Note: --brief removed as it's not supported in current bd CLI
        if limit:
            cmd.extend(["--limit", str(limit)])

        data = await self._run_cached(cmd)
        if not isinstance(data, list):
            return []
        return [BeadTask.from_dict(item) for item in data]

    async def get_task_detail(self, task_id: str) -> BeadTask:
        """Get full task details with dependencies and comments."""
        cmd = [self._binary, "show", task_id, "--json"]
        data = await self._run_cached(cmd, cache_key=f"task:{task_id}")
        if not isinstance(data, dict):
            return BeadTask.empty(task_id)
        return BeadTask.from_dict(data)

    async def query_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        assignee: Optional[str] = None,
        limit: int = 20,
        brief: bool = True,
        fields: Optional[List[str]] = None,
    ) -> List[BeadTask]:
        """Query tasks with filters."""
        cmd = [self._binary, "list", "--json", "--limit", str(limit)]
        # Note: --brief removed as it's not supported in current bd CLI
        if status:
            cmd.extend(["--status", status])
        if priority is not None:
            cmd.extend(["--priority", str(priority)])
        if assignee:
            cmd.extend(["--assignee", assignee])

        data = await self._run_cached(cmd)
        if not isinstance(data, list):
            return []
        return [BeadTask.from_dict(item) for item in data]

    async def _run_cached(
        self,
        cmd: List[str],
        cache_key: Optional[str] = None,
    ) -> Any:
        cache_key = cache_key or " ".join(cmd)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        payload = await self._run_command(cmd)
        if payload is not None:
            self._set_cached(cache_key, payload)
        return payload

    def _get_cached(self, key: str) -> Optional[Any]:
        cached = self._cache.get(key)
        if not cached:
            return None
        timestamp, payload = cached
        if time.time() - timestamp > self._cache_ttl:
            self._cache.pop(key, None)
            return None
        return payload

    def _set_cached(self, key: str, payload: Any) -> None:
        self._cache[key] = (time.time(), payload)

    async def _run_command(self, cmd: List[str], timeout: float = 30.0) -> Any:
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            if process.returncode != 0:
                raise BeadsCLIError(
                    stderr.decode().strip() or f"Beads CLI exited {process.returncode}"
                )
            return json.loads(stdout.decode() or "[]")
        except asyncio.TimeoutError:
            # A hung bd must not block the tool call indefinitely (the caller
            # joins this on a thread with no timeout). Kill and reap it.
            logger.error("Beads CLI timed out after %ss: %s", timeout, " ".join(cmd))
            if process is not None:
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
            raise BeadsCLIError(f"Beads CLI timed out after {timeout}s")
        except BeadsCLIError:
            raise
        except Exception as exc:
            logger.error("Beads CLI error: %s", exc)
            raise BeadsCLIError(str(exc)) from exc

    # ========== DEPENDENCY TREE METHODS ==========

    async def get_dependency_tree(
        self,
        task_id: str,
        max_depth: int = 10,
    ) -> List[DependencyNode]:
        """Get dependency tree for a task with depth information.

        Returns list of DependencyNode objects ordered by depth.
        Use format_tree_ascii() to get a visual representation.
        """
        cmd = [self._binary, "dep", "tree", task_id, "--json"]
        data = await self._run_cached(cmd, cache_key=f"tree:{task_id}")
        if not isinstance(data, list):
            return []
        nodes = [DependencyNode.from_dict(item) for item in data]
        return [n for n in nodes if n.depth <= max_depth]

    async def get_blocked_tasks(self, limit: int = 50) -> List[BlockedTask]:
        """Get all blocked tasks with their blocking dependencies.

        Returns tasks that cannot start until their blockers are resolved.
        """
        # Note: bd blocked doesn't support --limit, we filter in Python
        cmd = [self._binary, "blocked", "--json"]
        data = await self._run_cached(cmd)
        if not isinstance(data, list):
            return []
        tasks = [BlockedTask.from_dict(item) for item in data]
        return tasks[:limit] if limit else tasks

    async def get_full_graph(self) -> List[DependencyGraph]:
        """Get full dependency graph for all open issues.

        Returns list of connected components, each with root and issues.
        """
        cmd = [self._binary, "graph", "--all", "--json"]
        data = await self._run_cached(cmd, cache_key="graph:all")
        if not isinstance(data, list):
            return []
        return [DependencyGraph.from_dict(item) for item in data]

    async def get_critical_path(self) -> List[BeadTask]:
        """Get tasks on the critical path (most dependents).

        Returns tasks sorted by number of dependents (most blocking first).
        P2-2 FIX: query_tasks already returns full BeadTask objects with
        dependencies populated - no need to re-fetch each task individually
        (was spawning N+1 subprocesses).
        """
        all_tasks = await self.query_tasks(limit=200)
        critical = [t for t in all_tasks if t.dependencies]
        return critical

    def format_tree_ascii(
        self,
        nodes: List[DependencyNode],
        show_status: bool = True,
        show_estimate: bool = True,
    ) -> str:
        """Format dependency tree as ASCII art.

        Example output:
        MOO-002: Red Queen Co-evolution Safety [open] (8h)
        ├── MOO-001: Implement 8-Objective Vector [open] (12h)
        └── RQ-008: 7 Red Queen Objectives [open] (12h)
            └── RQ-007: Co-Evolutionary Helix Loop [open] (16h)
                └── RQ-006: 6-Step Threat Pipeline [open] (12h)
        """
        if not nodes:
            return "(empty tree)"

        # ASCII-compatible status icons (Windows cp1252 safe)
        STATUS_ICONS = {
            "open": "[ ]",
            "in_progress": "[~]",
            "blocked": "[X]",
            "closed": "[+]",
            "deferred": "[-]",
        }

        lines = []
        rendered_ids: set = set()

        # Group nodes by parent_id for tree structure
        # Exclude self-references (where parent_id == id)
        children: Dict[Optional[str], List[DependencyNode]] = {}
        for node in nodes:
            parent = node.parent_id
            # Skip self-references to avoid infinite recursion
            if parent == node.id:
                parent = None
            if parent not in children:
                children[parent] = []
            children[parent].append(node)

        def _render_node(
            node: DependencyNode, prefix: str, is_last: bool, depth: int = 0
        ) -> None:
            # Prevent infinite recursion
            if node.id in rendered_ids or depth > 20:
                return
            rendered_ids.add(node.id)

            # Build node line
            connector = "..." if is_last else "|-- "
            icon = STATUS_ICONS.get(node.status, "?")

            parts = [f"{prefix}{connector}{node.title}"]
            if show_status:
                parts.append(f" [{icon} {node.status}]")
            if show_estimate and node.estimated_minutes > 0:
                hours = node.estimated_minutes / 60
                parts.append(f" ({hours:.1f}h)")

            lines.append("".join(parts))

            # Render children (excluding self)
            node_children = [c for c in children.get(node.id, []) if c.id != node.id]
            new_prefix = prefix + ("    " if is_last else "|   ")
            for i, child in enumerate(node_children):
                _render_node(child, new_prefix, i == len(node_children) - 1, depth + 1)

        # Find and render root nodes (depth 0)
        roots = [n for n in nodes if n.depth == 0]
        for root in roots:
            if root.id in rendered_ids:
                continue
            rendered_ids.add(root.id)

            icon = STATUS_ICONS.get(root.status, "?")
            parts = [root.title]
            if show_status:
                parts.append(f" [{icon} {root.status}]")
            if show_estimate and root.estimated_minutes > 0:
                hours = root.estimated_minutes / 60
                parts.append(f" ({hours:.1f}h)")
            lines.append("".join(parts))

            # Render children of root (excluding root itself)
            root_children = [c for c in children.get(root.id, []) if c.id != root.id]
            for i, child in enumerate(root_children):
                _render_node(child, "", i == len(root_children) - 1, 1)

        return "\n".join(lines)

    async def print_dependency_tree(self, task_id: str) -> str:
        """Convenience method: Get and format dependency tree as ASCII."""
        nodes = await self.get_dependency_tree(task_id)
        return self.format_tree_ascii(nodes)

    async def get_execution_order(self) -> List[List[BeadTask]]:
        """Get tasks grouped by execution layer.

        Layer 0 = no dependencies (start immediately)
        Layer 1 = depends only on Layer 0
        Layer N = depends on layers < N

        Tasks in the same layer can run in parallel.
        P2-2 FIX: Pre-fetch all tasks in one call to avoid N+1 subprocess
        spawns (was calling get_task_detail per blocked task).
        """
        ready = await self.get_ready_tasks(limit=100)
        blocked = await self.get_blocked_tasks(limit=100)

        layers: Dict[int, List[BeadTask]] = {0: ready}

        # Build dependency depth map
        blocked_map = {b.id: b for b in blocked}

        # Pre-fetch all tasks in one call instead of per-task detail fetches
        all_tasks = await self.query_tasks(limit=200)
        task_by_id = {t.id: t for t in all_tasks}

        def _get_layer(task_id: str, visited: set) -> int:
            if task_id in visited:
                return 0  # Cycle detected, treat as layer 0
            visited.add(task_id)

            if task_id not in blocked_map:
                return 0

            blocked_task = blocked_map[task_id]
            if not blocked_task.blocked_by:
                return 0

            max_dep_layer = 0
            for dep_id in blocked_task.blocked_by:
                dep_layer = _get_layer(dep_id, visited)
                max_dep_layer = max(max_dep_layer, dep_layer)

            return max_dep_layer + 1

        # Assign blocked tasks to layers using pre-fetched data
        for task in blocked:
            layer = _get_layer(task.id, set())
            if layer not in layers:
                layers[layer] = []
            detail = task_by_id.get(task.id, BeadTask.empty(task.id))
            layers[layer].append(detail)

        # Return as list of lists, sorted by layer
        return [layers.get(i, []) for i in range(max(layers.keys()) + 1)]


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ========== ORG-005: Memory MCP Integration ==========
