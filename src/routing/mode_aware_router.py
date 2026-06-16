"""
Mode-Aware Router - Dual Filing Cabinet routing by interaction mode.

ORG-002: Implement mode-aware routing.

Routing Weights by Mode:
- Execution: 80% Beads (tasks) / 20% Memory (context)
- Planning: 50% Beads / 50% Memory + LLM Council
- Brainstorming: 20% Beads / 80% Memory (exploration)

Purpose:
- Route queries to appropriate sources based on detected mode
- Balance between structured task data (Beads) and semantic memory
- Support LLM Council integration for planning decisions

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger


class InteractionMode(Enum):
    """Interaction modes for routing decisions."""

    EXECUTION = "execution"
    PLANNING = "planning"
    BRAINSTORMING = "brainstorming"


@dataclass
class RoutingWeight:
    """Weight configuration for a routing decision."""

    beads_weight: float  # Weight for Beads (tasks/structured data)
    memory_weight: float  # Weight for Memory MCP (semantic context)
    use_council: bool  # Whether to invoke LLM Council


# Mode routing configurations
MODE_WEIGHTS: Dict[InteractionMode, RoutingWeight] = {
    InteractionMode.EXECUTION: RoutingWeight(
        beads_weight=0.80, memory_weight=0.20, use_council=False
    ),
    InteractionMode.PLANNING: RoutingWeight(
        beads_weight=0.50, memory_weight=0.50, use_council=True
    ),
    InteractionMode.BRAINSTORMING: RoutingWeight(
        beads_weight=0.20, memory_weight=0.80, use_council=False
    ),
}


@dataclass
class RoutingDecision:
    """Result of a routing decision."""

    mode: InteractionMode
    beads_weight: float
    memory_weight: float
    use_council: bool
    sources: List[str]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode.value,
            "beads_weight": self.beads_weight,
            "memory_weight": self.memory_weight,
            "use_council": self.use_council,
            "sources": self.sources,
            "timestamp": self.timestamp,
        }


class ModeAwareRouter:
    """
    Route queries based on interaction mode.

    Implements the Dual Filing Cabinet contract:
    - Beads: Structured task data, dependencies, status
    - Memory MCP: Semantic context, learned patterns, expertise

    Routing Strategy:
    - Execution: Fast path, mostly Beads (80%)
    - Planning: Balanced, with LLM Council support (50/50)
    - Brainstorming: Exploratory, mostly Memory (80%)

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(
        self,
        beads_client: Optional[Any] = None,
        memory_client: Optional[Any] = None,
        council_client: Optional[Any] = None,
    ):
        """
        Initialize mode-aware router.

        Args:
            beads_client: Beads CLI/API client
            memory_client: Memory MCP client
            council_client: LLM Council client (optional)

        NASA Rule 10: 15 LOC (<=60)
        """
        self.beads_client = beads_client
        self.memory_client = memory_client
        self.council_client = council_client
        self.routing_history: List[RoutingDecision] = []

        logger.info("ModeAwareRouter initialized")

    def route(
        self,
        query: str,
        mode: InteractionMode,
        context: Optional[Dict[str, Any]] = None,
    ) -> RoutingDecision:
        """
        Route a query based on interaction mode.

        Args:
            query: User query
            mode: Detected interaction mode
            context: Optional additional context

        Returns:
            RoutingDecision with weights and sources

        NASA Rule 10: 35 LOC (<=60)
        """
        # Get weights for mode
        weights = MODE_WEIGHTS.get(mode, MODE_WEIGHTS[InteractionMode.EXECUTION])

        # Determine sources to query
        sources = self._determine_sources(weights, context)

        # Create decision
        decision = RoutingDecision(
            mode=mode,
            beads_weight=weights.beads_weight,
            memory_weight=weights.memory_weight,
            use_council=weights.use_council,
            sources=sources,
            timestamp=datetime.utcnow().isoformat(),
        )

        # Track history
        self.routing_history.append(decision)
        if len(self.routing_history) > 100:
            self.routing_history = self.routing_history[-50:]

        logger.info(
            f"Routed query: mode={mode.value}, "
            f"beads={weights.beads_weight:.0%}, memory={weights.memory_weight:.0%}"
        )

        return decision

    def _determine_sources(
        self, weights: RoutingWeight, context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Determine which sources to query based on weights.

        Args:
            weights: Routing weights
            context: Optional context

        Returns:
            List of source names to query

        NASA Rule 10: 25 LOC (<=60)
        """
        sources = []

        # Always include both if weights > 0
        if weights.beads_weight > 0:
            sources.append("beads")
        if weights.memory_weight > 0:
            sources.append("memory_mcp")

        # Add council for planning mode
        if weights.use_council and self.council_client:
            sources.append("llm_council")

        # Add context-specific sources
        if context:
            if context.get("include_graph"):
                sources.append("graph")
            if context.get("include_bayesian"):
                sources.append("bayesian")

        return sources

    def merge_results(
        self,
        decision: RoutingDecision,
        beads_results: Optional[List[Dict[str, Any]]] = None,
        memory_results: Optional[List[Dict[str, Any]]] = None,
        council_results: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Merge results from multiple sources using weighted scoring.

        Args:
            decision: Routing decision with weights
            beads_results: Results from Beads
            memory_results: Results from Memory MCP
            council_results: Results from LLM Council (if used)

        Returns:
            Merged and ranked results

        NASA Rule 10: 45 LOC (<=60)
        """
        merged = []

        # Score Beads results
        if beads_results:
            for result in beads_results:
                result["_source"] = "beads"
                result["_weight"] = decision.beads_weight
                result["_score"] = result.get("relevance", 0.5) * decision.beads_weight
                merged.append(result)

        # Score Memory results
        if memory_results:
            for result in memory_results:
                result["_source"] = "memory_mcp"
                result["_weight"] = decision.memory_weight
                result["_score"] = result.get("relevance", 0.5) * decision.memory_weight
                merged.append(result)

        # Add council recommendation (if present)
        if council_results and decision.use_council:
            council_item = {
                "_source": "llm_council",
                "_weight": 1.0,
                "_score": council_results.get("confidence", 0.8),
                "recommendation": council_results.get("recommendation"),
                "consensus": council_results.get("consensus"),
            }
            merged.append(council_item)

        # Sort by weighted score
        merged.sort(key=lambda x: x.get("_score", 0), reverse=True)

        logger.debug(
            f"Merged {len(merged)} results from {len(decision.sources)} sources"
        )
        return merged

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.

        Returns:
            Dict with routing stats

        NASA Rule 10: 25 LOC (<=60)
        """
        if not self.routing_history:
            return {"total_routes": 0, "by_mode": {}}

        by_mode = {}
        for decision in self.routing_history:
            mode_name = decision.mode.value
            if mode_name not in by_mode:
                by_mode[mode_name] = 0
            by_mode[mode_name] += 1

        return {
            "total_routes": len(self.routing_history),
            "by_mode": by_mode,
            "last_route": self.routing_history[-1].to_dict()
            if self.routing_history
            else None,
        }

    def adjust_weights(
        self, mode: InteractionMode, beads_weight: float, memory_weight: float
    ) -> None:
        """
        Dynamically adjust weights for a mode (for A/B testing).

        Args:
            mode: Mode to adjust
            beads_weight: New Beads weight (0-1)
            memory_weight: New Memory weight (0-1)

        NASA Rule 10: 15 LOC (<=60)
        """
        if mode not in MODE_WEIGHTS:
            logger.warning(f"Unknown mode: {mode}")
            return

        current = MODE_WEIGHTS[mode]
        MODE_WEIGHTS[mode] = RoutingWeight(
            beads_weight=max(0, min(1, beads_weight)),
            memory_weight=max(0, min(1, memory_weight)),
            use_council=current.use_council,
        )

        logger.info(
            f"Adjusted {mode.value} weights: "
            f"beads={beads_weight:.0%}, memory={memory_weight:.0%}"
        )
