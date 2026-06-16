"""
Memory Promoter - Promotion decision algorithm for seed archive.

SEED-002: Implement MemoryPromoter class.

Promotion Score Algorithm:
- Access frequency: 25%
- Reference count: 25%
- Content type bonus: 25%
- User importance: 25%

Promote if combined score >= 0.5

Purpose:
- Evaluate memories for promotion to seed archive
- Apply configurable promotion criteria
- Track promotion decisions for audit

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from loguru import logger


class ContentType(Enum):
    """Content types with promotion bonuses."""

    EXPERTISE = "expertise"  # 1.0 bonus
    DECISION = "decision"  # 0.9 bonus
    PATTERN = "pattern"  # 0.8 bonus
    FIX = "fix"  # 0.7 bonus
    FINDING = "finding"  # 0.6 bonus
    CONTEXT = "context"  # 0.5 bonus
    GENERAL = "general"  # 0.3 bonus


# Content type promotion bonuses (0-1)
CONTENT_TYPE_BONUS: Dict[ContentType, float] = {
    ContentType.EXPERTISE: 1.0,
    ContentType.DECISION: 0.9,
    ContentType.PATTERN: 0.8,
    ContentType.FIX: 0.7,
    ContentType.FINDING: 0.6,
    ContentType.CONTEXT: 0.5,
    ContentType.GENERAL: 0.3,
}


@dataclass
class PromotionCriteria:
    """Configuration for promotion decision."""

    min_score: float = 0.5  # Minimum score to promote
    access_weight: float = 0.25  # Weight for access frequency
    reference_weight: float = 0.25  # Weight for reference count
    content_weight: float = 0.25  # Weight for content type
    importance_weight: float = 0.25  # Weight for user importance
    min_age_days: int = 7  # Minimum age before promotion eligible


@dataclass
class PromotionCandidate:
    """A memory candidate for promotion evaluation."""

    memory_id: str
    text: str
    metadata: Dict[str, Any]
    access_count: int = 0
    reference_count: int = 0
    content_type: ContentType = ContentType.GENERAL
    user_importance: float = 0.5
    created_at: Optional[str] = None
    decay_score: float = 1.0


@dataclass
class PromotionResult:
    """Result of a promotion evaluation."""

    memory_id: str
    should_promote: bool
    total_score: float
    access_score: float
    reference_score: float
    content_score: float
    importance_score: float
    reason: str
    evaluated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory_id,
            "should_promote": self.should_promote,
            "total_score": round(self.total_score, 3),
            "scores": {
                "access": round(self.access_score, 3),
                "reference": round(self.reference_score, 3),
                "content": round(self.content_score, 3),
                "importance": round(self.importance_score, 3),
            },
            "reason": self.reason,
            "evaluated_at": self.evaluated_at,
        }


class MemoryPromoter:
    """
    Evaluate memories for promotion to seed archive.

    Promotion Algorithm:
    1. Calculate access frequency score (normalized)
    2. Calculate reference count score (normalized)
    3. Apply content type bonus
    4. Include user importance
    5. Combine with configurable weights
    6. Promote if score >= min_score (default 0.5)

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self, criteria: Optional[PromotionCriteria] = None):
        """
        Initialize memory promoter.

        Args:
            criteria: Promotion criteria configuration

        NASA Rule 10: 10 LOC (<=60)
        """
        self.criteria = criteria or PromotionCriteria()
        self.evaluation_history: List[PromotionResult] = []

        logger.info(f"MemoryPromoter initialized (min_score={self.criteria.min_score})")

    def should_promote(self, candidate: PromotionCandidate) -> PromotionResult:
        """
        Evaluate if a memory should be promoted.

        Args:
            candidate: Memory candidate to evaluate

        Returns:
            PromotionResult with decision and scores

        NASA Rule 10: 50 LOC (<=60)
        """
        # Calculate individual scores
        access_score = self._score_access(candidate.access_count)
        reference_score = self._score_references(candidate.reference_count)
        content_score = self._score_content_type(candidate.content_type)
        importance_score = min(1.0, max(0.0, candidate.user_importance))

        # Calculate weighted total
        total_score = (
            access_score * self.criteria.access_weight
            + reference_score * self.criteria.reference_weight
            + content_score * self.criteria.content_weight
            + importance_score * self.criteria.importance_weight
        )

        # Make decision
        promote = total_score >= self.criteria.min_score

        # Determine reason
        if promote:
            reason = self._promotion_reason(
                access_score, reference_score, content_score, importance_score
            )
        else:
            reason = (
                f"Score {total_score:.2f} below threshold {self.criteria.min_score}"
            )

        result = PromotionResult(
            memory_id=candidate.memory_id,
            should_promote=promote,
            total_score=total_score,
            access_score=access_score,
            reference_score=reference_score,
            content_score=content_score,
            importance_score=importance_score,
            reason=reason,
        )

        # Track history
        self.evaluation_history.append(result)
        if len(self.evaluation_history) > 1000:
            self.evaluation_history = self.evaluation_history[-500:]

        logger.debug(
            f"Evaluated {candidate.memory_id}: "
            f"score={total_score:.3f}, promote={promote}"
        )

        return result

    def _score_access(self, access_count: int) -> float:
        """
        Score access frequency (0-1).

        Uses log scaling: score = min(1, log10(access + 1) / 2)
        - 0 accesses = 0.0
        - 10 accesses = 0.5
        - 100 accesses = 1.0

        NASA Rule 10: 12 LOC (<=60)
        """
        import math

        if access_count <= 0:
            return 0.0
        # Log scale: 10 accesses = 0.5, 100 = 1.0
        score = math.log10(access_count + 1) / 2.0
        return min(1.0, score)

    def _score_references(self, reference_count: int) -> float:
        """
        Score reference count (0-1).

        Uses linear scaling with cap at 10 references.
        - 0 references = 0.0
        - 5 references = 0.5
        - 10+ references = 1.0

        NASA Rule 10: 10 LOC (<=60)
        """
        if reference_count <= 0:
            return 0.0
        # Linear scale: 10 references = 1.0
        score = reference_count / 10.0
        return min(1.0, score)

    def _score_content_type(self, content_type: ContentType) -> float:
        """
        Get content type bonus score (0-1).

        NASA Rule 10: 5 LOC (<=60)
        """
        return CONTENT_TYPE_BONUS.get(content_type, 0.3)

    def _promotion_reason(
        self,
        access_score: float,
        reference_score: float,
        content_score: float,
        importance_score: float,
    ) -> str:
        """
        Generate promotion reason based on top contributing factors.

        NASA Rule 10: 20 LOC (<=60)
        """
        factors = [
            ("High access frequency", access_score),
            ("Many references", reference_score),
            ("Valuable content type", content_score),
            ("User marked important", importance_score),
        ]

        # Sort by score
        factors.sort(key=lambda x: x[1], reverse=True)

        # Top 2 factors
        top_factors = [f[0] for f in factors[:2] if f[1] >= 0.5]

        if top_factors:
            return "; ".join(top_factors)
        return "Cumulative score meets threshold"

    def evaluate_batch(
        self, candidates: List[PromotionCandidate]
    ) -> List[PromotionResult]:
        """
        Evaluate multiple candidates for promotion.

        Args:
            candidates: List of candidates

        Returns:
            List of promotion results

        NASA Rule 10: 15 LOC (<=60)
        """
        results = []
        for candidate in candidates:
            result = self.should_promote(candidate)
            results.append(result)

        promoted = sum(1 for r in results if r.should_promote)
        logger.info(
            f"Batch evaluation: {promoted}/{len(candidates)} candidates promoted"
        )

        return results

    def get_promotion_stats(self) -> Dict[str, Any]:
        """
        Get promotion statistics.

        Returns:
            Dict with promotion stats

        NASA Rule 10: 20 LOC (<=60)
        """
        if not self.evaluation_history:
            return {"total_evaluated": 0, "promoted": 0, "promotion_rate": 0.0}

        promoted = sum(1 for r in self.evaluation_history if r.should_promote)
        total = len(self.evaluation_history)

        return {
            "total_evaluated": total,
            "promoted": promoted,
            "promotion_rate": promoted / total if total > 0 else 0.0,
            "avg_score": sum(r.total_score for r in self.evaluation_history) / total,
            "criteria": {
                "min_score": self.criteria.min_score,
                "access_weight": self.criteria.access_weight,
                "reference_weight": self.criteria.reference_weight,
                "content_weight": self.criteria.content_weight,
                "importance_weight": self.criteria.importance_weight,
            },
        }
