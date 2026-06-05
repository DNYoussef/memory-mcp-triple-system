"""Mode Detection Confidence Scorer for CAPTURE-003.

Scores confidence for mode detection (Execution, Planning, Brainstorming).

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from src.integrations.confidence_scoring_schema import (
    ConfidenceScore,
    ClassificationResult,
    ClassificationType,
    EscalationReason,
    combine_confidences,
    entropy_based_confidence,
    margin_based_confidence,
    ESCALATION_THRESHOLD,
)

logger = logging.getLogger(__name__)


class Mode:
    """Detected operating modes."""
    EXECUTION = "execution"
    PLANNING = "planning"
    BRAINSTORMING = "brainstorming"


# Pattern weights for each mode
MODE_PATTERNS = {
    Mode.EXECUTION: {
        "patterns": [
            (r"\bwhat is\b", 0.8),
            (r"\bhow do i\b", 0.85),
            (r"\bshow me\b", 0.75),
            (r"\bget\b.*\b(file|data|info)", 0.7),
            (r"\bread\b.*\b(file|code)", 0.8),
            (r"\brun\b", 0.85),
            (r"\bexecute\b", 0.9),
            (r"\bfind\b", 0.7),
            (r"\bsearch\b", 0.7),
            (r"\blist\b", 0.65),
            (r"\bwhere\b", 0.7),
            (r"\bfix\b", 0.8),
            (r"\binstall\b", 0.85),
            (r"\bupdate\b", 0.75),
            (r"\bdelete\b", 0.8),
            (r"\bcreate\b", 0.75),
        ],
        "question_weight": 0.6,
        "imperative_weight": 0.8,
    },
    Mode.PLANNING: {
        "patterns": [
            (r"\bwhat should\b", 0.85),
            (r"\bhow should\b", 0.85),
            (r"\bplan\b", 0.9),
            (r"\bstrategy\b", 0.85),
            (r"\bcompare\b", 0.8),
            (r"\bwhich.*better\b", 0.85),
            (r"\bpros and cons\b", 0.9),
            (r"\btrade.?offs?\b", 0.85),
            (r"\bdesign\b", 0.75),
            (r"\barchitecture\b", 0.8),
            (r"\bapproach\b", 0.7),
            (r"\bshould i\b", 0.8),
            (r"\bwould it be\b", 0.7),
            (r"\bbest way\b", 0.75),
            (r"\brecommend\b", 0.8),
        ],
        "question_weight": 0.8,
        "imperative_weight": 0.5,
    },
    Mode.BRAINSTORMING: {
        "patterns": [
            (r"\bwhat if\b", 0.9),
            (r"\bimagine\b", 0.95),
            (r"\bbrainstorm\b", 0.95),
            (r"\bideas?\b", 0.8),
            (r"\bpossibilities\b", 0.85),
            (r"\bcreative\b", 0.8),
            (r"\binnovate\b", 0.85),
            (r"\bexplore\b", 0.7),
            (r"\bthink about\b", 0.75),
            (r"\bconsider\b", 0.6),
            (r"\bhypothetical\b", 0.9),
            (r"\btheoretically\b", 0.85),
            (r"\bwhat.*possible\b", 0.8),
            (r"\bcould we\b", 0.7),
        ],
        "question_weight": 0.7,
        "imperative_weight": 0.4,
    },
}


@dataclass
class ModeDetectionConfig:
    """Configuration for mode detection scorer."""

    escalation_threshold: float = ESCALATION_THRESHOLD
    ambiguity_margin: float = 0.15
    min_text_length: int = 5
    enable_caching: bool = True


class ModeDetectionScorer:
    """Confidence scorer for mode detection.

    Analyzes input text to determine operating mode and confidence.
    """

    def __init__(self, config: Optional[ModeDetectionConfig] = None):
        """Initialize mode detection scorer.

        Args:
            config: Scorer configuration
        """
        self.config = config or ModeDetectionConfig()
        self._cache: Dict[str, ClassificationResult] = {}
        self._stats = {
            "total_detections": 0,
            "by_mode": {m: 0 for m in [Mode.EXECUTION, Mode.PLANNING, Mode.BRAINSTORMING]},
            "escalations": 0,
            "ambiguous": 0,
        }

    def detect_mode(self, text: str) -> ClassificationResult:
        """Detect operating mode from text with confidence score.

        Args:
            text: Input text to analyze

        Returns:
            ClassificationResult with mode and confidence
        """
        # Check cache
        cache_key = text[:200].lower()
        if self.config.enable_caching and cache_key in self._cache:
            return self._cache[cache_key]

        # Normalize text
        text_lower = text.lower().strip()

        # Short text handling
        if len(text_lower) < self.config.min_text_length:
            result = ClassificationResult.create(
                classification_type=ClassificationType.MODE_DETECTION,
                value=Mode.EXECUTION,
                confidence_score=0.5,
                input_text=text,
                confidence_components={"text_length_penalty": 0.5},
            )
            self._update_stats(result)
            return result

        # Calculate scores for each mode
        mode_scores: Dict[str, float] = {}
        mode_components: Dict[str, Dict[str, float]] = {}

        for mode, config in MODE_PATTERNS.items():
            score, components = self._calculate_mode_score(text_lower, mode, config)
            mode_scores[mode] = score
            mode_components[mode] = components

        # Get top modes
        sorted_modes = sorted(mode_scores.items(), key=lambda x: x[1], reverse=True)
        top_mode, top_score = sorted_modes[0]
        second_mode, second_score = sorted_modes[1] if len(sorted_modes) > 1 else (None, 0.0)

        # Calculate overall confidence
        confidence_score = self._calculate_confidence(
            top_score, second_score, mode_scores
        )

        # Build alternatives
        alternatives = [
            {"mode": m, "confidence": round(s, 4)}
            for m, s in sorted_modes[1:]
            if s > 0.1
        ]

        # Create result
        result = ClassificationResult.create(
            classification_type=ClassificationType.MODE_DETECTION,
            value=top_mode,
            confidence_score=confidence_score,
            input_text=text,
            alternatives=alternatives,
            confidence_components=mode_components.get(top_mode, {}),
        )

        # Update cache and stats
        if self.config.enable_caching:
            self._cache[cache_key] = result

        self._update_stats(result)

        return result

    def _calculate_mode_score(
        self,
        text: str,
        mode: str,
        config: Dict[str, Any],
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate score for a specific mode."""
        components: Dict[str, float] = {}
        pattern_scores: List[float] = []

        # Check patterns
        for pattern, weight in config["patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                pattern_scores.append(weight)
                components[f"pattern:{pattern[:20]}"] = weight

        # Calculate pattern score
        if pattern_scores:
            pattern_score = max(pattern_scores) * 0.7 + (sum(pattern_scores) / len(pattern_scores)) * 0.3
        else:
            pattern_score = 0.1

        components["pattern_score"] = pattern_score

        # Check sentence structure
        is_question = text.rstrip().endswith("?")
        has_imperative = bool(re.match(r"^(show|get|find|run|create|fix|list|read)", text))

        if is_question:
            structure_score = config["question_weight"]
            components["question_detected"] = structure_score
        elif has_imperative:
            structure_score = config["imperative_weight"]
            components["imperative_detected"] = structure_score
        else:
            structure_score = 0.5
            components["neutral_structure"] = structure_score

        # Combine scores
        final_score = pattern_score * 0.6 + structure_score * 0.4
        components["final_score"] = final_score

        return final_score, components

    def _calculate_confidence(
        self,
        top_score: float,
        second_score: float,
        all_scores: Dict[str, float],
    ) -> float:
        """Calculate overall confidence from mode scores."""
        # Margin-based confidence (how much better is top vs second)
        margin_conf = margin_based_confidence(top_score, second_score)

        # Score magnitude (how strong is the top score itself)
        magnitude_conf = min(1.0, top_score)

        # Combine with weighted average favoring margin
        # Margin is most important for mode detection
        return 0.6 * margin_conf + 0.4 * magnitude_conf

    def _update_stats(self, result: ClassificationResult) -> None:
        """Update internal statistics."""
        self._stats["total_detections"] += 1
        self._stats["by_mode"][result.value] = (
            self._stats["by_mode"].get(result.value, 0) + 1
        )

        if result.confidence.needs_escalation():
            self._stats["escalations"] += 1

        if result.is_ambiguous():
            self._stats["ambiguous"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get scorer statistics."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
        }

    def clear_cache(self) -> None:
        """Clear the detection cache."""
        self._cache.clear()

    def get_escalation_reason(
        self,
        result: ClassificationResult,
    ) -> Optional[EscalationReason]:
        """Determine escalation reason if needed."""
        if not result.confidence.needs_escalation():
            return None

        if result.is_ambiguous():
            return EscalationReason.AMBIGUOUS_CLASSIFICATION

        if result.confidence.score < 0.4:
            return EscalationReason.LOW_CONFIDENCE

        return EscalationReason.MODEL_UNCERTAINTY
