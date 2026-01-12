"""Async Beads CLI bridge with TTL caching."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


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
    description: Optional[str]
    status: str
    priority: int
    issue_type: str
    assignee: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
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
            dependencies=[
                BeadDependency.from_dict(dep)
                for dep in data.get("dependencies", [])
            ],
            labels=list(data.get("labels", [])),
            comments=[
                BeadComment.from_dict(comment)
                for comment in data.get("comments", [])
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
        if brief:
            cmd.append("--brief")
        if fields:
            cmd.extend(["--fields", ",".join(fields)])
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
        if brief:
            cmd.append("--brief")
        if fields:
            cmd.extend(["--fields", ",".join(fields)])
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

    async def _run_command(self, cmd: List[str]) -> Any:
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logger.warning("Beads CLI failed: %s", stderr.decode().strip())
                return []
            return json.loads(stdout.decode() or "[]")
        except Exception as exc:
            logger.error("Beads CLI error: %s", exc)
            return []


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
