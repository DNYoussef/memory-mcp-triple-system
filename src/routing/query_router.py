"""
Query Router - Polyglot Storage Selector

Routes queries to appropriate storage tier(s) based on pattern matching.
Part of Week 8 implementation for Memory MCP Triple System.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List, Dict, Optional, Any
from enum import Enum
import re
from loguru import logger


class StorageTier(Enum):
    """Storage tier identifiers (5-tier architecture)."""
    KV = "kv"
    RELATIONAL = "relational"
    VECTOR = "vector"
    GRAPH = "graph"
    EVENT_LOG = "event_log"
    BAYESIAN = "bayesian"


class QueryMode(Enum):
    """Query modes from mode detection."""
    EXECUTION = "execution"
    PLANNING = "planning"
    BRAINSTORMING = "brainstorming"


class QueryRouter:
    """
    Route queries to appropriate storage tier(s) based on pattern.

    PREMORTEM Risk #1 Mitigation:
    - Skip Bayesian for execution mode (60% of queries)
    - Reduces query latency from 800ms → 200ms

    Routing Rules:
    - "What's my X?" → KV (preferences)
    - "What client/project X?" → Relational (entities)
    - "What about X?" → Vector (semantic)
    - "What led to X?" → Graph (multi-hop)
    - "What happened on X?" → Event Log (temporal)
    - "P(X|Y)?" → Bayesian (probabilistic)

    Target: ≥90% routing accuracy

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self) -> None:
        """Initialize router with pattern rules."""
        self.patterns = self._compile_patterns()
        logger.info("QueryRouter initialized with routing patterns")

    def route(
        self,
        query: str,
        mode: QueryMode = QueryMode.EXECUTION,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[StorageTier]:
        """
        Route query to appropriate storage tier(s).

        Args:
            query: User query text
            mode: Detected query mode (execution/planning/brainstorming)
            user_context: Optional context for routing hints

        Returns:
            List of storage tiers to query (ordered by priority)

        Example:
            >>> router = QueryRouter()
            >>> tiers = router.route("What's my coding style?", QueryMode.EXECUTION)
            >>> print(tiers)
            [<StorageTier.KV: 'kv'>]

            >>> tiers = router.route("What about machine learning?", QueryMode.PLANNING)
            >>> print(tiers)
            [<StorageTier.VECTOR: 'vector'>, <StorageTier.GRAPH: 'graph'>]

        NASA Rule 10: 37 LOC (≤60) ✅
        """
        query_lower = query.lower().strip()
        matched_tiers: List[StorageTier] = []

        # Try pattern matching
        for pattern, tiers in self.patterns.items():
            if re.search(pattern, query_lower):
                matched_tiers = tiers
                logger.debug(f"Matched pattern '{pattern}' → {[t.value for t in tiers]}")
                break

        # ISS-029 FIX: Use keyword fallback instead of hardcoded default
        if not matched_tiers:
            matched_tiers = self._keyword_fallback(query_lower)
            logger.debug(f"No pattern match, using keyword fallback: {[t.value for t in matched_tiers]}")

        # Apply mode-based optimization
        if self.should_skip_bayesian(mode):
            # Remove Bayesian from results (60% optimization)
            matched_tiers = [t for t in matched_tiers if t != StorageTier.BAYESIAN]

        logger.info(f"Routed query to tiers: {[t.value for t in matched_tiers]}")
        return matched_tiers

    def should_skip_bayesian(
        self,
        mode: QueryMode,
        query_complexity: Optional[float] = None
    ) -> bool:
        """
        Decide whether to skip Bayesian network query.

        PREMORTEM Risk #1 Optimization:
        - Skip for execution mode (60% of queries)
        - Always query for planning/brainstorming modes

        Args:
            mode: Query mode
            query_complexity: Optional complexity score (0-1)

        Returns:
            True if should skip Bayesian, False otherwise

        NASA Rule 10: 13 LOC (≤60) ✅
        """
        # Execution mode: skip Bayesian (user wants facts, not probabilistic inference)
        if mode == QueryMode.EXECUTION:
            return True

        # Planning/brainstorming: use Bayesian for exploration
        return False

    def _compile_patterns(self) -> Dict[str, List[StorageTier]]:
        """
        ISS-029 FIX: Enhanced pattern matching with more coverage.

        Returns pattern dictionary mapping regex -> storage tiers.

        NASA Rule 10: 60 LOC (<=60)
        """
        patterns = {
            # KV Store: Preferences, settings, simple lookups
            r"what'?s?\s+my\s+": [StorageTier.KV],
            r"my\s+(coding|style|preference|setting|config)": [StorageTier.KV],
            r"(get|fetch|retrieve)\s+my\s+": [StorageTier.KV],
            r"(remember|recall)\s+my\s+": [StorageTier.KV],

            # Relational: Entity queries, structured data
            r"what\s+(client|project|task|file|user|document)\s+": [StorageTier.RELATIONAL],
            r"(list|show|find|search)\s+all\s+": [StorageTier.RELATIONAL, StorageTier.VECTOR],
            r"(how\s+many|count)\s+": [StorageTier.RELATIONAL],

            # Event Log: Temporal, historical queries
            r"what\s+happened\s+(on|at|during|in|since|before|after)": [StorageTier.EVENT_LOG],
            r"(when|timeline|history|recent|latest)\s+": [StorageTier.EVENT_LOG, StorageTier.GRAPH],
            r"(yesterday|today|last\s+(week|month|year))": [StorageTier.EVENT_LOG],

            # Graph: Multi-hop, relationship queries
            r"what\s+led\s+to": [StorageTier.GRAPH],
            r"(why|how)\s+did": [StorageTier.GRAPH, StorageTier.EVENT_LOG],
            r"(relationship|connection|link)\s+(between|with)": [StorageTier.GRAPH],
            r"(related|connected|associated)\s+to": [StorageTier.GRAPH, StorageTier.VECTOR],
            r"(trace|follow|path)\s+": [StorageTier.GRAPH],

            # Bayesian: Probabilistic, uncertainty queries
            r"p\s*\(.*\|.*\)": [StorageTier.BAYESIAN],
            r"(probability|likely|chance|likelihood)\s+": [StorageTier.BAYESIAN, StorageTier.GRAPH],
            r"(uncertain|confident|sure)\s+": [StorageTier.BAYESIAN],
            r"(predict|forecast|estimate)\s+": [StorageTier.BAYESIAN, StorageTier.VECTOR],

            # Vector: Semantic search, conceptual queries
            r"what\s+about": [StorageTier.VECTOR, StorageTier.GRAPH],
            r"(explain|describe|tell\s+me\s+about|elaborate)": [StorageTier.VECTOR],
            r"(similar|like|related)\s+to\s+": [StorageTier.VECTOR],
            r"(concept|idea|topic|theme)\s+": [StorageTier.VECTOR],
            r"(understand|learn|know)\s+about": [StorageTier.VECTOR],
        }

        logger.debug(f"Compiled {len(patterns)} routing patterns")
        return patterns

    def _keyword_fallback(self, query: str) -> List[StorageTier]:
        """ISS-029 FIX: Keyword-based fallback when no pattern matches."""
        keywords = {
            StorageTier.KV: ["preference", "setting", "config", "my"],
            StorageTier.RELATIONAL: ["client", "project", "task", "list", "all"],
            StorageTier.EVENT_LOG: ["when", "history", "timeline", "happened"],
            StorageTier.GRAPH: ["why", "relationship", "led", "caused", "connected"],
            StorageTier.BAYESIAN: ["probability", "likely", "chance", "predict"],
            StorageTier.VECTOR: ["about", "explain", "describe", "similar"],
        }
        query_lower = query.lower()
        scores = {tier: 0 for tier in StorageTier}
        for tier, words in keywords.items():
            for word in words:
                if word in query_lower:
                    scores[tier] += 1
        # Return tiers with highest scores
        max_score = max(scores.values())
        if max_score > 0:
            return [t for t, s in scores.items() if s == max_score]
        return [StorageTier.VECTOR, StorageTier.GRAPH]

    def validate_routing_accuracy(
        self,
        test_queries: List[Dict[str, Any]]
    ) -> float:
        """
        Validate routing accuracy against labeled test queries.

        Args:
            test_queries: List of dicts with keys:
                - query (str): Query text
                - expected_tiers (List[StorageTier]): Expected routing
                - mode (QueryMode): Query mode

        Returns:
            Accuracy score (0-1), target ≥0.90

        NASA Rule 10: 30 LOC (≤60) ✅
        """
        if not test_queries:
            logger.warning("No test queries provided for validation")
            return 0.0

        correct = 0
        total = len(test_queries)

        for test in test_queries:
            query = test["query"]
            expected = set(test["expected_tiers"])
            mode = test.get("mode", QueryMode.EXECUTION)

            # Route query
            actual = set(self.route(query, mode))

            # Check if routing matches expected
            if actual == expected:
                correct += 1

        accuracy = correct / total if total > 0 else 0.0

        logger.info(f"Routing accuracy: {accuracy:.2%} ({correct}/{total})")
        return accuracy
