"""
Pattern-based mode detection.

Detects interaction mode (execution, planning, brainstorming) from query patterns.
"""

import re
from typing import Tuple
from loguru import logger

from .mode_profile import ModeProfile, EXECUTION, PLANNING, BRAINSTORMING


class ModeDetector:
    """
    Pattern-based mode detector.

    Uses regex patterns to detect mode from query text.
    Falls back to execution mode if confidence <0.7.

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self) -> None:
        """Initialize mode detector with pattern definitions."""
        # Execution patterns (imperative, factual)
        self.execution_patterns = [
            r"\bwhat\s+is\b",
            r"\bwhat\s+are\b",
            r"\bhow\s+do\s+i\b",
            r"\bhow\s+to\b",
            r"\bshow\s+me\b",
            r"\bget\b",
            r"\bfind\b",
            r"\bfetch\b",
            r"\btell\s+me\b",
            r"\bexplain\b",
            r"\bdescribe\b"
        ]

        # Planning patterns (conditional, comparative)
        self.planning_patterns = [
            r"\bwhat\s+should\b",
            r"\bhow\s+can\s+i\b",
            r"\bhow\s+should\b",
            r"\bwhat\s+are\s+the\s+options\b",
            r"\bcompare\b",
            r"\bwhich\s+is\s+better\b",
            r"\bshould\s+i\b",
            r"\bwhen\s+should\b",
            r"\bwhat\s+if\s+i\b"
        ]

        # Brainstorming patterns (creative, exploratory)
        self.brainstorming_patterns = [
            r"\bwhat\s+if\b",
            r"\bcould\s+we\b",
            r"\bimagine\b",
            r"\bexplore\b",
            r"\bwhat\s+are\s+all\b",
            r"\bwhat\s+other\b",
            r"\blist\s+all\b",
            r"\bbrainstorm\b",
            r"\bideas\s+for\b"
        ]

        logger.info("ModeDetector initialized")

    def detect(self, query: str) -> Tuple[ModeProfile, float]:
        """
        Detect mode from query using pattern matching.

        Args:
            query: User query string

        Returns:
            (profile, confidence) tuple
            - profile: Detected ModeProfile
            - confidence: Detection confidence (0.0-1.0)

        Behavior:
            - If confidence >= 0.7: Return detected mode
            - If confidence < 0.7: Fallback to EXECUTION
        """
        if not query or not query.strip():
            logger.warning("Empty query, defaulting to execution mode")
            return EXECUTION, 0.5

        query_lower = query.lower().strip()

        # Score each mode
        scores = {
            'execution': self._score_execution_patterns(query_lower),
            'planning': self._score_planning_patterns(query_lower),
            'brainstorming': self._score_brainstorming_patterns(query_lower)
        }

        # Find mode with highest score
        detected_mode = max(scores, key=lambda x: scores[x])
        confidence = scores[detected_mode]

        # Fallback to execution if confidence too low
        if confidence < 0.7:
            logger.debug(
                f"Low confidence ({confidence:.2f}), "
                f"falling back to execution mode"
            )
            return EXECUTION, 0.5

        # Return detected mode
        profile = {
            'execution': EXECUTION,
            'planning': PLANNING,
            'brainstorming': BRAINSTORMING
        }[detected_mode]

        logger.debug(
            f"Detected mode: {detected_mode} "
            f"(confidence: {confidence:.2f})"
        )

        return profile, confidence

    def _score_execution_patterns(self, query: str) -> float:
        """
        Score query against execution patterns.

        Args:
            query: Lowercase query string

        Returns:
            Confidence score (0.0-1.0)
        """
        matches = 0

        for pattern in self.execution_patterns:
            if re.search(pattern, query):
                matches += 1

        # Normalize score (1 match = 0.8, 2+ matches = 1.0)
        if matches == 0:
            return 0.0
        elif matches == 1:
            return 0.8
        else:
            return 1.0

    def _score_planning_patterns(self, query: str) -> float:
        """
        Score query against planning patterns.

        Args:
            query: Lowercase query string

        Returns:
            Confidence score (0.0-1.0)
        """
        matches = 0

        for pattern in self.planning_patterns:
            if re.search(pattern, query):
                matches += 1

        # Normalize score (1 match = 0.8, 2+ matches = 1.0)
        if matches == 0:
            return 0.0
        elif matches == 1:
            return 0.8
        else:
            return 1.0

    def _score_brainstorming_patterns(self, query: str) -> float:
        """
        Score query against brainstorming patterns.

        Args:
            query: Lowercase query string

        Returns:
            Confidence score (0.0-1.0)
        """
        matches = 0

        for pattern in self.brainstorming_patterns:
            if re.search(pattern, query):
                matches += 1

        # Normalize score (1 match = 0.8, 2+ matches = 1.0)
        if matches == 0:
            return 0.0
        elif matches == 1:
            return 0.8
        else:
            return 1.0
