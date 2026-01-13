"""Metadata synchronization between Beads and Memory MCP."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from .beads_bridge import BeadTask

logger = logging.getLogger(__name__)


class MetadataSync:
    """Sync metadata between Beads tasks and Memory MCP tagging."""

    def beads_to_memory_mcp(self, task: BeadTask, project: str) -> Dict[str, Any]:
        """Map Beads task metadata to Memory MCP tagging protocol."""
        who = task.assignee or "unknown"
        when = task.updated_at.isoformat() + "Z" if task.updated_at else _now_iso()
        why = task.issue_type or "task"
        return {
            "WHO": who,
            "WHEN": when,
            "PROJECT": project,
            "WHY": why,
            "beads": {
                "id": task.id,
                "status": task.status,
                "priority": task.priority,
                "labels": task.labels,
            },
        }

    async def sync_task_to_memory(
        self,
        task: BeadTask,
        memory_service: Any,
        project: str,
    ) -> None:
        """Sync a Beads task into Memory MCP store."""
        metadata = self.beads_to_memory_mcp(task, project)
        content = _task_to_content(task)
        try:
            store_fn = getattr(memory_service, "store_context", None)
            if store_fn is None:
                logger.warning("Memory service missing store_context")
                return
            result = store_fn(content, metadata, {"source": "beads"})
            if hasattr(result, "__await__"):
                await result
        except Exception as exc:
            logger.warning("Failed to sync task %s: %s", task.id, exc)


def _task_to_content(task: BeadTask) -> str:
    description = task.description or ""
    return f"{task.title}\n\n{description}".strip()


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"
