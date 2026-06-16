"""
Unified Search Router for Text and Visual Memories.

MEM-QWEN-005: Single API to search both text (Nexus) and visual memories.
Routes queries to appropriate backends and merges results.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from ..nexus.processor import NexusProcessor
    from .visual_memory_service import VisualMemoryService


class UnifiedSearchRouter:
    """
    Unified search across text and visual memories.

    Routes queries to appropriate backends (NexusProcessor for text,
    VisualMemoryService for images) and merges results with configurable weights.
    """

    def __init__(
        self,
        nexus_processor: "NexusProcessor",
        visual_memory_service: Optional["VisualMemoryService"] = None,
        visual_weight: float = 0.3,
        text_weight: float = 0.7,
    ):
        """
        Initialize unified search router.

        Args:
            nexus_processor: Text memory NexusProcessor
            visual_memory_service: Visual memory service (optional)
            visual_weight: Weight for visual results in unified search
            text_weight: Weight for text results in unified search
        """
        self.nexus_processor = nexus_processor
        self.visual_service = visual_memory_service
        self.visual_weight = visual_weight
        self.text_weight = text_weight

        logger.info(
            f"UnifiedSearchRouter initialized: "
            f"text_weight={text_weight}, visual_weight={visual_weight}"
        )

    def search(
        self,
        query: str,
        mode: str = "execution",
        top_k: int = 10,
        include_visual: bool = True,
        include_text: bool = True,
    ) -> Dict[str, Any]:
        """
        Unified search across all memory types.

        Args:
            query: Search query
            mode: Query mode (execution, planning, brainstorming)
            top_k: Total number of results
            include_visual: Include visual memories
            include_text: Include text memories

        Returns:
            Unified search results with text and visual sections
        """
        results = {
            "query": query,
            "mode": mode,
            "text_results": [],
            "visual_results": [],
            "unified_results": [],
            "stats": {},
        }

        # Calculate per-source limits
        text_k, visual_k = self._calculate_limits(top_k, include_text, include_visual)

        # Execute searches
        if include_text:
            results["text_results"] = self._search_text(query, mode, text_k)
            results["stats"]["text_count"] = len(results["text_results"])

        if include_visual and self._visual_available():
            results["visual_results"] = self._search_visual(query, visual_k)
            results["stats"]["visual_count"] = len(results["visual_results"])

        # Merge and rank unified results
        results["unified_results"] = self._merge_results(
            text_results=results["text_results"],
            visual_results=results["visual_results"],
            top_k=top_k,
        )
        results["stats"]["unified_count"] = len(results["unified_results"])

        return results

    def _calculate_limits(
        self, top_k: int, include_text: bool, include_visual: bool
    ) -> tuple:
        """Calculate per-source result limits."""
        if include_text and include_visual:
            text_k = int(top_k * 0.7)
            visual_k = top_k - text_k
        elif include_text:
            text_k = top_k
            visual_k = 0
        else:
            text_k = 0
            visual_k = top_k
        return text_k, visual_k

    def _visual_available(self) -> bool:
        """Check if visual service is available."""
        return self.visual_service is not None and self.visual_service.enabled

    def _search_text(self, query: str, mode: str, top_k: int) -> List[Dict[str, Any]]:
        """Execute text search via NexusProcessor."""
        try:
            result = self.nexus_processor.process(query=query, mode=mode, top_k=top_k)
            return result.get("core", []) + result.get("extended", [])
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            return []

    def _search_visual(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Execute visual search via VisualMemoryService."""
        try:
            return self.visual_service.search_visual(query=query, top_k=top_k)
        except Exception as e:
            logger.error(f"Visual search failed: {e}")
            return []

    def _merge_results(
        self, text_results: List[Dict], visual_results: List[Dict], top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Merge and rank text and visual results.

        Args:
            text_results: Results from NexusProcessor
            visual_results: Results from VisualMemoryService
            top_k: Number of results to return

        Returns:
            Merged and ranked results
        """
        merged = []

        # Add text results with source tag (spread first to avoid score override)
        for result in text_results:
            original_score = result.get("score", 0)
            item = {**result}  # Copy original
            item["source"] = "text"
            item["original_score"] = original_score
            item["score"] = original_score * self.text_weight
            merged.append(item)

        # Add visual results with source tag
        for result in visual_results:
            original_score = result.get("score", 0)
            item = {**result}  # Copy original
            item["source"] = "visual"
            item["original_score"] = original_score
            item["score"] = original_score * self.visual_weight
            merged.append(item)

        # Sort by weighted score
        merged.sort(key=lambda x: x["score"], reverse=True)

        return merged[:top_k]

    def search_text_only(
        self, query: str, mode: str = "execution", top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search only text memories.

        Args:
            query: Text query
            mode: Query mode
            top_k: Number of results

        Returns:
            Text memory results
        """
        return self._search_text(query, mode, top_k)

    def search_visual_only(
        self, query: str, top_k: int = 10, visual_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search only visual memories.

        Args:
            query: Text query
            top_k: Number of results
            visual_type: Optional filter (screenshot, diagram, etc.)

        Returns:
            Visual memory results
        """
        if not self._visual_available():
            return []

        return self.visual_service.search_visual(
            query=query, top_k=top_k, visual_type=visual_type
        )

    def get_info(self) -> Dict[str, Any]:
        """Get router configuration info."""
        return {
            "text_weight": self.text_weight,
            "visual_weight": self.visual_weight,
            "visual_enabled": self._visual_available(),
            "visual_stats": (
                self.visual_service.get_stats() if self._visual_available() else None
            ),
        }
