"""Mode-aware retrieval router for Beads and Memory MCP."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..integrations.beads_bridge import BeadsBridge, BeadTask

logger = logging.getLogger(__name__)


class UnifiedRetrievalRouter:
    """Route retrieval between Beads and Memory MCP based on mode."""

    def __init__(
        self,
        beads_bridge: BeadsBridge,
        memory_service: Any,
    ) -> None:
        self._beads_bridge = beads_bridge
        self._memory_service = memory_service
        self._weights = {
            "execution": (0.8, 0.2),
            "planning": (0.5, 0.5),
            "brainstorming": (0.2, 0.8),
        }

    async def retrieve(
        self,
        query: str,
        mode: Optional[str] = None,
        token_budget: int = 10000,
    ) -> Dict[str, Any]:
        """Retrieve results from Beads and Memory MCP in parallel."""
        normalized_mode = (mode or "execution").lower()
        beads_weight, memory_weight = self._weights.get(
            normalized_mode, self._weights["execution"]
        )
        beads_budget = int(token_budget * beads_weight)
        memory_budget = max(0, token_budget - beads_budget)

        beads_task = self._retrieve_beads(query, beads_budget, normalized_mode)
        memory_task = self._retrieve_memory(query, memory_budget, normalized_mode)

        beads_result, memory_result = await asyncio.gather(
            beads_task,
            memory_task,
            return_exceptions=True,
        )

        beads_tasks = self._coerce_tasks(beads_result)
        memory_payload = self._coerce_memory(memory_result)

        return {
            "mode": normalized_mode,
            "token_budget": token_budget,
            "beads_budget": beads_budget,
            "memory_budget": memory_budget,
            "beads": beads_tasks,
            "memory": memory_payload,
        }

    async def _retrieve_beads(
        self,
        query: str,
        budget: int,
        mode: str,
    ) -> List[BeadTask]:
        try:
            limit = max(1, min(25, budget // 200))
            if mode == "execution":
                tasks = await self._beads_bridge.get_ready_tasks(limit=limit, brief=True)
            else:
                tasks = await self._beads_bridge.query_tasks(limit=limit, brief=True)
            return self._trim_to_budget(tasks, budget)
        except Exception as exc:
            logger.warning("Beads retrieval failed: %s", exc)
            return []

    async def _retrieve_memory(
        self,
        query: str,
        budget: int,
        mode: str,
    ) -> Dict[str, Any]:
        try:
            search = getattr(self._memory_service, "semantic_search", None)
            if search is None:
                logger.warning("Memory service missing semantic_search")
                return {"core": [], "extended": []}
            result = search(query=query, mode=mode, top_k=50, token_budget=budget)
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as exc:
            logger.warning("Memory retrieval failed: %s", exc)
            return {"core": [], "extended": []}

    def _trim_to_budget(self, tasks: List[BeadTask], budget: int) -> List[BeadTask]:
        if budget <= 0:
            return []
        trimmed: List[BeadTask] = []
        total = 0
        for task in tasks:
            estimate = _estimate_tokens(task)
            if total + estimate > budget:
                break
            trimmed.append(task)
            total += estimate
        return trimmed

    def _coerce_tasks(self, result: Any) -> List[BeadTask]:
        if isinstance(result, Exception):
            return []
        if isinstance(result, list):
            return result
        return []

    def _coerce_memory(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, Exception):
            return {"core": [], "extended": []}
        if isinstance(result, dict):
            return result
        return {"core": [], "extended": []}


def _estimate_tokens(task: BeadTask) -> int:
    title_tokens = len(task.title.split())
    desc_tokens = len((task.description or "").split())
    return max(10, title_tokens + desc_tokens)
