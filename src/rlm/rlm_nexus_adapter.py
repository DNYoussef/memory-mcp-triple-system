"""
RLM Nexus Adapter - replaces Nexus 5-step SOP with RLM exploration.

RLM-008: Add RLM mode to Nexus Processor.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from loguru import logger

from .rlm_environment import RLMConfig
from .rlm_memory_env import RLMMemoryEnvironment


class RLMNexusAdapter:
    """Adapter that returns Nexus-shaped results using RLM search."""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        config: Optional[RLMConfig] = None,
        environment: Optional[RLMMemoryEnvironment] = None,
    ) -> None:
        self._env = environment or RLMMemoryEnvironment(config=config, data_dir=data_dir)
        self._loaded = False

    def explore(
        self,
        query: str,
        mode: str = "execution",
        top_k: int = 50,
        token_budget: int = 10000,
    ) -> Dict[str, Any]:
        if not self._loaded:
            self._loaded = self._env.load_data("all")
            logger.info(f"RLM environment loaded: {self._loaded}")

        results = self._env.search(query, limit=top_k)
        core = results[:5]
        extended = results[5:25] if mode != "execution" else []
        token_count = sum(len(r.get("content", "").split()) for r in core + extended)
        ratio = token_count / max(1, token_budget)

        return {
            "core": core,
            "extended": extended,
            "token_count": token_count,
            "compression_ratio": ratio,
            "mode": mode,
            "rlm_stats": self._env.get_stats(),
        }
